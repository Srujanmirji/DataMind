import hashlib
import json
from collections import OrderedDict
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from time import monotonic
from typing import Any
from uuid import uuid4

from app.analysis import analysis_steps, derive
from app.compiler import compile_plan
from app.config import Settings
from app.models import Plan, Question
from app.planner import BackendError, Planner
from app.warehouse import Warehouse


class QuestionService:
    def __init__(self, settings: Settings, dataset: dict, planner: Planner, warehouse: Warehouse, lock=None):
        self.settings = settings
        self.dataset = dataset
        self.planner = planner
        self.warehouse = warehouse
        self.lock = lock if lock is not None else Lock()
        self._plans: OrderedDict[str, tuple[float, str]] = OrderedDict()
        self._planner_version = hashlib.sha256(
            b"".join(
                Path(__file__).with_name(name).read_bytes()
                for name in ("planner.py", "models.py", "compiler.py", "analysis.py", "grounding.py")
            )
        ).hexdigest()

    def ask(self, request: Question) -> dict:
        if request.dataset_id != self.dataset["id"]:
            raise BackendError("unknown_dataset", "Unknown dataset. See GET /datasets.", 404)
        if not self.lock.acquire(blocking=False):
            raise BackendError("busy", "Another question is running. Retry when it completes.", 429)
        try:
            key = hashlib.sha256(
                json.dumps(
                    {
                        "question": request.question,
                        "dataset": self.dataset,
                        "backend": self.settings.llm_backend,
                        "model": self.settings.model_name,
                        "endpoint": self.settings.ollama_base_url
                        if self.settings.llm_backend == "ollama"
                        else "ai_studio",
                        "database": self.settings.snowflake_database,
                        "schema": self.settings.snowflake_schema,
                        "planner": self._planner_version,
                    },
                    sort_keys=True,
                ).encode()
            ).hexdigest()
            cached = self._plans.pop(key, None)
            plan = Plan.model_validate_json(cached[1]) if cached and cached[0] > monotonic() else None
            result = self._ask(request, plan)
            result["plan_cache_hit"] = plan is not None
            if result["status"] in ("answered", "empty"):
                # shortcut: process-local cache clears on restart; use shared storage for multiple workers.
                expires = cached[0] if plan is not None else monotonic() + 3600
                self._plans[key] = (expires, json.dumps(result["plan"]))
                if len(self._plans) > 256:
                    self._plans.popitem(last=False)
            return result
        finally:
            self.lock.release()

    def _ask(self, request: Question, cached_plan: Plan | None = None) -> dict:
        run_id = str(uuid4())
        plan = cached_plan if cached_plan is not None else self.planner.plan(request.question)
        result: dict[str, Any] = {
            "run_id": run_id,
            "dataset_id": request.dataset_id,
            "question": request.question,
            "created_at": datetime.now(UTC).isoformat(),
            "status": plan.status,
            "answer": plan.message,
            "plan": plan.model_dump(),
            "evidence": [],
            "claims": [],
            "warnings": [],
        }
        if plan.status != "query":
            return result
        if plan.analysis != "aggregate":
            return self._multi(plan, result, run_id)
        try:
            query = compile_plan(
                plan, self.dataset, self.settings.snowflake_database, self.settings.snowflake_schema
            )
        except ValueError as exc:
            raise BackendError(
                "invalid_model_plan",
                "Gemma proposed an unsupported field or filter; no query was executed.",
                502,
            ) from exc
        evidence = self.warehouse.execute(query, run_id)
        result["evidence"] = [evidence]
        result["explanation"] = {
            "metrics": {name: self.dataset["metrics"][name]["description"] for name in plan.metrics},
            "grouped_by": plan.dimensions,
            "filters": [item.model_dump() for item in plan.filters],
            "sort": [item.model_dump() for item in plan.sort],
            "source": self.dataset["source"],
            "method": "Gemma selected a validated plan; Python compiled SQL; Snowflake computed the values.",
        }
        result["warnings"] = list(self.dataset["limitations"])
        if evidence["truncated"]:
            result["warnings"].append(f"Showing the first {plan.limit} ordered groups; more groups exist.")
        rows = evidence["rows"]
        # A null SUM can mean missing prices, not absent records. Do not conflate them.
        count_metric = self.dataset.get("count_metric", "order_count")
        zero_count = (
            count_metric in plan.metrics
            and bool(rows)
            and all(row[evidence["columns"].index(count_metric)] == 0 for row in rows)
        )
        missing_measurements = bool(rows) and all(
            row[evidence["columns"].index(name)] is None for row in rows for name in plan.metrics
        )
        if missing_measurements:
            result["status"] = "empty"
            result["answer"] = (
                "The requested measurements are unavailable in the selected dataset for these filters."
            )
            return result
        if not rows or zero_count:
            result["status"] = "empty"
            result["answer"] = self.dataset.get(
                "empty_message", "No matching orders were found for these filters."
            )
            return result
        result["status"] = "answered"
        # Answers are rendered from verified result cells, not unconstrained generated prose.
        summaries = []
        for row_index, row in enumerate(rows[:5]):
            group = ", ".join(f"{name}: {row[evidence['columns'].index(name)]}" for name in plan.dimensions)
            facts = []
            for name in plan.metrics:
                column_index = evidence["columns"].index(name)
                value = row[column_index]
                label = self.dataset["metrics"][name]["label"]
                facts.append(f"{label}: {value if value is not None else 'unavailable'}")
                result["claims"].append(
                    {
                        "metric": name,
                        "value": value,
                        "evidence_id": "query_1",
                        "row_index": row_index,
                        "column": name,
                    }
                )
            summaries.append((group + " — " if group else "") + "; ".join(facts))
        result["answer"] = ". ".join(summaries) + "."
        if len(rows) > 5:
            result["answer"] += f" See the evidence table for all {len(rows)} returned rows."
        return result

    def _multi(self, plan, result, run_id):
        try:
            queries = analysis_steps(plan, self.dataset, self.settings)
        except ValueError as exc:
            raise BackendError(
                "invalid_model_plan", "The analysis scopes or metric are invalid; no query executed.", 502
            ) from exc
        evidence = []
        for index, query in enumerate(queries, 1):
            item = self.warehouse.execute(query, run_id)
            item.update(id=f"query_{index}", kind="query")
            evidence.append(item)
        calculation, warnings = derive(plan, evidence, self.dataset)
        result["evidence"] = [*evidence, calculation]
        result["analysis"] = {
            "kind": plan.analysis,
            "metric": plan.metrics[0],
            "target_filters": [item.model_dump() for item in plan.filters],
            "reference_filters": [item.model_dump() for item in plan.reference_filters],
        }
        result["explanation"] = {
            "metrics": {plan.metrics[0]: self.dataset["metrics"][plan.metrics[0]]["description"]},
            "grouped_by": plan.dimensions,
            "filters": result["analysis"]["target_filters"],
            "reference_filters": result["analysis"]["reference_filters"],
            "sort": [item.model_dump() for item in plan.sort],
            "source": self.dataset["source"],
            "method": "Two validated Snowflake queries followed by deterministic Decimal calculations.",
            "formulas": calculation["formulas"],
        }
        result["warnings"] = [
            *self.dataset["limitations"],
            *warnings,
            "The two query IDs are separate executions; concurrent data edits may affect comparability.",
        ]
        if calculation["truncated"]:
            result["warnings"].append("Additional matching groups exist beyond the requested limit.")
        result["status"] = "answered" if calculation["rows"] else "empty"
        if not calculation["rows"]:
            result["answer"] = "No groups are established as above the overall average for this scope."
            return result
        if plan.analysis in ("compare", "share") and any(
            value is None for row in calculation["rows"] for value in row[:2]
        ):
            result["status"] = "empty"
            result["answer"] = (
                "A required measurement is unavailable in the selected dataset; this comparison cannot be established."
            )
            return result
        summaries = []
        for row_index, row in enumerate(calculation["rows"][:5]):
            facts = []
            for column, value in zip(calculation["columns"], row, strict=True):
                facts.append(f"{column}: {value if value is not None else 'undefined/unavailable'}")
                result["claims"].append(
                    {
                        "metric": column,
                        "value": value,
                        "evidence_id": "calculation_1",
                        "row_index": row_index,
                        "column": column,
                    }
                )
            summaries.append("; ".join(facts))
        result["answer"] = ". ".join(summaries) + "."
        if len(calculation["rows"]) > 5:
            result["answer"] += " See the calculation table for additional groups."
        return result
