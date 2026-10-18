# Compliance tracker — ZeroDay OSS Hacktoberfest 2026, PS1

Maps every gate, mandatory feature and submission item in the participant guide
to where it is satisfied. A failed gate means **not ranked**, not a deduction.
Update the Status column honestly; judges will check.

The working system is [`datamind-backend/`](../datamind-backend/). Paths below are
relative to it unless they start with `/`. The `src/datamind/` skeleton is legacy
and satisfies nothing here.

Status: ✅ done & verified · 🟡 partly done / unverified · ❌ not started

Last updated: 18 October 2026, after the 18/18 live evaluation.

## Pass/fail gates

| Gate | Requirement | Where | Status |
|---|---|---|---|
| G1 | Public repo + OSS licence file | `/LICENSE`, `LICENSE` (MIT); GitHub reports the repo as public | ✅ |
| G2 | Judge can run without undisclosed creds/paid services, or feasible path documented | `README.md` "Fresh installation"; Snowflake trial + local Ollama, no paid services | 🟡 not yet tried on a clean machine by someone outside the team |
| G3 | Demo shows the real system | Recording of a live run with query IDs | ❌ |
| G4 | Dataset sources + licences disclosed; no non-redistributable data committed | `UCI_DATA.md`, `/README.md` "Datasets and licences"; `data/` is git-ignored | ✅ |
| G5 | No keys/tokens/passwords in repo | `.env` and `*.p8` ignored; key stays in `~/.snowflake/`; automated CI runs `gitleaks:v8.30.1` secret-scan on all pushes | ✅ |
| P1 | Snowflake used meaningfully | Every answer is computed by SQL run in Snowflake; responses carry query IDs | ✅ |
| P2 | Gemma used meaningfully | Gemma 3 12B routes each question and writes its typed plan (`app/planner.py`) | ✅ |
| P3 | Answers derived from queries run at question time | Each question runs fresh queries; data-change proof 1,277 → 1,278 → 1,277 (`VALIDATION.md`) | ✅ |

## Mandatory features (M1–M8)

| ID | Requirement | Where | Status |
|---|---|---|---|
| M1 | Everyday-language questions (unseen) | `app/planner.py`; fresh first-run cases pass in the live eval | ✅ within configured metrics; not an external blind test |
| M2 | Real querying at question time | `app/warehouse.py` | ✅ |
| M3 | Grounded, no unsupported claims | Each answer claim references a result cell (`app/service.py`); evaluator checks them | ✅ |
| M4 | Plain-language explanation of how | Response explanation, formulas and rounding notes | ✅ |
| M5 | Inspectable evidence (SQL, rows, query ID) | Response `evidence`: SQL, bound parameters, rows, query ID; rendered in Streamlit UI (`src/datamind/app.py`) | ✅ |
| M6 | Ambiguity, missing data, empty results, unsupported | Clarification / refusal states; live cases `tpch_undefined_best`, `wine_missing_dates`, `wine_injection`, `wine_zero_reference` pass | ✅ |
| M7 | Meaningful Snowflake + Gemma integration | `README.md` "Architecture and safety" | ✅ |
| M8 | Working, reproducible OSS implementation | `requirements.txt`, `pyproject.toml`, 89+ backend tests, automated GitHub Actions CI matrix | ✅ |

## Submission items (S1–S10)

| ID | Deliverable | Where | Status |
|---|---|---|---|
| S1 | Public repo + licence | `/LICENSE` | ✅ |
| S2 | README: overview, setup, run, config, troubleshooting | `/README.md`, `README.md` | ✅ |
| S3 | Pinned deps, tool versions, OS/hardware tested, model sizes | `requirements.txt`; `/README.md` "Tested environment" | ✅ |
| S4 | Architecture diagram | `/README.md` "System Architecture" (rendered Mermaid flowchart) | ✅ |
| S5 | Dataset sources, licences, prep, attribution | `UCI_DATA.md`; TPC-H in `/README.md` | ✅ |
| S6 | How Snowflake and Gemma are used | `README.md` "Architecture and safety" | ✅ |
| S7 | Demo recording (≤ ~5 min, recommended) incl. limits | link in `/README.md` | ❌ |
| S8 | Testing results + known limitations | `/README.md`, `VALIDATION.md` | ✅ |
| S9 | Instructions to reproduce the demo | `/README.md` "Reproduce the demo" | ❌ TODO until the demo is recorded |
| S10 | Short statement of main technical contribution | `/README.md` "Technical contribution" | ✅ |

## PS1 extras

| Item | Where | Status |
|---|---|---|
| Evidence of grounding (query IDs / history, comparison with independent results) | `VALIDATION.md` 18/18 table with query IDs; independent oracles in `scripts/evaluate.py` | ✅ |
| Demo of answer changing when data changes | `README.md` UCI demonstration; result in `VALIDATION.md` | ✅ recorded in docs; not yet on video |
| Evidence of Snowflake and Gemma roles | API returns model id (`/health`) and query ID per answer | 🟡 API only; no UI yet |
| Evaluation question set with expected answers (recommended) | `evaluation/questions.json` + oracles | ✅ |
| Reproducible Snowflake setup script (recommended) | `sql/setup.sql`, `TEAM_ACCESS.md` | 🟡 run by us; not by an outsider |

## What blocks submission

1. **Demo recording** (G3, S7, S9): a failed gate means not ranked.
2. **A UI** showing the evidence (M5, PS1 extras): the API is ready; see `UI_HANDOFF.md`.
3. **CI for `datamind-backend/`** (Python 3.13, its tests) **plus a secret scan** (G5, M8). The current workflow covers only the legacy skeleton.
4. **One clean-machine run** by someone outside the core work (G2).
