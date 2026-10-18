from datetime import date, datetime
from decimal import Decimal
from time import monotonic

import snowflake.connector
from snowflake.connector.errors import Error

from app.compiler import CompiledQuery
from app.config import Settings
from app.planner import BackendError


def json_value(value):
    # Preserve fixed-point precision rather than rounding through float/JavaScript.
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


class Warehouse:
    def __init__(self, settings: Settings, private_key: bytes | None = None, dev_mode: bool = False):
        self.settings = settings
        self.private_key = private_key
        self.dev_mode = dev_mode

    def _simulate(self, query: CompiledQuery, run_id: str) -> dict:
        import re

        cols = getattr(query, "columns", None)
        if not cols:
            matches = re.findall(r'AS\s+"([^"]+)"', query.sql)
            cols = matches if matches else ["VAL"]

        limit = min(getattr(query, "limit", 5), 5)
        sample_rows = []
        if "country" in cols:
            demo_countries = [
                ("LUXEMBOURG", "128734.50"),
                ("IRELAND", "103685.20"),
                ("SWITZERLAND", "99994.80"),
                ("NORWAY", "87961.80"),
                ("SINGAPORE", "84734.10"),
            ]
            for i in range(limit):
                c_name, val = demo_countries[i % len(demo_countries)]
                row = []
                for c in cols:
                    if c == "country":
                        row.append(c_name)
                    elif c == "year":
                        row.append(2023)
                    elif c == "order_count":
                        row.append("1500000")
                    elif "gdp" in c or "per_capita" in c:
                        row.append(val)
                    else:
                        row.append("100.00")
                sample_rows.append(row)
        else:
            row = []
            for c in cols:
                if "count" in c:
                    row.append("1500000")
                elif "pct" in c or "share" in c:
                    row.append("19.70")
                elif "year" in c:
                    row.append(2023)
                else:
                    row.append("42.00")
            sample_rows.append(row)

        return {
            "id": "query_1",
            "query_id": f"01b8e4f1-dev-{run_id[:8]}",
            "sql": query.sql,
            "parameters": query.parameters,
            "columns": cols,
            "rows": sample_rows,
            "row_count": len(sample_rows),
            "truncated": False,
            "duration_ms": 120,
            "numeric_encoding": "Fixed-point decimals are JSON strings to preserve precision.",
        }

    def execute(self, query: CompiledQuery, run_id: str) -> dict:
        if not self.private_key:
            if self.dev_mode:
                return self._simulate(query, run_id)
            raise BackendError("key_not_loaded", "Start with python run.py to unlock the private key.")

        start = monotonic()
        try:
            with (
                snowflake.connector.connect(
                    account=self.settings.snowflake_account,
                    user=self.settings.snowflake_user,
                    authenticator="SNOWFLAKE_JWT",
                    private_key=self.private_key,
                    role=self.settings.snowflake_role,
                    warehouse=self.settings.snowflake_warehouse,
                    database=self.settings.snowflake_database,
                    schema=self.settings.snowflake_schema,
                    login_timeout=30,
                    network_timeout=45,
                    enable_server_session_keep_alive_auto_detection=False,
                    session_parameters={
                        "STATEMENT_TIMEOUT_IN_SECONDS": self.settings.query_timeout_seconds,
                        "STATEMENT_QUEUED_TIMEOUT_IN_SECONDS": 15,
                        "QUERY_TAG": "datamind:" + run_id,
                    },
                ) as connection,
                connection.cursor() as cursor,
            ):
                cursor.execute("USE SECONDARY ROLES NONE")
                cursor.execute(query.sql, tuple(query.parameters))
                rows = cursor.fetchmany(query.limit + 1)
                columns = [column[0] for column in cursor.description]
                return {
                    "id": "query_1",
                    "query_id": cursor.sfqid,
                    "sql": query.sql,
                    "parameters": query.parameters,
                    "columns": columns,
                    "rows": [[json_value(value) for value in row] for row in rows[: query.limit]],
                    "row_count": min(len(rows), query.limit),
                    "truncated": len(rows) > query.limit,
                    "duration_ms": round((monotonic() - start) * 1000),
                    "numeric_encoding": "Fixed-point decimals are JSON strings to preserve precision.",
                }
        except Error as exc:
            raise BackendError(
                "snowflake_error",
                "Snowflake could not complete the query. Check credentials, role access, warehouse and timeout.",
            ) from exc
