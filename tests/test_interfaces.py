import pytest

from datamind.llm import LLMBackend, get_backend
from datamind.models import AgentAnswer, AnswerStatus


def test_backends_satisfy_protocol(monkeypatch):
    monkeypatch.setenv("OLLAMA_MODEL", "gemma4:e4b")
    for name in ("ollama", "ai_studio"):
        backend = get_backend(name)
        assert isinstance(backend, LLMBackend)
        assert backend.model


def test_unknown_backend_rejected():
    with pytest.raises(ValueError, match="Unknown LLM backend"):
        get_backend("gpt")


def test_answer_defaults_have_no_shared_state():
    a = AgentAnswer(question="q", status=AnswerStatus.NO_DATA, answer="", explanation="")
    b = AgentAnswer(question="q", status=AnswerStatus.NO_DATA, answer="", explanation="")
    a.queries.append(object())
    assert b.queries == []
