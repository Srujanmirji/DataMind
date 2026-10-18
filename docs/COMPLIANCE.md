# Compliance tracker — ZeroDay OSS Hacktoberfest 2026, PS1

Maps every gate, mandatory feature and submission item in the participant guide
to where it is satisfied. A failed gate means **not ranked**, not a deduction.
Update the Status column honestly; judges will check.

Status: ✅ done & verified · 🟡 scaffolded / unverified · ❌ not started

## Pass/fail gates

| Gate | Requirement | Where | Status |
|---|---|---|---|
| G1 | Public repo + OSS licence file | `LICENSE` (MIT); repo visibility set to public | 🟡 make repo public |
| G2 | Judge can run without undisclosed creds/paid services, or feasible path documented | README "Evaluation path for judges"; Snowflake trial + Ollama/free AI Studio key | 🟡 |
| G3 | Demo shows the real system | Recording of live run with query IDs | ❌ |
| G4 | Dataset sources + licences disclosed; no non-redistributable data committed | `docs/DATASETS.md`; `.gitignore` blocks `data/`, `*.csv` | 🟡 |
| G5 | No keys/tokens/passwords in repo | `.env` ignored; `.env.example` only; placeholder password in `00_setup.sql` | 🟡 add a secret scan to CI |
| P1 | Snowflake used meaningfully | All answers from SQL run in Snowflake | ❌ |
| P2 | Gemma used meaningfully | Classify, NL→SQL, explain | ❌ |
| P3 | Answers derived from queries run at question time | `agent.ask` → `run_query` per question; no caching of answers | ❌ |

## Mandatory features (M1–M8)

| ID | Requirement | Where | Status |
|---|---|---|---|
| M1 | Everyday-language questions (unseen) | `agent.classify`, `agent.generate_sql` | ❌ |
| M2 | Real querying at question time | `snowflake_client.run_query` | ❌ |
| M3 | Grounded, no unsupported claims | `agent.explain` + `agent.verify` | ❌ |
| M4 | Plain-language explanation of how | `AgentAnswer.explanation`, `assumptions` | ❌ |
| M5 | Inspectable evidence (SQL, rows, query ID) | `AgentAnswer.queries` → UI "Evidence" | ❌ |
| M6 | Ambiguity, missing data, empty results, unsupported | `AnswerStatus`; eval t08–t12 | ❌ |
| M7 | Meaningful Snowflake + Gemma integration | `docs/ARCHITECTURE.md` | 🟡 |
| M8 | Working, reproducible OSS implementation | pinned `pyproject.toml`, CI, README | 🟡 |

## Submission items (S1–S10)

| ID | Deliverable | Where | Status |
|---|---|---|---|
| S1 | Public repo + licence | `LICENSE` | 🟡 |
| S2 | README: overview, setup, run, config, troubleshooting | `README.md` | 🟡 |
| S3 | Pinned deps, tool versions, OS/hardware tested, model sizes | `pyproject.toml`; README "Tested environment" | 🟡 fill hardware + model size |
| S4 | Architecture diagram | `docs/ARCHITECTURE.md` | ✅ |
| S5 | Dataset sources, licences, prep, attribution | `docs/DATASETS.md` | 🟡 record OWID snapshot |
| S6 | How Snowflake and Gemma are used | `docs/ARCHITECTURE.md` | 🟡 |
| S7 | Demo recording (≤ ~5 min, recommended) incl. limits | link in README | ❌ |
| S8 | Testing results + known limitations | README; `eval/results/` | ❌ |
| S9 | Instructions to reproduce the demo | README "Reproduce the demo" | 🟡 |
| S10 | Short statement of main technical contribution | README "Technical contribution" | 🟡 |

## PS1 extras

| Item | Where | Status |
|---|---|---|
| Evidence of grounding (query IDs / history, comparison with independent results) | `eval_runner` report | ❌ |
| Demo of answer changing when data changes | `eval/README.md` procedure on `owid_energy` | ❌ |
| Evidence of Snowflake and Gemma roles | UI shows model id + query ID per answer | ❌ |
| Evaluation question set with expected answers (recommended) | `eval/questions_tpch.yaml` | 🟡 fill `expected` from reference runs |
| Reproducible Snowflake setup script (recommended) | `snowflake/00_setup.sql`, `10_load_owid_energy.sql` | 🟡 not yet executed |
