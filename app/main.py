"""FastAPI application entry point: middleware, centralized exception handling,
and router registration. Run with:

    uvicorn app.main:app --reload --port 8000
"""
from __future__ import annotations

import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError

from app.api.v1.health import router as health_router
from app.api.v1.router import api_v1_router
from app.config import get_settings
from app.core.exceptions import DomainError
from app.core.logging_config import configure_logging, log_event, request_id_ctx

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger("hospital_surgery_ai")

app = FastAPI(
    title="Hospital Surgery Management AI Agent",
    description=(
        "Internal hospital surgery operations API with an AI agent assistant. "
        "All patient data and hospital policies in this system are SYNTHETIC, for "
        "portfolio/demonstration purposes only."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    token = request_id_ctx.set(request_id)
    start = time.perf_counter()
    try:
        response = await call_next(request)
    finally:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        log_event(
            logger, logging.INFO, "http_request",
            method=request.method, path=request.url.path, latency_ms=elapsed_ms,
        )
        request_id_ctx.reset(token)
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    log_event(
        logger, logging.WARNING, "domain_error",
        path=request.url.path, error_type=type(exc).__name__, detail=exc.message,
    )
    return JSONResponse(
        status_code=exc.http_status,
        content={"error": type(exc).__name__, "detail": exc.message, "context": exc.context},
    )


@app.exception_handler(PydanticValidationError)
async def pydantic_validation_error_handler(request: Request, exc: PydanticValidationError) -> JSONResponse:
    log_event(logger, logging.WARNING, "validation_error", path=request.url.path, error=str(exc))
    return JSONResponse(status_code=422, content={"error": "ValidationError", "detail": str(exc), "context": {}})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    log_event(logger, logging.ERROR, "unhandled_error", path=request.url.path, error_type=type(exc).__name__)
    return JSONResponse(
        status_code=500,
        content={"error": "InternalServerError", "detail": "An unexpected error occurred.", "context": {}},
    )


app.include_router(health_router)
app.include_router(api_v1_router)


@app.on_event("startup")
def auto_ingest_policies_if_empty() -> None:
    """Convenience for local/Docker first-run: ingest the policy corpus
    automatically if the vector store is empty, so `docker compose up` and
    `uvicorn app.main:app` work without a separate manual ingestion step."""
    from app.dependencies import get_container

    container = get_container()
    if container.policy_service.collection_size() == 0:
        log_event(logger, logging.INFO, "auto_ingest_start")
        result = container.policy_service.reingest()
        log_event(logger, logging.INFO, "auto_ingest_complete", **result)
