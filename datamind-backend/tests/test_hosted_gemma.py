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


@pytest.mark.parametrize(
    "status,code",
    [
        (400, "model_request_rejected"),
        (401, "model_access_denied"),
        (403, "model_access_denied"),
        (404, "model_configuration"),
        (429, "model_rate_limited"),
        (503, "model_unavailable"),
    ],
)
def test_provider_errors_are_specific_without_leaking_details(status, code):
    settings = Settings(_env_file=None, llm_backend="ai_studio", google_api_key=SecretStr("private-test-key"))
    with (
        httpx.Client(
            transport=httpx.MockTransport(
                lambda r: httpx.Response(
                    status, json={"error": {"message": "private-test-key sensitive provider detail"}}
                )
            )
        ) as client,
        pytest.raises(BackendError) as error,
    ):
        Planner(settings, {})._generate(
            client, {"messages": [{"role": "system", "content": "test"}], "format": {}}
        )
    assert error.value.code == code
    assert "private-test-key" not in str(error.value) and "sensitive provider detail" not in str(error.value)


def test_transient_google_failure_is_retried_once(monkeypatch):
    monkeypatch.setattr("app.planner.sleep", lambda _: None)
    settings = Settings(_env_file=None, llm_backend="ai_studio", google_api_key=SecretStr("test-key"))
    requests = []

    def handle(request):
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(503)
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "{}"}]}}]})

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        assert (
            Planner(settings, {})._generate(
                client, {"messages": [{"role": "system", "content": "test"}], "format": {}}
            )
            == "{}"
        )
    assert len(requests) == 2
