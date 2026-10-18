"""Download, attribute, validate and load real World Bank WDI indicators (CC BY 4.0)."""

import csv
import hashlib
import json
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from urllib.request import urlopen

from app.compiler import IDENTIFIER
from app.config import ROOT, Settings

API = "https://api.worldbank.org/v2"
FIRST_YEAR, LAST_YEAR = 1990, 2024
TABLE = "DATAMIND_DEMO.WORLDBANK.WDI_COUNTRY_YEAR_V1"
MARKER = "DataMind World Bank WDI v1; CC BY 4.0; economies only, 1990-2024"
SCALE = Decimal("0.000001")
# (World Bank indicator code, column name). Labels and units come from the API and go in the manifest.
INDICATORS = [
    ("SP.POP.TOTL", "POPULATION"),
    ("NY.GDP.MKTP.CD", "GDP_USD"),
    ("NY.GDP.PCAP.CD", "GDP_PER_CAPITA_USD"),
    ("NY.GDP.MKTP.KD.ZG", "GDP_GROWTH_PCT"),
    ("FP.CPI.TOTL.ZG", "INFLATION_PCT"),
    ("SL.UEM.TOTL.ZS", "UNEMPLOYMENT_PCT"),
    ("SP.DYN.LE00.IN", "LIFE_EXPECTANCY_YEARS"),
    ("SP.DYN.IMRT.IN", "INFANT_MORTALITY_PER_1000"),
    ("SP.DYN.TFRT.IN", "FERTILITY_RATE"),
    ("SP.URB.TOTL.IN.ZS", "URBAN_POPULATION_PCT"),
    ("IT.NET.USER.ZS", "INTERNET_USERS_PCT"),
    ("EG.ELC.ACCS.ZS", "ELECTRICITY_ACCESS_PCT"),
    ("EG.FEC.RNEW.ZS", "RENEWABLE_ENERGY_PCT"),
    ("EN.GHG.CO2.PC.CE.AR5", "CO2_PER_CAPITA_TONNES"),
    ("SH.XPD.CHEX.GD.ZS", "HEALTH_SPENDING_PCT_GDP"),
    ("SE.XPD.TOTL.GD.ZS", "EDUCATION_SPENDING_PCT_GDP"),
    ("NE.TRD.GNFS.ZS", "TRADE_PCT_GDP"),
    ("SE.ADT.LITR.ZS", "ADULT_LITERACY_PCT"),
]
KEYS = ["COUNTRY_CODE", "COUNTRY_NAME", "REGION", "INCOME_GROUP", "YEAR"]
COLUMNS = [*KEYS, *[column for _, column in INDICATORS]]


def fetch(path: str) -> bytes:
    with urlopen(f"{API}/{path}", timeout=60) as response:
        data = response.read(20_000_001)
    if len(data) > 20_000_000:
        raise ValueError("World Bank response larger than expected; refusing import.")
    return data


def single_page(raw: bytes) -> tuple[dict, list[dict]]:
    payload = json.loads(raw)
    if not isinstance(payload, list) or len(payload) != 2 or not isinstance(payload[1], list):
        raise ValueError(f"Unexpected World Bank API response: {str(payload)[:200]}")
    meta, records = payload
    if int(meta["pages"]) != 1:
        raise ValueError("World Bank response was paginated; refusing a partial import.")
    return meta, records


def to_decimal(value) -> Decimal | None:
    if value is None:
        return None
    number = Decimal(repr(value))
    if not number.is_finite():
        raise ValueError("Non-finite indicator value.")
    return number.quantize(SCALE, rounding=ROUND_HALF_UP)


def build_rows(countries_raw: bytes, indicator_raw: dict[str, bytes]) -> list[tuple]:
    """One row per economy and year; World Bank aggregates (regions, income groups) are excluded."""
    _, countries = single_page(countries_raw)
    economies = {
        c["id"]: (c["name"], c["region"]["value"].strip(), c["incomeLevel"]["value"].strip())
        for c in countries
        if c["region"]["value"].strip() != "Aggregates"
    }
    values: dict[tuple[str, int], dict[str, Decimal | None]] = {}
    for code, column in INDICATORS:
        _, records = single_page(indicator_raw[code])
        for record in records:
            if record["indicator"]["id"] != code:
                raise ValueError(f"Response for {code} contained another indicator.")
            iso3, year = record["countryiso3code"], int(record["date"])
            if iso3 in economies and FIRST_YEAR <= year <= LAST_YEAR:
                values.setdefault((iso3, year), {})[column] = to_decimal(record["value"])
    return [
        (iso3, name, region, income, year, *[values.get((iso3, year), {}).get(c) for _, c in INDICATORS])
        for iso3, (name, region, income) in sorted(economies.items())
        for year in range(FIRST_YEAR, LAST_YEAR + 1)
    ]


def prepare_data(directory: Path = ROOT / "data" / "worldbank") -> list[tuple]:
    """Download once into an ignored snapshot, then always rebuild rows from that exact snapshot."""
    raw_dir = directory / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = directory / "manifest.json"
    sources = {"countries": "country?format=json&per_page=400"}
    sources |= {
        code: f"country/all/indicator/{code}?format=json&per_page=20000&date={FIRST_YEAR}:{LAST_YEAR}"
        for code, _ in INDICATORS
    }
    recorded = json.loads(manifest_path.read_text())["sha256"] if manifest_path.exists() else {}
    raw, hashes = {}, {}
    for name, path in sources.items():
        file = raw_dir / f"{name}.json"
        if not file.exists():
            file.write_bytes(fetch(path))
        raw[name] = file.read_bytes()
        hashes[name] = hashlib.sha256(raw[name]).hexdigest()
        if name in recorded and recorded[name] != hashes[name]:
            raise ValueError(f"Cached World Bank snapshot {name} changed; refusing import.")
    rows = build_rows(raw.pop("countries"), raw)
    indicator_meta = {}
    for code, column in INDICATORS:
        meta, records = single_page(raw[code])
        indicator_meta[column] = {
            "code": code,
            "label": records[0]["indicator"]["value"] if records else None,
            "source_last_updated": meta.get("lastupdated"),
            "non_null_rows": sum(row[COLUMNS.index(column)] is not None for row in rows),
        }
    manifest = {
        "source": "World Bank, World Development Indicators",
        "url": "https://datacatalog.worldbank.org/search/dataset/0037712",
        "api": API,
        "licence": "CC BY 4.0",
        "citation": "World Bank (2026). World Development Indicators. Accessed via the World Bank API.",
        "years": [FIRST_YEAR, LAST_YEAR],
        "economies": len({row[0] for row in rows}),
        "row_count": len(rows),
        "indicators": indicator_meta,
        "sha256": hashes,
        "adaptations": [
            "Kept economies only; dropped World Bank aggregates (World, regions, income groups)",
            "One row per economy and year, one column per indicator",
            "Values rounded half-up to 6 decimal places; missing values kept as NULL, never filled",
        ],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    with (directory / "wdi_country_year.csv").open("w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(COLUMNS)
        writer.writerows(rows)
    return rows


def verify_table(cursor, expected: list[tuple]) -> None:
    cursor.execute(f"SELECT {', '.join(COLUMNS)} FROM {TABLE} ORDER BY COUNTRY_CODE, YEAR")
    if [tuple(row) for row in cursor.fetchall()] != expected:
        raise RuntimeError("Snowflake table differs from the World Bank snapshot; refusing to overwrite it.")


def provision(connection, settings: Settings, rows: list[tuple]) -> dict:
    if not IDENTIFIER.fullmatch(settings.snowflake_role):
        raise ValueError("Reader role must be a simple identifier.")
    definitions = [
        "COUNTRY_CODE VARCHAR(3) NOT NULL",
        "COUNTRY_NAME VARCHAR NOT NULL",
        "REGION VARCHAR NOT NULL",
        "INCOME_GROUP VARCHAR NOT NULL",
        "YEAR INTEGER NOT NULL",
        *[f"{column} NUMBER(38, 6)" for _, column in INDICATORS],
    ]
    query_ids = []
    with connection.cursor() as cursor:
        for sql in [
            "CREATE DATABASE IF NOT EXISTS DATAMIND_DEMO",
            "CREATE SCHEMA IF NOT EXISTS DATAMIND_DEMO.WORLDBANK",
            f"CREATE TABLE IF NOT EXISTS {TABLE} ({', '.join(definitions)}) COMMENT = '{MARKER}'",
        ]:
            cursor.execute(sql)
            query_ids.append(cursor.sfqid)
        cursor.execute(
            """SELECT COMMENT FROM DATAMIND_DEMO.INFORMATION_SCHEMA.TABLES
               WHERE TABLE_SCHEMA = 'WORLDBANK' AND TABLE_NAME = 'WDI_COUNTRY_YEAR_V1'"""
        )
        entry = cursor.fetchone()
        if not entry or entry[0] != MARKER:
            raise RuntimeError("Existing table is not marked as this WDI dataset; refusing to edit it.")
        cursor.execute(f"SELECT COUNT(*) FROM {TABLE}")
        if cursor.fetchone()[0] == 0:
            cursor.execute("BEGIN")
            try:
                sql = (
                    f"INSERT INTO {TABLE} ({', '.join(COLUMNS)}) VALUES ({', '.join(['%s'] * len(COLUMNS))})"
                )
                for start in range(0, len(rows), 500):
                    cursor.executemany(sql, rows[start : start + 500])
                    query_ids.append(cursor.sfqid)
                verify_table(cursor, rows)
                cursor.execute("COMMIT")
            except Exception:
                cursor.execute("ROLLBACK")
                raise
        else:
            verify_table(cursor, rows)
        for sql in [
            f"GRANT USAGE ON DATABASE DATAMIND_DEMO TO ROLE {settings.snowflake_role}",
            f"GRANT USAGE ON SCHEMA DATAMIND_DEMO.WORLDBANK TO ROLE {settings.snowflake_role}",
            f"GRANT SELECT ON TABLE {TABLE} TO ROLE {settings.snowflake_role}",
        ]:
            cursor.execute(sql)
            query_ids.append(cursor.sfqid)
    return {"table": TABLE, "row_count": len(rows), "query_ids": query_ids}


if __name__ == "__main__":
    records = prepare_data()
    print(f"Verified {len(records)} economy-year rows for {len({r[0] for r in records})} economies.")
