# Srujan — Lead · Gemma & agent pipeline

**Owns:** `src/datamind/agent.py`, `src/datamind/llm/`
**Rubric weight carried:** Gemma integration (12), NL-to-data interaction (10), and most of correctness (20)

## Tasks

- [ ] **Day 1 — probe the Gemini API** with `gemma-4-26b-a4b-it`: does it accept
  `system_instruction`? `response_mime_type="application/json"`? Record the answers in
  `docs/ARCHITECTURE.md`. Everything else in prompt design depends on this.
- [ ] Implement `AIStudioBackend.generate`: temperature 0, latency timing, 429 retry with
  exponential backoff, clear error on bad key/model id.
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

- Needs: Zishan's `SnowflakeClient` + `SchemaCatalog`, Vishal's `validate_sql`.
  Until then, use fakes that return canned `QueryResult`s.
- Unblocks: Saisudheer (UI), Vishal (eval runner).
