import copy
import json
import sqlite3
from decimal import Decimal
from unittest.mock import Mock

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError

from app.compiler import compile_plan
from app.config import ROOT, Settings
from app.main import create_app
from app.models import Plan, Question
from app.planner import BackendError, Planner
from app.service import QuestionService
from app.warehouse import json_value


@pytest.fixture
def dataset():
    return json.loads((ROOT / "datasets/tpch_orders.json").read_text())


@pytest.fixture
def settings(tmp_path):
    return Settings(_env_file=None, history_path=tmp_path / "runs.sqlite3")


def test_query_values_cannot_inject_sql(dataset):
    attack = "FRANCE'); DROP TABLE ORDERS; --"
    plan = Plan(
        status="query",
        metrics=["order_count"],
        filters=[{"field": "nation", "operator": "eq", "values": [attack]}],
    )
    query = compile_plan(plan, dataset, "DB", "SCHEMA")
    assert attack not in query.sql
    assert query.parameters == [attack]
    assert "n.N_NAME = %s" in query.sql


@pytest.mark.parametrize(
    "changes",
    [
        {"metrics": ["COUNT(*); DROP TABLE ORDERS"]},
        {"dimensions": ["secret_table"]},
        {"filters": [{"field": "password", "operator": "eq", "values": ["x"]}]},
        {"filters": [{"field": "order_date", "operator": "eq", "values": ["2025-02-30"]}]},
        {"filters": [{"field": "order_year", "operator": "eq", "values": ["1995"]}]},
        {"sort": [{"field": "password", "direction": "desc"}]},
        {"filters": [{"field": "order_year", "operator": "between", "values": [1999, 1990]}]},
    ],
)
def test_invalid_plans_cannot_compile(dataset, changes):
    plan = Plan.model_validate({"status": "query", "metrics": ["order_count"], **changes})
    with pytest.raises(ValueError):
        compile_plan(plan, dataset, "DB", "SCHEMA")


@pytest.mark.parametrize(
    "changes",
    [
        {"limit": 100000},
        {"limit": True},
        {"metrics": []},
        {"metrics": ["order_count", "order_count"]},
        {"filters": [{"field": "nation", "operator": "eq", "values": ["A", "B"]}]},
        {"filters": [{"field": "nation", "operator": "eq", "values": [True]}]},
        {"sql": "SELECT * FROM secrets"},
    ],
)
def test_invalid_model_shapes_rejected(changes):
    with pytest.raises(ValidationError):
        Plan.model_validate({"status": "query", "metrics": ["order_count"], **changes})


def test_identifier_configuration_checked(dataset):
    with pytest.raises(ValueError):
        compile_plan(Plan(status="query", metrics=["order_count"]), dataset, "DB; DROP DATABASE X", "S")


def test_aggregations_against_independent_ground_truth(dataset):
    """Run compiled SQL against fixture rows; expected values are hand calculated."""
    config = copy.deepcopy(dataset)
    config["from"] = "orders o"
    config["joins"] = [
        "LEFT JOIN customer c ON o.O_CUSTKEY = c.C_CUSTKEY",
        "LEFT JOIN nation n ON c.C_NATIONKEY = n.N_NATIONKEY",
        "LEFT JOIN region r ON n.N_REGIONKEY = r.R_REGIONKEY",
    ]
    with sqlite3.connect(":memory:") as db:
        db.executescript("""
        CREATE TABLE orders (O_CUSTKEY INTEGER, O_TOTALPRICE NUMERIC, O_ORDERDATE TEXT);
        CREATE TABLE customer (C_CUSTKEY INTEGER, C_NATIONKEY INTEGER);
        CREATE TABLE nation (N_NATIONKEY INTEGER, N_NAME TEXT, N_REGIONKEY INTEGER);
        CREATE TABLE region (R_REGIONKEY INTEGER, R_NAME TEXT);
        INSERT INTO region VALUES (1, 'EUROPE');
        INSERT INTO nation VALUES (1, 'FRANCE', 1), (2, 'GERMANY', 1);
        INSERT INTO customer VALUES (1, 1), (2, 2), (3, 2);
        INSERT INTO orders VALUES (1, 10, '1995-01-01'), (1, 20, '1995-02-01'),
                                  (2, 50, '1995-03-01'), (3, 40, '1996-01-01');
        """)
        plan = Plan(
            status="query",
            metrics=["order_count", "total_order_value", "customer_count"],
            dimensions=["nation"],
            limit=1,
            sort=[{"field": "total_order_value", "direction": "desc"}],
        )
        query = compile_plan(plan, config, "DB", "S")
        # Compiler fetches N+1 after aggregation to determine whether groups were truncated.
        assert db.execute(query.sql).fetchall() == [("GERMANY", 2, 90, 2), ("FRANCE", 2, 30, 1)]
        filtered = Plan(
            status="query",
            metrics=["order_count", "total_order_value"],
            filters=[{"field": "nation", "operator": "eq", "values": ["FRANCE"]}],
        )
        query = compile_plan(filtered, config, "DB", "S")
        assert db.execute(query.sql.replace("%s", "?"), query.parameters).fetchall() == [(2, 30)]


def make_service(settings, dataset, plan=None, rows=None):
    planner = Mock()
    planner.plan.return_value = plan or Plan(status="query", metrics=["order_count"])
    warehouse = Mock()
    warehouse.execute.return_value = {
        "id": "query_1",
        "query_id": "real-id-placeholder-in-test-only",
        "sql": "SELECT ...",
        "parameters": [],
        "columns": ["order_count"],
        "rows": [[1500000]] if rows is None else rows,
        "truncated": False,
    }
    return QuestionService(settings, dataset, planner, warehouse)


def test_answer_cells_and_history_agree(settings, dataset):
    service = make_service(settings, dataset)
    with TestClient(create_app(settings, service=service)) as client:
        response = client.post("/questions", json={"question": "How many orders?"})
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "answered"
        assert "1500000" in body["answer"]
        claim = body["claims"][0]
        assert claim["value"] == body["evidence"][0]["rows"][claim["row_index"]][0]
        assert client.get("/runs/" + body["run_id"]).json() == body
        assert client.get("/runs/not-a-uuid").status_code == 422
        assert client.get("/runs/00000000-0000-0000-0000-000000000000").status_code == 404


@pytest.mark.parametrize("status", ["needs_clarification", "unsupported"])
def test_non_query_never_touches_snowflake(settings, dataset, status):
    plan = Plan(status=status, message="Please specify total order value.")
    service = make_service(settings, dataset, plan)
    assert service.ask(Question(question="What about sales?"))["status"] == status
    service.warehouse.execute.assert_not_called()


def test_invalid_semantics_never_touch_snowflake(settings, dataset):
    service = make_service(settings, dataset, Plan(status="query", metrics=["profit"]))
    with pytest.raises(BackendError, match="unsupported field"):
        service.ask(Question(question="What is profit?"))
    service.warehouse.execute.assert_not_called()


def test_empty_results_are_explicit(settings, dataset):
    assert (
        make_service(settings, dataset, rows=[]).ask(Question(question="Count orders"))["status"] == "empty"
    )
    assert (
        make_service(settings, dataset, rows=[[0]]).ask(Question(question="Count orders"))["status"]
        == "empty"
    )


def test_null_and_zero_sums_are_not_assumed_empty(settings, dataset):
    for value in [None, "0.00"]:
        service = make_service(settings, dataset, Plan(status="query", metrics=["total_order_value"]))
        service.warehouse.execute.return_value.update(columns=["total_order_value"], rows=[[value]])
        result = service.ask(Question(question="Total order value?"))
        assert result["status"] == ("empty" if value is None else "answered")
        if value is None:
            assert "unavailable" in result["answer"] and not result["claims"]


def test_model_failure_and_lock_release(settings, dataset):
    service = make_service(settings, dataset)
    service.planner.plan.side_effect = BackendError("model_unavailable", "Start Ollama.")
    with TestClient(create_app(settings, service=service)) as client:
        response = client.post("/questions", json={"question": "Count orders"})
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "model_unavailable"
    assert not service.lock.locked()


def test_busy_and_auth_and_validation(settings, dataset):
    settings.api_key = SecretStr("test-key")
    service = make_service(settings, dataset)
    with TestClient(create_app(settings, service=service)) as client:
        assert client.post("/questions", json={"question": "Count orders"}).status_code == 401
        headers = {"X-API-Key": "test-key"}
        assert client.post("/questions", headers=headers, json={"question": "   "}).status_code == 422
        assert (
            client.post(
                "/questions", headers=headers, json={"question": "Count orders", "dataset_id": "missing"}
            ).status_code
            == 404
        )
        service.lock.acquire()
        try:
            assert (
                client.post("/questions", headers=headers, json={"question": "Count orders"}).status_code
                == 429
            )
        finally:
            service.lock.release()


def test_decimal_precision_preserved():
    assert json_value(Decimal("9318715232.78")) == "9318715232.78"


def test_ollama_malformed_response(settings, dataset, monkeypatch):
    response = Mock()
    response.json.return_value = {"message": {"content": '{"sql": "DROP TABLE ORDERS"}'}}
    client = Mock()
    client.__enter__ = Mock(return_value=client)
    client.__exit__ = Mock(return_value=False)
    client.post.return_value = response
    monkeypatch.setattr(httpx, "Client", Mock(return_value=client))
    with pytest.raises(BackendError) as error:
        Planner(settings, dataset).plan("Count orders")
    assert error.value.code == "invalid_model_plan"


def test_model_repairs_invalid_year_before_execution(settings, dataset, monkeypatch):
    invalid = {
        "status": "query",
        "metrics": ["order_count"],
        "filters": [{"field": "order_year", "operator": "eq", "values": ["1995-01-01"]}],
    }
    valid = {
        "status": "query",
        "metrics": ["order_count"],
        "filters": [{"field": "order_year", "operator": "eq", "values": [1995]}],
    }
    responses = []
    for body in [{"mode": "aggregate", "reason": "Count orders in a year"}, invalid, valid]:
        response = Mock()
        response.json.return_value = {"message": {"content": json.dumps(body)}}
        responses.append(response)
    client = Mock()
    client.__enter__ = Mock(return_value=client)
    client.__exit__ = Mock(return_value=False)
    client.post.side_effect = responses
    monkeypatch.setattr(httpx, "Client", Mock(return_value=client))
    plan = Planner(settings, dataset).plan("How many orders in 1995?")
    assert plan.filters[0].values == [1995]
    assert client.post.call_count == 3


def test_truncation_and_nulls_are_visible(settings, dataset):
    service = make_service(settings, dataset, Plan(status="query", metrics=["total_order_value"]))
    service.warehouse.execute.return_value.update(
        columns=["total_order_value"], rows=[[None]], truncated=True
    )
    result = service.ask(Question(question="Total order value?"))
    assert "unavailable" in result["answer"]
    assert any("more groups exist" in warning for warning in result["warnings"])


def test_date_parameters_and_half_open_year(dataset):
    plan = Plan(
        status="query",
        metrics=["order_count"],
        filters=[
            {"field": "order_date", "operator": "gte", "values": ["1995-01-01"]},
            {"field": "order_date", "operator": "lt", "values": ["1996-01-01"]},
        ],
    )
    query = compile_plan(plan, dataset, "DB", "SCHEMA")
    assert "o.O_ORDERDATE >= TO_DATE(%s)" in query.sql
    assert "o.O_ORDERDATE < TO_DATE(%s)" in query.sql
    assert query.parameters == ["1995-01-01", "1996-01-01"]


def test_warehouse_does_not_expose_connector_errors(settings, monkeypatch):
    from snowflake.connector.errors import DatabaseError

    from app.compiler import CompiledQuery
    from app.warehouse import Warehouse

    monkeypatch.setattr("snowflake.connector.connect", Mock(side_effect=DatabaseError("secret-token")))
    with pytest.raises(BackendError) as error:
        Warehouse(settings, b"test-only").execute(CompiledQuery("SELECT 1", [], 1), "test")
    assert "secret-token" not in error.value.message
    assert error.value.code == "snowflake_error"


def test_numeric_condition_cannot_be_silently_dropped(settings, dataset, monkeypatch):
    plan = {"status": "query", "metrics": ["order_count"]}
    payloads = [{"mode": "aggregate", "reason": "Count in year"}, plan, plan]
    responses = []
    for payload in payloads:
        response = Mock()
        response.json.return_value = {"message": {"content": json.dumps(payload)}}
        responses.append(response)
    client = Mock()
    client.__enter__ = Mock(return_value=client)
    client.__exit__ = Mock(return_value=False)
    client.post.side_effect = responses
    monkeypatch.setattr(httpx, "Client", Mock(return_value=client))
    with pytest.raises(BackendError, match="invalid analysis plan"):
        Planner(settings, dataset).plan("How many orders in 1996?")


def test_write_request_refused_without_model(settings, dataset, monkeypatch):
    client = Mock()
    monkeypatch.setattr(httpx, "Client", client)
    assert Planner(settings, dataset).plan("Delete all orders then count them").status == "unsupported"
    client.assert_not_called()


@pytest.mark.parametrize(
    "question",
    ["What was the drop in order count from 1994 to 1995?", "Give me an update on average order value"],
)
def test_analytical_drop_and_update_are_not_write_requests(settings, dataset, monkeypatch, question):
    response = Mock()
    response.json.return_value = {
        "message": {"content": json.dumps({"mode": "needs_clarification", "reason": "Reached model router"})}
    }
    client = Mock()
    client.__enter__ = Mock(return_value=client)
    client.__exit__ = Mock(return_value=False)
    client.post.return_value = response
    monkeypatch.setattr(httpx, "Client", Mock(return_value=client))
    result = Planner(settings, dataset).plan(question)
    assert result.status == "needs_clarification"
    client.post.assert_called_once()


def test_scalar_limit_does_not_cover_missing_question_threshold(settings, monkeypatch):
    from app.datasets import load_datasets

    dataset = load_datasets(settings)["worldbank_wdi"]
    plan = {
        "status": "query",
        "analysis": "share",
        "metrics": ["country_count"],
        "filters": [{"field": "region", "operator": "eq", "values": ["SOUTH ASIA"]}],
        "reference_filters": [],
        "limit": 8,
    }
    payloads = [{"mode": "share", "reason": "Percentage of countries"}, plan, plan]
    responses = []
    for payload in payloads:
        response = Mock()
        response.json.return_value = {"message": {"content": json.dumps(payload)}}
        responses.append(response)
    client = Mock()
    client.__enter__ = Mock(return_value=client)
    client.__exit__ = Mock(return_value=False)
    client.post.side_effect = responses
    monkeypatch.setattr(httpx, "Client", Mock(return_value=client))
    with pytest.raises(BackendError, match="invalid analysis plan"):
        Planner(settings, dataset).plan(
            "Among South Asian countries in 2023, what percentage had a fertility rate of 8 or higher?"
        )


@pytest.mark.parametrize("target,reference", [([1993], [1994]), ([1993, 1994], [1993])])
def test_period_change_rejects_reversed_or_combined_cohorts(
    settings, dataset, monkeypatch, target, reference
):
    def body(target_years, reference_years):
        return {
            "status": "query",
            "analysis": "compare",
            "metrics": ["order_count"],
            "filters": [{"field": "order_year", "operator": "in", "values": target_years}],
            "reference_filters": [{"field": "order_year", "operator": "in", "values": reference_years}],
        }

    payloads = [{"mode": "compare", "reason": "Two years"}, body(target, reference), body([1994], [1993])]
    responses = []
    for payload in payloads:
        response = Mock()
        response.json.return_value = {"message": {"content": json.dumps(payload)}}
        responses.append(response)
    client = Mock()
    client.__enter__ = Mock(return_value=client)
    client.__exit__ = Mock(return_value=False)
    client.post.side_effect = responses
    monkeypatch.setattr(httpx, "Client", Mock(return_value=client))
    plan = Planner(settings, dataset).plan("From 1993 to 1994, how did order count change?")
    assert plan.filters[0].values == [1994]
    assert plan.reference_filters[0].values == [1993]
    assert client.post.call_count == 3
