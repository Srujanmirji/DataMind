"""Schema discovery: turns live Snowflake metadata plus dataset config into model context."""

from __future__ import annotations

from collections import defaultdict
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
        lines: list[str] = [
            f"Dataset: {self.dataset.display_name} ({self.dataset.name})",
            f"Database: {self.dataset.database.upper()}",
            f"Schema: {self.dataset.schema.upper()}",
        ]

        if self.dataset.description:
            lines.append(f"Description: {self.dataset.description}")

        lines.append("\nTables and Columns:")

        # Group discovered columns by table name
        cols_by_table: dict[str, list[ColumnInfo]] = defaultdict(list)
        for col in self.columns:
            cols_by_table[col.table.upper()].append(col)

        table_specs = {t.name.upper(): t for t in self.dataset.tables}

        for tbl_name, spec in table_specs.items():
            desc_part = f" - {spec.description}" if spec.description else ""
            lines.append(f"• {tbl_name}{desc_part}")
            cols = cols_by_table.get(tbl_name, [])
            if cols:
                col_strs = []
                for c in cols:
                    cmt = f" /* {c.comment} */" if c.comment else ""
                    col_strs.append(f"{c.name} {c.data_type}{cmt}")
                lines.append(f"  Columns: {', '.join(col_strs)}")

        if self.dataset.relationships:
            lines.append("\nRelationships (Joins):")
            for rel in self.dataset.relationships:
                lines.append(f"• {rel}")

        if self.dataset.glossary:
            lines.append("\nGlossary (Business Definitions):")
            for term, definition in self.dataset.glossary.items():
                lines.append(f"• {term}: {definition}")

        rendered = "\n".join(lines)
        if len(rendered) > max_chars:
            rendered = rendered[: max_chars - 20] + "\n... [TRUNCATED]"

        return rendered
