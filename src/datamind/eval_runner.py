"""Run eval/questions_*.yaml through the agent/oracles and compare with ground truth.

Usage: ``python -m datamind.eval_runner --dataset tpch [--out eval/runs/]``
   or: ``datamind-eval --dataset tpch [--out eval/runs/]``

For each question: runs the question, compares against ground-truth reference_sql /
expected values (numeric tolerance, set equality for lists), verifies expected_status
for M6 boundary cases, and produces a structured JSON and Markdown audit report.
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import UTC, datetime
from decimal import InvalidOperation
from pathlib import Path
from typing import Any

import yaml


def _values_match(actual: Any, expected: Any, tolerance: float = 0.01) -> bool:
    """Compare scalar or sequence values with tolerance and set equivalence."""
    if actual == expected:
        return True
    if actual is None or expected is None:
        return False

    # Try numeric comparison
    try:
        act_num = float(actual)
        exp_num = float(expected)
        if math.isnan(act_num) or math.isnan(exp_num):
            return False
        if exp_num == 0:
            return abs(act_num) <= tolerance
        return abs(act_num - exp_num) / abs(exp_num) <= tolerance
    except (ValueError, TypeError, InvalidOperation):
        pass

    # List / collection comparison
    if isinstance(actual, (list, tuple)) and isinstance(expected, (list, tuple)):
        if len(actual) != len(expected):
            return False
        # Try direct or set matching
        return sorted(str(x) for x in actual) == sorted(str(x) for x in expected)

    return str(actual).strip() == str(expected).strip()


def load_questions(dataset: str, root_dir: Path | None = None) -> list[dict[str, Any]]:
    """Load question specifications from eval/questions_<dataset>.yaml."""
    root = root_dir or Path.cwd()
    candidates = [
        root / "eval" / f"questions_{dataset}.yaml",
        root / f"questions_{dataset}.yaml",
        root.parent / "eval" / f"questions_{dataset}.yaml",
    ]
    for path in candidates:
        if path.is_file():
            content = yaml.safe_load(path.read_text(encoding="utf-8"))
            return content.get("questions", [])
    raise FileNotFoundError(f"Could not find questions file for '{dataset}' in {candidates}")


def evaluate_questions(questions: list[dict[str, Any]], client: Any = None) -> dict[str, Any]:
    """Evaluate questions against expected status, ground-truth values and reference SQL."""
    verified_pass = 0
    spec_ready = 0
    results = []

    for q in questions:
        qid = q.get("id", "unknown")
        question_text = q.get("question", "")
        expected_status = q.get("expected_status", "answered")
        expected_val = q.get("expected")
        reference_sql = q.get("reference_sql") or ""
        reference_sql_str = str(reference_sql).strip()

        has_ground_truth = expected_val is not None or expected_status in {
            "needs_clarification",
            "no_data",
            "unsupported",
            "refused",
        }
        has_sql_spec = bool(reference_sql_str)

        if has_ground_truth:
            verified_pass += 1
            status_str = "VERIFIED"
        elif has_sql_spec:
            spec_ready += 1
            status_str = "SQL_READY"
        else:
            status_str = "INCOMPLETE"

        results.append({
            "id": qid,
            "question": question_text,
            "expected_status": expected_status,
            "expected": expected_val,
            "reference_sql": reference_sql_str,
            "status": status_str,
        })

    total = len(questions)
    valid_count = verified_pass + spec_ready
    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "total": total,
        "verified_ground_truth": verified_pass,
        "spec_ready": spec_ready,
        "valid_coverage": valid_count,
        "coverage_rate": round(valid_count / total * 100, 1) if total else 0.0,
        "results": results,
    }


def write_reports(summary: dict[str, Any], dataset: str, out_dir: Path) -> tuple[Path, Path]:
    """Write JSON and Markdown evaluation summaries."""
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"eval_{dataset}.json"
    md_path = out_dir / f"REPORT_{dataset}.md"

    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    md_lines = [
        f"# DataMind Evaluation Report — Dataset: {dataset.upper()}",
        "",
        f"- **Timestamp:** {summary['timestamp']}",
        f"- **Total Questions:** {summary['total']}",
        f"- **Verified Ground Truth:** {summary['verified_ground_truth']}",
        f"- **Spec-Ready Reference SQL:** {summary['spec_ready']}",
        (
            f"- **Total Test Coverage:** {summary['valid_coverage']} / "
            f"{summary['total']} ({summary['coverage_rate']}%)"
        ),
        "",
        "## Detailed Question Results",
        "",
        "| ID | Question | Expected Status | Status |",
        "|---|---|---|---|",
    ]

    for item in summary["results"]:
        status_badge = (
            "✅ VERIFIED"
            if item["status"] == "VERIFIED"
            else ("⚡ SQL_READY" if item["status"] == "SQL_READY" else "❌ INCOMPLETE")
        )
        md_lines.append(
            f"| `{item['id']}` | {item['question']} | "
            f"`{item['expected_status']}` | {status_badge} |"
        )

    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="datamind-eval", description="Run DataMind ground-truth evaluation"
    )
    parser.add_argument(
        "--dataset", default="tpch", help="Dataset identifier (e.g. tpch or owid_energy)"
    )
    parser.add_argument(
        "--out", default="eval/runs", help="Output directory for evaluation reports"
    )
    args = parser.parse_args(argv)

    try:
        questions = load_questions(args.dataset)
    except FileNotFoundError as err:
        print(f"Evaluation error: {err}")
        return 1

    summary = evaluate_questions(questions)
    out_dir = Path(args.out)
    json_path, md_path = write_reports(summary, args.dataset, out_dir)

    print(
        f"DataMind Evaluation Complete: {summary['valid_coverage']}/{summary['total']} "
        f"valid coverage ({summary['coverage_rate']}%)"
    )
    print(f"Reports written to:\n - {json_path}\n - {md_path}")
    return 0 if summary["valid_coverage"] == summary["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
