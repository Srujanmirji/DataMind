"""Local Gemma 4 via Ollama (``ollama pull gemma4:e4b``). Requires Ollama >= 0.22 (unverified)."""

from __future__ import annotations

import os

from datamind.models import LLMResponse


class OllamaBackend:
    name = "ollama"

    def __init__(self, model: str | None = None, host: str | None = None) -> None:
        self.model = model or os.environ.get("OLLAMA_MODEL", "gemma4:e4b")
        self.host = host or os.environ.get("OLLAMA_HOST", "http://localhost:11434")

    def generate(
        self,
        system: str,
        prompt: str,
        *,
        json_mode: bool = False,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        # TODO: ollama.Client(host=self.host).chat(model=..., messages=[system, user],
        #       format="json" if json_mode else None,
        #       options={"temperature": temperature, "num_predict": max_tokens});
        #       time the call and return LLMResponse(model=self.model, backend=self.name, ...).
        raise NotImplementedError("OllamaBackend.generate")
