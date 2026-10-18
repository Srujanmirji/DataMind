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

## Known caveats

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

## Live 0.2.0 evaluation — 18/18 (18 October 2026)

Live Gemma 3 12B and live Snowflake, started privately by the user with
`run.py --evaluate --replace`. All **18/18** cases passed against independent oracles
(static SQL for TPC-H, source-data arithmetic for UCI): 6 TPC-H and 12 UCI cases,
including ambiguity, missing dates, zero baselines and a prompt-injection refusal.
Because every case passed, 0.2.0 replaced the old server on port 8000.
Report: `data/evaluations/20261018T094254Z-0c3b86bb/REPORT.md` (local; `data/` is gitignored).

The first full live attempt scored **17/18**
(`data/evaluations/20261018T092139Z-820c8a89`). The failure was real: Snowflake's
`AVG` over an integer column returns 6 decimals, so the white-versus-red quality
percentage came out as 4.291785% instead of the exact 4.291800%. Average metrics now
cast inputs to `NUMBER(38, 6)`, which gives 12-decimal results. The re-run returned
4.291800%. SQLite returns floats, which is why local runs had not shown this.

Sample evidence from the 18/18 run:

| Case | Answer | Snowflake query IDs |
|---|---|---|
| 1993 → 1994 order counts | 226,645 → 227,597; +952; +0.420040% | `01c7cf47-000e-1673-0000-0002b3de82bd`, `01c7cf47-000e-16b8-0002-b3de0001317e` |
| White vs red mean quality | 5.877909 vs 5.636023; +0.241887; +4.291800% | `01c7cf4a-000e-16cf-0002-b3de000160ca`, `01c7cf4a-000e-16d0-0002-b3de000150ca` |

Earlier partial attempt (2 cases, before the fix):
`data/evaluations/20261018T081248Z-ad449718`. The evaluator prints RUN case
counters before each operation so long model inference is visibly distinguished
from a stopped process.
