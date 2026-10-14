from __future__ import annotations

from pathlib import Path

from app.models.schemas import OperatingRoom
from app.repositories.base import JsonFileRepository


class OperatingRoomRepository(JsonFileRepository[OperatingRoom]):
    def __init__(self, data_dir: Path) -> None:
        super().__init__(data_dir / "operating_rooms.json", OperatingRoom, id_field="room_id")
