"""Gemma backends. Select with $DATAMIND_LLM_BACKEND (``ai_studio`` default | ``ollama``)."""

from __future__ import annotations

import os

from datamind.llm.ai_studio_backend import AIStudioBackend
from datamind.llm.base import LLMBackend
from datamind.llm.ollama_backend import OllamaBackend

BACKENDS: dict[str, type] = {"ollama": OllamaBackend, "ai_studio": AIStudioBackend}


def get_backend(name: str | None = None) -> LLMBackend:
    name = name or os.environ.get("DATAMIND_LLM_BACKEND", "ai_studio")
    try:
        return BACKENDS[name]()
    except KeyError:
        raise ValueError(f"Unknown LLM backend {name!r}; choose from {sorted(BACKENDS)}") from None


__all__ = ["LLMBackend", "get_backend", "OllamaBackend", "AIStudioBackend"]
