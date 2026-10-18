import json
from unittest.mock import Mock

import pytest

from app.config import ROOT, Settings
from app.grounding import check_scope, clarification
from app.models import Plan, Question
from app.planner import Planner
from app.service import QuestionService


@pytest.fixture
def wdi():
    return json.loads((ROOT / "datasets/worldbank_wdi.json").read_text())


def plan(country="IND", year=2023, metric="total_population"):
    return Plan(
        status="query",
        metrics=[metric],
        filters=[
            {"field": "year", "operator": "eq", "values": [year]},
            *([{"field": "country_code", "operator": "eq", "values": [country]}] if country else []),
        ],
    )


@pytest.mark.parametrize(
    "question,body",
    [
        ("India's population in 2023?", plan()),
        ("Can you show the population of India in 2023?", plan()),
        ("US population in 2023?", plan("USA")),
        ("Nigeria population in 2023?", plan("NGA")),
        ("Population of Equatorial Guinea in 2023?", plan("GNQ")),
        ("What was the GDP of South Korea in 2023?", plan("KOR", metric="total_gdp_usd")),
        (
            "Top 5 countries by GDP per capita in 2023?",
            Plan(
                status="query",
                metrics=["gdp_per_capita_usd"],
                dimensions=["country"],
                filters=[{"field": "year", "operator": "eq", "values": [2023]}],
                limit=5,
            ),
        ),
    ],
)
def test_explicit_dataset_scopes_are_allowed(wdi, question, body):
    check_scope(question, body, wdi)


@pytest.mark.parametrize(
    "question,body",
    [
        ("India's population?", plan()),
        ("India's population in 2023?", plan(year=2022)),
        ("India's population in 2023?", plan("CHN")),
        ("India's population in 2023?", plan(None)),
        ("Population in 2023?", plan()),
        ("India and China population in 2023?", plan()),
        ("Nigeria population in 2023?", plan("NER")),
        ("Population of Equatorial Guinea in 2023?", plan("GIN")),
        ("India's GDP in 2023?", plan(metric="total_population")),
        ("India's GDP per capita in 2023?", plan(metric="total_gdp_usd")),
        ("India's population in 2030?", plan(year=2030)),
    ],
)
def test_invented_omitted_or_changed_scopes_are_rejected(wdi, question, body):
    with pytest.raises(ValueError):
        check_scope(question, body, wdi)


@pytest.mark.parametrize(
    "stage,status",
    [
        ("router", "unsupported"),
        ("router", "needs_clarification"),
        ("planner", "unsupported"),
        ("planner", "needs_clarification"),
    ],
)
def test_refusals_never_execute_or_repeat_model_facts(wdi, stage, status):
    planner = Planner(Settings(_env_file=None), wdi)
    bad_message = "The cricket winner was a made-up team."
    decision = (
        {"mode": status, "reason": bad_message}
        if stage == "router"
        else {"status": status, "message": bad_message}
    )
    outputs = [decision] if stage == "router" else [{"mode": "aggregate"}, decision]
    planner._generate = Mock(side_effect=[json.dumps(o) for o in outputs])
    warehouse = Mock()
    result = QuestionService(planner.settings, wdi, planner, warehouse).ask(
        Question(question="Who won the cricket match?", dataset_id="worldbank_wdi")
    )
    assert result["status"] == status and bad_message not in result["answer"]
    assert not result["evidence"] and not result["plan_cache_hit"]
    warehouse.execute.assert_not_called()


def test_model_invented_country_fails_closed_after_one_retry(wdi):
    planner = Planner(Settings(_env_file=None), wdi)
    planner._generate = Mock(
        side_effect=[
            json.dumps({"mode": "aggregate"}),
            plan("CHN").model_dump_json(),
            plan("CHN").model_dump_json(),
        ]
    )
    warehouse = Mock()
    result = QuestionService(planner.settings, wdi, planner, warehouse).ask(
        Question(question="India's population in 2023?", dataset_id="worldbank_wdi")
    )
    assert result["status"] == "needs_clarification" and not result["evidence"]
    warehouse.execute.assert_not_called()


def test_unavailable_measurement_is_not_reported_as_a_fact(wdi):
    planner, warehouse = Mock(), Mock()
    planner.plan.return_value = plan(metric="life_expectancy_years")
    warehouse.execute.return_value = {
        "columns": ["life_expectancy_years"],
        "rows": [[None]],
        "truncated": False,
    }
    result = QuestionService(Settings(_env_file=None), wdi, planner, warehouse).ask(
        Question(question="India's life expectancy in 2023?", dataset_id="worldbank_wdi")
    )
    assert result["status"] == "empty" and "unavailable" in result["answer"]
    assert not result["claims"] and result["evidence"]


def test_single_year_cannot_be_broadened_to_since(wdi):
    body = plan()
    body.filters[0].operator = "gte"
    with pytest.raises(ValueError, match="exact requested"):
        check_scope("India population in 2023?", body, wdi)
    check_scope("India population since 2023?", body, wdi)


def test_supported_question_still_runs_sql_and_uses_plan_cache(wdi):
    planner = Planner(Settings(_env_file=None), wdi)
    planner._generate = Mock(
        side_effect=[
            json.dumps({"mode": "aggregate"}),
            plan(metric="life_expectancy_years", year=2022).model_dump_json(),
        ]
    )
    warehouse = Mock()
    warehouse.execute.side_effect = [
        {"columns": ["life_expectancy_years"], "rows": [[71.698]], "truncated": False, "query_id": "new-1"},
        {"columns": ["life_expectancy_years"], "rows": [[72.0]], "truncated": False, "query_id": "new-2"},
    ]
    service = QuestionService(planner.settings, wdi, planner, warehouse)
    q = Question(question="India's life expectancy in 2022?", dataset_id="worldbank_wdi")
    first, second = service.ask(q), service.ask(q)
    assert first["status"] == second["status"] == "answered"
    assert not first["plan_cache_hit"] and second["plan_cache_hit"]
    assert planner._generate.call_count == 2 and warehouse.execute.call_count == 2
    assert first["evidence"][0]["rows"] != second["evidence"][0]["rows"]


def test_missing_comparison_input_has_no_claims_or_invented_difference(wdi):
    planner, warehouse = Mock(), Mock()
    body = plan(metric="life_expectancy_years", year=2023)
    body.analysis = "compare"
    body.reference_filters = plan(metric="life_expectancy_years", year=2022).filters
    planner.plan.return_value = body
    warehouse.execute.side_effect = [
        {"columns": ["life_expectancy_years"], "rows": [[None]], "truncated": False},
        {"columns": ["life_expectancy_years"], "rows": [[71.698]], "truncated": False},
    ]
    result = QuestionService(Settings(_env_file=None), wdi, planner, warehouse).ask(
        Question(question="Compare India's life expectancy from 2022 to 2023", dataset_id="worldbank_wdi")
    )
    assert result["status"] == "empty" and not result["claims"]
    assert "unavailable" in result["answer"]


def test_missing_year_asks_only_for_the_missing_period(wdi):
    result = clarification(wdi, "What was India's GDP?")
    assert result.status == "needs_clarification"
    assert "Which year" in result.message and "1990" in result.message and "2024" in result.message


def test_average_across_region_is_not_silently_grouped_by_country(wdi):
    question = "What was the average CO2 emissions per person across Sub-Saharan African countries in 2020?"
    body = Plan(
        status="query",
        metrics=["co2_per_capita_tonnes"],
        filters=[
            {"field": "region", "operator": "eq", "values": ["SUB-SAHARAN AFRICA"]},
            {"field": "year", "operator": "eq", "values": [2020]},
        ],
    )
    check_scope(question, body, wdi)
    body.dimensions = ["country"]
    with pytest.raises(ValueError, match="Grouping"):
        check_scope(question, body, wdi)


@pytest.mark.parametrize(
    "question",
    [
        "List the 10 countries with the lowest total GDP in 2023",
        "Show me the 10 countries with the lowest total GDP in 2023",
        "Give 10 countries with the lowest total GDP in 2023",
        "Which are the 10 countries with the lowest total GDP in 2023?",
        "Bottom 10 countries by total GDP in 2023",
        "The 10 lowest countries by total GDP in 2023",
    ],
)
def test_natural_list_size_is_a_limit_not_a_filter(wdi, question):
    planner = Planner(Settings(_env_file=None), wdi)
    body = Plan(
        status="query",
        metrics=["total_gdp_usd"],
        dimensions=["country"],
        filters=[{"field": "year", "operator": "eq", "values": [2023]}],
        sort=[{"field": "total_gdp_usd", "direction": "asc"}],
        limit=10,
    )
    planner._generate = Mock(side_effect=[json.dumps({"mode": "aggregate"}), body.model_dump_json()])
    assert planner.plan(question) == body
    assert planner._generate.call_count == 2


def test_incorrect_list_size_gets_one_repair(wdi):
    planner = Planner(Settings(_env_file=None), wdi)
    body = Plan(
        status="query",
        metrics=["total_gdp_usd"],
        dimensions=["country"],
        filters=[{"field": "year", "operator": "eq", "values": [2023]}],
        sort=[{"field": "total_gdp_usd", "direction": "asc"}],
        limit=20,
    )
    repaired = body.model_copy(update={"limit": 10})
    planner._generate = Mock(
        side_effect=[json.dumps({"mode": "aggregate"}), body.model_dump_json(), repaired.model_dump_json()]
    )
    assert planner.plan("List the 10 countries with the lowest total GDP in 2023").limit == 10
    assert planner._generate.call_count == 3


@pytest.mark.parametrize(
    "question,metric",
    [
        ("How long could people in India expect to live at birth in 2022?", "life_expectancy_years"),
        ("What fraction of people in India were connected online in 2022?", "internet_users_pct"),
        ("What was India's education spending as a share of GDP in 2022?", "education_spending_pct_gdp"),
        ("What was India's trade in 2022?", "trade_pct_gdp"),
        ("What percentage of adults in India could read and write in 2022?", "adult_literacy_pct"),
    ],
)
def test_semantic_paraphrases_are_not_limited_to_keyword_examples(wdi, question, metric):
    planner = Planner(Settings(_env_file=None), wdi)
    body = plan(metric=metric, year=2022)
    planner._generate = Mock(side_effect=[json.dumps({"mode": "aggregate"}), body.model_dump_json()])
    assert planner.plan(question) == body


def test_clarification_uses_only_validated_missing_fields(wdi):
    planner = Planner(Settings(_env_file=None), wdi)
    planner._generate = Mock(
        return_value=json.dumps(
            {
                "mode": "needs_clarification",
                "reason": "invented facts",
                "missing_fields": ["baseline", "baseline", "invented facts"],
            }
        )
    )
    result = planner.plan("Compare India's GDP in 2023")
    assert "compare against" in result.message
    assert "invented facts" not in result.message
    assert "Which year" not in result.message


def test_grouping_does_not_require_a_fixed_introductory_phrase(wdi):
    body = plan(country=None, metric="life_expectancy_years")
    body.dimensions = ["country"]
    check_scope("Where did people live longest in 2023?", body, wdi)


@pytest.mark.parametrize(
    "question",
    [
        "What is India’s GDP in 2022?",
        "What is Indiaʼs GDP in 2022?",
        "What is ‘India’ GDP in 2022?",
    ],
)
def test_unicode_punctuation_preserves_country_boundaries(wdi, question):
    planner = Planner(Settings(_env_file=None), wdi)
    body = plan(metric="total_gdp_usd", year=2022)
    planner._generate = Mock(side_effect=[json.dumps({"mode": "aggregate"}), body.model_dump_json()])
    assert planner.plan(question) == body
    assert planner._generate.call_count == 2
    with pytest.raises(ValueError):
        check_scope(question, plan("CHN", year=2022, metric="total_gdp_usd"), wdi)
