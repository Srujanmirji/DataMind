from datetime import UTC, datetime
from threading import Lock
from typing import Any
from uuid import uuid4

from app.analysis import analysis_steps, derive
from app.compiler import compile_plan
from app.config import Settings
from app.models import Question
from app.planner import BackendError, Planner
from app.warehouse import Warehouse


class QuestionService:
    def __init__(self, settings: Settings, dataset: dict, planner: Planner, warehouse: Warehouse, lock=None):
        self.settings = settings
        self.dataset = dataset
        self.planner = planner
        self.warehouse = warehouse
        self.lock = lock if lock is not None else Lock()

    def ask(self, request: Question) -> dict:
        if request.dataset_id != self.dataset["id"]:
            raise BackendError("unknown_dataset", "Unknown dataset. See GET /datasets.", 404)
        if not self.lock.acquire(blocking=False):
            raise BackendError("busy", "Another question is running. Retry when it completes.", 429)
        try:
            return self._ask(request)
        finally:
            self.lock.release()

    def _ask(self, request: Question) -> dict:
        run_id = str(uuid4())
        plan = self.planner.plan(request.question)
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
