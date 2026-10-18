"""Live Gemma TPC-H semantic-plan checks; no Snowflake connection or result claims."""

import json
from datetime import UTC, datetime
from time import perf_counter

from app.analysis import analysis_steps
from app.config import ROOT, Settings
from app.datasets import load_datasets
from app.planner import Planner


def same_fields(plan, expected):
    observed = plan.model_dump()
    # Filter conjunction and metric-list order do not change these scalar analyses.
    return all(
        sorted(json.dumps(item, sort_keys=True) for item in observed[field])
        == sorted(json.dumps(item, sort_keys=True) for item in wanted)
        if isinstance(wanted, list)
        else observed[field] == wanted
        for field, wanted in expected.items()
    )


def main():
    settings = Settings()
    dataset = load_datasets(settings)["tpch_orders"]
    cases = json.loads((ROOT / "evaluation/questions.json").read_text())["cases"]
    report = {
        "mode": "Live Gemma semantic plans only; NO Snowflake execution",
        "model": settings.model_name,
        "created_at": datetime.now(UTC).isoformat(),
        "cases": [],
    }
    folder = ROOT / "data/planner-evaluation"
    folder.mkdir(parents=True, exist_ok=True)
    for case in cases:
        if case["dataset_id"] != "tpch_orders":
            continue
        entry = {"id": case["id"], "question": case["question"], "passed": False}
        started = perf_counter()
        try:
            plan = Planner(settings, dataset).plan(case["question"])
            entry["plan"] = plan.model_dump()
            if case.get("expected_plan"):
                assert plan.status == "query" and same_fields(plan, case["expected_plan"]), (
                    "Semantic plan mismatch"
                )
                entry["compiled_queries"] = [
                    query.__dict__ for query in analysis_steps(plan, dataset, settings)
                ]
            else:
                assert plan.status == case["expected_status"], "Wrong refusal/clarification"
            entry["passed"] = True
        except Exception as exc:  # noqa: BLE001 -- record and fail, never silently pass.
            entry["failure"] = str(exc)
        entry["duration_ms"] = round((perf_counter() - started) * 1000)
        report["cases"].append(entry)
        print(f"{'PASS' if entry['passed'] else 'FAIL'} {case['id']}", flush=True)
        (folder / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    report["passed"] = sum(case["passed"] for case in report["cases"])
    report["total"] = len(report["cases"])
    (folder / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    raise SystemExit(0 if report["passed"] == report["total"] else 1)


if __name__ == "__main__":
    main()
