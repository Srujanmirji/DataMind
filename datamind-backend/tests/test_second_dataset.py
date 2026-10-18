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
from app.service import QuestionService
from scripts.worldbank_wdi import COLUMNS, INDICATORS, MARKER, provision

SMALL_ROWS = [
    ("IND", "India", "South Asia", "Lower middle income", 2023, *([Decimal("1.250000")] * len(INDICATORS))),
    ("IND", "India", "South Asia", "Lower middle income", 2024, *([None] * len(INDICATORS))),
]


@pytest.fixture
def settings(tmp_path):
    return Settings(_env_file=None, history_path=tmp_path / "runs.sqlite3")


@pytest.fixture
def wdi():
    return json.loads((ROOT / "datasets/worldbank_wdi.json").read_text())


def test_catalog_and_cross_dataset_sql(settings, wdi):
    assert set(load_datasets(settings)) == {"tpch_orders", "worldbank_wdi"}
    query = compile_plan(Plan(status="query", metrics=["country_count"]), wdi, "OTHER", "OTHER")
    assert "DATAMIND_DEMO.WORLDBANK.WDI_COUNTRY_YEAR_V1" in query.sql
    assert "OTHER" not in query.sql
    assert "COUNT(DISTINCT w.COUNTRY_CODE)" in query.sql
    with TestClient(create_app(settings)) as client:
        assert {d["id"] for d in client.get("/datasets").json()["datasets"]} == {
            "tpch_orders",
            "worldbank_wdi",
        }


def test_dataset_override_is_validated(wdi):
    wdi["database"] = "DB; DROP DATABASE X"
    with pytest.raises(ValueError):
        compile_plan(Plan(status="query", metrics=["country_count"]), wdi, "DB", "S")


def test_other_dataset_metrics_cannot_cross(wdi):
    with pytest.raises(ValueError, match="Unknown metric"):
        compile_plan(Plan(status="query", metrics=["order_count"]), wdi, "DB", "S")


def test_country_filter_is_bound_not_interpolated(wdi):
    plan = Plan(
        status="query",
        metrics=["life_expectancy_years"],
        filters=[{"field": "country_code", "operator": "eq", "values": ["IND' OR 1=1 --"]}],
    )
    query = compile_plan(plan, wdi, "DB", "S")
    assert "OR 1=1" not in query.sql and query.parameters == ["IND' OR 1=1 --"]


def test_second_dataset_empty_state(settings, wdi):
    planner, warehouse = Mock(), Mock()
    planner.plan.return_value = Plan(status="query", metrics=["country_count"])
    warehouse.execute.return_value = {"columns": ["country_count"], "rows": [[0]], "truncated": False}
    result = QuestionService(settings, wdi, planner, warehouse).ask(
        Question(question="How many countries?", dataset_id="worldbank_wdi")
    )
    assert result["status"] == "empty"
    assert "ISO3 code" in result["answer"]


class FixtureConnection:
    """Stateful admin test double, not a substitute for live Snowflake proof."""

    def __init__(self, existing_rows=None):
        self.calls = []
        self.comment = MARKER
        self.rows = list(existing_rows or [])

    @contextmanager
    def cursor(self):
        yield FixtureCursor(self)


class FixtureCursor:
    def __init__(self, connection):
        self.connection = connection
        self.rows = []
        self.sfqid = None

    def execute(self, sql, parameters=()):
        self.connection.calls.append((sql, parameters))
        self.sfqid = "fixture-admin-" + str(len(self.connection.calls))
        if "SELECT COMMENT" in sql:
            self.rows = [(self.connection.comment,)]
        elif sql.startswith("SELECT COUNT(*)"):
            self.rows = [(len(self.connection.rows),)]
        elif sql.startswith(f"SELECT {COLUMNS[0]}"):
            self.rows = sorted(self.connection.rows, key=lambda row: (row[0], row[4]))

    def executemany(self, sql, rows):
        self.connection.calls.append((sql, rows))
        self.connection.rows.extend(rows)

    def fetchone(self):
        return self.rows[0]

    def fetchall(self):
        return self.rows


def test_provision_loads_verifies_and_grants_only_read_access(settings):
    connection = FixtureConnection()
    result = provision(connection, settings, SMALL_ROWS)
    assert result["row_count"] == 2 and connection.rows == SMALL_ROWS
    grants = [sql for sql, _ in connection.calls if sql.startswith("GRANT")]
    assert len(grants) == 3
    assert all("SELECT" in sql or "USAGE" in sql for sql in grants)
    assert not any("UPDATE" in sql or "INSERT" in sql or "ALL PRIVILEGES" in sql for sql in grants)


def test_provision_refuses_unowned_table(settings):
    connection = FixtureConnection()
    connection.comment = "Someone else's table"
    with pytest.raises(RuntimeError, match="refusing to edit"):
        provision(connection, settings, SMALL_ROWS)
    assert not any(sql.startswith(("INSERT", "MERGE", "UPDATE")) for sql, _ in connection.calls)


def test_provision_refuses_to_overwrite_a_changed_table(settings):
    changed = [SMALL_ROWS[0][:5] + (Decimal("9.999999"),) + SMALL_ROWS[0][6:], SMALL_ROWS[1]]
    connection = FixtureConnection(existing_rows=changed)
    with pytest.raises(RuntimeError, match="differs from the World Bank snapshot"):
        provision(connection, settings, SMALL_ROWS)
    assert not any(sql.startswith("INSERT") for sql, _ in connection.calls)


def test_planner_unquotes_integer_filters_only(wdi):
    from app.planner import coerce_integer_values

    fields = {**wdi["dimensions"], **wdi["filter_fields"]}
    data = {
        "filters": [
            {"field": "year", "operator": "eq", "values": ["2020"]},
            {"field": "country_code", "operator": "eq", "values": ["123"]},
        ],
        "reference_filters": [{"field": "year", "operator": "eq", "values": ["2020 OR 1=1"]}],
    }
    coerce_integer_values(data, fields)
    assert data["filters"][0]["values"] == [2020]
    assert data["filters"][1]["values"] == ["123"]
    assert data["reference_filters"][0]["values"] == ["2020 OR 1=1"]
