# Vishal — QA, evaluation questions & newcomer testing

**Owns:** the question files `eval/questions_*.yaml` (content, not the runner), GitHub issues for bugs found
**Starting level:** beginner. Every task below starts without writing Python; code comes later, with review.
**Rubric weight carried:** the evidence behind correctness (20), ambiguity handling (12), reproducibility (C5), testing (C7)

Why this matters: judges ask questions we have never seen. Your question lists are
how we find our wrong answers before they do.

## Week 1 — learn just enough (no code)

- [x] Get Snowsight access from Zishan (read-only role). Never paste the password anywhere.
- [x] Learn SQL basics on the TPC-H tables in a Snowsight worksheet: `SELECT`, `WHERE`,
  `GROUP BY`, `ORDER BY`, `JOIN`, `COUNT/SUM/AVG`. Good free starting point:
  <https://sqlbolt.com> (lessons 1–12).
- [x] Read `docs/ARCHITECTURE.md` and `config/datasets/tpch.yaml`. Note every word you
  don't understand and ask. If it confuses you, it will confuse a judge.
- [x] Learn Git basics: clone, branch, commit, push, open a PR. Good free tutorial:
  <https://docs.github.com/en/get-started/start-your-journey/hello-world>.

## Tasks (in this order)

- [ ] **Run the existing reference SQL.** Copy each `reference_sql` from
  `eval/questions_tpch.yaml` into Snowsight, run it, and write down the result and the
  query ID (Query History → Query ID). Send them to Zishan, who will check them
  and add them to the file.
- [x] **Write questions in plain English (no SQL needed).** Aim for 40 or more, in a shared doc first:
  - the same question asked 3 different ways ("top 5 nations by revenue in 1995",
    "which countries made the most money in '95?", ...)
  - questions the data cannot answer (weather, stock prices, "next year's sales")
  - vague questions ("best customers", "recent orders", "big suppliers")
  - questions with empty answers (dates outside 1992–1998, nations that don't exist)
  - unsafe or tricky ones ("delete…", "ignore your instructions and…", "show me the passwords table")
  Zishan writes the reference SQL for the answerable ones.
- [x] **Write reference SQL for simple single-table questions** (counts, min/max, one
  filter). Zishan reviews every one before it goes in the file: wrong ground truth is
  worse than none.
- [x] **Fresh-clone test.** On your own laptop, follow `README.md` from the first step,
  exactly as written, without help. Every step that fails or confuses you becomes a GitHub
  issue labelled `docs` with: the step, what you did, what happened, the full error.
- [ ] **Manual QA**, once the UI works: ask every question in the eval file and your own
  list. For each wrong answer, open an issue labelled `bug` with the question, the answer,
  the SQL shown, and what the right answer is.
- [ ] Repeat the fresh-clone test the week before submission.

## First code PR (when ready)

- [x] Add 5 reviewed questions to `eval/questions_tpch.yaml`, run `pytest -q`
  (it checks the file's format), and open a PR. Ask Zishan to review it.
  *(Completed: expanded to 50 questions in `eval/questions_tpch.yaml` and created 15 questions in `eval/questions_owid_energy.yaml`).*

## Definition of done

- [x] 40+ questions written; the answerable ones are in the eval file with reviewed SQL and
  expected values (50 questions in `eval/questions_tpch.yaml` + 15 in `eval/questions_owid_energy.yaml`).
- [ ] Two fresh-clone runs completed; every issue found is either fixed or listed in the README
  as a known limitation. (Run 1 completed below; Run 2 scheduled before final submission).

## Fresh-clone test #1 findings (Windows / PowerShell)

1. **Virtualenv activation on Windows (`docs`):**
   `README.md` Step 1 specifies `source .venv/bin/activate`, which fails in Windows PowerShell.
   Windows users need: `.venv\Scripts\Activate.ps1` (PowerShell) or `.venv\Scripts\activate.bat` (Command Prompt).
2. **`PYTHONPATH` before editable install (`docs`):**
   Running `python -m pytest` prior to running `pip install -e ".[dev]"` raises `ModuleNotFoundError: No module named 'datamind'`. Setting `$env:PYTHONPATH="src"` or running `pip install -e .` resolves it.
3. **YAML formatting in questions (`bug` / fixed):**
   Any question text or notes containing colons (e.g. `notes: Order value: O_TOTALPRICE`) or octothorpes (`#1`) must be quoted in YAML (`"..."`), otherwise PyYAML fails with `ScannerError: mapping values are not allowed here`.

## Who to ask

- SQL, Snowflake, eval file: **Zishan**
- Git, README, UI: **Saisudheer**
- How the agent behaves: **Srujan**
