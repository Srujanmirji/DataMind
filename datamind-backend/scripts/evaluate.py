"""Evaluate held-out questions against independent SQL/source-data oracles."""

import hashlib
import json
import sys
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation, localcontext
from pathlib import Path
from uuid import uuid4

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from fastapi.testclient import TestClient

from app.compiler import CompiledQuery
from app.config import ROOT, Settings
from app.warehouse import Warehouse


def wdi_oracle(name):
    """Independent arithmetic on the raw World Bank API snapshot, without the loader's row builder."""
    raw = ROOT / "data" / "worldbank" / "raw"
    countries = {
        c["id"]: c
        for c in json.loads((raw / "countries.json").read_text())[1]
        if c["region"]["value"] != "Aggregates"
    }

    def series(code):
        values = {}
        for record in json.loads((raw / f"{code}.json").read_text())[1]:
            if record["countryiso3code"] in countries and record["value"] is not None:
                number = Decimal(repr(record["value"])).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
                values[(record["countryiso3code"], int(record["date"]))] = number
        return values

    def mean(values):
        values = list(values)
        return sum(values) / Decimal(len(values))

    def comparison(target, reference):
        difference = target - reference
        return {
            "columns": ["target_value", "reference_value", "difference", "percent_change"],
            "rows": [[target, reference, difference, difference * 100 / reference]],
        }

    def upper(iso3, key):
        return (countries[iso3][key] if key == "name" else countries[iso3][key]["value"]).strip().upper()

    with localcontext() as context:
        context.prec = 50
        if name == "wdi_three_country_gdp_per_capita_2022":
            gdp = series("NY.GDP.PCAP.CD")
            return {
                "columns": ["country", "gdp_per_capita_usd"],
                "rows": [[upper(iso, "name"), gdp[(iso, 2022)]] for iso in ("IND", "BRA", "CHN")],
            }
        if name == "wdi_unemployment_over_8_5_2022":
            unemployment = series("SL.UEM.TOTL.ZS")
            return {
                "columns": ["country", "unemployment_pct"],
                "rows": [
                    [upper(iso, "name"), value]
                    for (iso, year), value in unemployment.items()
                    if year == 2022 and value > Decimal("8.5")
                ],
            }
        if name == "wdi_india_latest_gdp":
            gdp = series("NY.GDP.MKTP.CD")
            latest = max(year for iso, year in gdp if iso == "IND")
            return {"columns": ["year", "total_gdp_usd"], "rows": [[latest, gdp[("IND", latest)]]]}
        if name == "wdi_india_gdp_population_trend_2019_2023":
            gdp, population = series("NY.GDP.MKTP.CD"), series("SP.POP.TOTL")
            return {
                "columns": ["year", "total_gdp_usd", "total_population"],
                "rows": [[year, gdp[("IND", year)], population[("IND", year)]] for year in range(2019, 2024)],
            }
        if name == "wdi_india_gdp_life_expectancy_2022":
            return {
                "columns": ["total_gdp_usd", "life_expectancy_years"],
                "rows": [[series("NY.GDP.MKTP.CD")[("IND", 2022)], series("SP.DYN.LE00.IN")[("IND", 2022)]]],
            }
        if name == "wdi_lowest10_total_gdp_2023":
            gdp = series("NY.GDP.MKTP.CD")
            ranked = sorted(((v, upper(iso, "name")) for (iso, year), v in gdp.items() if year == 2023))[:10]
            return {
                "columns": ["country", "total_gdp_usd"],
                "rows": [[name, value] for value, name in ranked],
            }
        if name == "wdi_top5_gdp_per_capita_2023":
            gdp = series("NY.GDP.PCAP.CD")
            ranked = sorted(((v, iso) for (iso, year), v in gdp.items() if year == 2023), reverse=True)[:5]
            return {
                "columns": ["country", "gdp_per_capita_usd"],
                "rows": [[upper(iso, "name"), value] for value, iso in ranked],
            }
        if name == "wdi_india_life_expectancy_2022":
            return {"columns": ["life_expectancy_years"], "rows": [[series("SP.DYN.LE00.IN")[("IND", 2022)]]]}
        if name == "wdi_india_internet_2015_2023":
            internet = series("IT.NET.USER.ZS")
            return comparison(internet[("IND", 2023)], internet[("IND", 2015)])
        if name == "wdi_china_vs_india_gdp_per_capita_2023":
            gdp = series("NY.GDP.PCAP.CD")
            return comparison(gdp[("CHN", 2023)], gdp[("IND", 2023)])
        if name == "wdi_india_population_share_2023":
            population = series("SP.POP.TOTL")
            target = population[("IND", 2023)]
            reference = sum(v for (_, year), v in population.items() if year == 2023)
            return {
                "columns": ["target_value", "reference_value", "share_percent"],
                "rows": [[target, reference, target * 100 / reference]],
            }
        if name == "wdi_regions_life_expectancy_2022":
            life = {iso: v for (iso, year), v in series("SP.DYN.LE00.IN").items() if year == 2022}
            overall = mean(life.values())
            regions = {upper(iso, "region") for iso in life}
            rows = []
            for region in sorted(regions):
                value = mean(v for iso, v in life.items() if upper(iso, "region") == region)
                if value > overall:
                    rows.append([region, value, overall, value - overall])
            return {
                "columns": ["region", "life_expectancy_years", "overall_average", "difference"],
                "rows": rows,
            }
        if name == "wdi_gdp_by_income_group_2023":
            gdp = {iso: v for (iso, year), v in series("NY.GDP.MKTP.CD").items() if year == 2023}
            groups = sorted({upper(iso, "incomeLevel") for iso in countries})
            return {
                "columns": ["income_group", "total_gdp_usd"],
                "rows": [
                    [g, sum(v for iso, v in gdp.items() if upper(iso, "incomeLevel") == g)] for g in groups
                ],
            }
        if name == "wdi_ssa_co2_2020":
            co2 = series("EN.GHG.CO2.PC.CE.AR5")
            scope = [
                v
                for (iso, year), v in co2.items()
                if year == 2020 and upper(iso, "region") == "SUB-SAHARAN AFRICA"
            ]
            return {"columns": ["co2_per_capita_tonnes"], "rows": [[mean(scope)]]}
    raise ValueError("Unknown World Bank oracle.")


def tables_equal(actual, expected):
    if not set(expected["columns"]).issubset(actual["columns"]):
        return False
    # Compare by column name and group label, not presentation order.
    columns = expected["columns"]
    actual_rows = [[row[actual["columns"].index(column)] for column in columns] for row in actual["rows"]]
    if len(actual_rows) != len(expected["rows"]):
        return False

    def equal_row(observed, wanted):
        for a, e in zip(observed, wanted, strict=True):
            if e is None:
                if a is not None:
                    return False
            elif isinstance(e, (Decimal, int, float)):
                try:
                    difference = abs(Decimal(str(a)) - Decimal(str(e)))
                    if not difference.is_finite() or difference > Decimal("0.00001"):
                        return False
                except (InvalidOperation, ValueError, TypeError):
                    return False
            elif a != e:
                return False
        return True

    remaining = list(actual_rows)
    for wanted in expected["rows"]:
        match = next((index for index, observed in enumerate(remaining) if equal_row(observed, wanted)), None)
        if match is None:
            return False
        remaining.pop(match)
    return True


def _numeric(value):
    try:
        Decimal(value)
        return True
    except (InvalidOperation, TypeError, ValueError):
        return False


def verify_lineage(body, live):
    evidence = {item["id"]: item for item in body["evidence"]}
    query_ids = [item["query_id"] for item in evidence.values() if item.get("kind") != "calculation"]
    if live:
        assert all(query_ids) and len(set(query_ids)) == len(query_ids)
    for claim in body["claims"]:
        item = evidence[claim["evidence_id"]]
        assert claim["value"] == item["rows"][claim["row_index"]][item["columns"].index(claim["column"])]
    for item in evidence.values():
        for inputs in item.get("inputs", []):
            for reference in inputs.values():
                source = evidence[reference["evidence_id"]]
                assert reference["column"] in source["columns"]
                assert 0 <= reference["row_index"] < len(source["rows"])


def run_evaluation(app, settings: Settings, private_key: bytes | None, dataset_id: str | None = None):
    cases = json.loads((ROOT / "evaluation/questions.json").read_text())["cases"]
    if dataset_id:
        cases = [case for case in cases if case["dataset_id"] == dataset_id]
    seen_cases = set()
    for previous in (ROOT / "data/evaluations").glob("*/results.json"):
        previous_report = json.loads(previous.read_text())
        seen_cases.update(case["id"] for case in previous_report.get("cases", []))
    planner_report = ROOT / "data/planner-evaluation/results.json"
    if planner_report.exists():
        seen_cases.update(case["id"] for case in json.loads(planner_report.read_text()).get("cases", []))
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + str(uuid4())[:8]
    folder = ROOT / "data" / "evaluations" / stamp
    folder.mkdir(parents=True)
    oracle_reader = Warehouse(settings, private_key)
    report = {
        "mode": "Live Gemma + live Snowflake",
        "method": "Developer-authored cases; separately marked fresh cases are first-run holdouts. No oracle results enter prompts. Not an external blind benchmark.",
        "model": settings.model_name,
        "planner_sha256": hashlib.sha256((ROOT / "app/planner.py").read_bytes()).hexdigest(),
        "cases": [],
        "created_at": stamp,
    }
    headers = {"X-API-Key": settings.api_key.get_secret_value()}
    print(
        f"Starting {len(cases)} checks with {settings.model_name}. This can take several minutes; keep this terminal open.",
        flush=True,
    )
    with TestClient(app) as client:
        for case in cases:
            print(f"RUN {len(report['cases']) + 1}/{len(cases)} {case['id']}", flush=True)
            entry = {
                "id": case["id"],
                "dataset_id": case["dataset_id"],
                "question": case["question"],
                "passed": False,
                "suite": "fresh_holdout"
                if case.get("suite") == "fresh_holdout" and case["id"] not in seen_cases
                else "regression",
            }
            try:
                expected = None
                if case.get("oracle_wdi"):
                    expected = wdi_oracle(case["oracle_wdi"])
                elif case.get("oracle_sql"):
                    raw = oracle_reader.execute(
                        CompiledQuery(case["oracle_sql"], [], 100), "oracle:" + case["id"]
                    )
                    raw["columns"] = [column.lower() for column in raw["columns"]]
                    # Convert numeric oracle strings back to Decimal for tolerant numeric comparison.
                    expected = {
                        "columns": raw["columns"],
                        "rows": [
                            [
                                Decimal(value) if isinstance(value, str) and _numeric(value) else value
                                for value in row
                            ]
                            for row in raw["rows"]
                        ],
                    }
                    entry["independent_query"] = raw
                response = client.post(
                    "/questions",
                    headers=headers,
                    json={"question": case["question"], "dataset_id": case["dataset_id"]},
                )
                body = response.json()
                (folder / (case["id"] + ".json")).write_text(json.dumps(body, indent=2) + "\n")
                entry.update(http=response.status_code, observed_status=body.get("status"))
                assert response.status_code == 200, body.get("error", body)
                assert body["status"] == case["expected_status"], "Unexpected response state"
                if expected is not None:
                    assert body["plan"]["analysis"] == case["analysis"], "Wrong analysis mode"
                    output = body["evidence"][-1]
                    entry["extra_context_columns"] = sorted(set(output["columns"]) - set(expected["columns"]))
                    assert tables_equal(output, expected), (
                        "Values/groups differ from independent ground truth"
                    )
                    verify_lineage(body, live=True)
                    entry["expected"] = expected
                    entry["query_ids"] = [
                        e["query_id"] for e in body["evidence"] if e.get("kind") != "calculation"
                    ]
                else:
                    assert body["evidence"] == [], "Unsupported/ambiguous question executed a query"
                assert client.get("/runs/" + body["run_id"], headers=headers).json() == body
                entry["passed"] = True
            except Exception as exc:  # noqa: BLE001 -- each failure is persisted and printed, never treated as a pass.
                entry["failure"] = str(exc)[:1000]
            report["cases"].append(entry)
            print(f"{'PASS' if entry['passed'] else 'FAIL'} {case['id']}", flush=True)
            (folder / "results.json").write_text(json.dumps(report, indent=2, default=str) + "\n")
    report["passed"] = sum(case["passed"] for case in report["cases"])
    report["total"] = len(cases)
    (folder / "results.json").write_text(json.dumps(report, indent=2, default=str) + "\n")
    (ROOT / "data/evaluations/latest.json").write_text(
        json.dumps(
            {
                "folder": str(folder),
                "mode": report["mode"],
                "passed": report["passed"],
                "total": report["total"],
            },
            indent=2,
        )
        + "\n"
    )
    lines = [
        "# Held-out question evaluation",
        "",
        report["mode"],
        "",
        report["method"],
        "",
        f"Passed: **{report['passed']}/{report['total']}**",
        "",
        "| Question | Result |",
        "|---|---|",
    ]
    lines += [
        f"| {case['question']} | {'PASS' if case['passed'] else 'FAIL: ' + case['failure']} |"
        for case in report["cases"]
    ]
    (folder / "REPORT.md").write_text("\n".join(lines) + "\n")
    print(f"Evaluation: {report['passed']}/{report['total']}; report {folder / 'REPORT.md'}", flush=True)
    return report
