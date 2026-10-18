"""Run eval/questions_*.yaml through the agent and compare with ground truth.

Usage: ``datamind-eval --dataset tpch [--out eval/runs/]``

For each question: run the agent, run the question's ``reference_sql`` directly
in Snowflake, compare (numeric tolerance, set equality for lists), check the
expected status for M6 cases, and write a JSON + Markdown report including
every Snowflake query ID. Commit curated reports to eval/results/ (S8).
"""

from __future__ import annotations

import argparse


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="datamind-eval")
    parser.add_argument("--dataset", default=None)
    parser.add_argument("--out", default="eval/runs")
    parser.parse_args(argv)
    raise NotImplementedError("eval runner")
