"""Thin Snowflake access layer. All SQL that produces an answer runs through here."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import snowflake.connector

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
        account = os.environ.get("SNOWFLAKE_ACCOUNT")
        if not account:
            raise ValueError("SNOWFLAKE_ACCOUNT environment variable is required")

        user = os.environ.get("SNOWFLAKE_USER", "DATAMIND_APP")
        password = os.environ.get("SNOWFLAKE_PASSWORD")
        role = os.environ.get("SNOWFLAKE_ROLE", "DATAMIND_READER")
        warehouse = os.environ.get("SNOWFLAKE_WAREHOUSE", "DATAMIND_WH")
        private_key_path = os.environ.get("SNOWFLAKE_PRIVATE_KEY_PATH")
        private_key_passphrase = os.environ.get("SNOWFLAKE_PRIVATE_KEY_PASSPHRASE")

        connect_kwargs: dict[str, Any] = {
            "account": account,
            "user": user,
            "role": role,
            "warehouse": warehouse,
            "session_parameters": {"QUERY_TAG": "datamind"},
        }

        if private_key_path:
            from cryptography.hazmat.primitives import serialization

            key_path = Path(private_key_path)
            if not key_path.is_file():
                raise FileNotFoundError(f"Snowflake private key file not found: {private_key_path}")

            with open(key_path, "rb") as key_file:
                p_key = serialization.load_pem_private_key(
                    key_file.read(),
                    password=private_key_passphrase.encode("utf-8")
                    if private_key_passphrase
                    else None,
                )
            pkb = p_key.private_bytes(
                encoding=serialization.Encoding.DER,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
            connect_kwargs["private_key"] = pkb
        elif password:
            connect_kwargs["password"] = password
        else:
            raise ValueError(
                "Either SNOWFLAKE_PASSWORD or SNOWFLAKE_PRIVATE_KEY_PATH must be provided"
            )

        conn = snowflake.connector.connect(**connect_kwargs)
        return cls(conn)

    def run_query(self, sql: str, *, max_rows: int, timeout_s: int) -> QueryResult:
        """Execute already-guarded SQL; return rows plus ``cursor.sfqid`` as query_id.

        Fetch at most ``max_rows`` rows, but report the true ``row_count``.
        """
        start = time.perf_counter()
        with self._conn.cursor() as cur:
            if timeout_s > 0:
                cur.execute(f"ALTER SESSION SET STATEMENT_TIMEOUT_IN_SECONDS = {int(timeout_s)}")

            cur.execute(sql)
            query_id = getattr(cur, "sfqid", "") or ""
            columns = [col[0] for col in cur.description] if cur.description else []

            # If the driver already knows total rowcount, fetch up to max_rows
            if getattr(cur, "rowcount", None) is not None and cur.rowcount >= 0:
                row_count = cur.rowcount
                fetched = cur.fetchmany(max_rows)
            else:
                fetched_all = cur.fetchall()
                row_count = len(fetched_all)
                fetched = fetched_all[:max_rows]

            truncated = row_count > max_rows
            rows = [tuple(r) for r in fetched]
            elapsed_ms = int((time.perf_counter() - start) * 1000)

            return QueryResult(
                query_id=query_id,
                sql=sql,
                columns=columns,
                rows=rows,
                row_count=row_count,
                truncated=truncated,
                elapsed_ms=elapsed_ms,
            )

    def describe_columns(self, dataset: DatasetConfig) -> list[ColumnInfo]:
        """Columns of the dataset's allowlisted tables from INFORMATION_SCHEMA.COLUMNS."""
        if not dataset.tables:
            return []

        table_names = [t.name.upper() for t in dataset.tables]
        escaped_tables = ", ".join(f"'{name}'" for name in table_names)
        db = dataset.database.upper()
        sch = dataset.schema.upper()

        query = f"""
            SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, COMMENT
            FROM {db}.INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = '{sch}'
              AND TABLE_NAME IN ({escaped_tables})
            ORDER BY TABLE_NAME, ORDINAL_POSITION
        """

        with self._conn.cursor() as cur:
            cur.execute(query)
            results = cur.fetchall() or []

        columns: list[ColumnInfo] = []
        for row in results:
            table = str(row[0])
            name = str(row[1])
            data_type = str(row[2])
            comment = str(row[3]) if len(row) > 3 and row[3] is not None else ""
            columns.append(ColumnInfo(table=table, name=name, data_type=data_type, comment=comment))

        return columns

    def close(self) -> None:
        self._conn.close()
