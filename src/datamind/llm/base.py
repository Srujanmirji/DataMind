"""Gemma backend interface.

Gemma interprets and explains; it never executes anything and never sees
credentials. Keeping inference behind this interface separates it from data
storage and query processing (Snowflake), as the PS1 brief requires.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from datamind.models import LLMResponse


@runtime_checkable
class LLMBackend(Protocol):
    name: str  # "ollama" | "ai_studio"
    model: str  # exact model id, recorded on every LLMResponse

    def generate(
        self,
        system: str,
        prompt: str,
        *,
        json_mode: bool = False,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        """Return one completion.

        ``json_mode=True`` asks the backend for a single JSON object; callers must
        still parse and validate it, because small models break format.
        Temperature defaults to 0 so the same question yields the same SQL.
        """
        ...
