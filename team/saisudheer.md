# Saisudheer — UI, docs & submission

**Owns:** `src/datamind/app.py`, `README.md`, `docs/`, demo video
**Rubric weight carried:** evidence display (part of 15), practical relevance/UX (8), and most of the common rubric (C1, C4, C5, C6, C8)

## Tasks

- [ ] Build the Streamlit UI against a **fake `AgentAnswer`** now (no need to wait for the
  agent): question box → answer → "How this was answered" (explanation, assumptions) →
  "Evidence" (SQL, Snowflake query ID, result table, row count, truncation note) →
  model id + backend.
- [ ] Distinct, readable rendering for each `AnswerStatus` (clarifying question, no data,
  unsupported, refused, error, rate limited).
- [ ] Session history for follow-up questions; dataset picker in the sidebar.
- [ ] Basic accessibility: readable contrast, no meaning by colour alone, tables with headers.
- [ ] Add a secret scan to CI (e.g. gitleaks action) for gate G5.
- [ ] Fix every `docs` issue Vishal files from the fresh-clone tests (C5); help Vishal
  with Git and the first PR.
- [ ] Fill every `_TODO_` in `README.md`: tested environment, testing results, reproduce the
  demo, technical contribution, judge evaluation path.
- [ ] Keep `docs/COMPLIANCE.md` current; run a gate check before submission.
- [ ] Record the ≤ 5-minute demo: real questions, visible SQL and query IDs, one ambiguous,
  one empty, one refused, one data-change, and the second dataset. Show limitations honestly.
- [ ] Make the GitHub repo public before the deadline (gate G1).

## Definition of done

- A newcomer can go from clone to first answer using only the README.
- Every row in `docs/COMPLIANCE.md` is ✅ or carries an honest explanation.

## Depends on / unblocks

- Needs: Srujan's `DataMindAgent.ask` for the live UI; Zishan's eval report for S8;
  Vishal's fresh-clone and QA issues.
- Unblocks: the submission.
