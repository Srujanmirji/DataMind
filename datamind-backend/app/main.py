import logging
import secrets
import sqlite3
from threading import Lock
from uuid import UUID

from fastapi import Depends, FastAPI, File, Form, Header, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import Settings
from app.datasets import load_datasets
from app.models import Question
from app.planner import BackendError, Planner
from app.service import QuestionService
from app.store import RunStore
from app.warehouse import Warehouse

logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None, private_key: bytes | None = None, service: QuestionService | None = None
) -> FastAPI:
    settings = settings or Settings()
    catalog = load_datasets(settings)
    lock = Lock()
    services = {
        dataset_id: QuestionService(
            settings, dataset, Planner(settings, dataset), Warehouse(settings, private_key), lock
        )
        for dataset_id, dataset in catalog.items()
    }
    if service is not None:
        services[service.dataset["id"]] = service
    store = RunStore(settings.history_path)
    app = FastAPI(
        title="DataMind backend", version="0.2.0", description="Local Gemma + Snowflake evidence API"
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-API-Key"],
    )

    def authorize(x_api_key: str | None = Header(default=None)):
        expected = settings.api_key.get_secret_value()
        if expected and not secrets.compare_digest(x_api_key or "", expected):
            raise BackendError("unauthorized", "A valid X-API-Key header is required.", 401)

    @app.exception_handler(BackendError)
    async def backend_error(_request: Request, exc: BackendError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"status": "error", "error": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(Exception)
    async def unexpected_error(_request: Request, exc: Exception):
        # Never log exception values: connector errors may contain account/user metadata.
        logger.error("Unhandled backend exception type=%s", type(exc).__name__)
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error": {"code": "internal_error", "message": "An unexpected backend error occurred."},
            },
        )

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "version": "0.2.0",
            "model": settings.ollama_model,
            "key_loaded": private_key is not None,
            "note": "Liveness only; does not query Snowflake or run inference.",
        }

    @app.get("/datasets", dependencies=[Depends(authorize)])
    def datasets():
        return {
            "datasets": [
                {key: value for key, value in dataset.items() if key not in {"from", "joins"}}
                for dataset in catalog.values()
            ]
        }

    @app.post("/questions", dependencies=[Depends(authorize)])
    def questions(body: Question):
        selected_service = services.get(body.dataset_id)
        if selected_service is None:
            raise BackendError("unknown_dataset", "Unknown dataset. See GET /datasets.", 404)
        result = selected_service.ask(body)
        try:
            store.save(result)
        except sqlite3.Error:
            result["warnings"].append("Run history could not be saved; keep this response as evidence.")
        return result

    if settings.enable_multimodal:
        from app.multimodal import multimodal_processor

        @app.post("/questions/multimodal", dependencies=[Depends(authorize)])
        async def questions_multimodal(
            question: str = Form(default=""),
            dataset_id: str = Form(default="tpch_orders"),
            audio: UploadFile | None = File(default=None),  # noqa: B008
            image: UploadFile | None = File(default=None),  # noqa: B008
        ):
            text_query = question.strip()
            if audio is not None:
                audio_bytes = await audio.read()
                text_query = multimodal_processor.process_audio(audio_bytes, audio.filename or "audio.wav")
            elif image is not None:
                image_bytes = await image.read()
                text_query = multimodal_processor.process_image(image_bytes, image.filename or "image.png")
                if question.strip():
                    text_query = f"{question.strip()} (Context: {text_query})"

            if not text_query:
                raise BackendError("invalid_input", "Please provide a question, audio clip, or image.", 422)

            selected_service = services.get(dataset_id)
            if selected_service is None:
                raise BackendError("unknown_dataset", "Unknown dataset. See GET /datasets.", 404)

            result = selected_service.ask(Question(question=text_query, dataset_id=dataset_id))
            result["multimodal"] = {
                "has_audio": audio is not None,
                "has_image": image is not None,
                "extracted_query": text_query,
            }
            try:
                store.save(result)
            except (sqlite3.Error, KeyError):
                result["warnings"].append("Run history could not be saved; keep this response as evidence.")
            return result

    @app.get("/runs/{run_id}", dependencies=[Depends(authorize)])
    def runs(run_id: UUID):
        result = store.get(str(run_id))
        if result is None:
            raise BackendError("run_not_found", "Run not found.", 404)
        return result

    return app
