# Team

| Member | Role | Owns |
|---|---|---|
| [Srujan](srujan.md) | Lead · Gemma, agent pipeline, SQL guard | `src/datamind/agent.py`, `src/datamind/llm/`, `src/datamind/sql_guard.py` |
| [Zishan](zishan.md) | Snowflake, data & eval runner | `snowflake/`, `src/datamind/snowflake_client.py`, `src/datamind/schema.py`, `config/datasets/`, `src/datamind/eval_runner.py` |
| [Vishal](vishal.md) | QA, eval questions, newcomer testing (beginner; mentored) | `eval/questions_*.yaml` content, bug/docs issues |
| [Saisudheer](saisudheer.md) | UI, docs & submission | `src/datamind/app.py`, `README.md`, `docs/`, demo video |

Owners review every PR that touches their files. Anyone may open a PR anywhere.

Vishal is starting as a beginner: correctness-critical code (guard, eval runner) stays
with experienced members, and Zishan reviews every reference SQL Vishal writes. Answer
Vishal's questions quickly — confusion found early is a docs fix, not a judge's complaint.

## Shared rules

- **`src/datamind/models.py` is the contract between all four areas.** Change it only
  by a PR that every affected owner approves.
- Never commit `.env`, keys, passwords or dataset files (gates G4/G5 — a failure
  means the team is **not ranked**).
- Correctness beats polish: if answer correctness is scored Poor, the PS1 score is
  capped at 50 regardless of UI.
- `docs/COMPLIANCE.md` is the single status board. Update your rows in the same PR
  as the work.
- One Snowflake trial account for the team (Zishan is admin). Share credentials
  privately, never in the repo or chat logs.
- Each member creates their **own** AI Studio key in their **own** Google Cloud
  project: free-tier rate limits are per project, so shared keys throttle everyone.

## Order of work

Deadlines come from the organizers; fill them in here when announced.

| Phase | Goal | Exit check |
|---|---|---|
| 1. Foundations | Snowflake set up; Gemma API call works; guard passes its spec | `00_setup.sql` returns 150000; one Gemma 4 call from `ai_studio_backend.py`; `tests/test_sql_guard_contract.py` has no xfails |
| 2. End to end | A question in the UI returns an answer with SQL, query ID and rows | t01–t05 answered correctly through the UI |
| 3. Correctness | Eval runner scores the full question set | ≥ 80% of `eval/questions_tpch.yaml` correct, failures understood |
| 4. Robustness | Ambiguous, empty, unsupported and unsafe questions handled; second dataset works | t08–t12 pass; `owid_energy` answers with no code change |
| 5. Submission | Every row in `docs/COMPLIANCE.md` is ✅ or honestly explained | Repo public, demo recorded, README TODOs gone |

## Dependency map

```
Zishan: SnowflakeClient ──┐
                          ├──> Srujan: DataMindAgent ──> Saisudheer: UI ──> demo
Srujan: validate_sql  ────┘            │                      │
                                       │                      └──> Vishal: manual QA ──> issues
Vishal: questions ──> Zishan: reference SQL + expected values ──┐
                                       └──> Zishan: eval runner ┴──> results in README
```

Until a dependency lands, code against the interface with a fake (see each file).
