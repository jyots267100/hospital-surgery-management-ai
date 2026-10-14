from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_container_dep
from app.dependencies import Container
from app.models.api_models import SurgeonResponse, SurgeryResponse

router = APIRouter(prefix="/surgeons", tags=["surgeons"])


@router.get("", response_model=list[SurgeonResponse])
def list_surgeons(container: Container = Depends(get_container_dep)) -> list[SurgeonResponse]:
    return [SurgeonResponse.from_domain(s) for s in container.surgeon_service.list_surgeons()]


@router.get("/{surgeon_id}", response_model=SurgeonResponse)
def get_surgeon(surgeon_id: str, container: Container = Depends(get_container_dep)) -> SurgeonResponse:
    return SurgeonResponse.from_domain(container.surgeon_service.get_surgeon(surgeon_id))


@router.get("/{surgeon_id}/schedule", response_model=list[SurgeryResponse])
def get_surgeon_schedule(
    surgeon_id: str, on_date: date | None = Query(None), container: Container = Depends(get_container_dep),
) -> list[SurgeryResponse]:
    surgeries = container.surgeon_service.get_schedule(surgeon_id, on_date)
    return [SurgeryResponse(**s.model_dump()) for s in surgeries]
