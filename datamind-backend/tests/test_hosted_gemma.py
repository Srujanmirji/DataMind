import json

import httpx
import pytest
from pydantic import SecretStr

from app.config import Settings
from app.errors import BackendError
from app.planner import Planner


def test_hosted_request_preserves_retry_history_and_schema():
    settings = Settings(_env_file=None, llm_backend="ai_studio", google_api_key=SecretStr("test-key"))
    payload = {
        "format": {"type": "object"},
        "messages": [
            {"role": "system", "content": "Plan safely"},
            {"role": "user", "content": "Count countries"},
            {"role": "assistant", "content": "{}"},
            {"role": "user", "content": "Fix the plan"},
        ],
    }

    def handle(request):
        assert request.url.host == "generativelanguage.googleapis.com"
        assert request.headers["x-goog-api-key"] == "test-key"
        body = json.loads(request.content)
        assert [m["role"] for m in body["contents"]] == ["user", "model", "user"]
        assert '"type": "object"' in body["systemInstruction"]["parts"][0]["text"]
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {"thought": True, "text": "private reasoning"},
                                {"text": '```json\n{"ok": true}\n```'},
                            ]
                        }
                    }
                ]
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        assert json.loads(Planner(settings, {})._generate(client, payload)) == {"ok": True}
    assert settings.model_name == "gemma-4-26b-a4b-it"


def test_hosted_missing_key_and_rate_limit_are_clear():
    settings = Settings(_env_file=None, llm_backend="ai_studio")
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(429))) as client:
        planner = Planner(settings, {})
        with pytest.raises(BackendError, match="GOOGLE_API_KEY"):
            planner._generate(client, {})
        settings.google_api_key = SecretStr("test-key")
        with pytest.raises(BackendError, match="rate limited"):
            planner._generate(client, {"messages": [{"role": "system", "content": "test"}], "format": {}})
