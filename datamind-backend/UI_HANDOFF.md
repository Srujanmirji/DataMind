# DataMind: frontend integration handoff

Multi-step support requires backend **0.2.0**. Check `GET /health.version` after
the private-key unlock/restart described in README.md. The old running process
does not automatically reload these changes.

Connect the existing UI to the running local backend. The UI does not need Gemma
or Snowflake credentials. Backend inference and querying happen server-side.

**Base URL:** `http://127.0.0.1:8000`
**Interactive API:** `http://127.0.0.1:8000/docs`
**OpenAPI:** `http://127.0.0.1:8000/openapi.json` (also saved as `openapi.json`).

## Dataset selector

Call `GET /datasets`. Use `datasets[].id` as the selected value and `name` as its
label. Descriptions, metric definitions, licence notes and limitations are included.

| ID | Source | Good starter questions |
|---|---|---|
| `tpch_orders` | Snowflake TPC-H SF1 order data | How many orders are in the dataset? / Which five customer nations have the highest total order value? |
| `uci_wine_quality` | Real UCI Wine Quality, 6,497 red/white samples | How many wine samples have a quality score of at least 7? / Show sample count and average quality by wine type. |

Do not mix the datasets' example questions or metrics. Send the selected ID on
every request; omission defaults to TPC-H. The cafe dataset has been removed.

## Submit a question

```http
POST /questions
Content-Type: application/json

{"dataset_id":"uci_wine_quality","question":"How many wine samples have a quality score of at least 7?"}
```

```javascript
const response = await fetch(`${backendUrl}/questions`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ dataset_id: selectedDatasetId, question }),
});
const result = await response.json();
if (!response.ok) {
  const validationMessage = Array.isArray(result.detail)
    ? result.detail.map((item) => item.msg).join("; ")
    : undefined;
  throw new Error(result.error?.message ?? validationMessage ?? "Request failed.");
}
// Render result.status first, then its answer/explanation/evidence/warnings.
```

Question length: 3–2,000 characters, with at least three non-space characters.
Do not send chat history or extra properties; unknown request properties are rejected.

## Response states

HTTP 200 can mean any of these domain states:

| `status` | UI behaviour |
|---|---|
| `answered` | Show answer, calculation explanation, evidence table and limitations |
| `empty` | Show the empty-data message; preserve evidence, such as COUNT=0 |
| `needs_clarification` | Show `answer` as the clarification; user submits a complete revised question |
| `unsupported` | Show `answer` explaining the limitation; do not present it as an outage |

Clarification/unsupported responses have an empty evidence list and may omit
`explanation`. There is no conversational memory or streaming endpoint yet.

Non-200 errors have `{ "status": "error", "error": { "code": "...", "message": "..." } }`,
except input-validation errors (422), which use FastAPI's `detail` array.

| HTTP | Meaning |
|---|---|
| 401 | Configured API key missing or invalid |
| 404 | Unknown dataset or missing saved run |
| 422 | Invalid request or run ID |
| 429 | Another question is running; only one active query pipeline is allowed |
| 502 | Invalid model plan or unexpected query/calculation result; show the supplied error message |
| 503 | Gemma/Snowflake unavailable or query failed |
| 504 | Gemma timed out |

## Fields to render

- `answer`: verified result summary. Render as text, not raw HTML.
- `explanation.metrics`: metric definitions; `filters`, `grouped_by`, `sort` and
  `method` explain the actual computation. `source` gives provenance.
- `evidence[]`: each entry has executed SQL, bound `parameters`, `query_id`,
  `columns`, `rows`, `row_count`, `truncated`, and `duration_ms`.
- `claims[]`: each claim references an evidence ID, zero-based `row_index`, column
  name, metric and verified value. Useful for highlighting answer evidence.
- `warnings[]`: dataset limitations and truncation notices; keep these accessible.
- `run_id`: use `GET /runs/{run_id}` to reopen the exact saved answer and evidence.

Build the evidence table using `columns` as headers and `rows` as cell arrays.
SQL is a parameterized template: display SQL **and its parameters together**.
Offer copy actions for query ID and SQL/evidence. Do not execute SQL in the browser.

Raw query counts are JSON integers; numeric calculation-table cells (including
target/reference counts) and fixed-point decimals are **JSON strings** to preserve
precision; missing values are `null`. Do not render null as zero or round decimal
strings silently. Charts must use verified result rows and label any conversion.
`row_count` is the displayed result-row count, not the source observation count.
`duration_ms` measures database execution including connection setup, not total
Gemma/API latency. Answer prose summarizes at most the first five rows; the full
returned evidence table can contain more. Respect `truncated=true`.

## Loading and connection behaviour

- Disable repeated submission while a request is pending and show a loading state.
- Local Gemma may take a few minutes; a plan can get one repair attempt. The backend
  model timeout is 180 seconds per attempt. Do not use a short fetch timeout.
- Do not automatically retry POST: it can trigger another warehouse query.
- `GET /health` is liveness only. `key_loaded=true` does not independently prove
  Snowflake/model availability; an actual question verifies the full path.
- Keep the backend terminal and Ollama running during integration and the demo.

## CORS and teammates' machines

Allowed frontend origins are currently **`http://localhost:3000`** and
**`http://localhost:5173`**. `http://127.0.0.1:3000` is a different origin. To add
an origin, update the JSON `CORS_ORIGINS` list in the backend `.env` and restart it.

The backend binds to `127.0.0.1`, so this URL works only on the Mac running it.
For immediate testing, run the frontend on that same Mac. A teammate's localhost
points to their own computer. Remote access needs a separate authenticated
deployment/network setup; this handoff does not expose the local server publicly.

No API key is configured for current loopback development. If one is configured
later, send `X-API-Key`. Do not put a long-lived deployment secret in publicly
shipped frontend code; use a suitable server-side proxy/authentication layer.

## Data provenance and demo

TPC-H sample data is synthetic benchmark data hosted in Snowflake. Wine Quality
is real UCI data, CC BY 4.0, cited in `UCI_DATA.md`; retain attribution in the product's
data-source view. Wine results describe these samples, not all wines.

The wine API uses a labelled working copy. The successful change demonstration
showed **1,277 -> 1,278 -> 1,277** samples with quality >= 7, with different
Snowflake query IDs. The original source table remained unchanged and the working
score was restored. Proof: `data/change-demo/REPORT.md` and `proof.json`.


## Verified integration examples

All 13 live checks in the latest integration run passed: both datasets, count and
ranking/aggregate correctness, empty states, clarification, refusal, validation,
unknown dataset, saved evidence and both configured CORS origins.

Real response bodies are included in `examples/responses/` for the UI team:

- `uci_count.json`: scalar answer (6,497 observations).
- `uci_groups.json`: grouped rows and decimal means, independently checked.
- `uci_empty.json`: empty-data domain response with query evidence.
- `uci_unsupported.json`: refusal without query evidence.
- `tpch_clarification.json`: clarification without query evidence.
- `invalid_input.json`: HTTP 422 validation body.
- `unknown_dataset.json`: HTTP 404 error body.

These are captured examples for UI development, not canned backend answers.
Live endpoints always plan and query at question time. UCI aggregates retain
CC BY 4.0 attribution from UCI_DATA.md. Example query/run IDs are evidence IDs,
not credentials. No keys, private-key files, passphrases or .env are needed by UI.


## Multi-step responses (0.2.0)

The request shape is unchanged. Examples:

- TPC-H: "From 1993 to 1994, how did the number of orders change in absolute and percentage terms?"
- Wine: "Among white wines, what percentage of samples scored 8 or higher?"
- Wine: "Which wine types have average residual sugar above the overall average residual sugar?"

Render `plan.analysis`: aggregate, compare, share, or above_average. Multi-step
answers additionally include `analysis.target_filters` and `analysis.reference_filters`.
Show both scopes so the user can check the intended denominator/baseline.

For multi-step answers, `evidence` contains:

1. `query_1`: target aggregate or grouped means, with executed SQL and query ID.
2. `query_2`: baseline/population aggregate, with its own SQL and query ID.
3. `calculation_1`, `kind=calculation`: final table, formulas, and `inputs` linking
   each output row to the input evidence cells. Its `sql` and `query_id` are null;
   calculations are performed in Python, not an additional Snowflake execution.

Build charts from the **calculation table** for multi-step answers. Query tables
remain available for verification. Keep null percentages visible as "Undefined"
with the warning; do not substitute zero. Derived numeric values are decimal strings
rounded half-up to six places; threshold comparisons use original precision.

Comparisons use target minus baseline and divide by the baseline for percent change.
A share divides numerator by denominator. Above-average results use the overall mean
of underlying observations, rather than the mean of the group means. `claims` can
reference calculation evidence and calculated/grouping columns; resolve evidence
by ID and column rather than assuming query_1 or a configured source metric.

An incomplete grouped population (over 100 groups) returns HTTP 422 with an error
message asking for narrower filters. Upstream/plan errors return 502; they are not
successful answers. Local inference includes routing plus planning, with one bounded
repair attempt, so keep the pending state until completion. Check `/health.version`
is `0.2.0` after restart. Older snapshots below examples/responses are aggregate
responses captured from the previous live server; do not treat them as multi-step tests.


The configured model is now `gemma3:12b`. A multi-step response includes two SQL
executions and deterministic calculations; model routing/planning happen before
those queries. Keep a clear pending indicator while waiting. All inference remains
local to the backend Mac. No additional model integration is needed in the frontend.
