# DataMind backend

For another laptop, use [TEAM_ACCESS.md](TEAM_ACCESS.md) to create individual
Snowflake access and configure that person's own key. Frontend developers should
start with [UI_HANDOFF.md](UI_HANDOFF.md).

Local FastAPI backend for PS1: Gemma interprets questions, a deterministic Python
compiler builds approved SQL, and Snowflake computes answers at question time.
Each answer contains SQL, bound parameters, result rows, a Snowflake query ID,
and references from answer claims to result cells. No frontend is included.

## Run on this Mac

The environment and non-secret `.env` settings have already been created.
The private key remains outside the project in `~/.snowflake/datamind_key.p8`.

1. Keep Ollama running in a separate Terminal tab:

   ```bash
   ollama serve
   ```

   If it says the address is in use, Ollama may already be running. Verify with
   `curl http://127.0.0.1:11434/api/tags`. The installed model is `gemma3:12b`.

2. In a new Terminal tab:

   ```bash
   cd /Users/srujanmirji/Codex/datamind-backend
   source .venv/bin/activate
   python run.py
   ```

3. Enter the private-key passphrase when prompted (typing is invisible).
   It is held in process memory only; it is never written by the application.
   Restarting the server prompts again. Stop with Ctrl+C.

4. Open http://127.0.0.1:8000/docs to try the API. Use POST `/questions`,
   click **Try it out**, and submit:

   ```json
   {"question": "How many orders are in the dataset?", "dataset_id": "tpch_orders"}
   ```

   The established sample count is 1,500,000. Check the returned query ID and rows
   on every run rather than treating this reference value as a cached answer.
   Startup does not validate Snowflake credentials; the first question does.

## API for the frontend team

Send your UI team **UI_HANDOFF.md**, **openapi.json**, and **examples/responses/**.
The handoff contains the verified contract and captured response states.


Base URL: `http://127.0.0.1:8000`. CORS permits `http://localhost:3000` and
`http://localhost:5173`; edit the JSON `CORS_ORIGINS` list in `.env` to change it,
including `http://127.0.0.1:3000` if that is your frontend's origin.

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness, configured model, key-loaded flag; no external calls |
| GET | `/datasets` | Available metrics, dimensions, filters, source, limitations |
| POST | `/questions` | Interpret question and execute a supported analysis |
| GET | `/runs/{run_id}` | Previously saved response and execution evidence |
| GET | `/openapi.json` | Machine-readable API description |

`POST /questions/multimodal` (audio/image input) exists in `app/multimodal.py` but is
**disabled**. It does not yet interpret audio or images: it derives the question from the
file name or a fixed prompt. It is enabled only with `ENABLE_MULTIMODAL=true`, for
development, until Gemma reads the input itself.

Example request from another Terminal tab:

```bash
curl -sS http://127.0.0.1:8000/questions \
  -H 'Content-Type: application/json' \
  -d '{"question":"Which five customer nations have the highest total order value?"}' \
  | python3 -m json.tool
```

Example browser integration (render the returned text as text, not HTML):

```javascript
const response = await fetch("http://127.0.0.1:8000/questions", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ question, dataset_id: "tpch_orders" }),
});
const result = await response.json();
if (!response.ok) {
  throw new Error(result.error?.message ?? "The backend request failed.");
}
// Render result.status, result.answer, result.explanation and result.evidence.
```

Successful HTTP responses have status `answered`, `empty`, `needs_clarification`,
or `unsupported`. Clarification/unsupported responses have no query evidence,
and no Snowflake query executes. Send a complete revised question after a
clarification; conversation memory is not implemented.

An answered response includes:

- `run_id`, question, dataset, timestamp, validated semantic `plan`.
- `answer`: summary rendered from the first five returned rows.
- `claims`: metric/value and zero-based row index/column in `query_1`.
- `explanation`: metric definitions, filters, grouping and sorting that actually ran.
- `evidence`: executed SQL template, bound `parameters`, query ID, columns, rows,
  truncation flag, row count and elapsed time (includes connection setup).
- `warnings`: dataset scope, units, and any result truncation/history failure.

Fixed-point decimal values are JSON **strings**, preserving precision. Counts
are integers. Null aggregates are unavailable values, never invented zeros.
SQL uses placeholders; inspect SQL and parameters together when reproducing it.
The compiler requests N+1 groups to detect truncation and returns only N.

Error responses use non-200 HTTP codes and
`{"status":"error","error":{"code":"...","message":"..."}}`.
Input validation uses FastAPI's standard HTTP 422 `detail` format.
Expected errors: 401 invalid configured API key, 404 unknown dataset/run,
429 another question is running, 502 invalid model plan, 503 model/Snowflake
unavailable, and 504 model timeout. Disable the submit button while a request is
pending and allow a few minutes for local inference. Do not automatically retry
POST requests: a retry can create an additional warehouse query.

## Supported questions and scope

- How many orders are in the dataset?
- Which five customer nations have the highest total order value?
- Show order counts by region.
- What was the average order value in 1995?
- How many orders were placed in France during 1995?
- Count distinct customers with orders by customer segment.

Metrics: order count, total order value, average order value, distinct customers
with orders. Dimensions: customer nation/region/segment, order year/month/status/
priority. Filters support equality, inequality, comparisons, inclusive between,
and in-lists combined with AND. Explicit calendar dates are supported.

This is an initial scoped backend, not the complete hackathon submission:

- No TPC-H product/line-item analysis, raw records, OR filters, cross-query comparisons,
  derived percentages, forecasts, document retrieval, or conversational follow-ups.
- No implied equivalence between revenue/profit and order value. Ambiguous terms
  should produce clarification; inspect the interpreted plan for semantic errors.
- Gemma can still misinterpret a question even when its JSON is valid. Add an
  independently verified evaluation set before making broad accuracy claims.
- Two dataset configurations are supplied: TPC-H orders and real UCI Wine Quality.
  The second dataset and reversible data-change runner require `python run.py --demo`
  to provision and verify against Snowflake. Public repo and recording remain
  submission work. Shared Snowflake sample tables cannot be updated by consumers.

## Architecture and safety

```text
UI -> FastAPI -> Gemma structured plan -> Pydantic + semantic validation
   -> deterministic SQL compiler -> Snowflake reader -> verified rows
   -> deterministic answer + explanation + evidence -> UI
```

The API selects a dataset by `dataset_id`, with one shared concurrency lock. Each dataset can
configure its own database/schema, metrics, joins, count metric and empty-state message.
Gemma is central to interpreting unseen questions. It cannot submit raw SQL:
the plan contains only configured names, operators, bounded limits and values.
SQL expressions come from a trusted local configuration, identifiers are
validated, and filter values are bound using the Snowflake connector.
Data source joins preserve one row per order under TPC-H keys. Group limits
apply after aggregation. Query and queue timeouts limit warehouse execution;
a small result limit alone does not guarantee low compute cost.

Fresh Snowflake connections use the configured reader role and disable secondary
roles. The current imported-privileges grant allows reading the shared sample
database, not only TPCH_SF1. For deployment, create a dedicated service user with
only the intended role and review PUBLIC-role privileges. The development key is
currently registered on your existing user; merely choosing a role is not a
replacement for a dedicated deployment identity.

`run.py` binds to **127.0.0.1**, one process and one active question at a time.
This is a local development server. Do not expose it publicly as-is. Optional
`API_KEY` in `.env` protects datasets/questions/history with an `X-API-Key` header;
CORS is an origin policy, not authentication. Questions and result evidence are
saved locally under ignored `data/runs.sqlite3`; stop the server and delete that
file to clear history. It has no retention policy yet. Model planning stays on
the configured Ollama host; Snowflake execution uses the network.

## Files

| File | Responsibility |
|---|---|
| `run.py` | Unlock private key once and launch local API |
| `app/main.py` | HTTP endpoints, CORS, optional API key, errors |
| `app/models.py` | Strict request/plan schemas |
| `app/planner.py` | Gemma structured-output call |
| `app/compiler.py` | Validate names and compile parameterized SQL |
| `app/warehouse.py` | Execute query and capture evidence |
| `app/service.py` | Orchestration and evidence-grounded answer rendering |
| `app/store.py` | SQLite run evidence |
| `datasets/*.json` | Trusted data models and metric definitions |

To adapt to compatible data, edit a copy of the trusted dataset JSON and point
`DATASET_PATH` at it, or add its absolute path to the JSON `ADDITIONAL_DATASET_PATHS`
list in `.env`. Configure its database/schema overrides and send its dataset ID. The
configuration includes trusted SQL expressions: accept it only from developers,
never from an uploaded user file. Schema discovery is not automatic.

## Fresh installation on another machine

Tested locally on macOS / Apple M5, 16 GB RAM, Python 3.13. Current model:
Gemma 3 12B (`gemma3:12b`), about 8.2 GB download; digest begins `b92b218582c5`.
It needs about 8 GB GPU/unified memory at 8,192 context. On smaller machines set
`OLLAMA_MODEL=gemma3:4b` (3.4 GB), but expect worse answers: it scored 4/8 on our
held-out UCI evaluation versus 12/12 for 12B.
Ollama client reported version 0.31.1. Pin/model-record your own environment.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
ollama pull gemma3:12b
```

Configure your Snowflake account and **LOGIN_NAME** (which may differ from user
NAME), acquire the sample database, and provision a warehouse and reader role.
Register your public RSA key on the login user; keep your encrypted private key
outside the repository. Then run `ollama serve` and `python run.py` in separate
Terminal tabs. See `sql/setup.sql` for role grants (admin setup only).

The `.env` on this Mac contains connection identifiers but no passphrase.
`.env`, private keys, the virtual environment and run history are gitignored.
Never commit credentials. Do not copy benchmark tables into the repository.
The MIT licence covers this backend's source, not Gemma weights or dataset rights.
UCI Wine Quality remains CC BY 4.0; attribution is in UCI_DATA.md.

References:
[Google Gemma with Ollama](https://ai.google.dev/gemma/docs/integrations/ollama),
[Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs),
[Gemma model/licence](https://ollama.com/library/gemma3:12b),
[Snowflake sample data](https://docs.snowflake.com/en/user-guide/sample-data),
[Snowflake key-pair authentication](https://docs.snowflake.com/en/user-guide/key-pair-auth).

## Test and troubleshoot

```bash
python -m pytest -q
ruff check .
```

Tests use explicit fixture data and service doubles; they do not claim to validate
live Snowflake or Gemma. Ground-truth aggregation tests execute compiled SQL
against hand-calculated relational fixtures. A separate live Gemma planner smoke
test is in `scripts/check_gemma.py`; it never contacts Snowflake.

- **Cannot unlock key:** check the private-key passphrase, not the Snowflake password.
- **JWT invalid user:** `.env` needs LOGIN_NAME from `DESCRIBE USER`, not NAME.
- **Cannot reach Ollama:** run `ollama serve`; keep that tab running.
- **Invalid model plan:** no query executes. Rephrase and inspect supported metrics.
- **Snowflake error:** check the warehouse, role grants, account/login and query timeout.
- **Port 8000 occupied:** stop the existing local server before restarting.
- **CORS error:** allow the frontend's exact origin in `.env`, then restart.


## Second dataset: real UCI Wine Quality

The cafe prototype has been removed. The second dataset is now **UCI Wine Quality**,
with all **6,497 original observations**: 1,599 red and 4,898 white wines. All 11
physicochemical measurements and the sensory quality score are preserved.
Source: https://archive.ics.uci.edu/dataset/186/wine+quality

Licence: **CC BY 4.0**. Full citation, attribution, source SHA-256 and adaptation
notes are in `UCI_DATA.md`. Original archive and normalized CSV are downloaded under
ignored `data/uci/`; no manual download or additional package is needed.

Dataset ID: **`uci_wine_quality`**. Normal questions query the labelled working
copy, which is restored to original UCI values after each successful demonstration.
The original source table is independently compared with all downloaded rows.

| Object | Purpose |
|---|---|
| `DATAMIND_DEMO.UCI.WINE_QUALITY_SOURCE_V1` | Preserved original source observations |
| `DATAMIND_DEMO.UCI.WINE_QUALITY_WORKING_V1` | Queryable working copy; only table changed in the demo |
| `scripts/uci_wine.py` | Hash-verified download, parsing and transactional import |
| `datasets/uci_wine_quality.json` | Dataset-specific semantics, no application-code rewrite |
| `scripts/demo.py` | Reversible before/after proof with full execution evidence |

### Run the complete UCI import and demonstration

Stop the existing backend with Ctrl+C in its terminal, then run:

```bash
~/Codex/datamind-backend/.venv/bin/python ~/Codex/datamind-backend/run.py --demo
```

Enter the existing private-key passphrase locally once. The command automatically:

1. Verifies/downloads the source archive and records provenance in `data/uci/manifest.json`.
2. Opens an explicit ACCOUNTADMIN setup session. Creates only the fixed demo database,
   schema and source/working tables; refuses to edit unmarked or mismatched tables.
3. Loads all original observations transactionally and compares **every source value**.
   Existing matching tables are reused; no table is replaced or dropped.
4. Grants the application reader only USAGE on this database/schema and SELECT on
   the working table. No UPDATE/INSERT/DELETE is granted to the reader.
5. Asks: **How many wine samples have a quality score of at least 7?**
6. Temporarily changes the first source sample with score 6 to score 7 in the working
   copy only. Repeats the identical question and checks identical SQL/parameters,
   a new Snowflake query ID, and an increase of exactly one.
7. Restores the score after a confirmed mutation, including if the after-query fails.
   Checks the restored answer and all source/working observations again.
8. Saves `data/change-demo/proof.json` and `REPORT.md`, closes the admin connection,
   and starts the ordinary read-only API on port 8000.

Expected counts, independently computed from the real downloaded source:
**1,277 -> 1,278 -> 1,277**. These are expectations until the live Snowflake run
finishes; check the generated report for actual query IDs and observed answers.
The threshold 7 is our explicit analysis rule, not a binary label supplied by UCI.
The temporary quality adjustment is artificial and disclosed as a demo change;
it is not represented as a correction to the research dataset.

The proof uses the real `/questions` application route through FastAPI's in-process
client, real Gemma inference and real Snowflake queries. Responses are not mocked.
The source CSV is used for ingestion and independent ground truth, never to answer
API questions. No HTTP mutation/admin endpoint is exposed.

If setup, mutation or restoration fails, the proof status is failed rather than
passed. Inspect `proof.json` before retrying. Do not run concurrent demos or edit
these working rows during the test. Reports are invalidated at startup, before
provisioning, so a failed rerun cannot leave an old successful report as current.
Each restart requires a local key unlock; no passphrase is persisted.
Normal `python run.py` does not load or modify datasets; use `--demo` explicitly.

### Ask UCI questions after import

```bash
curl -sS http://127.0.0.1:8000/questions \
  -H 'Content-Type: application/json' \
  -d '{"dataset_id":"uci_wine_quality","question":"How many wine samples have a quality score of at least 7?"}'
```

Other examples: "What is the average quality by wine type?", "How many red wine
samples are there?", and "What is the average alcohol content for white wines?".
Supported UCI metrics: sample count, average quality, average alcohol, average
residual sugar; grouping/filtering by wine type and integer quality score.
Dates, brands, grape varieties, prices and causal conclusions are unsupported.

`GET /datasets` lists `tpch_orders` and `uci_wine_quality`. Questions without a
`dataset_id` still select TPC-H. The backend must be restarted to pick up this
replacement if it is still running the previous version.


## Multi-step analysis (0.2.0)

Both existing datasets remain enabled. A question may now request one of three
bounded analyses, in addition to ordinary aggregates:

- Compare one metric across two cohorts/periods: values, signed difference and
  percent change relative to an explicit baseline.
- Calculate a subset's percentage of a population using a count/additive total.
- Find groups whose configured mean exceeds the pooled, row-weighted mean of the
  same metric and population. This does not average group averages.

Gemma classifies the request and creates a typed, validated plan. Python compiles
and executes two parameterized, read-only queries, then calculates with Decimal.
Each response includes both source query IDs, target/reference filters, formulas,
cell references, and a calculation evidence table. Percentage change is undefined
when the baseline is zero; return null and a warning. No infinite/NaN result is used.

Limits: one metric per multi-step analysis, two query scopes, at most 100 complete
groups. Arbitrary analysis chains, forecasts and conversational follow-ups remain
unsupported. The two SQL executions are separate snapshots; do not edit data during
comparisons. Final prose is rendered from verified cells. Evidence validates the
calculation, while model interpretation of a new question can still be wrong: review
its displayed filters and baseline.

### Evaluate and replace the running backend

```bash
~/Codex/datamind-backend/.venv/bin/python ~/Codex/datamind-backend/run.py --evaluate --replace
```

Enter your existing private-key passphrase locally. The command runs the evaluation
against real Gemma and Snowflake before replacing the verified DataMind listener.
Another application's listener is never stopped. No data is changed by evaluation.
Results, independent ground truth and actual responses are saved under
`data/evaluations/<timestamp>/`; `latest.json` points to the newest completed run.
Failures are printed and saved rather than treated as passing checks.

The developer-authored evaluation includes regression cases used during prompt
iteration and separately marked first-run holdouts. It is not an external blind
benchmark. Independent static SQL verifies TPC-H, and direct Python arithmetic on
the original downloaded UCI observations verifies wine answers. Expected answers
and oracle code are never included in model prompts.

Latest live result (18 October 2026): **18/18** with Gemma 3 12B and Snowflake.
See [VALIDATION.md](VALIDATION.md) for the run, the bug the first attempt caught,
and sample query IDs.

For private-key-free planner development, `.venv/bin/python -m scripts.evaluate`
uses real Gemma plus SQLite loaded with the original UCI data. Its reports are
explicitly labelled **NOT Snowflake** and cannot establish live warehouse integration.


The tested local configuration now uses **Gemma 3 12B**. The earlier 4B model made
filter/scope mistakes in held-out testing. The larger model is installed in Ollama;
it uses about 8 GB GPU memory at the configured 8,192-token context on this Mac.
Routing and planning are separate model calls, so inference can take tens of seconds
or longer. Keep the UI loading state visible and display scopes before interpreting
an answer. The existing server picks up this model setting on its next restart.

`python -m scripts.evaluate_plans` checks TPC-H semantic plans without warehouse
credentials. This is separate from verifying actual query results in Snowflake.
The answer evaluator checks required ground-truth columns, row cardinality and values;
additional context labels are recorded, and missing metrics/wrong values still fail.
