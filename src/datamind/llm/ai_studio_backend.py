"""Hosted Gemma 4 via Google AI Studio (free API key in $GOOGLE_API_KEY).

The model id default is unverified — check AI Studio's model list and set
$AI_STUDIO_MODEL. Note: questions and schema text leave the machine on this
backend; result rows are sent only during the explanation step.
"""

from __future__ import annotations

import os

from datamind.models import LLMResponse


class AIStudioBackend:
    name = "ai_studio"

    def __init__(self, model: str | None = None, api_key: str | None = None) -> None:
        self.model = model or os.environ.get("AI_STUDIO_MODEL", "gemma-4-31b-it")
        self._api_key = api_key or os.environ.get("GOOGLE_API_KEY")

    def generate(
        self,
        system: str,
        prompt: str,
        *,
        json_mode: bool = False,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        # TODO: google.genai.Client(api_key=self._api_key).models.generate_content(
        #       model=self.model, contents=prompt, config={system_instruction, temperature,
        #       max_output_tokens, response_mime_type="application/json" if json_mode}).
        #       Some Gemma endpoints reject system_instruction; fall back to prefixing it.
        raise NotImplementedError("AIStudioBackend.generate")
