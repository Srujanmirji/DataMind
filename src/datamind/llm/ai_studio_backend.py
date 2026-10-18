"""Hosted Gemma 4 via the Gemini API / Google AI Studio (default backend).

Free API key in $GOOGLE_API_KEY. The default model id is the one used in
Google's "Run Gemma with the Gemini API" docs; confirm it in AI Studio's model
list. Data sent to Google: the question, the schema block, and (explanation
step only) the capped result rows. No credentials are ever sent.
"""

from __future__ import annotations

import os

from datamind.models import LLMResponse


class AIStudioBackend:
    name = "ai_studio"

    def __init__(self, model: str | None = None, api_key: str | None = None) -> None:
        self.model = model or os.environ.get("AI_STUDIO_MODEL", "gemma-4-26b-a4b-it")
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
        #       model=self.model, contents=..., config=types.GenerateContentConfig(
        #       temperature=..., max_output_tokens=...)).
        # Verify on a real call before relying on them (Gemma 3 on this API rejected both):
        #   * system_instruction — if rejected, prepend `system` to the user turn.
        #   * response_mime_type="application/json" — if rejected, ask for JSON in the
        #     prompt and parse/validate it yourself (callers must validate either way).
        # Free tier is rate-limited per project: retry HTTP 429 with exponential backoff,
        # and surface a clear "rate limited" AgentAnswer instead of crashing.
        raise NotImplementedError("AIStudioBackend.generate")
