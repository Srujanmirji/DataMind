# Vishal — Safety & correctness

**Owns:** `src/datamind/sql_guard.py`, `src/datamind/eval_runner.py`, `eval/`
**Rubric weight carried:** correctness evidence (20, with the trust cap), ambiguity/unsafe handling (12), testing (C7)

## Tasks

- [ ] Implement `validate_sql` with `sqlglot` (Snowflake dialect) until
  `tests/test_sql_guard_contract.py` has **zero xfails**: single statement, SELECT/WITH only,
  allowlisted tables (qualify unqualified names, ignore CTE names), no
  `RESULT_SCAN`/`INFER_SCHEMA`, LIMIT capped and reported.
- [ ] Add adversarial guard cases: comments hiding statements, quoted identifiers,
  `SELECT ... INTO`, subqueries into other schemas, case tricks.
- [ ] Run every `reference_sql` in `eval/questions_tpch.yaml` in Snowflake; fill in each
  `expected` value and record the query ID.
- [ ] Grow the TPC-H set to 30+ questions: varied phrasing of the same intent, more joins,
  more multi-step, one per glossary term. Write reference SQL by hand, never from agent output.
- [ ] Write `eval/questions_owid_energy.yaml` (10+ questions, including missing-data cases).
- [ ] Implement `eval_runner`: run agent + reference SQL, compare (numeric tolerance, set
  equality for lists), check expected status, write JSON + Markdown report with query IDs.
- [ ] Prompt-injection tests: questions that try to override instructions or reach
  other schemas (extend t12).

## Definition of done

- Guard: all contract tests pass; CI green.
- A committed report in `eval/results/` with the pass rate by category, including failures.

## Depends on / unblocks

- Needs: Zishan's `run_query` for reference runs (use the Snowsight UI until then).
  The full eval needs Srujan's `DataMindAgent.ask`.
- Unblocks: Srujan (guard), Saisudheer (results for README S8).
