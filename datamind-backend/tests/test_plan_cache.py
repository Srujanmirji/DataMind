import json
from unittest.mock import Mock

import pytest

from app.config import ROOT, Settings
from app.errors import BackendError
from app.models import Plan, Question
from app.service import QuestionService


@pytest.fixture
def service():
    dataset = json.loads((ROOT / "datasets/tpch_orders.json").read_text())
    planner, warehouse = Mock(), Mock()
    planner.plan.return_value = Plan(status="query", metrics=["order_count"])
    executions = 0

    def execute(query, run_id):
        nonlocal executions
        executions += 1
        return {
            "id": "query_1",
            "query_id": f"query-{executions}",
            "columns": ["order_count"],
            "rows": [[executions]],
            "truncated": False,
        }

    warehouse.execute.side_effect = execute
    return QuestionService(Settings(_env_file=None), dataset, planner, warehouse)


def test_repeated_question_skips_model_but_reads_new_rows_and_query_ids(service):
    request = Question(question="How many orders?")
    first = service.ask(request)
    # Editing a response must not poison the next cached plan.
    first["plan"]["metrics"] = ["not_a_metric"]
    second = service.ask(request)
    assert not first["plan_cache_hit"] and second["plan_cache_hit"]
    assert service.planner.plan.call_count == 1
    assert service.warehouse.execute.call_count == 2
    assert first["run_id"] != second["run_id"]
    assert first["evidence"][0]["query_id"] != second["evidence"][0]["query_id"]
    assert first["claims"][0]["value"] == 1 and second["claims"][0]["value"] == 2


def test_cached_comparison_runs_both_sql_queries_again(service):
    service.planner.plan.return_value = Plan(
        status="query",
        analysis="compare",
        metrics=["order_count"],
        filters=[{"field": "order_year", "operator": "eq", "values": [2023]}],
        reference_filters=[{"field": "order_year", "operator": "eq", "values": [2022]}],
    )
    q = Question(question="Compare the two years")
    first, second = service.ask(q), service.ask(q)
    assert second["plan_cache_hit"]
    assert service.planner.plan.call_count == 1
    assert service.warehouse.execute.call_count == 4
    assert first["evidence"][-1]["rows"] != second["evidence"][-1]["rows"]


def test_expiry_is_one_hour_from_creation_not_last_hit(service, monkeypatch):
    now = [0]
    monkeypatch.setattr("app.service.monotonic", lambda: now[0])
    q = Question(question="How many orders?")
    service.ask(q)
    now[0] = 3599
    assert service.ask(q)["plan_cache_hit"]
    now[0] = 3600
    assert not service.ask(q)["plan_cache_hit"]
    assert service.planner.plan.call_count == 2


@pytest.mark.parametrize("change", ["question", "dataset", "model", "backend", "planner"])
def test_changed_context_misses_cache(service, change):
    q = Question(question="How many orders?")
    service.ask(q)
    if change == "question":
        q = Question(question="How many customers?")
    elif change == "dataset":
        service.dataset["planning_notes"] += " changed"
    elif change == "model":
        service.settings.ollama_model = "another-model"
    elif change == "backend":
        service.settings.llm_backend = "ai_studio"
    else:
        service._planner_version = "new-version"
    assert not service.ask(q)["plan_cache_hit"]
    assert service.planner.plan.call_count == 2


@pytest.mark.parametrize("status", ["unsupported", "needs_clarification", "invalid", "failure"])
def test_nonquery_invalid_and_failed_requests_are_not_cached(service, status):
    if status in ("unsupported", "needs_clarification"):
        service.planner.plan.return_value = Plan(status=status, message="More detail needed")
    elif status == "invalid":
        service.planner.plan.return_value = Plan(status="query", metrics=["unknown"])
    else:
        service.warehouse.execute.side_effect = BackendError("warehouse_error", "Unavailable")
    for _ in range(2):
        try:
            service.ask(Question(question="How many orders?"))
        except BackendError:
            assert status in ("invalid", "failure")
    assert not service._plans
    assert service.planner.plan.call_count == 2


def test_cache_is_bounded(service):
    for i in range(257):
        service.ask(Question(question=f"Count orders question {i}"))
    assert len(service._plans) == 256
    assert not service.ask(Question(question="Count orders question 0"))["plan_cache_hit"]
