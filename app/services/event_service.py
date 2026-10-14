from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.models.schemas import SurgeryEvent
from app.repositories.event_repository import EventRepository


class EventService:
    """Creates and reads immutable surgery audit events."""

    def __init__(self, event_repo: EventRepository) -> None:
        self._event_repo = event_repo

    def add_event(
        self,
        surgery_id: str,
        event_type: str,
        description: str,
        actor: str,
        previous_value: str | None = None,
        new_value: str | None = None,
    ) -> SurgeryEvent:
        event = SurgeryEvent(
            event_id=f"E{uuid.uuid4().hex[:10]}",
            surgery_id=surgery_id,
            timestamp=datetime.now(timezone.utc),
            event_type=event_type,
            description=description,
            actor=actor,
            previous_value=previous_value,
            new_value=new_value,
        )
        return self._event_repo.append(event)

    def get_history(self, surgery_id: str) -> list[SurgeryEvent]:
        return self._event_repo.find_by_surgery(surgery_id)
