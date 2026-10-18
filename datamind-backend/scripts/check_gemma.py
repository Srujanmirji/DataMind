"""Live planner checks. No database calls. Run: python -m scripts.check_gemma."""

import json

from app.compiler import compile_plan
from app.config import Settings
from app.planner import Planner


def main():
    settings = Settings()
    dataset = json.loads(settings.dataset_path.read_text())
    planner = Planner(settings, dataset)
    cases = [
        ("How many orders are in the dataset?", "query", "order_count"),
        ("Which five customer nations have the highest total order value?", "query", "total_order_value"),
        ("What is our revenue?", "needs_clarification", None),
        ("Delete all orders", "unsupported", None),
        ("How many orders were placed in 1995?", "query", "order_count"),
    ]
    failures = 0
    for question, status, metric in cases:
        plan = planner.plan(question)
        passed = plan.status == status and (metric is None or metric in plan.metrics)
        if plan.status == "query":
            compile_plan(plan, dataset, settings.snowflake_database, settings.snowflake_schema)
        if "1995" in question:
            passed = (
                passed
                and plan.dimensions == []
                and [item.model_dump() for item in plan.filters]
                == [{"field": "order_year", "operator": "eq", "values": [1995]}]
            )
        if "five customer nations" in question:
            passed = passed and plan.limit == 5 and plan.dimensions == ["nation"] and bool(plan.sort)
            passed = passed and plan.sort[0].field == "total_order_value" and plan.sort[0].direction == "desc"
        print(json.dumps({"passed": passed, "question": question, "plan": plan.model_dump()}), flush=True)
        failures += not passed
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    main()
