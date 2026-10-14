from __future__ import annotations

from datetime import date as date_type

from app.models.schemas import SurgeryStatus
from app.repositories.operating_room_repository import OperatingRoomRepository
from app.services.surgery_service import SurgeryService


class DashboardService:
    def __init__(self, surgery_service: SurgeryService, room_repo: OperatingRoomRepository) -> None:
        self._surgery_service = surgery_service
        self._room_repo = room_repo

    def get_summary(self) -> dict:
        today = date_type.today()
        all_surgeries = self._surgery_service.list_surgeries()
        todays = [s for s in all_surgeries if s.scheduled_date == today]

        status_counts = {status.value: 0 for status in SurgeryStatus}
        for s in all_surgeries:
            status_counts[s.status.value] += 1

        delayed = [s for s in all_surgeries if s.delay_minutes > 0]
        avg_delay = round(sum(s.delay_minutes for s in delayed) / len(delayed), 1) if delayed else 0.0

        rooms = self._room_repo.list_all()
        active_today = [s for s in todays if s.status != SurgeryStatus.CANCELLED]
        booked_minutes = sum(s.duration_minutes for s in active_today)
        available_minutes = len(rooms) * 8 * 60  # assume an 8-hour operating day per room
        or_utilization_pct = round(min(booked_minutes / available_minutes, 1.0) * 100, 1) if rooms else 0.0

        return {
            "as_of_date": today,
            "total_surgeries": len(all_surgeries),
            "todays_surgery_count": len(todays),
            "status_breakdown": status_counts,
            "average_delay_minutes": avg_delay,
            "operating_room_utilization_pct": or_utilization_pct,
            "total_operating_rooms": len(rooms),
        }
