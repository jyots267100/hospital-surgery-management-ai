"""Base JSON-file repository.

Persistence for this portfolio version is file-based JSON (documented limitation --
see docs/architecture.md for how this would move to PostgreSQL in production). Each
concrete repository is responsible for one entity type and its own file.
"""
from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Generic, TypeVar

from pydantic import BaseModel

from app.core.exceptions import RepositoryError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class JsonFileRepository(Generic[T]):
    """Generic read/write/append access to a single JSON array file.

    A per-instance lock guards read-modify-write sequences so concurrent FastAPI
    requests (single-process, threaded) don't corrupt the file.
    """

    def __init__(self, file_path: Path, model: type[T], id_field: str) -> None:
        self._file_path = file_path
        self._model = model
        self._id_field = id_field
        self._lock = threading.Lock()
        if not self._file_path.exists():
            self._file_path.parent.mkdir(parents=True, exist_ok=True)
            self._file_path.write_text("[]", encoding="utf-8")

    def _read_raw(self) -> list[dict]:
        try:
            with self._file_path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            raise RepositoryError(f"Failed to read data file {self._file_path.name}: {exc}") from exc

    def _write_raw(self, records: list[dict]) -> None:
        try:
            tmp_path = self._file_path.with_suffix(".tmp")
            with tmp_path.open("w", encoding="utf-8") as f:
                json.dump(records, f, indent=2, default=str)
            tmp_path.replace(self._file_path)
        except OSError as exc:
            raise RepositoryError(f"Failed to write data file {self._file_path.name}: {exc}") from exc

    def list_all(self) -> list[T]:
        with self._lock:
            return [self._model.model_validate(r) for r in self._read_raw()]

    def get_by_id(self, record_id: str) -> T | None:
        with self._lock:
            for raw in self._read_raw():
                if raw.get(self._id_field) == record_id:
                    return self._model.model_validate(raw)
            return None

    def create(self, record: T) -> T:
        with self._lock:
            records = self._read_raw()
            new_raw = json.loads(record.model_dump_json())
            if any(r.get(self._id_field) == new_raw[self._id_field] for r in records):
                raise RepositoryError(f"Record with id {new_raw[self._id_field]} already exists")
            records.append(new_raw)
            self._write_raw(records)
            return record

    def update(self, record_id: str, record: T) -> T:
        with self._lock:
            records = self._read_raw()
            updated_raw = json.loads(record.model_dump_json())
            for i, raw in enumerate(records):
                if raw.get(self._id_field) == record_id:
                    records[i] = updated_raw
                    self._write_raw(records)
                    return record
            raise RepositoryError(f"Record with id {record_id} not found for update")

    def delete(self, record_id: str) -> bool:
        with self._lock:
            records = self._read_raw()
            filtered = [r for r in records if r.get(self._id_field) != record_id]
            if len(filtered) == len(records):
                return False
            self._write_raw(filtered)
            return True

    def append(self, record: T) -> T:
        """Append-only write (used for immutable audit events)."""
        with self._lock:
            records = self._read_raw()
            records.append(json.loads(record.model_dump_json()))
            self._write_raw(records)
            return record
