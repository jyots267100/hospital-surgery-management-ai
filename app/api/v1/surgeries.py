"""Surgery endpoints.

Design decision: DELETE /surgeries/{id} is reserved for administrative removal of
synthetic/test records. Normal cancellation is a status transition --
PATCH /surgeries/{id}/status with {"status": "cancelled", "reason": "..."} --
because a cancelled surgery must remain in the system for audit history (see
policies/surgery_cancellation_policy.txt, Section 6). See docs/api.md.
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_container_dep
from app.dependencies import Container
from app.models.api_models import (
    AddSurgeryEventRequest,
    CreateSurgeryRequest,
    RescheduleSurgeryRequest,
    SurgeryEventResponse,
    SurgeryResponse,
    UpdateSurgeryStatusRequest,
)
from app.models.schemas import SurgeryStatus

router = APIRouter(prefix="/surgeries", tags=["surgeries"])


@router.get("", response_model=list[SurgeryResponse])
def list_surgeries(
    status_filter: SurgeryStatus | None = Query(None, alias="status"),
    today_only: bool = Query(False),
    container: Container = Depends(get_container_dep),
) -> list[SurgeryResponse]:
    if today_only:
        surgeries = container.surgery_service.get_todays_surgeries()
    else:
        surgeries = container.surgery_service.list_surgeries(status=status_filter)
    return [SurgeryResponse(**s.model_dump()) for s in surgeries]


@router.get("/delayed", response_model=list[SurgeryResponse])
def list_delayed_surgeries(container: Container = Depends(get_container_dep)) -> list[SurgeryResponse]:
    surgeries = container.surgery_service.get_delayed_surgeries()
    return [SurgeryResponse(**s.model_dump()) for s in surgeries]


@router.get("/{surgery_id}", response_model=SurgeryResponse)
def get_surgery(surgery_id: str, container: Container = Depends(get_container_dep)) -> SurgeryResponse:
    surgery = container.surgery_service.get_surgery(surgery_id)
    return SurgeryResponse(**surgery.model_dump())


@router.post("", response_model=SurgeryResponse, status_code=status.HTTP_201_CREATED)
def create_surgery(
    payload: CreateSurgeryRequest, container: Container = Depends(get_container_dep),
) -> SurgeryResponse:
    surgery = container.surgery_service.create_surgery(
        patient_id=payload.patient_id,
        surgery_type=payload.surgery_type,
        surgeon_id=payload.surgeon_id,
        operating_room=payload.operating_room,
        scheduled_date=payload.scheduled_date,
        scheduled_time=payload.scheduled_time,
        duration_minutes=payload.duration_minutes,
        priority=payload.priority,
        actor="api_client",
    )
    return SurgeryResponse(**surgery.model_dump())


@router.patch("/{surgery_id}/status", response_model=SurgeryResponse)
def update_surgery_status(
    surgery_id: str, payload: UpdateSurgeryStatusRequest, container: Container = Depends(get_container_dep),
) -> SurgeryResponse:
    if payload.status == SurgeryStatus.CANCELLED:
        surgery = container.surgery_service.cancel_surgery(
            surgery_id, reason=payload.reason or "Cancelled via API", actor="api_client",
        )
    else:
        surgery = container.surgery_service.update_status(
            surgery_id, payload.status, actor="api_client", reason=payload.reason,
            delay_minutes=payload.delay_minutes,
        )
    return SurgeryResponse(**surgery.model_dump())


@router.patch("/{surgery_id}/reschedule", response_model=SurgeryResponse)
def reschedule_surgery(
    surgery_id: str, payload: RescheduleSurgeryRequest, container: Container = Depends(get_container_dep),
) -> SurgeryResponse:
    surgery = container.surgery_service.reschedule_surgery(
        surgery_id, payload.new_date, payload.new_time, payload.new_room, actor="api_client",
    )
    return SurgeryResponse(**surgery.model_dump())


@router.post("/{surgery_id}/events", response_model=SurgeryEventResponse, status_code=status.HTTP_201_CREATED)
def add_surgery_event(
    surgery_id: str, payload: AddSurgeryEventRequest, container: Container = Depends(get_container_dep),
) -> SurgeryEventResponse:
    container.surgery_service.get_surgery(surgery_id)
    event = container.event_service.add_event(
        surgery_id=surgery_id, event_type=payload.event_type, description=payload.description, actor="api_client",
    )
    return SurgeryEventResponse.from_domain(event)


@router.get("/{surgery_id}/events", response_model=list[SurgeryEventResponse])
def get_surgery_events(surgery_id: str, container: Container = Depends(get_container_dep)) -> list[SurgeryEventResponse]:
    container.surgery_service.get_surgery(surgery_id)
    events = container.event_service.get_history(surgery_id)
    return [SurgeryEventResponse.from_domain(e) for e in events]


@router.delete("/{surgery_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_surgery(surgery_id: str, container: Container = Depends(get_container_dep)) -> None:
    """Administrative hard-delete for synthetic/test records only -- NOT used for
    normal cancellation. See module docstring."""
    container.surgery_service.delete_surgery_record(surgery_id)
