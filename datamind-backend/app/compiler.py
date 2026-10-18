import re
from dataclasses import dataclass
from datetime import date

from app.models import Plan

IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
OPERATORS = {"eq": "=", "ne": "<>", "gt": ">", "gte": ">=", "lt": "<", "lte": "<="}


@dataclass
class CompiledQuery:
    sql: str
    parameters: list[str | int]
    limit: int


def compile_plan(plan: Plan, dataset: dict, database: str, schema: str) -> CompiledQuery:
    """Only trusted local configuration contributes SQL; model values are bound."""
    if plan.status != "query":
        raise ValueError("Only query plans can execute.")
    if plan.analysis != "aggregate":
        raise ValueError("Multi-step plans must be compiled through the analysis orchestrator.")
    database = dataset.get("database", database)
    schema = dataset.get("schema", schema)
    if not IDENTIFIER.fullmatch(database) or not IDENTIFIER.fullmatch(schema):
        raise ValueError("Database and schema must be simple Snowflake identifiers.")
    metrics = dataset["metrics"]
    dimensions = dataset["dimensions"]
    fields = {**dimensions, **dataset["filter_fields"]}
    selected = plan.dimensions + plan.metrics
    if any(name not in metrics for name in plan.metrics):
        raise ValueError("Unknown metric.")
    if any(name not in dimensions for name in plan.dimensions):
        raise ValueError("Unknown grouping dimension.")
    if any(not IDENTIFIER.fullmatch(name) for name in selected):
        raise ValueError("Invalid output identifier.")
    projections = [f'{dimensions[name]["sql"]} AS "{name}"' for name in plan.dimensions]
    projections += [f'{metrics[name]["sql"]} AS "{name}"' for name in plan.metrics]
    context = {"database": database, "schema": schema}
    source = dataset["from"].format(**context)
    joins = [join.format(**context) for join in dataset["joins"]]
    sql = "SELECT " + ", ".join(projections) + "\nFROM " + source
    if joins:
        sql += "\n" + "\n".join(joins)
    clauses, parameters = [], []
    for item in plan.filters:
        if item.field not in fields:
            raise ValueError("Unknown filter field.")
        field = fields[item.field]
        values = []
        for value in item.values:
            if field["type"] == "date":
                if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
                    raise ValueError("Dates must use YYYY-MM-DD.")
            elif field["type"] == "integer":
                if type(value) is not int:
                    raise ValueError("This filter needs integer values.")
            elif not isinstance(value, str):
                raise ValueError("This filter needs text values.")
            values.append(value)
        expression = field["sql"]
        placeholder = "TO_DATE(%s)" if field["type"] == "date" else "%s"
        if item.operator == "in":
            clauses.append(f"{expression} IN ({', '.join([placeholder] * len(values))})")
        elif item.operator == "between":
            if type(values[0]) is not type(values[1]):
                raise ValueError("Range endpoints must have the same type.")
            if values[0] > values[1]:  # type: ignore[operator]
                raise ValueError("Range start must precede range end.")
            clauses.append(f"{expression} BETWEEN {placeholder} AND {placeholder}")
        else:
            clauses.append(f"{expression} {OPERATORS[item.operator]} {placeholder}")
        parameters.extend(values)
    if clauses:
        sql += "\nWHERE " + " AND ".join(clauses)
    if plan.dimensions:
        sql += "\nGROUP BY " + ", ".join(dimensions[name]["sql"] for name in plan.dimensions)
    ordering = []
    for sort_item in plan.sort:
        if sort_item.field not in selected:
            raise ValueError("Sort fields must be selected metrics or dimensions.")
        ordering.append(f'"{sort_item.field}" {sort_item.direction.upper()} NULLS LAST')
    # Stable tie-breaking is useful both for evidence and evaluation.
    sorted_fields = {item.field for item in plan.sort}
    ordering.extend(f'"{name}" ASC NULLS LAST' for name in plan.dimensions if name not in sorted_fields)
    if ordering:
        sql += "\nORDER BY " + ", ".join(ordering)
    # Fetch one extra group to detect truncation; never limit the source rows.
    sql += f"\nLIMIT {plan.limit + 1}"
    return CompiledQuery(sql, parameters, plan.limit)
