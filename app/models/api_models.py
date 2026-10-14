"""Pydantic request/response models for the FastAPI v1 API. Kept separate from
app/models/schemas.py (the persisted domain shape) so HTTP concerns -- optional
fields, pagination, free-text reasons -- never leak into the domain models.
"""
from __future__ import annotations

from datetime import date, time

from pydantic import BaseModel, Field

from app.models.schemas import Surgeon, SurgeryEvent, SurgeryPriority, SurgeryStatus


# ---------- Surgery ----------

class SurgeryResponse(BaseModel):
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
    duration_minutes: int
    status: SurgeryStatus
    priority: SurgeryPriority
    delay_minutes: int
    delay_reason: str | None
    cancellation_reason: str | None


class CreateSurgeryRequest(BaseModel):
    patient_id: str
    surgery_type: str
    surgeon_id: str
    operating_room: str
    scheduled_date: date
    scheduled_time: time
    duration_minutes: int = 60
    priority: SurgeryPriority = SurgeryPriority.ROUTINE


class UpdateSurgeryStatusRequest(BaseModel):
    status: SurgeryStatus
    reason: str | None = None
    delay_minutes: int | None = None


class RescheduleSurgeryRequest(BaseModel):
    new_date: date
    new_time: time
    new_room: str | None = None


class AddSurgeryEventRequest(BaseModel):
    event_type: str
    description: str


class SurgeryEventResponse(BaseModel):
    event_id: str
    surgery_id: str
    timestamp: str
    event_type: str
    description: str
    actor: str
    previous_value: str | None
    new_value: str | None

    @classmethod
    def from_domain(cls, event: SurgeryEvent) -> "SurgeryEventResponse":
        return cls(
            event_id=event.event_id, surgery_id=event.surgery_id, timestamp=event.timestamp.isoformat(),
            event_type=event.event_type, description=event.description, actor=event.actor,
            previous_value=event.previous_value, new_value=event.new_value,
        )


# ---------- Operating rooms ----------

class OperatingRoomResponse(BaseModel):
    room_id: str
    name: str
    floor: str


class AvailabilityRequest(BaseModel):
    on_date: date
    window_start: time
    window_end: time


class RoomAvailabilityResponse(BaseModel):
    room_id: str
    date: date
    is_available: bool
    conflicting_surgeries: list[SurgeryResponse]


# ---------- Surgeons ----------

class SurgeonResponse(BaseModel):
    surgeon_id: str
    name: str
    specialty: str

    @classmethod
    def from_domain(cls, surgeon: Surgeon) -> "SurgeonResponse":
        return cls(surgeon_id=surgeon.surgeon_id, name=surgeon.name, specialty=surgeon.specialty)


# ---------- Dashboard ----------

class DashboardSummaryResponse(BaseModel):
    as_of_date: date
    total_surgeries: int
    todays_surgery_count: int
    status_breakdown: dict[str, int]
    average_delay_minutes: float
    operating_room_utilization_pct: float
    total_operating_rooms: int


# ---------- Chat / Agent ----------

class ToolCallPayload(BaseModel):
    id: str
    name: str
    args: dict = Field(default_factory=dict)


class ChatMessage(BaseModel):
    role: str = Field(..., description="'user', 'assistant', or 'tool'")
    content: str = ""
    # Present on an 'assistant' message that triggered one or more tool calls.
    tool_calls: list[ToolCallPayload] | None = None
    # Present on a 'tool' message: which tool call this is the result of.
    tool_call_id: str | None = None
    name: str | None = None


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = Field(default_factory=list)
    actor: str = Field("staff_user", description="Identifier of the requesting staff member, for audit logging.")


class ChatResponse(BaseModel):
    response: str
    citations: list[str] = Field(default_factory=list)
    pending_action: dict | None = None
    confirmation_status: str = "none"
    history: list[ChatMessage] = Field(default_factory=list)


# ---------- Policy ----------

class PolicySearchRequest(BaseModel):
    query: str


class PolicySearchResponse(BaseModel):
    sufficient_evidence: bool
    citations: list[str]
    context: str | None = None


class PolicyIngestResponse(BaseModel):
    documents_ingested: list[str]
    page_count: int
    chunk_count: int


# ---------- Errors ----------

class ErrorResponse(BaseModel):
    error: str
    detail: str
    context: dict = Field(default_factory=dict)
