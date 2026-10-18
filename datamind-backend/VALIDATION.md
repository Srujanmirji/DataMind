# Validation — 18 October 2026

## Current feature: multi-step analysis 0.2.0

- 85 automated tests pass; Ruff check/format pass; mypy checks all 13 app modules;
  pip check reports no broken requirements.
- Covers scalar comparisons, subset shares, row-weighted population averages,
  null/zero denominators, Decimal precision, group truncation refusal, explicit
  threshold coverage, query/cell lineage, safe process replacement and API history.
- Code review completed. Fixed two confirmed planner guard bugs: analytical "drop"
  must not be confused with a write, and scalar LIMIT cannot cover a missing threshold.
- Evaluation uses independent source-data arithmetic for UCI and independent static
  SQL for TPC-H. It verifies response states, result cells, claim references and history.
- First developer-held-out UCI evaluation using Gemma3 4B passed **4/8**. Subsequent
  prompt-development regressions also failed (3/8, 0/8, 3/8, 2/8). These failures are
  preserved under data/evaluations. No broad reliability claim follows from unit tests.
- Current model evaluation is recorded below once complete. Reports identify actual
  model, planner hash, fresh holdouts versus regressions, and execution engine.

## Previously verified live integration (before 0.2.0)

Both datasets were tested with real Gemma and Snowflake using the user-unlocked key.
The prior UI integration suite passed **13/13**. Examples are retained in
examples/responses and data/ui-handoff-tests/results.json. These are aggregate
answers from the old backend, not live tests of the new multi-step feature.

- TPC-H SF1: 1,500,000 orders. Includes joins/rankings/year filters, empty results,
  ambiguity, refusal and evidence/history verification. 1995 has 228,637 orders.
- UCI Wine Quality: 6,497 observations, 1,599 red and 4,898 white; 1,277 scores >=7.
  Download and ingestion retain all original measurements; source SHA-256 and licence
  are documented in UCI_DATA.md and data/uci/manifest.json.
- Live data-change proof passed **1,277 -> 1,278 -> 1,277** using the labelled working
  copy. Actual distinct Snowflake query IDs and restored/source-unchanged checks are
  in data/change-demo/proof.json and REPORT.md. The original source was not edited.

## Current live boundary

The old user-started server remains running on port 8000 with its unlocked key.
New code has not replaced that process. Full new-feature Snowflake evaluation needs
one private local unlock via `python run.py --evaluate --replace`. It executes only
SELECT queries and replaces the old DataMind listener only after all cases pass.
The passphrase is neither available to the agent nor stored in the project.
Local SQLite evidence is explicitly labelled and is not live Snowflake proof.

The test client emits an existing Starlette/httpx deprecation warning; tests and
runtime HTTP requests pass despite the warning. Concurrent edits between the two
queries can change comparison inputs; calculations do not promise one snapshot.


## Final local model evaluation

Configured Gemma 3 12B; about 8 GB GPU memory at 8,192 context was observed on the
user's Mac. The 4B model remains installed but is no longer the configured default.
Latest UCI evaluation: **12/12 passed**, using real Gemma plus original UCI data in
SQLite and independent Python arithmetic. Report:
`data/evaluations/20261018T080252Z-df11d485/REPORT.md`.
Four fresh developer-authored UCI questions passed on first execution across the
recorded runs; the remaining final checks are regressions. This is not an external
blind benchmark. Latest TPC-H semantic plans: **6/6 passed**, with metric, target,
baseline, grouping and all-groups limit checked; source SQL was compiled, not executed.
Plan report: `data/planner-evaluation/results.json`.

## Partial live 0.2.0 evaluation

The user privately unlocked the key and started `run.py --evaluate --replace`.
Two TPC-H cases passed with actual Snowflake query IDs and independent SQL oracles:
year-over-year order counts and France's average-order-value comparison. The process
then exited before completing the other cases; the old server was left running.
Partial results: `data/evaluations/20261018T081248Z-ad449718/results.json`.
The year comparison returned **226,645 -> 227,597**, difference **952** and percentage
change **0.420040%**. Source query IDs:
`01c7ceed-000e-1619-0000-0002b3de71a5` and `01c7ceee-000e-1673-0000-0002b3de81ad`.
Do not claim the entire 18-case live suite passed or that 0.2.0 replaced the old server.
The evaluator now prints RUN case counters before each operation so long model
inference is visibly distinguished from a stopped process.
