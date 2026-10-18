# Compliance tracker — ZeroDay OSS Hacktoberfest 2026, PS1

Maps every gate, mandatory feature and submission item in the participant guide
to where it is satisfied. A failed gate means **not ranked**, not a deduction.
Update the Status column honestly; judges will check.

The working system is [`datamind-backend/`](../datamind-backend/). Paths below are
relative to it unless they start with `/`. The `src/datamind/` skeleton is legacy
and satisfies nothing here.

Status: ✅ done & verified · 🟡 partly done / unverified · ❌ not started

Last updated: 18 October 2026, after switching to World Bank WDI and connecting the UI.

## Pass/fail gates

| Gate | Requirement | Where | Status |
|---|---|---|---|
| G1 | Public repo + OSS licence file | `/LICENSE`, `LICENSE` (MIT); GitHub reports the repo as public | ✅ |
| G2 | Judge can run without undisclosed creds/paid services, or feasible path documented | `README.md` "Fresh installation"; Snowflake trial + local Ollama, no paid services | 🟡 not yet tried on a clean machine by someone outside the team |
| G3 | Demo shows the real system | Recording of a live run with query IDs | ❌ |
| G4 | Dataset sources + licences disclosed; no non-redistributable data committed | `WORLDBANK_DATA.md`, `/README.md` "Datasets and licences"; `data/` is git-ignored | ✅ |
| G5 | No keys/tokens/passwords in repo | `.env` and `*.p8` ignored; key stays in `~/.snowflake/`; gitleaks scans full history on every push (`/.github/workflows/ci.yml`) | ✅ |
| P1 | Snowflake used meaningfully | Every answer is computed by SQL run in Snowflake; responses carry query IDs | ✅ |
| P2 | Gemma used meaningfully | Gemma (hosted Gemma 4 or local fallback) routes each uncached question and writes its typed plan (`app/planner.py`) | ✅ |
| P3 | Answers derived from queries run at question time | Each question runs fresh Snowflake queries with new query IDs | 🟡 data-change proof must be redone on World Bank data (the wine proof was removed with that dataset) |

## Mandatory features (M1–M8)

| ID | Requirement | Where | Status |
|---|---|---|---|
| M1 | Everyday-language questions (unseen) | `app/planner.py`; fresh first-run cases pass in the live eval | ✅ within configured metrics; not an external blind test |
| M2 | Real querying at question time | `app/warehouse.py` | ✅ |
| M3 | Grounded, no unsupported claims | Each answer claim references a result cell (`app/service.py`); evaluator checks them | ✅ |
| M4 | Plain-language explanation of how | Response explanation, formulas and rounding notes | ✅ |
| M5 | Inspectable evidence (SQL, rows, query ID) | API `evidence`; the UI at `/` shows SQL, bound parameters, Snowflake query ID, rows and calculation | ✅ |
| M6 | Ambiguity, missing data, empty results, unsupported | Clarification / refusal states; live cases `tpch_undefined_best`, `wdi_undefined_best`, `wdi_forecast` pass; empty state tested | ✅ |
| M7 | Meaningful Snowflake + Gemma integration | `README.md` "Architecture and safety" | ✅ |
| M8 | Working, reproducible OSS implementation | `requirements.txt`, CI runs the backend tests on Python 3.13, live eval in `VALIDATION.md` | 🟡 no outside reproduction yet |

## Submission items (S1–S10)

| ID | Deliverable | Where | Status |
|---|---|---|---|
| S1 | Public repo + licence | `/LICENSE` | ✅ |
| S2 | README: overview, setup, run, config, troubleshooting | `/README.md`, `README.md` | ✅ |
| S3 | Pinned deps, tool versions, OS/hardware tested, model sizes | `requirements.txt`; `/README.md` "Tested environment" | ✅ |
| S4 | Architecture diagram | `README.md` "Architecture and safety" (text diagram) | 🟡 text only; a rendered diagram would read better |
| S5 | Dataset sources, licences, prep, attribution | `WORLDBANK_DATA.md`; TPC-H in `/README.md` | ✅ |
| S6 | How Snowflake and Gemma are used | `README.md` "Architecture and safety" | ✅ |
| S7 | Demo recording (≤ ~5 min, recommended) incl. limits | link in `/README.md` | ❌ |
| S8 | Testing results + known limitations | `/README.md`, `VALIDATION.md` | ✅ |
| S9 | Instructions to reproduce the demo | `/README.md` "Reproduce the demo" | ❌ TODO until the demo is recorded |
| S10 | Short statement of main technical contribution | `/README.md` "Technical contribution" | ✅ |

## PS1 extras

| Item | Where | Status |
| Evidence of grounding (query IDs / history, comparison with independent results) | `VALIDATION.md` current hosted smoke checks and historical evaluation query IDs; independent oracles in `scripts/evaluate.py` | ✅ |
| Demo of answer changing when data changes | To redo on `DATAMIND_DEMO.WORLDBANK` | ❌ |
| Evidence of Snowflake and Gemma roles | Rendered in Glassmorphic Web UI and Streamlit UI; Snowflake query ID per answer; `/health` reports the model | ✅ |
| Evaluation question set with expected answers (recommended) | `evaluation/questions.json` + oracles | ✅ |
| Reproducible Snowflake setup script (recommended) | `sql/setup.sql`, `TEAM_ACCESS.md` | 🟡 run by us; not by an outsider |

## What blocks submission

1. **Demo recording** (G3, S7, S9): a failed gate means not ranked.
2. **Data-change proof on World Bank data** (P3, PS1 extra).
3. **One clean-machine test / outsider run** (G2): verify reproducible fresh install instructions on an external machine.
4. **Connecting Friend's Snowflake & Cloud/Local Gemma**: hook up credentials to `.env` for final end-to-end video recording.

