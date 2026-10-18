"""Data contracts shared by every pipeline stage.

These types are the evidence trail: the UI and the eval runner render an
``AgentAnswer`` and nothing else, so every claim shown to a user must be
traceable to a ``QueryRecord`` inside it (rubric criterion 3, feature M5).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AnswerStatus(str, Enum):
    """How the agent resolved a question (feature M6)."""

    ANSWERED = "answered"
    NEEDS_CLARIFICATION = "needs_clarification"  # ambiguous; ask, or answer with stated assumption
    NO_DATA = "no_data"  # query ran, returned nothing — say so, do not invent
    UNSUPPORTED = "unsupported"  # outside the dataset (e.g. weather in a sales DB)
    REFUSED = "refused"  # unsafe request (writes, DDL, other schemas)
    ERROR = "error"  # infrastructure or repeated SQL failure


@dataclass(frozen=True)
class QueryResult:
    """What Snowflake returned for one executed statement."""

    query_id: str  # Snowflake query ID — lets anyone find it in QUERY_HISTORY
    sql: str  # exact text sent to Snowflake, after guard rewrites
    columns: list[str]
    rows: list[tuple[Any, ...]]
    row_count: int  # total rows produced, before truncation
    truncated: bool
    elapsed_ms: int


@dataclass(frozen=True)
class GuardResult:
    """Outcome of static SQL validation before anything reaches Snowflake."""

    allowed: bool
    sql: str  # possibly rewritten (e.g. LIMIT added)
    tables: list[str]  # fully qualified tables referenced
    reasons: list[str] = field(default_factory=list)  # why rejected / what was rewritten


@dataclass(frozen=True)
class LLMResponse:
    """One Gemma call, recorded so its role in an answer is auditable."""

    text: str
    model: str  # e.g. "gemma4:e4b" — exactly what served the call
    backend: str  # "ollama" | "ai_studio"
    latency_ms: int


@dataclass
class QueryRecord:
    """One attempt in the pipeline: generated SQL, guard verdict, result or error."""

    generated_sql: str
    guard: GuardResult
    result: QueryResult | None = None
    error: str | None = None


@dataclass
class AgentAnswer:
    """The single object the UI and eval runner consume."""

    question: str
    status: AnswerStatus
    answer: str  # user-facing text; every number in it must appear in evidence rows
    explanation: str  # plain-language how: tables, filters, definitions, assumptions (M4)
    assumptions: list[str] = field(default_factory=list)
    queries: list[QueryRecord] = field(default_factory=list)  # inspectable evidence (M5)
    llm_calls: list[LLMResponse] = field(default_factory=list)
    clarifying_question: str | None = None
    dataset: str = ""
