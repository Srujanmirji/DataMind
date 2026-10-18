from decimal import Decimal

from scripts.evaluate import tables_equal


def test_table_matching_handles_numeric_group_reordering_and_duplicate_rows():
    expected = {"columns": ["quality", "count"], "rows": [[7, 20], [6, 30]]}
    actual = {"columns": ["count", "quality"], "rows": [[30, 6], [20, 7]]}
    assert tables_equal(actual, expected)
    actual["rows"] = [[30, 6], [30, 6]]
    assert not tables_equal(actual, expected)


def test_table_matching_rejects_nonfinite_and_invalid_numeric_cells():
    expected = {"columns": ["value"], "rows": [[Decimal("1.123456")]]}
    for value in ["NaN", "wrong", None, "1.13"]:
        assert not tables_equal({"columns": ["value"], "rows": [[value]]}, expected)
    assert tables_equal({"columns": ["value"], "rows": [["1.1234561"]]}, expected)


def test_semantic_plan_check_ignores_filter_order_but_detects_wrong_baseline():
    from app.models import Plan
    from scripts.evaluate_plans import same_fields

    plan = Plan(
        status="query",
        analysis="compare",
        metrics=["order_count"],
        filters=[{"field": "order_year", "operator": "eq", "values": [1994]}],
        reference_filters=[{"field": "order_year", "operator": "eq", "values": [1993]}],
    )
    assert same_fields(plan, {"metrics": ["order_count"], "analysis": "compare"})
    assert not same_fields(
        plan, {"reference_filters": [{"field": "order_year", "operator": "eq", "values": [1992]}]}
    )


def test_required_values_match_with_extra_context_but_not_missing_metrics():
    expected = {"columns": ["count"], "rows": [[180]]}
    assert tables_equal({"columns": ["wine_type", "count"], "rows": [["WHITE", 180]]}, expected)
    assert not tables_equal({"columns": ["wine_type"], "rows": [["WHITE"]]}, expected)
    assert not tables_equal({"columns": ["wine_type", "count"], "rows": [["WHITE", 179]]}, expected)
