"""The question-answering pipeline.

    question
      -> classify     (Gemma)      answerable / ambiguous / unsupported / unsafe
      -> generate_sql (Gemma)      SQL + stated assumptions, JSON
      -> validate_sql (code)       allowlist, read-only, LIMIT        [sql_guard]
      -> run_query    (Snowflake)  rows + query ID                    [snowflake_client]
         (on SQL error: feed the error back to generate_sql, max ``max_repairs`` times)
      -> explain      (Gemma)      answer + plain-language explanation, from rows only
      -> verify       (code)       every number in the answer appears in result rows

Gemma never executes anything; code never invents facts.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from datamind.config import DatasetConfig
from datamind.llm import LLMBackend
from datamind.models import AgentAnswer, AnswerStatus, LLMResponse, QueryRecord
from datamind.schema import SchemaCatalog
from datamind.snowflake_client import SnowflakeClient


@dataclass
class Turn:
    question: str
    answer: AgentAnswer


@dataclass
class Classification:
    status: AnswerStatus  # ANSWERED means "proceed to SQL"
    reason: str
    clarifying_question: str | None = None
    llm_call: LLMResponse | None = None


@dataclass
class SqlDraft:
    sql: str
    assumptions: list[str] = field(default_factory=list)
    llm_call: LLMResponse | None = None


class DataMindAgent:
    def __init__(
        self,
        dataset: DatasetConfig,
        catalog: SchemaCatalog,
        llm: LLMBackend,
        snowflake: SnowflakeClient,
        max_repairs: int = 2,
    ) -> None:
        self.dataset = dataset
        self.catalog = catalog
        self.llm = llm
        self.snowflake = snowflake
        self.max_repairs = max_repairs

    def ask(self, question: str, history: list[Turn] | None = None) -> AgentAnswer:
        """Run the full pipeline. Must always return an AgentAnswer, never raise."""
        raise NotImplementedError("DataMindAgent.ask")

    def classify(self, question: str, history: list[Turn]) -> Classification:
        raise NotImplementedError

    def generate_sql(
        self, question: str, history: list[Turn], previous: QueryRecord | None = None
    ) -> SqlDraft:
        """``previous`` carries the failed SQL and Snowflake's error for a repair attempt."""
        raise NotImplementedError

    def explain(self, question: str, record: QueryRecord, assumptions: list[str]) -> AgentAnswer:
        """Answer only from ``record.result.rows``; empty rows -> AnswerStatus.NO_DATA."""
        raise NotImplementedError

    def verify(self, answer: AgentAnswer) -> list[str]:
        """Return claims (numbers, names) in ``answer.answer`` not found in evidence rows."""
        raise NotImplementedError
