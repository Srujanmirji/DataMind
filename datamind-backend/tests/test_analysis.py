import json
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from app.analysis import analysis_steps, derive
from app.config import ROOT, Settings
from app.errors import BackendError
from app.models import Plan, Question
from app.service import QuestionService


@pytest.fixture
def dataset():
    return json.loads((ROOT / "datasets/uci_wine_quality.json").read_text())


def f(value, field="quality", operator="eq"):
    return {"field": field, "operator": operator, "values": [value]}


def compare(**kwargs):
    return Plan(
        status="query",
        analysis="compare",
        metrics=["sample_count"],
        filters=[f(8)],
        reference_filters=[f(7)],
        **kwargs,
    )


def evidence(value, identifier="query_1", column="sample_count"):
    return {"id": identifier, "columns": [column], "rows": [[value]], "truncated": False}


def test_comparison_math_and_source_lineage(dataset):
    calculation, warnings = derive(compare(), [evidence(120), evidence(80, "query_2")], dataset)
    assert calculation["rows"] == [["120.000000", "80.000000", "40.000000", "50.000000"]]
    assert calculation["inputs"][0]["target"] == {
        "evidence_id": "query_1",
        "row_index": 0,
        "column": "sample_count",
    }
    assert not warnings


@pytest.mark.parametrize(
    "target,reference,expected",
    [
        (0, 0, ["0.000000", "0.000000", "0.000000", None]),
        (3, 0, ["3.000000", "0.000000", "3.000000", None]),
        (None, 4, [None, "4.000000", None, None]),
        (4, None, ["4.000000", None, None, None]),
    ],
)
def test_zero_and_null_inputs_do_not_invent_percentages(dataset, target, reference, expected):
    calculation, warnings = derive(compare(), [evidence(target), evidence(reference, "query_2")], dataset)
    assert calculation["rows"] == [expected]
    assert warnings


def test_percentage_decrease_and_precision(dataset):
    calculation, _ = derive(compare(), [evidence("0.20"), evidence("0.30", "query_2")], dataset)
    assert calculation["rows"][0][2:] == ["-0.100000", "-33.333333"]


def test_share_uses_explicit_subset_denominator(dataset):
    plan = Plan(
        status="query",
        analysis="share",
        metrics=["sample_count"],
        filters=[f("WHITE", "wine_type"), f(8, operator="gte")],
        reference_filters=[f("WHITE", "wine_type")],
    )
    queries = analysis_steps(plan, dataset, Settings(_env_file=None))
    assert queries[0].parameters == ["WHITE", 8]
    assert queries[1].parameters == ["WHITE"]
    calculation, _ = derive(plan, [evidence(1), evidence(3, "query_2")], dataset)
    assert calculation["rows"][0][-1] == "33.333333"


@pytest.mark.parametrize(
    "analysis,metric,filters,reference,dimensions",
    [
        ("share", "average_quality", [f(8)], [], []),
        ("share", "sample_count", [f(8)], [f(7)], []),
        ("share", "sample_count", [], [], []),
        ("compare", "sample_count", [], [], []),
        ("above_average", "sample_count", [], [], ["wine_type"]),
        ("above_average", "average_quality", [f(7)], [], ["wine_type"]),
    ],
)
def test_invalid_multi_scopes_never_execute(dataset, analysis, metric, filters, reference, dimensions):
    plan = Plan(
        status="query",
        analysis=analysis,
        metrics=[metric],
        filters=filters,
        reference_filters=reference,
        dimensions=dimensions,
    )
    planner, warehouse = Mock(), Mock()
    planner.plan.return_value = plan
    service = QuestionService(Settings(_env_file=None), dataset, planner, warehouse)
    with pytest.raises(BackendError):
        service.ask(Question(question="Analyze these samples", dataset_id="uci_wine_quality"))
    warehouse.execute.assert_not_called()


def test_above_average_uses_population_average_and_preserves_group_lineage(dataset):
    plan = Plan(
        status="query", analysis="above_average", metrics=["average_quality"], dimensions=["wine_type"]
    )
    first = {
        "id": "query_1",
        "columns": ["wine_type", "average_quality"],
        "rows": [["A", "2"], ["B", "7"], ["C", "10"]],
        "truncated": False,
    }
    second = evidence("8", "query_2", "average_quality")
    calculation, _ = derive(plan, [first, second], dataset)
    # Average of the three group means is 6.33; that would incorrectly include B.
    assert calculation["rows"] == [["C", "10.000000", "8.000000", "2.000000"]]
    assert calculation["inputs"][0]["query_1"]["row_index"] == 2
    queries = analysis_steps(plan, dataset, Settings(_env_file=None))
    assert "GROUP BY" in queries[0].sql and "LIMIT 101" in queries[0].sql
    assert "GROUP BY" not in queries[1].sql and "AVG(w.QUALITY)" in queries[1].sql


def test_truncated_groups_are_rejected(dataset):
    plan = Plan(status="query", analysis="above_average", metrics=["average_quality"], dimensions=["quality"])
    first = evidence("8", column="average_quality")
    first["truncated"] = True
    with pytest.raises(BackendError, match="More than 100"):
        derive(plan, [first, evidence("7", "query_2", "average_quality")], dataset)


def test_complete_service_returns_query_and_calculation_evidence(dataset):
    planner, warehouse = Mock(), Mock()
    planner.plan.return_value = compare()
    warehouse.execute.side_effect = [evidence(10), evidence(5)]
    service = QuestionService(Settings(_env_file=None), dataset, planner, warehouse)
    result = service.ask(Question(question="Compare two scores", dataset_id="uci_wine_quality"))
    assert [item["id"] for item in result["evidence"]] == ["query_1", "query_2", "calculation_1"]
    assert result["status"] == "answered" and warehouse.execute.call_count == 2
    for claim in result["claims"]:
        entry = next(item for item in result["evidence"] if item["id"] == claim["evidence_id"])
        assert claim["value"] == entry["rows"][claim["row_index"]][entry["columns"].index(claim["column"])]


def test_multi_shape_is_bounded():
    with pytest.raises(ValidationError):
        compare(dimensions=["quality"])
    with pytest.raises(ValidationError):
        Plan(status="query", analysis="above_average", metrics=["average_quality"])
    with pytest.raises(ValidationError):
        Plan(status="query", analysis="compare", metrics=["sample_count", "average_quality"])


def test_non_finite_results_rejected(dataset):
    with pytest.raises(BackendError):
        derive(compare(), [evidence("NaN"), evidence(1, "query_2")], dataset)
