"""Pydantic argument schemas for every agent tool. These double as the
LangChain `args_schema` for each tool and as the contract tests validate against.
"""
from __future__ import annotations

from datetime import date, time
from typing import Any

from pydantic import BaseModel, Field, field_validator


def _none_becomes_default(*field_names: str):
    """Some tool-calling models (observed with a local Llama 3.1 via Ollama)
    emit an explicit `null` for an optional/defaulted argument instead of
    omitting it -- e.g. {"duration_minutes": null} rather than leaving it out.
    Pydantic only applies a field's default when the key is absent, so an
    explicit null for an `int`/`bool`/`str` field still fails validation.
    This validator treats an explicit null the same as "omitted" for the
    named fields, falling back to each field's own default."""

    @field_validator(*field_names, mode="before")
    @classmethod
    def _coerce(cls, value: Any, info) -> Any:  # noqa: ANN401
        if value is None:
            return cls.model_fields[info.field_name].default
        return value

    return _coerce


class GetTodaysSurgeriesArgs(BaseModel):
    pass


class GetDelayedSurgeriesArgs(BaseModel):
    pass


class GetSurgeryStatusArgs(BaseModel):
    surgery_id: str = Field(..., description="The surgery identifier, e.g. 'S1004'.")


class SearchHospitalPolicyArgs(BaseModel):
    query: str = Field(..., description="Natural-language question about hospital policy.")


class CancelSurgeryArgs(BaseModel):
    surgery_id: str = Field(..., description="The surgery identifier to cancel.")
    reason: str = Field(..., description="Reason for cancellation.")
    confirmed: bool = Field(
        False, description="True only once the user has explicitly confirmed the cancellation.",
    )

    _coerce_nulls = _none_becomes_default("confirmed")


class CreateSurgeryArgs(BaseModel):
    patient_id: str = Field(..., description="Registered patient identifier, e.g. 'P102'.")
    surgery_type: str = Field(..., description="Procedure name, e.g. 'Knee Replacement'.")
    surgeon_id: str = Field(..., description="Registered surgeon identifier, e.g. 'SG001'.")
    operating_room: str = Field(..., description="Operating room identifier, e.g. 'OR-2'.")
    scheduled_date: date = Field(..., description="Date of the surgery (YYYY-MM-DD).")
    scheduled_time: time = Field(..., description="Start time of the surgery (HH:MM:SS).")
    duration_minutes: int = Field(60, description="Estimated duration in minutes.")
    priority: str = Field("routine", description="One of: routine, urgent, emergency.")
    confirmed: bool = Field(
        False, description="True only once the user has explicitly confirmed the new surgery.",
    )

    _coerce_nulls = _none_becomes_default("duration_minutes", "priority", "confirmed")


class RescheduleSurgeryArgs(BaseModel):
    surgery_id: str = Field(..., description="The surgery identifier to reschedule.")
    new_date: date = Field(..., description="New date (YYYY-MM-DD).")
    new_time: time = Field(..., description="New start time (HH:MM:SS).")
    new_room: str | None = Field(None, description="New operating room, if changing. Omit to keep the current room.")
    confirmed: bool = Field(
        False, description="True only once the user has explicitly confirmed the reschedule.",
    )

    _coerce_nulls = _none_becomes_default("confirmed")


class UpdateSurgeryStatusArgs(BaseModel):
    surgery_id: str = Field(..., description="The surgery identifier.")
    new_status: str = Field(
        ..., description="One of: scheduled, confirmed, in_progress, completed, delayed, cancelled.",
    )
    reason: str | None = Field(None, description="Reason for the status change (required for delayed/cancelled).")
    delay_minutes: int | None = Field(None, description="Delay duration in minutes, required when new_status is 'delayed'.")
    confirmed: bool = Field(
        False, description="True only once the user has explicitly confirmed the status change.",
    )

    _coerce_nulls = _none_becomes_default("confirmed")


class GetOperatingRoomAvailabilityArgs(BaseModel):
    room_id: str | None = Field(None, description="Specific operating room id, e.g. 'OR-2'. Omit to check all rooms.")
    on_date: date = Field(..., description="Date to check availability for.")
    window_start: time = Field(..., description="Start of the time window to check.")
    window_end: time = Field(..., description="End of the time window to check.")


class GetSurgeonScheduleArgs(BaseModel):
    surgeon_id: str | None = Field(None, description="Surgeon identifier, e.g. 'SG001'.")
    surgeon_name: str | None = Field(None, description="Surgeon name or partial name, e.g. 'Sharma', used if surgeon_id is unknown.")
    on_date: date | None = Field(None, description="Optional date filter.")


class GetSurgeryDashboardArgs(BaseModel):
    pass


class AddSurgeryEventArgs(BaseModel):
    surgery_id: str = Field(..., description="The surgery identifier this event relates to.")
    event_type: str = Field(..., description="Short event type, e.g. 'note_added'.")
    description: str = Field(..., description="Human-readable description of the event.")
