"""Executable spec for datamind.sql_guard.validate_sql.

Every case is xfail(raises=NotImplementedError) until the guard exists; once
implemented these become ordinary passing tests (and a regression fails loudly).
"""

import pytest

from datamind.config import load_dataset
from datamind.sql_guard import validate_sql

pending = pytest.mark.xfail(raises=NotImplementedError, reason="sql_guard not implemented")
TPCH = load_dataset("tpch")

ALLOWED = [
    "SELECT COUNT(*) FROM SNOWFLAKE_SAMPLE_DATA.TPCH_SF1.CUSTOMER",
    "select c_name from customer limit 5",  # unqualified -> dataset schema
    "WITH t AS (SELECT * FROM ORDERS) SELECT COUNT(*) FROM t",  # CTE is not a table
]

REJECTED = [
    "DELETE FROM ORDERS",
    "DROP TABLE ORDERS",
    "SELECT 1; DROP TABLE ORDERS",
    "UPDATE CUSTOMER SET C_NAME = 'x'",
    "SELECT * FROM SNOWFLAKE.ACCOUNT_USAGE.LOGIN_HISTORY",
    "SELECT * FROM SNOWFLAKE_SAMPLE_DATA.TPCDS_SF10TCL.STORE_SALES",  # not allowlisted
    "SELECT * FROM TABLE(RESULT_SCAN(LAST_QUERY_ID()))",
    "GRANT SELECT ON ORDERS TO ROLE PUBLIC",
    "USE ROLE ACCOUNTADMIN",
]


@pending
@pytest.mark.parametrize("sql", ALLOWED)
def test_allows_read_only_queries_on_allowlist(sql):
    result = validate_sql(sql, TPCH)
    assert result.allowed, result.reasons


@pending
@pytest.mark.parametrize("sql", REJECTED)
def test_rejects_unsafe_or_out_of_scope(sql):
    result = validate_sql(sql, TPCH)
    assert not result.allowed
    assert result.reasons


@pending
def test_enforces_row_cap():
    result = validate_sql("SELECT * FROM ORDERS LIMIT 100000", TPCH)
    assert result.allowed
    assert f"LIMIT {TPCH.guardrails.max_rows}" in result.sql.upper()
    assert result.reasons  # the rewrite is reported, not silent
