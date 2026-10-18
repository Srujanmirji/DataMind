"""Schema discovery: turns live Snowflake metadata plus dataset config into model context."""

from __future__ import annotations

from dataclasses import dataclass, field

from datamind.config import DatasetConfig
from datamind.snowflake_client import ColumnInfo, SnowflakeClient


@dataclass
class SchemaCatalog:
    dataset: DatasetConfig
    columns: list[ColumnInfo] = field(default_factory=list)

    @classmethod
    def discover(cls, client: SnowflakeClient, dataset: DatasetConfig) -> SchemaCatalog:
        """Read columns at startup so the prompt matches the warehouse, not a stale copy."""
        return cls(dataset=dataset, columns=client.describe_columns(dataset))

    def render_for_prompt(self, max_chars: int = 12_000) -> str:
        """Compact text block: tables, columns + types, relationships, glossary.

        Small Gemma variants degrade on long context — keep it under ``max_chars``
        and prefer column names + types over sample values.
        """
        raise NotImplementedError("SchemaCatalog.render_for_prompt")
