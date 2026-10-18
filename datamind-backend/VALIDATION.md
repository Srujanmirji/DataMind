# Validation — 18 October 2026

## Selected-dataset grounding checks — 18 October 2026

162 automated tests pass; Ruff passes. Tests cover invented/omitted country filters,
wrong years and wrong metrics, a single year incorrectly widened to a range,
clarification/refusal at both planning stages, and missing measurement handling.

Live hosted Gemma checks correctly refused sports, a mixed GDP/prime-minister request,
a World Bank question with TPC-H selected, and an instruction to answer from memory.
Missing-year GDP and an undefined "best country" question asked for clarification.
All six returned no SQL evidence. Two positive checks initially hit the API rate limit;
on retry, India 2022 life expectancy returned 71.698 in 13.0s and the top-five GDP-per-capita
ranking for 2023 returned Monaco, Liechtenstein, Luxembourg, Bermuda and Ireland in 11.5s.
Query IDs: `01c7cfeb-000e-16cf-0002-b3de00016742` and
`01c7cfeb-000e-16f2-0002-b3de0001e00a`.

The exact user query "List the 10 countries with the lowest total GDP in 2023"
now passes after extending the explicit list-size check (the old check only recognized
"top 10" / "10 lowest"). All ten returned rows match independent arithmetic on the
World Bank API snapshot. First request: 13.6s, query ID
`01c7cff4-000e-1619-0000-0002b3de7b65`; repeated request: 0.87s, cached plan with fresh
Snowflake query ID `01c7cff4-000e-1619-0000-0002b3de7b69`.
A separate Google HTTP 503 was observed during verification; the adapter now retries
one temporary server failure and distinguishes it from access/configuration errors.

These smoke checks do not establish perfect semantic interpretation or replace a full
held-out evaluation. Conservative alias matching may ask users to restate unusual names.

## Current hosted configuration and plan cache

18 October 2026: Gemma `gemma-4-26b-a4b-it` via Google AI Studio is running with
live Snowflake. 96 automated tests and Ruff pass (one optional Pillow test skipped).
Live checks: India's 2022 life expectancy = 71.698 years (16.4s), and internet use
14.9% (2015) to 60.2523% (2023), +304.377852% (25.8s).

Plan caching reuses only validated successful query plans for one hour (256 per
dataset, memory only). Identical life-expectancy requests took 16.11s then 1.43s;
Snowflake query IDs were `01c7cfdb-000e-1619-0000-0002b3de7b3d` and
`01c7cfdb-000e-16df-0002-b3de000183a6`. SQL and calculations still run each time.
Tests cover expiry, configuration invalidation, fresh rows and IDs, two-query
comparisons, bounded storage and refusal/error exclusion.

Full hosted evaluation is pending. The initial World Bank local-model run was 8/10;
subsequent runs were 15/16 overall and 9/10 World Bank, followed by 14/16 after a
speed change that was reverted. Later fixes have not had a completed full evaluation.
These are developer-authored tests, not an external blind benchmark.

The sections below are historical: wine data and its data-change proof were removed
when switching to World Bank WDI. Their scores do not establish current coverage.

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

The local Gemma 3 12B + Snowflake UI question run passed 12/12 checks (7 answers, 4 clarification/refusal checks, and a repeated question). Answers were checked against the downloaded World Bank source. The repeated question used a cached plan and fresh SQL. Report: `data/ui-question-checks/20261018T125441Z/results.json`.

Paraphrase handling now permits semantic descriptions without literal metric keywords, retains explicit-metric mismatch checks, and supports structured missing-detail clarification. All 18 loaded World Bank indicators are exposed in the catalog. Automated regressions exercise previously blocked paraphrases and all three newly exposed indicators.

Fresh live paraphrase checks passed 4/4 against raw World Bank values for India in 2022: life expectancy 71.698 years, trade 50.697938% of GDP, adult literacy 76.32%, education spending 4.098658% of GDP. Local Gemma 12B took 32–47 seconds per first request. Report: `data/runtime/paraphrase-check.json`.

Unicode punctuation regression: curly possessives such as “India’s” previously lost their word boundary during ASCII normalization and rejected a correct IND filter. Normalize punctuation to boundaries before transliteration. Regression tests cover curly quotes and modifier apostrophes while still rejecting a substituted CHN filter.


Flexible query regression checks now cover bound decimal thresholds, non-finite/injection
rejection, actual latest non-missing data per scope/group, missing year exposure rejection,
multiple-country comparisons, mixed literal/paraphrased metric selection, and consideration
of all 217 economies in above-average analysis. Source-data oracles and five independent
questions are saved in `evaluation/questions.json`; they are not passed to model prompts.

Live hosted checks matched raw World Bank data for the three-country GDP-per-capita
comparison (23.98s), all 51 countries with unemployment above 8.5% in 2022 (19.79s),
and India's latest available GDP (2024: 3,760,813,470,500.86 USD, 26.50s). Missing entity
clarification and unrelated sports refusal returned no evidence. A trend request initially
failed plan generation; the clarified year-by-year routing prompt subsequently produced the
correct five-year, two-metric plan. Some requests hit Google's rate limit; those were recorded
as failures rather than counted as passes. Follow-up live query results are recorded separately.

Final hosted API rerun after restart: latest available India GDP passed (24.79s),
the 2019–2023 GDP/population trend passed all five years against the raw source
(25.70s), and the identical latest question passed with a cached plan and a distinct
fresh Snowflake query ID (1.61s). Report: `data/runtime/flexible-final-results.json`.
A question combining literal GDP with “how long people could expect to live” also
passed (17.19s); both returned measures matched the raw World Bank source.
