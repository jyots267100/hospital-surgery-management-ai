from __future__ import annotations

from pathlib import Path

from app.models.schemas import Surgeon
from app.repositories.base import JsonFileRepository


class SurgeonRepository(JsonFileRepository[Surgeon]):
    def __init__(self, data_dir: Path) -> None:
        super().__init__(data_dir / "surgeons.json", Surgeon, id_field="surgeon_id")
