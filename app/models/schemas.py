"""Core domain models (Pydantic) shared by repositories, services, and tools.

These represent the persisted shape of entities. API request/response models
that wrap these for HTTP concerns live in app/models/api_models.py.
"""
from __future__ import annotations

from datetime import date, datetime, time
from enum import Enum

from pydantic import BaseModel, Field


class SurgeryStatus(str, Enum):
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    DELAYED = "delayed"
    CANCELLED = "cancelled"


class SurgeryPriority(str, Enum):
    ROUTINE = "routine"
    URGENT = "urgent"
    EMERGENCY = "emergency"


# Status transitions allowed by business rules (see docs/architecture.md).
ALLOWED_STATUS_TRANSITIONS: dict[SurgeryStatus, set[SurgeryStatus]] = {
    SurgeryStatus.SCHEDULED: {SurgeryStatus.CONFIRMED, SurgeryStatus.DELAYED, SurgeryStatus.CANCELLED},
    SurgeryStatus.CONFIRMED: {SurgeryStatus.IN_PROGRESS, SurgeryStatus.DELAYED, SurgeryStatus.CANCELLED},
    SurgeryStatus.DELAYED: {SurgeryStatus.CONFIRMED, SurgeryStatus.IN_PROGRESS, SurgeryStatus.CANCELLED},
    SurgeryStatus.IN_PROGRESS: {SurgeryStatus.COMPLETED, SurgeryStatus.DELAYED},
    SurgeryStatus.COMPLETED: set(),
    SurgeryStatus.CANCELLED: set(),
}


class Patient(BaseModel):
    patient_id: str
    name: str
    age: int
    gender: str


class Surgeon(BaseModel):
    surgeon_id: str
    name: str
    specialty: str


class OperatingRoom(BaseModel):
    room_id: str
    name: str
    floor: str


class Surgery(BaseModel):
    surgery_id: str
    patient_id: str
    patient_name: str
    age: int
    surgery_type: str
    surgeon_id: str
    surgeon_name: str
    operating_room: str
    scheduled_date: date
    scheduled_time: time
    duration_minutes: int = 60
    status: SurgeryStatus = SurgeryStatus.SCHEDULED
    priority: SurgeryPriority = SurgeryPriority.ROUTINE
    delay_minutes: int = 0
    delay_reason: str | None = None
    cancellation_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class SurgeryEvent(BaseModel):
    event_id: str
    surgery_id: str
    timestamp: datetime
    event_type: str
    description: str
    actor: str
    previous_value: str | None = None
    new_value: str | None = None
