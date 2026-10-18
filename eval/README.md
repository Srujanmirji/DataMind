# Evaluation

Judges score correctness against ground truth they compute themselves, on
questions you have not seen — and a Poor correctness score caps PS1 at 50.
This folder is how we find out first.

- `questions_<dataset>.yaml`: question, independent `reference_sql`, expected
  value and expected status (covers joins, multi-step, follow-ups and every M6 case).
- `datamind-eval --dataset tpch` (not yet implemented, `src/datamind/eval_runner.py`)
  runs both paths and writes a report to `eval/runs/` (git-ignored).
- Copy a verified report to `eval/results/` and summarise it in the README's
  "Testing results" section (S8). Include failures.

Rules for adding questions: write `reference_sql` by hand, never from agent
output; prefer questions whose answer you can check two ways; add at least one
question per glossary term so definitions are tested.

## Data-change test (rubric "answers change when data changes")

TPC-H sample data is read-only. Demonstrate it on `owid_energy`: ask a question,
then `UPDATE DATAMIND.OWID.ENERGY ...` as ACCOUNTADMIN (or load a newer CSV),
ask again, and record both answers with their query IDs. Restore afterwards.
