"""Static SQL validation: the last line of defence before Snowflake.

The read-only role in snowflake/00_setup.sql is the real permission boundary;
this guard gives fast, explainable rejections and enforces the table allowlist
and row cap so a bad generation never costs warehouse credits.

Contract (see tests/test_sql_guard_contract.py — xfail until implemented):
  * exactly one statement; reject ``;``-chained statements
  * SELECT / WITH ... SELECT only — no DML, DDL, GRANT, CALL, PUT, COPY, USE, SET
  * every referenced table resolves to ``dataset.allowed_tables`` after qualifying
    unqualified names with the dataset's database and schema; CTE names are not tables
  * no table functions that read outside the dataset (e.g. INFER_SCHEMA, RESULT_SCAN)
  * a LIMIT no larger than ``max_rows`` is enforced (added or lowered), and reported
  * rejections carry human-readable ``reasons`` the UI can show
Suggested approach: ``sqlglot.parse(sql, read="snowflake")`` and walk ``exp.Table``.
"""

from __future__ import annotations

from datamind.config import DatasetConfig
from datamind.models import GuardResult


def validate_sql(sql: str, dataset: DatasetConfig) -> GuardResult:
    raise NotImplementedError("validate_sql")
