from __future__ import annotations

from pathlib import Path

from app.models.schemas import Surgery
from app.repositories.base import JsonFileRepository


class SurgeryRepository(JsonFileRepository[Surgery]):
    def __init__(self, data_dir: Path) -> None:
        super().__init__(data_dir / "surgeries.json", Surgery, id_field="surgery_id")

    def find_by_date(self, iso_date: str) -> list[Surgery]:
        return [s for s in self.list_all() if s.scheduled_date.isoformat() == iso_date]

    def find_by_surgeon(self, surgeon_id: str) -> list[Surgery]:
        return [s for s in self.list_all() if s.surgeon_id == surgeon_id]

    def find_by_room(self, room_id: str) -> list[Surgery]:
        return [s for s in self.list_all() if s.operating_room == room_id]
