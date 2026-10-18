"""Bounded two-query analysis with Decimal arithmetic and cell-level provenance."""

from decimal import ROUND_HALF_UP, Decimal, localcontext
from typing import Any

from app.compiler import compile_plan
from app.config import Settings
from app.errors import BackendError
from app.models import Plan


def filter_keys(filters):
    return {item.model_dump_json() for item in filters}


def analysis_steps(plan: Plan, dataset: dict, settings: Settings):
    """Validate the entire analysis before any SQL executes."""
    if plan.analysis == "aggregate":
        return [compile_plan(plan, dataset, settings.snowflake_database, settings.snowflake_schema)]
    metric = plan.metrics[0]
    definition = dataset["metrics"].get(metric)
    if not definition:
        raise ValueError("Unknown metric.")
    target_keys = filter_keys(plan.filters)
    reference_keys = filter_keys(plan.reference_filters)
    if plan.analysis == "compare" and target_keys == reference_keys:
        raise ValueError("A comparison needs distinct, explicit target and reference scopes.")
    if plan.analysis == "share":
        if not definition.get("supports_share"):
            raise ValueError("Share needs a count or additive total, not an average.")
        if not reference_keys.issubset(target_keys):
            raise ValueError("For share, reference filters must also occur identically in target filters.")
        if reference_keys == target_keys:
            raise ValueError("A share needs a narrower target scope than its reference.")
    if plan.analysis == "above_average":
        if definition.get("aggregation") != "average":
            raise ValueError("Above-average analysis needs an average metric.")
        if target_keys != reference_keys:
            raise ValueError("Above-average group and population filters must be identical.")
    values = plan.model_dump()
    values.update(analysis="aggregate", reference_filters=[], dimensions=[], sort=[])
    first = Plan.model_validate({**values, "filters": [item.model_dump() for item in plan.filters]})
    second = Plan.model_validate(
        {**values, "filters": [item.model_dump() for item in plan.reference_filters]}
    )
    if plan.analysis == "above_average":
        first = Plan.model_validate(
            {
                **first.model_dump(),
                "dimensions": plan.dimensions,
                "sort": [item.model_dump() for item in plan.sort],
                "limit": 100,
            }
        )
    return [
        compile_plan(step, dataset, settings.snowflake_database, settings.snowflake_schema)
        for step in (first, second)
    ]


def decimal_value(value):
    if value is None:
        return None
    number = Decimal(str(value))
    if not number.is_finite():
        raise BackendError("invalid_result", "A query returned a non-finite value.", 502)
    return number


def display(number):
    if number is None:
        return None
    # Fixed precision for derived values; original query decimals remain unchanged.
    with localcontext() as context:
        context.prec = 60
        return format(number.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP), "f")


def cell(evidence, row_index, column):
    return {"evidence_id": evidence["id"], "row_index": row_index, "column": column}


def scalar(evidence, metric):
    if evidence["truncated"] or len(evidence["rows"]) != 1:
        raise BackendError("incomplete_result", "Expected one complete aggregate row.", 502)
    return decimal_value(evidence["rows"][0][evidence["columns"].index(metric)])


def derive(plan: Plan, evidence: list[dict], dataset: dict) -> tuple[dict, list[str]]:
    first, second = evidence
    metric = plan.metrics[0]
    reference = scalar(second, metric)
    warnings = []
    if plan.analysis == "above_average":
        if first["truncated"]:
            raise BackendError(
                "incomplete_groups", "More than 100 groups exist; narrow the filters first.", 422
            )
        dimension = plan.dimensions[0]
        selected = []
        for index, row in enumerate(first["rows"]):
            value = decimal_value(row[first["columns"].index(metric)])
            if value is not None and reference is not None and value > reference:
                selected.append((index, row, value))
        # Compare full-precision values before rounding, then apply requested top-N.
        metric_sort = next((sort for sort in plan.sort if sort.field == metric), None)
        if metric_sort:
            selected.sort(key=lambda item: item[2], reverse=metric_sort.direction == "desc")
        total_matches = len(selected)
        selected = selected[: plan.limit]
        rows, lineage = [], []
        for source_index, row, value in selected:
            group = row[first["columns"].index(dimension)]
            with localcontext() as context:
                context.prec = 60
                difference = value - reference
            rows.append([group, display(value), display(reference), display(difference)])
            lineage.append(
                {
                    "query_1": cell(first, source_index, metric),
                    "query_2": cell(second, 0, metric),
                    "group": cell(first, source_index, dimension),
                }
            )
        derived: dict[str, Any] = {
            "columns": [dimension, metric, "overall_average", "difference"],
            "rows": rows,
            "inputs": lineage,
            "truncated": total_matches > plan.limit,
            "formulas": {
                "selection": f"{metric} > overall_average",
                "overall_average": "Same metric computed over all underlying rows, not a mean of group means.",
                "difference": "group metric - overall_average",
            },
        }
        if reference is None:
            warnings.append("Overall average is unavailable; no above-average groups can be established.")
    else:
        target = scalar(first, metric)
        ratio = change = percent_change = share = None
        with localcontext() as context:
            context.prec = 60
            if target is not None and reference is not None:
                change = target - reference
                if reference != 0:
                    ratio = target / reference
                    percent_change = change / reference * 100
                    share = ratio * 100
                else:
                    warnings.append(
                        "Reference is zero; percentage change and share are undefined (null), not zero."
                    )
            else:
                warnings.append("An input aggregate is unavailable; derived values requiring it are null.")
        if plan.analysis == "share":
            columns = ["target_value", "reference_value", "share_percent"]
            rows = [[display(target), display(reference), display(share)]]
            formulas = {"share_percent": "target_value / reference_value * 100"}
        else:
            columns = ["target_value", "reference_value", "difference", "percent_change"]
            rows = [[display(target), display(reference), display(change), display(percent_change)]]
            formulas = {
                "difference": "target_value - reference_value",
                "percent_change": "(target_value - reference_value) / reference_value * 100",
            }
        derived = {
            "columns": columns,
            "rows": rows,
            "truncated": False,
            "formulas": formulas,
            "inputs": [{"target": cell(first, 0, metric), "reference": cell(second, 0, metric)}],
        }
    return {
        "id": "calculation_1",
        "kind": "calculation",
        "query_id": None,
        "sql": None,
        "parameters": [],
        "row_count": len(derived["rows"]),
        "analysis": plan.analysis,
        "metric": metric,
        "rounding": "Derived values rounded half-up to six decimal places; decisions use original precision.",
        **derived,
    }, warnings
