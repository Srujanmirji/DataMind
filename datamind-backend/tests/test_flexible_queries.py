import copy
import json
import sqlite3
from decimal import Decimal
from unittest.mock import Mock

import pytest

from app.compiler import compile_plan
from app.config import ROOT, Settings
from app.grounding import check_scope
from app.models import Plan
from app.planner import Planner


@pytest.fixture
def wdi():
    return json.loads((ROOT / "datasets/worldbank_wdi.json").read_text())


def test_fractional_indicator_filter_is_bound_not_inserted(wdi):
    body = Plan(
        status="query",
        metrics=["unemployment_pct"],
        dimensions=["country"],
        filters=[
            {"field": "year", "operator": "eq", "values": [2022]},
            {"field": "unemployment_pct", "operator": "gt", "values": ["8.5"]},
        ],
    )
    compiled = compile_plan(body, wdi, "DB", "SCHEMA")
    assert "w.UNEMPLOYMENT_PCT > %s" in compiled.sql
    assert compiled.parameters == [2022, Decimal("8.5")]
    assert "8.5" not in compiled.sql
    check_scope("Which countries had unemployment above 8.5 percent in 2022?", body, wdi)


@pytest.mark.parametrize("value", ["NaN", "Infinity", "0); DROP TABLE x;--"])
def test_numeric_filter_rejects_nonfinite_or_sql(wdi, value):
    body = Plan(
        status="query",
        metrics=["unemployment_pct"],
        filters=[
            {"field": "unemployment_pct", "operator": "gt", "values": [value]},
        ],
    )
    with pytest.raises(ValueError):
        compile_plan(body, wdi, "DB", "SCHEMA")


def test_latest_uses_actual_nonmissing_data_and_preserves_country_scope(wdi):
    body = Plan(
        status="query",
        metrics=["total_gdp_usd"],
        dimensions=["year"],
        time_selection="latest_available",
        filters=[
            {"field": "country_code", "operator": "eq", "values": ["IND"]},
        ],
    )
    config = copy.deepcopy(wdi)
    config["from"] = "wdi w"
    config["metrics"]["total_gdp_usd"]["sql"] = "SUM(w.GDP_USD)"
    query = compile_plan(body, config, "DB", "SCHEMA")
    check_scope("What is the latest available GDP for India in this dataset?", body, wdi)
    assert query.parameters == ["IND", "IND"]
    with sqlite3.connect(":memory:") as c:
        c.executescript("""CREATE TABLE wdi (COUNTRY_CODE TEXT, YEAR INTEGER, GDP_USD NUMERIC);
        INSERT INTO wdi VALUES ('IND',2022,100),('IND',2023,110),('IND',2024,NULL),('CHN',2024,500);""")
        assert c.execute(query.sql.replace("%s", "?"), query.parameters).fetchall() == [(2023, 110)]
    with pytest.raises(ValueError):
        check_scope("What is India GDP?", body, wdi)


def test_latest_cannot_mix_with_invented_year_or_hidden_year(wdi):
    base = {"status": "query", "metrics": ["total_gdp_usd"], "time_selection": "latest_available"}
    with pytest.raises(ValueError):
        compile_plan(Plan(**base), wdi, "DB", "SCHEMA")
    with pytest.raises(ValueError):
        compile_plan(
            Plan(
                **base, dimensions=["year"], filters=[{"field": "year", "operator": "eq", "values": [2024]}]
            ),
            wdi,
            "DB",
            "SCHEMA",
        )


def test_multicountry_comparison_can_use_grouped_results(wdi):
    planner = Planner(Settings(_env_file=None), wdi)
    body = Plan(
        status="query",
        metrics=["gdp_per_capita_usd"],
        dimensions=["country"],
        filters=[
            {"field": "year", "operator": "eq", "values": [2022]},
            {"field": "country_code", "operator": "in", "values": ["IND", "BRA", "CHN"]},
        ],
    )
    planner._generate = Mock(side_effect=[json.dumps({"mode": "aggregate"}), body.model_dump_json()])
    assert planner.plan("Compare GDP per person in India, Brazil and China in 2022.") == body


def test_latest_per_country_keeps_each_countrys_own_available_year(wdi):
    body = Plan(
        status="query",
        metrics=["total_gdp_usd"],
        dimensions=["country", "year"],
        time_selection="latest_available",
    )
    config = copy.deepcopy(wdi)
    config["from"] = "wdi w"
    config["dimensions"]["country"]["sql"] = "w.COUNTRY_CODE"
    compiled = compile_plan(body, config, "DB", "SCHEMA")
    with sqlite3.connect(":memory:") as c:
        c.executescript("""CREATE TABLE wdi (COUNTRY_CODE TEXT, YEAR INTEGER, GDP_USD NUMERIC);
        INSERT INTO wdi VALUES ('IND',2022,100),('IND',2023,110),('IND',2024,NULL),('CHN',2023,450),('CHN',2024,500);""")
        assert c.execute(compiled.sql.replace("%s", "?"), compiled.parameters).fetchall() == [
            ("CHN", 2024, 500),
            ("IND", 2023, 110),
        ]


def test_threshold_cannot_be_silently_changed(wdi):
    body = Plan(
        status="query",
        metrics=["unemployment_pct"],
        dimensions=["country"],
        filters=[
            {"field": "year", "operator": "eq", "values": [2022]},
            {"field": "unemployment_pct", "operator": "gt", "values": ["5.8"]},
        ],
    )
    with pytest.raises(ValueError, match="threshold"):
        check_scope("Which countries had unemployment above 8.5 percent in 2022?", body, wdi)


def test_plain_json_fraction_is_accepted_only_as_a_numeric_value(wdi):
    planner = Planner(Settings(_env_file=None), wdi)
    planner._generate = Mock(
        side_effect=[
            json.dumps({"mode": "aggregate"}),
            json.dumps(
                {
                    "status": "query",
                    "metrics": ["unemployment_pct"],
                    "dimensions": ["country"],
                    "filters": [
                        {"field": "year", "operator": "eq", "values": [2022]},
                        {"field": "unemployment_pct", "operator": "gt", "values": [8.5]},
                    ],
                }
            ),
        ]
    )
    body = planner.plan("Which countries had unemployment above 8.5 percent in 2022?")
    assert body.filters[1].values == ["8.5"]


def test_semantic_metric_selection_allows_mixed_literal_and_paraphrased_measures(wdi):
    question = "Show India’s GDP and how long people could expect to live at birth in 2022."
    planner = Planner(Settings(_env_file=None), wdi)
    body = Plan(
        status="query",
        metrics=["total_gdp_usd", "life_expectancy_years"],
        filters=[
            {"field": "country_code", "operator": "eq", "values": ["IND"]},
            {"field": "year", "operator": "eq", "values": [2022]},
        ],
    )
    planner._generate = Mock(
        side_effect=[
            json.dumps({"mode": "aggregate", "selected_metrics": body.metrics}),
            body.model_dump_json(),
        ]
    )
    assert planner.plan(question) == body
    with pytest.raises(ValueError, match="exactly"):
        check_scope(question, body, wdi, ["total_gdp_usd"])


def test_semantic_metric_mismatch_is_repaired_before_any_query(wdi):
    planner = Planner(Settings(_env_file=None), wdi)
    wrong = Plan(
        status="query",
        metrics=["total_population"],
        filters=[
            {"field": "country_code", "operator": "eq", "values": ["IND"]},
            {"field": "year", "operator": "eq", "values": [2022]},
        ],
    )
    correct = wrong.model_copy(update={"metrics": ["total_gdp_usd"]})
    planner._generate = Mock(
        side_effect=[
            json.dumps({"mode": "aggregate", "selected_metrics": ["total_gdp_usd"]}),
            wrong.model_dump_json(),
            correct.model_dump_json(),
        ]
    )
    assert planner.plan("What is India’s GDP in 2022?") == correct
    assert planner._generate.call_count == 3


def test_above_average_can_consider_all_217_economies(wdi):
    from app.analysis import analysis_steps, derive

    body = Plan(
        status="query",
        analysis="above_average",
        metrics=["life_expectancy_years"],
        dimensions=["country"],
        limit=500,
    )
    assert analysis_steps(body, wdi, Settings(_env_file=None))[0].limit == 500
    evidence = [
        {
            "id": "query_1",
            "columns": ["country", "life_expectancy_years"],
            "rows": [[str(i), i] for i in range(217)],
            "truncated": False,
        },
        {"id": "query_2", "columns": ["life_expectancy_years"], "rows": [[108]], "truncated": False},
    ]
    calculation, _ = derive(body, evidence, wdi)
    assert len(calculation["rows"]) == 108 and not calculation["truncated"]
