"""Explicit admin-only UCI setup and reversible data-change proof; never an API route."""

import json
import logging
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import snowflake.connector
from fastapi.testclient import TestClient

from app.config import ROOT, Settings
from scripts.uci_wine import SOURCE, WORKING, prepare_data, verify_table

logger = logging.getLogger(__name__)
TABLE = WORKING
QUESTION = "How many wine samples have a quality score of at least 7?"
DELTA = 1


def begin_report(output: Path | None = None):
    output = output or ROOT / "data" / "change-demo"
    output.mkdir(parents=True, exist_ok=True)
    (output / "REPORT.md").write_text(
        "# UCI data-change proof\n\nCurrent run: **starting**; not yet verified.\n"
    )
    (output / "proof.json").write_text(json.dumps({"status": "starting", "restored": False}) + "\n")


def record_failure(error: BaseException, output: Path | None = None):
    output = output or ROOT / "data" / "change-demo"
    try:
        path = output / "proof.json"
        report = json.loads(path.read_text()) if path.exists() else {}
        report["status"] = "failed"
        report["error_type"] = type(error).__name__
        report["note"] = "This run did not complete; inspect mutation/restoration evidence before retrying."
        (output / "REPORT.md").write_text(
            "# UCI data-change proof\n\nCurrent run: **failed**. See proof.json.\n"
        )
        path.write_text(json.dumps(report, indent=2) + "\n")
    except (OSError, ValueError):
        logger.error(
            "Could not persist failed demo status; do not treat existing artifacts as current proof."
        )


@contextmanager
def admin_session(settings: Settings, private_key: bytes):
    """Keep admin authority in this explicit setup command, outside normal requests."""
    with snowflake.connector.connect(
        account=settings.snowflake_account,
        user=settings.snowflake_user,
        authenticator="SNOWFLAKE_JWT",
        private_key=private_key,
        role="ACCOUNTADMIN",
        warehouse=settings.snowflake_warehouse,
        login_timeout=30,
        network_timeout=45,
        autocommit=True,
        enable_server_session_keep_alive_auto_detection=False,
        session_parameters={"QUERY_TAG": "datamind:uci-demo-setup", "STATEMENT_TIMEOUT_IN_SECONDS": 30},
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute("USE SECONDARY ROLES NONE")
        yield connection


def count_from_answer(response: dict) -> int:
    if response.get("status") != "answered":
        raise RuntimeError("The wine question did not produce an answered response.")
    plan = response["plan"]
    if (
        plan["metrics"] != ["sample_count"]
        or plan["dimensions"]
        or plan["filters"] != [{"field": "quality", "operator": "gte", "values": [7]}]
    ):
        raise RuntimeError("The demonstration needs a sample_count plan filtered to quality >= 7.")
    evidence = response["evidence"][0]
    if len(evidence["rows"]) != 1 or not evidence["query_id"] or evidence["truncated"]:
        raise RuntimeError("Expected one verified total with a Snowflake query ID.")
    return int(evidence["rows"][0][evidence["columns"].index("sample_count")])


def prove_change(app, connection, settings: Settings, output: Path | None = None) -> dict:
    try:
        return _prove_change(app, connection, settings, output)
    except BaseException as exc:
        # Includes user interruption: cleanup inside _prove_change still runs first.
        record_failure(exc, output)
        raise


def _prove_change(app, connection, settings: Settings, output: Path | None = None) -> dict:
    output = output or ROOT / "data" / "change-demo"
    output.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "status": "running",
        "created_at": datetime.now(UTC).isoformat(),
        "dataset_id": "uci_wine_quality",
        "question": QUESTION,
        "table": TABLE,
        "expected_count_delta": DELTA,
        "restored": False,
    }
    report_path = output / "proof.json"

    def save():
        report_path.write_text(json.dumps(report, indent=2) + "\n")
        (output / "REPORT.md").write_text(
            "# Data-change proof\n\nCurrent run status: **" + report["status"] + "**.\n\n"
            "Inspect proof.json for this run's stage and restoration evidence.\n"
        )

    # Invalidate any previous successful report before doing setup or a new query.
    save()

    headers = {"X-API-Key": settings.api_key.get_secret_value()}
    with TestClient(app) as client, connection.cursor() as cursor:

        def ask() -> dict:
            response = client.post(
                "/questions", headers=headers, json={"question": QUESTION, "dataset_id": "uci_wine_quality"}
            )
            if response.status_code != 200:
                raise RuntimeError("API request failed; inspect the backend and rerun the demo.")
            body = response.json()
            count_from_answer(body)
            if client.get("/runs/" + body["run_id"], headers=headers).json() != body:
                raise RuntimeError("Saved run evidence did not match the answer.")
            return body

        # Compare the preserved source table and working copy against every original observation.
        records = prepare_data()
        verify_table(cursor, SOURCE, records)
        verify_table(cursor, WORKING, records)
        expected = sum(row[-1] >= 7 for row in records)
        cursor.execute(f"SELECT COUNT_IF(QUALITY >= 7), COUNT(*) FROM {TABLE}")
        ground_count, count = cursor.fetchone()
        if ground_count != expected or count != len(records):
            raise RuntimeError("Working copy differs from its UCI baseline; no mutation performed.")
        report["ground_truth_before"] = {
            "high_quality_count": ground_count,
            "sample_count": count,
            "query_id": cursor.sfqid,
        }
        report["source"] = "https://archive.ics.uci.edu/dataset/186/wine+quality"
        report["licence"] = "CC BY 4.0"
        report["source_table"] = SOURCE
        target = next(row for row in records if row[-1] == 6)
        target_id = target[0]
        original, changed = 6, 7
        cursor.execute(f"SELECT QUALITY FROM {TABLE} WHERE SAMPLE_ID = %s", (target_id,))
        if cursor.fetchall() != [(original,)]:
            raise RuntimeError("Expected one unchanged source row; no mutation performed.")
        report["target_sample_id"] = target_id
        report["original_quality"] = original
        report["changed_quality"] = changed
        report["before"] = ask()
        if count_from_answer(report["before"]) != expected:
            raise RuntimeError(
                "API total differs from independently computed ground truth; no mutation performed."
            )
        save()
        mutation_confirmed = False
        try:
            cursor.execute(
                f"UPDATE {TABLE} SET QUALITY = %s WHERE SAMPLE_ID = %s AND QUALITY = %s",
                (changed, target_id, original),
            )
            report["mutation_query_id"] = cursor.sfqid
            if cursor.rowcount != 1:
                raise RuntimeError("Mutation did not affect exactly one working-copy row.")
            mutation_confirmed = True
            report["after"] = ask()
            if count_from_answer(report["after"]) != expected + DELTA:
                raise RuntimeError("Answer did not reflect the committed data change.")
            if report["after"]["evidence"][0]["query_id"] == report["before"]["evidence"][0]["query_id"]:
                raise RuntimeError("Before and after must be separate Snowflake executions.")
            for key in ("sql", "parameters"):
                if report["after"]["evidence"][0][key] != report["before"]["evidence"][0][key]:
                    raise RuntimeError("The before/after proof must execute identical SQL and parameters.")
            save()
        except Exception:
            report["status"] = "failed"
            save()
            raise
        finally:
            if mutation_confirmed:
                # Restore only our confirmed mutation; never undo another writer's update.
                cursor.execute(
                    f"UPDATE {TABLE} SET QUALITY = %s WHERE SAMPLE_ID = %s AND QUALITY = %s",
                    (original, target_id, changed),
                )
                report["restore_query_id"] = cursor.sfqid
                cursor.execute(f"SELECT QUALITY FROM {TABLE} WHERE SAMPLE_ID = %s", (target_id,))
                restored_rows = cursor.fetchall()
                report["restored"] = len(restored_rows) == 1 and restored_rows[0][0] == original
            else:
                report["restore_skipped"] = (
                    "Mutation was not confirmed; inspect current working copy before retrying."
                )
            save()
        if not report["restored"]:
            report["status"] = "restore_failed"
            save()
            raise RuntimeError(
                "The working-copy row could not be restored; inspect proof.json before retrying."
            )
        report["restored_answer"] = ask()
        if count_from_answer(report["restored_answer"]) != expected:
            raise RuntimeError("Restored answer differs from baseline.")
        verify_table(cursor, SOURCE, records)
        verify_table(cursor, WORKING, records)
        report["source_unchanged"] = True
        report["status"] = "passed"
        save()
    lines = [
        "# Live Snowflake data-change proof",
        "",
        "Real UCI Wine Quality data (CC BY 4.0); modifications occur only in a labelled working copy.",
        "",
        "Identical question: " + QUESTION,
        "",
        "| Stage | Samples with quality >= 7 | Snowflake query ID |",
        "|---|---:|---|",
    ]
    for label, key in [
        ("Before", "before"),
        ("After one score 6 → 7", "after"),
        ("Restored", "restored_answer"),
    ]:
        result = report[key]
        lines.append(f"| {label} | {count_from_answer(result):,} | `{result['evidence'][0]['query_id']}` |")
    lines += [
        "",
        "The API interpreted the question with Gemma and executed a fresh Snowflake query at every stage.",
        "Full plans, SQL, parameters, rows, run IDs and mutation/restoration query IDs are in proof.json.",
        "The application reader was never granted UPDATE. Only the explicit admin demo changed the labelled working copy. Source observations were verified unchanged.",
        "",
    ]
    (output / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    return report
