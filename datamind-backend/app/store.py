import json
import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path


class RunStore:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, body TEXT NOT NULL)")

    @contextmanager
    def connect(self):
        # sqlite3.Connection.__exit__ commits/rolls back but does not close.
        with closing(sqlite3.connect(self.path, timeout=10)) as connection, connection:
            yield connection

    def save(self, result: dict):
        with self.connect() as connection:
            connection.execute("INSERT INTO runs VALUES (?, ?)", (result["run_id"], json.dumps(result)))

    def get(self, run_id: str) -> dict | None:
        with self.connect() as connection:
            row = connection.execute("SELECT body FROM runs WHERE id = ?", (run_id,)).fetchone()
        return json.loads(row[0]) if row else None
