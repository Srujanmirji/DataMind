# Contributing

1. `python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`
2. Make your change on a branch; keep pull requests focused.
3. `ruff check . && ruff format --check . && pytest -q` must pass (CI runs the same).
4. If you change behaviour visible to judges or users, update `docs/COMPLIANCE.md`.

Ground rules:

- Never commit credentials, `.env`, or dataset files.
- No table, column or database names in code — they belong in `config/datasets/*.yaml`.
- New answer-producing logic needs an eval question in `eval/` with hand-written reference SQL.
- Don't delete or skip a failing test to get green; fix the cause or open an issue.
