import json
from contextlib import contextmanager
from decimal import Decimal
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.compiler import compile_plan
from app.config import ROOT, Settings
from app.datasets import load_datasets
from app.main import create_app
from app.models import Plan, Question
from app.planner import BackendError
from app.service import QuestionService
from scripts.demo import prove_change
from scripts.uci_wine import MARKER, WORKING, provision

SMALL_ROWS = [
    ("red-00001", "RED", *([Decimal("1.25")] * 11), 6),
    ("red-00002", "RED", *([Decimal("1.25")] * 11), 7),
    ("white-00001", "WHITE", *([Decimal("1.25")] * 11), 5),
]


@pytest.fixture(autouse=True)
def original_rows(monkeypatch):
    monkeypatch.setattr("scripts.demo.prepare_data", lambda: SMALL_ROWS)


@pytest.fixture
def settings(tmp_path):
    return Settings(_env_file=None, history_path=tmp_path / "runs.sqlite3")


@pytest.fixture
def wine():
    return json.loads((ROOT / "datasets/uci_wine_quality.json").read_text())


def test_catalog_and_cross_dataset_sql(settings, wine):
    assert set(load_datasets(settings)) == {"tpch_orders", "uci_wine_quality"}
    query = compile_plan(Plan(status="query", metrics=["sample_count"]), wine, "OTHER", "OTHER")
    assert "DATAMIND_DEMO.UCI.WINE_QUALITY_WORKING_V1" in query.sql
    assert "OTHER" not in query.sql
    assert "COUNT(*)" in query.sql
    with TestClient(create_app(settings)) as client:
        assert {d["id"] for d in client.get("/datasets").json()["datasets"]} == {
            "tpch_orders",
            "uci_wine_quality",
        }


def test_dataset_override_is_validated(wine):
    wine["database"] = "DB; DROP DATABASE X"
    with pytest.raises(ValueError):
        compile_plan(Plan(status="query", metrics=["sample_count"]), wine, "DB", "S")


def test_other_dataset_metrics_cannot_cross(wine):
    with pytest.raises(ValueError, match="Unknown metric"):
        compile_plan(Plan(status="query", metrics=["order_count"]), wine, "DB", "S")


def test_second_dataset_empty_state(settings, wine):
    planner, warehouse = Mock(), Mock()
    planner.plan.return_value = Plan(status="query", metrics=["sample_count"])
    warehouse.execute.return_value = {"columns": ["sample_count"], "rows": [[0]], "truncated": False}
    result = QuestionService(settings, wine, planner, warehouse).ask(
        Question(question="How many wines?", dataset_id="uci_wine_quality")
    )
    assert result["status"] == "empty"
    assert "wine samples" in result["answer"]


class FixtureConnection:
    """Stateful admin test double, not a substitute for live Snowflake proof."""

    def __init__(self):
        self.quality = 6
        self.calls = []
        self.comment = MARKER

    @contextmanager
    def cursor(self):
        yield FixtureCursor(self)


class FixtureCursor:
    def __init__(self, connection):
        self.connection = connection
        self.rows = []
        self.rowcount = 0
        self.sfqid = None

    def execute(self, sql, parameters=()):
        self.connection.calls.append((sql, parameters))
        self.sfqid = "fixture-admin-" + str(len(self.connection.calls))
        if sql.startswith("SELECT COUNT_IF"):
            self.rows = [(1 + int(self.connection.quality >= 7), 3)]
        elif sql.startswith("SELECT QUALITY"):
            self.rows = [(self.connection.quality,)]
        elif sql.startswith("SELECT COUNT(*)"):
            self.rows = [(3,)]
        elif sql.startswith("SELECT SAMPLE_ID"):
            self.rows = [
                tuple(row[:-1])
                + (self.connection.quality if row[0] == "red-00001" and WORKING in sql else row[-1],)
                for row in SMALL_ROWS
            ]
        elif "SELECT COMMENT" in sql:
            self.rows = [(self.connection.comment,)]
        elif sql.startswith("UPDATE"):
            value, _row_id, expected = parameters
            self.rowcount = int(self.connection.quality == expected)
            if self.rowcount:
                self.connection.quality = value

    def fetchone(self):
        return self.rows[0]

    def fetchall(self):
        return self.rows


def proof_app(settings, wine, connection, fail_after=False):
    planner, warehouse = Mock(), Mock()
    planner.plan.return_value = Plan(
        status="query",
        metrics=["sample_count"],
        filters=[{"field": "quality", "operator": "gte", "values": [7]}],
    )
    executions = 0

    def execute(query, run_id):
        nonlocal executions
        executions += 1
        if fail_after and executions == 2:
            raise BackendError("model_unavailable", "Test failure after mutation.")
        return {
            "id": "query_1",
            "query_id": f"fixture-query-{executions}",
            "sql": query.sql,
            "parameters": query.parameters,
            "columns": ["sample_count"],
            "rows": [[1 + int(connection.quality >= 7)]],
            "truncated": False,
        }

    warehouse.execute.side_effect = execute
    service = QuestionService(settings, wine, planner, warehouse)
    return create_app(settings, service=service)


def test_proof_requires_fresh_answers_and_restores(settings, wine, tmp_path):
    connection = FixtureConnection()
    report = prove_change(proof_app(settings, wine, connection), connection, settings, tmp_path)
    assert report["status"] == "passed" and report["restored"] is True
    assert connection.quality == 6
    assert report["before"]["evidence"][0]["rows"] == [[1]]
    assert report["after"]["evidence"][0]["rows"] == [[2]]
    assert report["restored_answer"]["evidence"][0]["rows"] == [[1]]
    assert (tmp_path / "REPORT.md").is_file()


def test_proof_restores_even_when_after_request_fails(settings, wine, tmp_path):
    connection = FixtureConnection()
    with pytest.raises(RuntimeError, match="API request failed"):
        prove_change(proof_app(settings, wine, connection, fail_after=True), connection, settings, tmp_path)
    assert connection.quality == 6
    report = json.loads((tmp_path / "proof.json").read_text())
    assert report["restored"] is True and report["status"] == "failed"


def test_provision_grants_only_read_access(settings):
    connection = FixtureConnection()
    provision(connection, settings, SMALL_ROWS)
    grants = [sql for sql, _ in connection.calls if sql.startswith("GRANT")]
    assert len(grants) == 3
    assert all("SELECT" in sql or "USAGE" in sql for sql in grants)
    assert not any("UPDATE" in sql or "INSERT" in sql or "ALL PRIVILEGES" in sql for sql in grants)


def test_provision_refuses_unowned_table(settings):
    connection = FixtureConnection()
    connection.comment = "Someone else's table"
    with pytest.raises(RuntimeError, match="refusing to edit"):
        provision(connection, settings, SMALL_ROWS)
    assert not any(sql.startswith(("MERGE", "UPDATE")) for sql, _ in connection.calls)


def test_failed_forward_cas_does_not_restore_another_writer(settings, wine, tmp_path):
    connection = FixtureConnection()
    original_cursor = connection.cursor

    @contextmanager
    def competing_cursor():
        with original_cursor() as cursor:
            execute = cursor.execute

            def race(sql, parameters=()):
                if sql.startswith("UPDATE"):
                    connection.quality = 7
                return execute(sql, parameters)

            cursor.execute = race
            yield cursor

    connection.cursor = competing_cursor
    with pytest.raises(RuntimeError, match="exactly one"):
        prove_change(proof_app(settings, wine, connection), connection, settings, tmp_path)
    assert connection.quality == 7
    assert len([sql for sql, _ in connection.calls if sql.startswith("UPDATE")]) == 1


def test_failed_rerun_invalidates_previous_success_report(settings, wine, tmp_path):
    connection = FixtureConnection()
    connection.quality = 5
    (tmp_path / "REPORT.md").write_text("Old success: PASSED")
    with pytest.raises(RuntimeError, match="differs from original UCI"):
        prove_change(proof_app(settings, wine, connection), connection, settings, tmp_path)
    assert "PASSED" not in (tmp_path / "REPORT.md").read_text()
    assert json.loads((tmp_path / "proof.json").read_text())["status"] != "passed"
