from __future__ import annotations

from datetime import date as date_type
from datetime import datetime, time, timedelta

from app.core.exceptions import NotFoundError, ValidationError
from app.models.schemas import OperatingRoom, Surgery
from app.repositories.operating_room_repository import OperatingRoomRepository
from app.services.surgery_service import SurgeryService


class OperatingRoomService:
    def __init__(self, room_repo: OperatingRoomRepository, surgery_service: SurgeryService) -> None:
        self._room_repo = room_repo
        self._surgery_service = surgery_service

    def list_rooms(self) -> list[OperatingRoom]:
        return self._room_repo.list_all()

    def get_room(self, room_id: str) -> OperatingRoom:
        room = self._room_repo.get_by_id(room_id)
        if room is None:
            raise NotFoundError(f"No operating room found with id '{room_id}'", room_id=room_id)
        return room

    def get_availability(
        self, room_id: str, on_date: date_type, window_start: time, window_end: time,
    ) -> dict:
        if window_start >= window_end:
            raise ValidationError("window_start must be before window_end")
        self.get_room(room_id)
        booked = self._surgery_service.get_room_schedule(room_id, on_date)

        today = date_type.today()
        w_start = datetime.combine(today, window_start)
        w_end = datetime.combine(today, window_end)

        conflicts: list[Surgery] = []
        for s in booked:
            s_start = datetime.combine(today, s.scheduled_time)
            s_end = s_start + timedelta(minutes=s.duration_minutes)
            if s_start < w_end and w_start < s_end:
                conflicts.append(s)

        return {
            "room_id": room_id,
            "date": on_date,
            "requested_window_start": window_start,
            "requested_window_end": window_end,
            "is_available": len(conflicts) == 0,
            "conflicting_surgeries": conflicts,
        }

    def get_all_rooms_availability(self, on_date: date_type, window_start: time, window_end: time) -> list[dict]:
        return [self.get_availability(r.room_id, on_date, window_start, window_end) for r in self.list_rooms()]
