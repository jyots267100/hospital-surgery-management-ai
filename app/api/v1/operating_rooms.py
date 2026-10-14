from __future__ import annotations

from datetime import date, time

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_container_dep
from app.dependencies import Container
from app.models.api_models import OperatingRoomResponse, RoomAvailabilityResponse, SurgeryResponse

router = APIRouter(prefix="/operating-rooms", tags=["operating-rooms"])


@router.get("", response_model=list[OperatingRoomResponse])
def list_rooms(container: Container = Depends(get_container_dep)) -> list[OperatingRoomResponse]:
    return [OperatingRoomResponse(**r.model_dump()) for r in container.operating_room_service.list_rooms()]


@router.get("/{room_id}", response_model=OperatingRoomResponse)
def get_room(room_id: str, container: Container = Depends(get_container_dep)) -> OperatingRoomResponse:
    room = container.operating_room_service.get_room(room_id)
    return OperatingRoomResponse(**room.model_dump())


@router.get("/{room_id}/availability", response_model=RoomAvailabilityResponse)
def get_room_availability(
    room_id: str,
    on_date: date = Query(...),
    window_start: time = Query(...),
    window_end: time = Query(...),
    container: Container = Depends(get_container_dep),
) -> RoomAvailabilityResponse:
    result = container.operating_room_service.get_availability(room_id, on_date, window_start, window_end)
    return RoomAvailabilityResponse(
        room_id=result["room_id"],
        date=result["date"],
        is_available=result["is_available"],
        conflicting_surgeries=[SurgeryResponse(**s.model_dump()) for s in result["conflicting_surgeries"]],
    )
