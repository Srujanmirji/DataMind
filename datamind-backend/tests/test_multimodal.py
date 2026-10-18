import io
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

ENABLED = Settings(enable_multimodal=True)


def test_multimodal_audio_input(monkeypatch):
    mock_service = MagicMock()
    mock_service.dataset = {"id": "tpch_orders"}
    mock_service.ask.return_value = {
        "status": "answered",
        "run_id": "00000000-0000-0000-0000-000000000001",
        "answer": "Test answer",
        "explanation": "Calculated",
        "evidence": [],
        "warnings": [],
    }

    app = create_app(settings=ENABLED, service=mock_service)
    client = TestClient(app)

    # Fake audio bytes (e.g. WAV header)
    fake_wav = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00D\xac\x00\x00"

    response = client.post(
        "/questions/multimodal",
        data={"dataset_id": "tpch_orders"},
        files={"audio": ("how_many_orders.wav", io.BytesIO(fake_wav), "audio/wav")},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "answered"
    assert data["multimodal"]["has_audio"] is True
    assert "orders" in data["multimodal"]["extracted_query"].lower()
    mock_service.ask.assert_called_once()


def test_multimodal_image_input(monkeypatch):
    pytest.importorskip("PIL")
    mock_service = MagicMock()
    mock_service.dataset = {"id": "tpch_orders"}
    mock_service.ask.return_value = {
        "status": "answered",
        "run_id": "00000000-0000-0000-0000-000000000002",
        "answer": "Test answer for chart image",
        "explanation": "Calculated from visual input",
        "evidence": [],
        "warnings": [],
    }

    app = create_app(settings=ENABLED, service=mock_service)
    client = TestClient(app)

    # 1x1 PNG fake bytes
    fake_png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
    )

    response = client.post(
        "/questions/multimodal",
        data={"dataset_id": "tpch_orders", "question": "Compare the metric shown"},
        files={"image": ("chart.png", io.BytesIO(fake_png), "image/png")},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "answered"
    assert data["multimodal"]["has_image"] is True
    mock_service.ask.assert_called_once()


def test_multimodal_empty_input_rejected():
    app = create_app(settings=ENABLED)
    client = TestClient(app)

    response = client.post(
        "/questions/multimodal",
        data={"dataset_id": "tpch_orders"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_input"


def test_multimodal_route_disabled_by_default():
    app = create_app(service=MagicMock(dataset={"id": "tpch_orders"}))
    response = TestClient(app).post("/questions/multimodal", data={"question": "How many orders?"})
    assert response.status_code == 404
