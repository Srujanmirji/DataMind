# Srujan — Lead · Gemma, agent pipeline & SQL guard

**Owns:** `src/datamind/agent.py`, `src/datamind/llm/`, `src/datamind/sql_guard.py`
**Rubric weight carried:** Gemma integration (12), NL-to-data interaction (10), and most of correctness (20)

## Tasks

- [ ] **Day 1 — probe the Gemini API** with `gemma-4-26b-a4b-it`: does it accept
  `system_instruction`? `response_mime_type="application/json"`? Record the answers in
  `docs/ARCHITECTURE.md`. Everything else in prompt design depends on this.
- [ ] Implement `AIStudioBackend.generate`: temperature 0, latency timing, 429 retry with
  exponential backoff, clear error on bad key/model id.
- [ ] Implement `validate_sql` with `sqlglot` (Snowflake dialect) until
  `tests/test_sql_guard_contract.py` has **zero xfails**: single statement, SELECT/WITH only,
  allowlisted tables (qualify unqualified names, ignore CTE names), no
  `RESULT_SCAN`/`INFER_SCHEMA`, LIMIT capped and reported. Do this early — it's well
  specified by the tests and it gates every query.
- [ ] Add adversarial guard tests: comments hiding statements, quoted identifiers,
  `SELECT ... INTO`, subqueries into other schemas, case tricks. Use Vishal's unsafe
  question list as input.
- [ ] Implement `OllamaBackend.generate` (fallback; lower priority).
- [ ] `DataMindAgent.classify` → JSON `{status, reason, clarifying_question}`; validate the enum.
- [ ] `DataMindAgent.generate_sql` → JSON `{sql, assumptions[]}` using
  `SchemaCatalog.render_for_prompt()`, glossary and relationships; repair loop feeding
  Snowflake's error back, max `max_repairs`.
- [ ] `DataMindAgent.explain` → answer only from result rows; empty rows → `NO_DATA`
  with the dataset's actual range (e.g. "orders cover 1992–1998").
- [ ] `DataMindAgent.verify` → flag numbers in the answer that are not in the rows
  (tolerate rounding / thousands separators).
- [ ] `DataMindAgent.ask` → never raises; every path returns an `AgentAnswer` with
  `queries` and `llm_calls` filled.
- [ ] Follow-up questions: pass the last N turns' question + SQL as context (eval t13).

## Definition of done

- Eval t01–t07 and t13 correct via `datamind-eval`; t08–t12 return the expected status.
- Unit tests with a fake `LLMBackend` and fake `SnowflakeClient` cover: happy path,
  SQL repair, guard rejection, empty result, unsupported question.

## Depends on / unblocks

- Needs: Zishan's `SnowflakeClient` + `SchemaCatalog`. Until then, use fakes that
  return canned `QueryResult`s.
- Unblocks: Saisudheer (UI), Zishan (eval runner), Vishal (manual QA).
