from __future__ import annotations

from pathlib import Path

from app.models.schemas import SurgeryEvent
from app.repositories.base import JsonFileRepository


class EventRepository(JsonFileRepository[SurgeryEvent]):
    """Append-only repository for surgery audit events. Historical events are
    never overwritten or deleted -- only new events are appended."""

    def __init__(self, data_dir: Path) -> None:
        super().__init__(data_dir / "surgery_events.json", SurgeryEvent, id_field="event_id")

    def find_by_surgery(self, surgery_id: str) -> list[SurgeryEvent]:
        events = [e for e in self.list_all() if e.surgery_id == surgery_id]
        return sorted(events, key=lambda e: e.timestamp)
