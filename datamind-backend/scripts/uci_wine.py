"""Download, attribute, validate and load the complete real UCI Wine Quality data."""

import csv
import hashlib
import io
import json
from decimal import Decimal
from pathlib import Path
from urllib.request import urlopen
from zipfile import ZipFile

from app.compiler import IDENTIFIER
from app.config import ROOT, Settings

URL = "https://archive.ics.uci.edu/static/public/186/wine+quality.zip"
SHA256 = "3ed56667f4b828242bd732d7d1dd7f2861e54432239d7fa63877014cbb0304d4"
SOURCE = "DATAMIND_DEMO.UCI.WINE_QUALITY_SOURCE_V1"
WORKING = "DATAMIND_DEMO.UCI.WINE_QUALITY_WORKING_V1"
MARKER = "DataMind UCI Wine Quality v1; CC BY 4.0; source sha256 " + SHA256
FEATURES = [
    "fixed acidity",
    "volatile acidity",
    "citric acid",
    "residual sugar",
    "chlorides",
    "free sulfur dioxide",
    "total sulfur dioxide",
    "density",
    "pH",
    "sulphates",
    "alcohol",
]
COLUMNS = ["SAMPLE_ID", "WINE_TYPE", *[name.upper().replace(" ", "_") for name in FEATURES], "QUALITY"]


def parse_archive(path: Path) -> list[tuple]:
    rows = []
    with ZipFile(path) as archive:
        for kind in ("red", "white"):
            # Read only known members; never extract arbitrary ZIP paths.
            content = archive.read(f"winequality-{kind}.csv").decode("utf-8-sig")
            reader = csv.DictReader(io.StringIO(content), delimiter=";")
            if reader.fieldnames != [*FEATURES, "quality"]:
                raise ValueError("Unexpected UCI source columns.")
            for index, row in enumerate(reader, 1):
                values = [Decimal(row[name]) for name in FEATURES]
                quality = int(row["quality"])
                if not all(value.is_finite() for value in values) or not 0 <= quality <= 10:
                    raise ValueError("Invalid source measurements.")
                rows.append((f"{kind}-{index:05}", kind.upper(), *values, quality))
    return rows


def prepare_data(directory: Path = ROOT / "data" / "uci") -> list[tuple]:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "wine-quality.zip"
    if not path.exists():
        with urlopen(URL, timeout=60) as response:
            data = response.read(2_000_001)
        if len(data) > 2_000_000 or hashlib.sha256(data).hexdigest() != SHA256:
            raise ValueError("UCI download hash/size differs from the verified source; refusing import.")
        path.write_bytes(data)
    if hashlib.sha256(path.read_bytes()).hexdigest() != SHA256:
        raise ValueError("Cached UCI archive hash mismatch; refusing import.")
    rows = parse_archive(path)
    counts = {kind: sum(row[1] == kind for row in rows) for kind in ("RED", "WHITE")}
    if counts != {"RED": 1599, "WHITE": 4898}:
        raise ValueError("Unexpected source observation counts; refusing partial import.")
    manifest = {
        "source": "https://archive.ics.uci.edu/dataset/186/wine+quality",
        "download_url": URL,
        "doi": "https://doi.org/10.24432/C56S3T",
        "licence": "CC BY 4.0",
        "archive_sha256": SHA256,
        "citation": "Cortez, P., Cerdeira, A., Almeida, F., Matos, T., & Reis, J. (2009). Wine Quality [Dataset]. UCI Machine Learning Repository.",
        "row_count": len(rows),
        "counts_by_type": counts,
        "high_quality_threshold": 7,
        "high_quality_count": sum(row[-1] >= 7 for row in rows),
        "adaptations": [
            "Combined original red and white files",
            "Added wine_type and stable source-row ID",
            "No source observations dropped or deduplicated; all 11 features and quality retained",
        ],
    }
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    with (directory / "wine_quality.csv").open("w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(COLUMNS)
        writer.writerows(rows)
    return rows


def verify_table(cursor, table: str, expected: list[tuple]):
    if table not in (SOURCE, WORKING):
        raise ValueError("Only the fixed UCI tables can be verified.")
    cursor.execute(f"SELECT {', '.join(COLUMNS)} FROM {table} ORDER BY SAMPLE_ID")
    actual = [tuple(row) for row in cursor.fetchall()]
    if actual != sorted(expected, key=lambda row: row[0]):
        raise RuntimeError(
            "Snowflake table differs from original UCI observations; refusing to overwrite it."
        )


def provision(connection, settings: Settings, rows: list[tuple]) -> dict:
    if not IDENTIFIER.fullmatch(settings.snowflake_role):
        raise ValueError("Reader role must be a simple identifier.")
    query_ids = []
    with connection.cursor() as cursor:
        for sql in [
            "CREATE DATABASE IF NOT EXISTS DATAMIND_DEMO",
            "CREATE SCHEMA IF NOT EXISTS DATAMIND_DEMO.UCI",
        ]:
            cursor.execute(sql)
            query_ids.append(cursor.sfqid)
        definitions = ["SAMPLE_ID VARCHAR NOT NULL", "WINE_TYPE VARCHAR NOT NULL"]
        definitions += [f"{name} NUMBER(38,17) NOT NULL" for name in COLUMNS[2:-1]]
        definitions += ["QUALITY INTEGER NOT NULL"]
        for table in (SOURCE, WORKING):
            cursor.execute(
                f"CREATE TABLE IF NOT EXISTS {table} ({', '.join(definitions)}) COMMENT = '{MARKER}'"
            )
            query_ids.append(cursor.sfqid)
            cursor.execute(
                """SELECT COMMENT FROM DATAMIND_DEMO.INFORMATION_SCHEMA.TABLES
                              WHERE TABLE_SCHEMA = 'UCI' AND TABLE_NAME = %s""",
                (table.split(".")[-1],),
            )
            entry = cursor.fetchone()
            if not entry or entry[0] != MARKER:
                raise RuntimeError("Existing table is not marked as this UCI dataset; refusing to edit it.")
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            if cursor.fetchone()[0] == 0:
                cursor.execute("BEGIN")
                try:
                    if table == SOURCE:
                        sql = f"INSERT INTO {SOURCE} ({', '.join(COLUMNS)}) VALUES ({', '.join(['%s'] * len(COLUMNS))})"
                        for start in range(0, len(rows), 500):
                            cursor.executemany(sql, rows[start : start + 500])
                            query_ids.append(cursor.sfqid)
                    else:
                        cursor.execute(f"INSERT INTO {WORKING} SELECT {', '.join(COLUMNS)} FROM {SOURCE}")
                        query_ids.append(cursor.sfqid)
                    verify_table(cursor, table, rows)
                    cursor.execute("COMMIT")
                except Exception:
                    cursor.execute("ROLLBACK")
                    raise
            else:
                verify_table(cursor, table, rows)
        for sql in [
            f"GRANT USAGE ON DATABASE DATAMIND_DEMO TO ROLE {settings.snowflake_role}",
            f"GRANT USAGE ON SCHEMA DATAMIND_DEMO.UCI TO ROLE {settings.snowflake_role}",
            f"GRANT SELECT ON TABLE {WORKING} TO ROLE {settings.snowflake_role}",
        ]:
            cursor.execute(sql)
            query_ids.append(cursor.sfqid)
    return {"source_table": SOURCE, "working_table": WORKING, "row_count": len(rows), "query_ids": query_ids}


if __name__ == "__main__":
    records = prepare_data()
    print(
        f"Verified {len(records)} real UCI observations; {sum(row[-1] >= 7 for row in records)} quality >= 7."
    )
