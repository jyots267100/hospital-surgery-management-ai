from __future__ import annotations

from datetime import date as date_type

from app.core.exceptions import NotFoundError
from app.models.schemas import Surgeon, Surgery
from app.repositories.surgeon_repository import SurgeonRepository
from app.services.surgery_service import SurgeryService


class SurgeonService:
    def __init__(self, surgeon_repo: SurgeonRepository, surgery_service: SurgeryService) -> None:
        self._surgeon_repo = surgeon_repo
        self._surgery_service = surgery_service

    def list_surgeons(self) -> list[Surgeon]:
        return self._surgeon_repo.list_all()

    def get_surgeon(self, surgeon_id: str) -> Surgeon:
        surgeon = self._surgeon_repo.get_by_id(surgeon_id)
        if surgeon is None:
            raise NotFoundError(f"No surgeon found with id '{surgeon_id}'", surgeon_id=surgeon_id)
        return surgeon

    def get_schedule(self, surgeon_id: str, on_date: date_type | None = None) -> list[Surgery]:
        self.get_surgeon(surgeon_id)
        return self._surgery_service.get_surgeries_for_surgeon(surgeon_id, on_date)

    def find_by_name(self, name_fragment: str) -> list[Surgeon]:
        fragment = name_fragment.strip().lower()
        return [s for s in self.list_surgeons() if fragment in s.name.lower()]
