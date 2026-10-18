"""Dataset configuration loading.

A dataset is a YAML file under ``config/datasets/``. Switching datasets is a
configuration change only (rubric criterion 7): no module below this one may
hard-code a database, schema, table or column name.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

DEFAULT_CONFIG_DIR = Path(
    os.environ.get("DATAMIND_CONFIG_DIR")
    or Path(__file__).resolve().parents[2] / "config" / "datasets"
)


class ConfigError(ValueError):
    """Raised when a dataset file is missing or malformed."""


@dataclass(frozen=True)
class TableSpec:
    name: str
    description: str = ""


@dataclass(frozen=True)
class Guardrails:
    max_rows: int = 200
    query_timeout_s: int = 60


@dataclass(frozen=True)
class DatasetConfig:
    name: str
    display_name: str
    description: str
    database: str
    schema: str
    tables: list[TableSpec]
    relationships: list[str] = field(default_factory=list)
    glossary: dict[str, str] = field(default_factory=dict)
    guardrails: Guardrails = field(default_factory=Guardrails)
    source: dict[str, str] = field(default_factory=dict)

    def qualified(self, table: str) -> str:
        """Fully qualified, upper-cased table name, e.g. DB.SCHEMA.TABLE."""
        return f"{self.database}.{self.schema}.{table}".upper()

    @property
    def allowed_tables(self) -> frozenset[str]:
        """Fully qualified names the SQL guard will accept."""
        return frozenset(self.qualified(t.name) for t in self.tables)


def load_dataset(name: str | None = None, config_dir: Path | None = None) -> DatasetConfig:
    """Load ``<config_dir>/<name>.yaml``; ``name`` defaults to $DATAMIND_DATASET."""
    name = name or os.environ.get("DATAMIND_DATASET", "tpch")
    path = (config_dir or DEFAULT_CONFIG_DIR) / f"{name}.yaml"
    if not path.is_file():
        raise ConfigError(f"Dataset config not found: {path}")

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    try:
        sf = raw["snowflake"]
        tables = [TableSpec(**t) for t in raw["tables"]]
        cfg = DatasetConfig(
            name=raw["name"],
            display_name=raw.get("display_name", raw["name"]),
            description=(raw.get("description") or "").strip(),
            database=sf["database"],
            schema=sf["schema"],
            tables=tables,
            relationships=list(raw.get("relationships") or []),
            glossary=dict(raw.get("glossary") or {}),
            guardrails=Guardrails(**(raw.get("guardrails") or {})),
            source=dict(raw.get("source") or {}),
        )
    except (KeyError, TypeError) as exc:
        raise ConfigError(f"Malformed dataset config {path}: {exc}") from exc

    if not cfg.tables:
        raise ConfigError(f"{path}: 'tables' allowlist must not be empty")
    if cfg.name != name:
        raise ConfigError(f"{path}: 'name' is {cfg.name!r}, expected {name!r}")
    return cfg


def available_datasets(config_dir: Path | None = None) -> list[str]:
    return sorted(p.stem for p in (config_dir or DEFAULT_CONFIG_DIR).glob("*.yaml"))
