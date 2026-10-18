import os
from unittest.mock import MagicMock, patch

import pytest

from datamind.config import load_dataset
from datamind.snowflake_client import ColumnInfo, SnowflakeClient


def test_from_env_missing_account(monkeypatch):
    monkeypatch.delenv("SNOWFLAKE_ACCOUNT", raising=False)
    with pytest.raises(ValueError, match="SNOWFLAKE_ACCOUNT environment variable is required"):
        SnowflakeClient.from_env()


def test_from_env_missing_auth(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ACCOUNT", "my_org-my_acc")
    monkeypatch.delenv("SNOWFLAKE_PASSWORD", raising=False)
    monkeypatch.delenv("SNOWFLAKE_PRIVATE_KEY_PATH", raising=False)
    with pytest.raises(ValueError, match="Either SNOWFLAKE_PASSWORD or SNOWFLAKE_PRIVATE_KEY_PATH"):
        SnowflakeClient.from_env()


def test_from_env_connects_with_password(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ACCOUNT", "my_org-my_acc")
    monkeypatch.setenv("SNOWFLAKE_USER", "MY_USER")
    monkeypatch.setenv("SNOWFLAKE_PASSWORD", "secret123")
    monkeypatch.setenv("SNOWFLAKE_ROLE", "MY_ROLE")
    monkeypatch.setenv("SNOWFLAKE_WAREHOUSE", "MY_WH")

    with patch("snowflake.connector.connect") as mock_connect:
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        client = SnowflakeClient.from_env()
        assert client is not None
        mock_connect.assert_called_once_with(
            account="my_org-my_acc",
            user="MY_USER",
            role="MY_ROLE",
            warehouse="MY_WH",
            session_parameters={"QUERY_TAG": "datamind"},
            password="secret123",
        )


def test_run_query_mock():
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    mock_cur.sfqid = "sfqid-12345"
    mock_cur.description = [("COL1",), ("COL2",)]
    mock_cur.rowcount = 1
    mock_cur.fetchmany.return_value = [(10, "val")]

    client = SnowflakeClient(mock_conn)
    result = client.run_query("SELECT 1", max_rows=100, timeout_s=30)

    assert result.query_id == "sfqid-12345"
    assert result.sql == "SELECT 1"
    assert result.columns == ["COL1", "COL2"]
    assert result.rows == [(10, "val")]
    assert result.row_count == 1
    assert not result.truncated
    assert result.elapsed_ms >= 0


def test_run_query_truncation_mock():
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    mock_cur.sfqid = "sfqid-67890"
    mock_cur.description = [("ID",)]
    mock_cur.rowcount = 500
    mock_cur.fetchmany.return_value = [(i,) for i in range(100)]

    client = SnowflakeClient(mock_conn)
    result = client.run_query("SELECT * FROM BIG_TABLE", max_rows=100, timeout_s=60)

    assert result.row_count == 500
    assert len(result.rows) == 100
    assert result.truncated is True


def test_describe_columns_mock():
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    mock_cur.fetchall.return_value = [
        ("CUSTOMER", "C_CUSTKEY", "NUMBER(38,0)", "Customer key"),
        ("CUSTOMER", "C_NAME", "VARCHAR(25)", None),
    ]

    client = SnowflakeClient(mock_conn)
    tpch = load_dataset("tpch")
    cols = client.describe_columns(tpch)

    assert len(cols) == 2
    assert cols[0] == ColumnInfo(
        table="CUSTOMER", name="C_CUSTKEY", data_type="NUMBER(38,0)", comment="Customer key"
    )
    assert cols[1] == ColumnInfo(
        table="CUSTOMER", name="C_NAME", data_type="VARCHAR(25)", comment=""
    )


@pytest.mark.skipif(
    not os.environ.get("SNOWFLAKE_ACCOUNT"),
    reason="Snowflake credentials not configured in environment",
)
def test_snowflake_live_integration():
    """Live smoke test verifying connection and query against TPC-H sample data."""
    client = SnowflakeClient.from_env()
    try:
        result = client.run_query(
            "SELECT COUNT(*) AS customers FROM SNOWFLAKE_SAMPLE_DATA.TPCH_SF1.CUSTOMER",
            max_rows=10,
            timeout_s=60,
        )
        assert result.query_id
        assert result.rows
        assert result.rows[0][0] == 150000
    finally:
        client.close()
