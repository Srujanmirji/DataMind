# Zishan — Snowflake & data

**Owns:** `snowflake/`, `src/datamind/snowflake_client.py`, `src/datamind/schema.py`, `config/datasets/`
**Rubric weight carried:** Snowflake integration (15), reusability on a second dataset (8)

## Tasks

- [ ] **Day 1 — create the team Snowflake trial** and run `snowflake/00_setup.sql`.
  Confirm the smoke test returns `150000`. Note the trial end date in `team/README.md`.
  It must still be active when judges review.
- [ ] Fix anything in the setup scripts that fails, and mark them ✅ in `docs/COMPLIANCE.md`.
- [ ] Implement `SnowflakeClient.from_env` (password and key-pair auth),
  `QUERY_TAG='datamind'`, read-only role.
- [ ] Implement `run_query`: statement timeout, fetch ≤ `max_rows`, true `row_count`,
  `cursor.sfqid` as `query_id`, `elapsed_ms`.
- [ ] Implement `describe_columns` from `INFORMATION_SCHEMA.COLUMNS` for allowlisted tables only.
- [ ] Implement `SchemaCatalog.render_for_prompt` (compact: table → columns + types,
  relationships, glossary; under `max_chars`).
- [ ] Load the second dataset with `snowflake/10_load_owid_energy.sql`; record the
  snapshot date, row count and max YEAR in `docs/DATASETS.md`.
- [ ] Data-change demo: script the `UPDATE` + restore on `DATAMIND.OWID.ENERGY` described
  in `eval/README.md`.
- [ ] Evidence query: SQL that lists all `datamind`-tagged queries from `QUERY_HISTORY`
  (for the submission's "Snowflake query IDs or history").
- [ ] Watch credit use; adjust the resource monitor quota if needed.

## Definition of done

- `SnowflakeClient` integration test (skipped when `SNOWFLAKE_ACCOUNT` is unset) runs t01's
  reference SQL and gets 150000 plus a query ID.
- Switching `DATAMIND_DATASET=owid_energy` works with zero code changes.

## Depends on / unblocks

- Needs: nothing. Start immediately.
- Unblocks: Srujan (agent), Vishal (eval runner needs `run_query` for reference SQL).
