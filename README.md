# DataMind — talk to your data

Ask a question in plain language; get an answer **computed by SQL in Snowflake**,
explained by **Gemma 4**, with the executed query, the Snowflake query ID and the
result rows shown beside it. If the question is ambiguous, unanswerable from the
data, or unsafe, DataMind says so instead of guessing.

Built for ZeroDay OSS Hacktoberfest 2026 — PS1 "DataMind: Talk to Your Data".

> **Status: skeleton.** Interfaces, configuration, Snowflake setup scripts, the
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
```

## Setup

### Prerequisites

- Python 3.10+ (CI tests 3.11 and 3.12)
- A Snowflake account — a [30-day trial](https://signup.snowflake.com) needs only an email
- Gemma 4 via **one** of:
  - [Ollama](https://ollama.com) (local; Gemma 4 needs a recent version — check the
    [library page](https://ollama.com/library/gemma4)), or
  - a free [Google AI Studio](https://aistudio.google.com) API key (hosted)

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

### 3. Gemma 4

Local:

```bash
ollama pull gemma4:e4b
# .env: DATAMIND_LLM_BACKEND=ollama, OLLAMA_MODEL=gemma4:e4b
```

Hosted:

```bash
# .env: DATAMIND_LLM_BACKEND=ai_studio, GOOGLE_API_KEY=..., AI_STUDIO_MODEL=<id from AI Studio's model list>
```

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
| `DATAMIND_LLM_BACKEND` | `ollama` or `ai_studio` | `ollama` |
| `OLLAMA_MODEL` / `OLLAMA_HOST` | local model and server | `gemma4:e4b` / `http://localhost:11434` |
| `AI_STUDIO_MODEL` / `GOOGLE_API_KEY` | hosted model and key | `gemma-4-31b-it` (verify) / — |
| `SNOWFLAKE_*` | connection; see `.env.example` | — |
| `DATAMIND_CONFIG_DIR` | alternative dataset config directory | `config/datasets` |

Switching datasets is configuration only; see [`docs/DATASETS.md`](docs/DATASETS.md#adding-a-dataset).

## Datasets and licences

TPC-H SF1 from Snowflake sample data (used in place, not redistributed) and Our World in
Data energy (CC BY 4.0). No data files are committed. Full details: [`docs/DATASETS.md`](docs/DATASETS.md).

## Evaluation path for judges

_TODO before submission:_ either (a) a judge-run path — trial account + `00_setup.sql`
+ Ollama, ~15 minutes — or (b) recorded evidence from our run: eval report with
Snowflake query IDs in `eval/results/` and the demo video.

## Tested environment

| | |
|---|---|
| OS / hardware | _TODO_ |
| Python | _TODO_ |
| Ollama version / Gemma variant / quantization / model file size | _TODO_ |
| Peak RAM, median answer latency | _TODO_ |
| Snowflake edition / cloud region | _TODO_ |

## Testing results and known limitations

_TODO: summary of the latest `eval/results/` report — pass rate by category,
including failures. Do not claim results that were not measured._

Known limitations (current):

- Agent pipeline not implemented yet.
- Snowflake setup scripts have not been executed by the maintainers yet.
- The AI Studio model id for Gemma 4 is unverified.

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
| `model "gemma4:e4b" not found` | `ollama pull gemma4:e4b`; upgrade Ollama |

## Licence

MIT — see [`LICENSE`](LICENSE). Datasets and model weights carry their own licences.
