from __future__ import annotations

from pathlib import Path

from app.models.schemas import Patient
from app.repositories.base import JsonFileRepository


class PatientRepository(JsonFileRepository[Patient]):
    def __init__(self, data_dir: Path) -> None:
        super().__init__(data_dir / "patients.json", Patient, id_field="patient_id")
