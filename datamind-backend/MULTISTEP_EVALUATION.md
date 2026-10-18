# Multi-step evaluation — backend 0.2.0

> **Historical record.** The UCI Wine Quality dataset described here was removed on
> 18 October 2026 and replaced by World Bank WDI. Current results: [VALIDATION.md](VALIDATION.md).

Existing datasets retained: Snowflake TPC-H SF1 and real UCI Wine Quality.
Gemma runs locally through Ollama; validated plans compile into parameterized,
read-only Snowflake SQL. Two source queries feed deterministic Decimal calculations.

## Implemented

- Two-cohort comparisons: values, signed difference and baseline percentage change.
- Subset shares with an explicit denominator.
- Groups whose configured mean exceeds the pooled mean of underlying observations.
- Query IDs, bound parameters, formulas, cell-level input references and saved runs.
- Zero/null denominator handling, bounded groups and one invalid-plan repair.

## Completed local checks

- **85 automated tests passed**; Ruff, mypy and dependency checks pass.
- **6/6 TPC-H semantic-plan checks passed** with live Gemma; these checks compile SQL
  and verify metric/scopes/grouping, but do not execute warehouse queries.
- **12/12 UCI answer checks passed** with live Gemma and SQLite loaded from the original
  UCI observations. Independent Python source-data arithmetic verifies the values.
  This is explicitly not Snowflake evidence.
- Four developer-authored fresh UCI questions passed on their first execution across
  the recorded runs. Other final cases are regressions after development iteration.
  This is not an external blind benchmark.

The first 4B evaluation passed 4/8. The model was upgraded to Gemma 3 12B, then
configured with separate target/reference planning. An initial TPC-H year-change
case combined periods; validation now rejects combined/reversed scopes before SQL
and repairs once. Its final semantic check passes. An early 12B UCI strict check
reported 10/11 because of an extra constant grouping label; required result values
were correct. The evaluator now records extra context columns while still rejecting
missing metrics, wrong row counts and incorrect values. Earlier reports remain saved.

## Live Snowflake verification

The user unlocked the key privately and started `run.py --evaluate --replace`.
That process exited after two passing TPC-H cases, leaving a partial report.
The old server was not replaced. A complete 18-case live success is not yet claimed. It verifies independent TPC-H
SQL oracles, original-source UCI arithmetic, evidence links and saved API runs.

## Limits

Support is bounded to two source scopes and one metric for multi-step analysis.
Arbitrary chains and conversational memory are not implemented. Separate query
executions can see concurrent edits. Model interpretation can still be wrong for
new wording: display the filters, reference scope, source SQL and calculations.
The 12B model uses about 8 GB GPU memory at 8,192 context; inference can take time.
