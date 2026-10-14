"""Converts domain models into the minimal JSON-safe dicts exposed to the LLM and
API, avoiding unnecessary patient data exposure (e.g. no raw file paths, no
internal-only fields)."""
from __future__ import annotations

from app.models.schemas import OperatingRoom, Surgeon, Surgery, SurgeryEvent


def surgery_to_dict(s: Surgery) -> dict:
    return {
        "surgery_id": s.surgery_id,
        "patient_id": s.patient_id,
        "patient_name": s.patient_name,
        "age": s.age,
        "surgery_type": s.surgery_type,
        "surgeon_id": s.surgeon_id,
        "surgeon_name": s.surgeon_name,
        "operating_room": s.operating_room,
        "scheduled_date": s.scheduled_date.isoformat(),
        "scheduled_time": s.scheduled_time.isoformat(),
        "duration_minutes": s.duration_minutes,
        "status": s.status.value,
        "priority": s.priority.value,
        "delay_minutes": s.delay_minutes,
        "delay_reason": s.delay_reason,
        "cancellation_reason": s.cancellation_reason,
    }


def surgeon_to_dict(s: Surgeon) -> dict:
    return {"surgeon_id": s.surgeon_id, "name": s.name, "specialty": s.specialty}


def room_to_dict(r: OperatingRoom) -> dict:
    return {"room_id": r.room_id, "name": r.name, "floor": r.floor}


def event_to_dict(e: SurgeryEvent) -> dict:
    return {
        "event_id": e.event_id,
        "surgery_id": e.surgery_id,
        "timestamp": e.timestamp.isoformat(),
        "event_type": e.event_type,
        "description": e.description,
        "actor": e.actor,
        "previous_value": e.previous_value,
        "new_value": e.new_value,
    }
