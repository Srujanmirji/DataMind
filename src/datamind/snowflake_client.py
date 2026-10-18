"""Thin Snowflake access layer. All SQL that produces an answer runs through here."""

from __future__ import annotations

from dataclasses import dataclass

from datamind.config import DatasetConfig
from datamind.models import QueryResult


@dataclass(frozen=True)
class ColumnInfo:
    table: str
    name: str
    data_type: str
    comment: str = ""


class SnowflakeClient:
    """Wraps one ``snowflake.connector`` connection using the read-only app role."""

    def __init__(self, connection) -> None:  # snowflake.connector.SnowflakeConnection
        self._conn = connection

    @classmethod
    def from_env(cls) -> SnowflakeClient:
        """Connect with SNOWFLAKE_* variables (see .env.example).

        Set ``session_parameters={"QUERY_TAG": "datamind"}`` so every app query
        can be listed from QUERY_HISTORY as evidence for judges.
        """
        # TODO: snowflake.connector.connect(account=..., user=..., role=..., warehouse=...)
        raise NotImplementedError("SnowflakeClient.from_env")

    def run_query(self, sql: str, *, max_rows: int, timeout_s: int) -> QueryResult:
        """Execute already-guarded SQL; return rows plus ``cursor.sfqid`` as query_id.

        Fetch at most ``max_rows`` rows, but report the true ``row_count``.
        """
        raise NotImplementedError("SnowflakeClient.run_query")

    def describe_columns(self, dataset: DatasetConfig) -> list[ColumnInfo]:
        """Columns of the dataset's allowlisted tables from INFORMATION_SCHEMA.COLUMNS."""
        raise NotImplementedError("SnowflakeClient.describe_columns")

    def close(self) -> None:
        self._conn.close()
