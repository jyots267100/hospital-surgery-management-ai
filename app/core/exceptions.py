"""Domain exceptions used across repository/service/tool/API layers.

Each exception maps to a specific HTTP status in the centralized API exception
handler (see app/main.py), so services never need to know about HTTP.
"""
from __future__ import annotations


class DomainError(Exception):
    """Base class for all domain-level errors."""

    http_status: int = 400

    def __init__(self, message: str, **context: object) -> None:
        super().__init__(message)
        self.message = message
        self.context = context


class NotFoundError(DomainError):
    http_status = 404


class ValidationError(DomainError):
    http_status = 422


class ConflictError(DomainError):
    """Scheduling conflicts: OR double-booked, surgeon double-booked, etc."""

    http_status = 409


class InvalidStateTransitionError(DomainError):
    http_status = 409


class PolicyViolationError(DomainError):
    """A requested action is blocked by hospital policy (e.g. cancellation window)."""

    http_status = 422


class ConfirmationRequiredError(DomainError):
    """A write operation requires explicit user confirmation before execution."""

    http_status = 409


class RepositoryError(DomainError):
    http_status = 500


class RAGError(DomainError):
    http_status = 502


class LLMError(DomainError):
    http_status = 502
