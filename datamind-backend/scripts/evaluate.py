"""Evaluate held-out questions against independent SQL/source-data oracles."""

import hashlib
import json
import sqlite3
import sys
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path
from uuid import uuid4

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from fastapi.testclient import TestClient

from app.compiler import CompiledQuery
from app.config import ROOT, Settings
from app.datasets import load_datasets
from app.main import create_app
from app.planner import Planner
from app.service import QuestionService
from app.warehouse import Warehouse
from scripts.uci_wine import prepare_data


def python_oracle(name, records):
    """Independent arithmetic on the original downloaded UCI observations."""
    red = [row for row in records if row[1] == "RED"]
    white = [row for row in records if row[1] == "WHITE"]

    def mean(rows, index):
        return sum(Decimal(row[index]) for row in rows) / Decimal(len(rows))

    def comparison(target, reference):
        difference = target - reference
        percent = difference * 100 / reference if reference else None
        return {
            "columns": ["target_value", "reference_value", "difference", "percent_change"],
            "rows": [[target, reference, difference, percent]],
        }

    with localcontext() as context:
        context.prec = 50
        if name == "fresh_white_alcohol_cohorts":
            return comparison(
                mean([row for row in white if row[-1] == 3], -2),
                mean([row for row in white if row[-1] == 7], -2),
            )
        if name == "fresh_sugar_comparison":
            return comparison(mean(white, 5), mean(red, 5))
        if name == "fresh_red_low_share":
            target = sum(row[-1] <= 5 for row in red)
            return {
                "columns": ["target_value", "reference_value", "share_percent"],
                "rows": [[target, len(red), Decimal(target) * 100 / Decimal(len(red))]],
            }
        if name == "fresh_score_six":
            return comparison(
                Decimal(sum(row[-1] == 6 for row in white)), Decimal(sum(row[-1] == 6 for row in red))
            )
        if name == "quality_comparison":
            return comparison(mean(white, -1), mean(red, -1))
        if name == "white_eight_share":
            target = sum(row[-1] >= 8 for row in white)
            return {
                "columns": ["target_value", "reference_value", "share_percent"],
                "rows": [[target, len(white), Decimal(target) * 100 / Decimal(len(white))]],
            }
        if name == "population_sugar":
            scope = [row for row in records if row[-1] >= 5]
            population = mean(scope, 5)
            groups = []
            for kind in ("RED", "WHITE"):
                value = mean([row for row in scope if row[1] == kind], 5)
                if value > population:
                    groups.append([kind, value, population, value - population])
            return {
                "columns": ["wine_type", "average_residual_sugar", "overall_average", "difference"],
                "rows": groups,
            }
        if name == "eight_count_comparison":
            return comparison(
                Decimal(sum(row[-1] >= 8 for row in red)), Decimal(sum(row[-1] >= 8 for row in white))
            )
        if name == "zero_reference":
            return comparison(
                Decimal(sum(row[-1] == 9 for row in white)), Decimal(sum(row[-1] == 10 for row in white))
            )
        if name == "filtered_alcohol":
            selected = [row for row in white if row[-1] in (8, 9)]
            return {
                "columns": ["sample_count", "average_alcohol"],
                "rows": [[len(selected), mean(selected, -2)]],
            }
    raise ValueError("Unknown independent oracle.")


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


def run_evaluation(app, settings: Settings, private_key: bytes | None, local_wine=False):
    cases = json.loads((ROOT / "evaluation/questions.json").read_text())["cases"]
    if local_wine:
        cases = [case for case in cases if case["dataset_id"] == "uci_wine_quality"]
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
    records = prepare_data()
    oracle_reader = Warehouse(settings, private_key)
    report = {
        "mode": "local UCI SQLite + live Gemma (NOT Snowflake)"
        if local_wine
        else "Live Gemma + live Snowflake",
        "method": "Developer-authored cases: wine regression cases were used during development; separately marked fresh cases are first-run holdouts. No oracle results enter prompts. Not an external blind benchmark.",
        "model": settings.ollama_model,
        "planner_sha256": hashlib.sha256((ROOT / "app/planner.py").read_bytes()).hexdigest(),
        "cases": [],
        "created_at": stamp,
    }
    headers = {"X-API-Key": settings.api_key.get_secret_value()}
    print(
        f"Starting {len(cases)} checks with {settings.ollama_model}. This can take several minutes; keep this terminal open.",
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
                if case.get("oracle_python"):
                    expected = python_oracle(case["oracle_python"], records)
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
                    verify_lineage(body, live=not local_wine)
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


class LocalWineReader:
    """Explicit offline evaluation adapter. Never masquerades as Snowflake evidence."""

    def __init__(self, records):
        self.connection = sqlite3.connect(":memory:", check_same_thread=False)
        self.connection.execute(
            "CREATE TABLE wines (WINE_TYPE TEXT, QUALITY INTEGER, ALCOHOL REAL, RESIDUAL_SUGAR REAL)"
        )
        self.connection.executemany(
            "INSERT INTO wines VALUES (?,?,?,?)",
            [(row[1], row[-1], float(row[-2]), float(row[5])) for row in records],
        )

    def execute(self, query, run_id):
        sql = query.sql.replace("DATAMIND_DEMO.UCI.WINE_QUALITY_WORKING_V1", "wines").replace("%s", "?")
        cursor = self.connection.execute(sql, query.parameters)
        rows = cursor.fetchmany(query.limit + 1)
        return {
            "id": "query_1",
            "query_id": None,
            "engine": "local SQLite evaluation only",
            "sql": sql,
            "submitted_snowflake_sql": query.sql,
            "parameters": query.parameters,
            "columns": [column[0] for column in cursor.description],
            "rows": [list(row) for row in rows[: query.limit]],
            "truncated": len(rows) > query.limit,
            "row_count": min(len(rows), query.limit),
        }


def main():
    settings = Settings().model_copy(update={"history_path": ROOT / "data/local-evaluation.sqlite3"})
    dataset = load_datasets(settings)["uci_wine_quality"]
    reader = LocalWineReader(prepare_data())
    try:
        service = QuestionService(settings, dataset, Planner(settings, dataset), reader)
        report = run_evaluation(create_app(settings, service=service), settings, None, local_wine=True)
        raise SystemExit(0 if report["passed"] == report["total"] else 1)
    finally:
        reader.connection.close()


if __name__ == "__main__":
    main()
