"""Structured JSON logging configuration.

Logs request/operation metadata (request id, operation, tool, latency, outcome) as
single-line JSON so logs can be piped into any log aggregator. Secrets (API keys,
tokens) and unnecessary patient data are never logged -- only identifiers such as
surgery_id are included.
"""
from __future__ import annotations

import json
import logging
import sys
import time
from contextvars import ContextVar
from typing import Any

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")

_REDACT_KEYS = {"api_key", "apikey", "gemini_api_key", "token", "authorization", "password", "secret"}


def _redact(data: dict[str, Any]) -> dict[str, Any]:
    cleaned = {}
    for key, value in data.items():
        if key.lower() in _REDACT_KEYS:
            cleaned[key] = "***REDACTED***"
        else:
            cleaned[key] = value
    return cleaned


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_ctx.get(),
        }
        extra = getattr(record, "extra_fields", None)
        if extra:
            payload.update(_redact(extra))
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)


def log_event(logger: logging.Logger, level: int, message: str, **fields: Any) -> None:
    logger.log(level, message, extra={"extra_fields": fields})


class Timer:
    """Context manager that measures elapsed wall-clock time in milliseconds."""

    def __enter__(self) -> "Timer":
        self._start = time.perf_counter()
        self.elapsed_ms = 0.0
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.elapsed_ms = round((time.perf_counter() - self._start) * 1000, 2)
