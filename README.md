# PS1 — DataMind: Talk to Your Data

## Working backend and team setup

The implemented FastAPI backend lives in [`datamind-backend/`](datamind-backend/).
It uses local **Gemma 3 12B**, Snowflake **TPC-H SF1**, and real **UCI Wine Quality**.
It supports aggregates, two-cohort comparisons, subset percentages and pooled-average
analysis with SQL, query IDs and calculation evidence.

- [Backend installation and launch](datamind-backend/README.md)
- [Frontend API contract](datamind-backend/UI_HANDOFF.md)
- [Connect a teammate's laptop to Snowflake](datamind-backend/TEAM_ACCESS.md)
- [Measured results and remaining live-verification limits](datamind-backend/VALIDATION.md)

The backend has 85 passing automated tests, 12/12 local UCI answer checks and 6/6
TPC-H semantic-plan checks. The full 18-case live Snowflake run is incomplete;
two live cases passed before its process exited. See the validation record.

The sections below document the original `src/datamind/` skeleton and its design.
Use the backend links above for the implemented demo and current setup.

> **Problem statement (ZeroDay OSS Hacktoberfest 2026, PS1).** Organizations hold large
> amounts of data, but getting answers from it usually takes SQL skills or hours of manual
> searching, so the people who understand the questions best are often the least able to
> reach the data. Build an AI-powered data experience where people ask questions in everyday
> language and get answers grounded in the real data, with enough explanation (query, rows,
> gaps) to trust them. Required technology: **Snowflake** for data and querying, **Google
> Gemma** for the AI task, delivered as reusable open source.

## DataMind — our solution

Ask a question in plain language; get an answer **computed by SQL in Snowflake**,
explained by **Gemma 4**, with the executed query, the Snowflake query ID and the
result rows shown beside it. If the question is ambiguous, unanswerable from the
data, or unsafe, DataMind says so instead of guessing.

Built for ZeroDay OSS Hacktoberfest 2026 — PS1 "DataMind: Talk to Your Data".

> **Legacy `src/datamind/` status: skeleton.** Interfaces, configuration, Snowflake setup scripts, the
> evaluation set and docs are in place. The agent pipeline is not implemented yet
> (`NotImplementedError` in `src/datamind/`). See [`docs/COMPLIANCE.md`](docs/COMPLIANCE.md)
> for what is done and what is not.

## How it works

```
question → Gemma 4 classifies → Gemma 4 writes SQL → guard checks SQL
        → Snowflake runs it (read-only role) → Gemma 4 explains the rows
        → code verifies every number in the answer appears in the rows
```

Details, diagram and the role of each technology: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Repository layout

```
config/datasets/     one YAML per dataset (tables allowlist, joins, glossary, limits)
snowflake/           setup SQL: read-only role, XS warehouse, credit cap, data loads
src/datamind/        agent pipeline, Gemma backends, SQL guard, Snowflake client, UI
eval/                question set with hand-written reference SQL and expected results
tests/               unit tests (+ executable spec for the SQL guard)
docs/                architecture, datasets & licences, compliance tracker
team/                who owns what, task lists, order of work
```

## Setup

### Prerequisites

- Python 3.10+ (CI tests 3.11 and 3.12)
- A Snowflake account — a [30-day trial](https://signup.snowflake.com) needs only an email
- A free [Google AI Studio](https://aistudio.google.com/apikey) API key for Gemma 4 (hosted, default)
- Optional: [Ollama](https://ollama.com) to run Gemma 4 locally instead

### 1. Install

```bash
git clone https://github.com/Srujanmirji/DataMind.git
cd DataMind
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env        # then edit .env
```

### 2. Snowflake

1. In Snowsight, open a worksheet as `ACCOUNTADMIN` and run [`snowflake/00_setup.sql`](snowflake/00_setup.sql)
   (replace the placeholder password first). The last statement should return `150000`.
2. Optional second dataset: follow [`snowflake/10_load_owid_energy.sql`](snowflake/10_load_owid_energy.sql).
3. Put the account identifier, user and password in `.env`.

### 3. Gemma 4 (Gemini API)

```bash
# .env
DATAMIND_LLM_BACKEND=ai_studio
GOOGLE_API_KEY=<your free key>
AI_STUDIO_MODEL=gemma-4-26b-a4b-it   # confirm in AI Studio's model list
```

The free tier is rate-limited per Google Cloud project; each question uses up to
3–5 model calls (classify, SQL, repairs, explain). Check current limits on AI
Studio's rate-limit page.

**Data handling:** on this backend the question, the schema description and the
capped result rows are sent to Google. Use datasets you are allowed to share
with a third-party API. To keep everything local, switch to Ollama:
`ollama pull gemma4:e4b` and set `DATAMIND_LLM_BACKEND=ollama`.

Model licence: confirm the terms on Google's official Gemma 4 model card before use.

### 4. Run

```bash
streamlit run src/datamind/app.py   # UI
pytest -q                           # tests
datamind-eval --dataset tpch        # evaluation (not yet implemented)
```

## Configuration

| Variable | Purpose | Default |
|---|---|---|
| `DATAMIND_DATASET` | dataset file under `config/datasets/` | `tpch` |
| `DATAMIND_LLM_BACKEND` | `ai_studio` or `ollama` | `ai_studio` |
| `AI_STUDIO_MODEL` / `GOOGLE_API_KEY` | hosted model and key | `gemma-4-26b-a4b-it` / — |
| `OLLAMA_MODEL` / `OLLAMA_HOST` | optional local model and server | `gemma4:e4b` / `http://localhost:11434` |
| `SNOWFLAKE_*` | connection; see `.env.example` | — |
| `DATAMIND_CONFIG_DIR` | alternative dataset config directory | `config/datasets` |

Switching datasets is configuration only; see [`docs/DATASETS.md`](docs/DATASETS.md#adding-a-dataset).

## Datasets and licences

TPC-H SF1 from Snowflake sample data (used in place, not redistributed) and Our World in
Data energy (CC BY 4.0). No data files are committed. Full details: [`docs/DATASETS.md`](docs/DATASETS.md).

## Evaluation path for judges

_TODO before submission:_ either (a) a judge-run path — Snowflake trial + `00_setup.sql`
+ a free AI Studio key, ~15 minutes, no payment details — or (b) recorded evidence from
our run: eval report with Snowflake query IDs in `eval/results/` and the demo video.

## Tested environment

| | |
|---|---|
| OS / hardware | _TODO_ |
| Python | _TODO_ |
| Gemma variant / API model id / date tested | _TODO_ |
| Median answer latency, model calls per answer | _TODO_ |
| Snowflake edition / cloud region | _TODO_ |

## Testing results and known limitations

_TODO: summary of the latest `eval/results/` report — pass rate by category,
including failures. Do not claim results that were not measured._

Known limitations (current):

- Agent pipeline not implemented yet.
- Snowflake setup scripts have not been executed by the maintainers yet.
- Gemma 4 support for system instructions and JSON mode on the Gemini API is unverified.
- Free-tier rate limits bound how many questions per minute the demo can answer.

## Reproduce the demo

_TODO: exact question list and steps used in the recording._

## Technical contribution

_TODO (2–3 sentences): e.g. a config-driven NL→SQL agent whose answers are
verified against the result rows, with an evaluation harness that compares every
answer to hand-written ground-truth SQL._

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| `Dataset config not found` | `DATAMIND_DATASET` doesn't match a file in `config/datasets/` |
| Snowflake `250001` / auth errors | Wrong account identifier format — use `orgname-accountname` |
| `Object does not exist` on sample data | Run step 1 of `00_setup.sql`; check `IMPORTED PRIVILEGES` grant |
| Warehouse suspended unexpectedly | Resource monitor quota reached — raise `CREDIT_QUOTA` |
| Gemini API `429 RESOURCE_EXHAUSTED` | Free-tier rate limit; wait, or reduce model calls per question |
| Gemini API `404 model not found` | `AI_STUDIO_MODEL` doesn't match an id in AI Studio's model list |
| Gemini API `400` mentioning system/developer instruction or JSON mode | Not supported for this model; see `ai_studio_backend.py` TODO |
| `model "gemma4:e4b" not found` (Ollama) | `ollama pull gemma4:e4b`; upgrade Ollama |

## Licence

MIT — see [`LICENSE`](LICENSE). Datasets and model weights carry their own licences.
