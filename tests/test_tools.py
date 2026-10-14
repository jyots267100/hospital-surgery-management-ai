from __future__ import annotations

from datetime import time

import pytest

from app.core.exceptions import NotFoundError
from app.tools import dashboard_tools, event_tools, policy_tools, surgery_tools
from tests.conftest import TODAY, TOMORROW


def test_get_todays_surgeries_tool(tool_ctx):
    result = surgery_tools.get_todays_surgeries(tool_ctx)
    assert result["count"] == 3


def test_get_delayed_surgeries_tool(tool_ctx):
    result = surgery_tools.get_delayed_surgeries(tool_ctx)
    assert result["count"] == 1
    assert result["surgeries"][0]["surgery_id"] == "S1002"


def test_get_surgery_status_tool_valid(tool_ctx):
    result = surgery_tools.get_surgery_status(tool_ctx, "S1001")
    assert result["surgery"]["surgery_id"] == "S1001"


def test_get_surgery_status_tool_unknown_id(tool_ctx):
    with pytest.raises(NotFoundError):
        surgery_tools.get_surgery_status(tool_ctx, "S9999")


def test_get_surgery_status_tool_malformed_id(tool_ctx):
    from app.core.exceptions import ValidationError
    with pytest.raises(ValidationError):
        surgery_tools.get_surgery_status(tool_ctx, "")


def test_search_hospital_policy_tool_sufficient_evidence(tool_ctx):
    result = policy_tools.search_hospital_policy(tool_ctx, "Can a completed surgery be cancelled?")
    assert result["sufficient_evidence"] is True
    assert len(result["citations"]) > 0


def test_search_hospital_policy_tool_insufficient_evidence(tool_ctx):
    result = policy_tools.search_hospital_policy(tool_ctx, "What is the capital of France?")
    assert result["sufficient_evidence"] is False


def test_cancel_surgery_requires_confirmation_first(tool_ctx):
    result = surgery_tools.cancel_surgery(tool_ctx, "S1001", reason="patient request", confirmed=False)
    assert result["status"] == "confirmation_required"
    # Not actually cancelled yet.
    status = surgery_tools.get_surgery_status(tool_ctx, "S1001")
    assert status["surgery"]["status"] != "cancelled"


def test_cancel_surgery_executes_after_confirmation(tool_ctx):
    surgery_tools.cancel_surgery(tool_ctx, "S1001", reason="patient request", confirmed=False)
    result = surgery_tools.cancel_surgery(tool_ctx, "S1001", reason="patient request", confirmed=True)
    assert result["status"] == "executed"
    assert result["surgery"]["status"] == "cancelled"


def test_cancel_surgery_rejects_completed(tool_ctx):
    result = surgery_tools.cancel_surgery(tool_ctx, "S1004", reason="x", confirmed=True)
    assert result["status"] == "rejected"


def test_create_surgery_requires_confirmation_first(tool_ctx):
    result = surgery_tools.create_surgery(
        tool_ctx, patient_id="P101", surgery_type="Hernia Repair", surgeon_id="SG001",
        operating_room="OR-2", scheduled_date=TOMORROW, scheduled_time=time(15, 0), confirmed=False,
    )
    assert result["status"] == "confirmation_required"


def test_create_surgery_executes_after_confirmation(tool_ctx):
    result = surgery_tools.create_surgery(
        tool_ctx, patient_id="P101", surgery_type="Hernia Repair", surgeon_id="SG001",
        operating_room="OR-2", scheduled_date=TOMORROW, scheduled_time=time(15, 0), confirmed=True,
    )
    assert result["status"] == "executed"
    assert result["surgery"]["surgery_type"] == "Hernia Repair"


def test_reschedule_surgery_requires_confirmation(tool_ctx):
    result = surgery_tools.reschedule_surgery(tool_ctx, "S1003", new_date=TOMORROW, new_time=time(16, 0), confirmed=False)
    assert result["status"] == "confirmation_required"


def test_update_surgery_status_requires_confirmation(tool_ctx):
    result = surgery_tools.update_surgery_status(tool_ctx, "S1001", new_status="confirmed", confirmed=False)
    assert result["status"] == "confirmation_required"


def test_update_surgery_status_executes(tool_ctx):
    surgery_tools.update_surgery_status(tool_ctx, "S1001", new_status="confirmed", confirmed=False)
    result = surgery_tools.update_surgery_status(tool_ctx, "S1001", new_status="confirmed", confirmed=True)
    assert result["status"] == "executed"
    assert result["surgery"]["status"] == "confirmed"


def test_get_operating_room_availability_tool(tool_ctx):
    result = surgery_tools.get_operating_room_availability(
        tool_ctx, on_date=TODAY, window_start=time(9, 0), window_end=time(10, 0), room_id="OR-1",
    )
    assert result["rooms"][0]["is_available"] is False


def test_get_surgeon_schedule_tool_by_id(tool_ctx):
    result = surgery_tools.get_surgeon_schedule(tool_ctx, surgeon_id="SG001")
    assert result["count"] == 2


def test_get_surgeon_schedule_tool_by_name(tool_ctx):
    result = surgery_tools.get_surgeon_schedule(tool_ctx, surgeon_name="Sharma")
    assert result["count"] == 2


def test_get_surgeon_schedule_tool_unknown_name(tool_ctx):
    result = surgery_tools.get_surgeon_schedule(tool_ctx, surgeon_name="Nobody")
    assert result["count"] == 0


def test_get_surgery_dashboard_tool(tool_ctx):
    result = dashboard_tools.get_surgery_dashboard(tool_ctx)
    assert result["total_surgeries"] == 4


def test_add_surgery_event_tool(tool_ctx):
    result = event_tools.add_surgery_event(tool_ctx, "S1001", "note_added", "Patient confirmed fasting.")
    assert result["event"]["surgery_id"] == "S1001"
    assert result["event"]["event_type"] == "note_added"


def test_add_surgery_event_tool_unknown_surgery(tool_ctx):
    with pytest.raises(NotFoundError):
        event_tools.add_surgery_event(tool_ctx, "S9999", "note_added", "x")


def test_create_surgery_args_tolerates_explicit_null_for_defaulted_fields():
    """Regression test: found live against Ollama (llama3.1:8b) -- the model
    emitted {"duration_minutes": null, "priority": null, "confirmed": null}
    instead of omitting those keys, which previously failed Pydantic
    validation (a default only applies when a key is absent, not when it's
    explicitly null) and forced an extra, avoidable confirmation round-trip."""
    from app.tools.schema import CancelSurgeryArgs, CreateSurgeryArgs

    args = CreateSurgeryArgs(
        patient_id="P101", surgery_type="Knee Replacement", surgeon_id="SG001", operating_room="OR-2",
        scheduled_date="2026-10-15", scheduled_time="14:00:00",
        duration_minutes=None, priority=None, confirmed=None,
    )
    assert args.duration_minutes == 60
    assert args.priority == "routine"
    assert args.confirmed is False

    cancel_args = CancelSurgeryArgs(surgery_id="S1001", reason="x", confirmed=None)
    assert cancel_args.confirmed is False


def test_create_surgery_tool_succeeds_with_null_optional_args(tool_ctx):
    """End-to-end: a tool call shaped exactly like the one that failed live
    (explicit nulls for duration_minutes/priority) must still execute once
    confirmed, not raise a validation error."""
    from app.tools.schema import CreateSurgeryArgs

    validated = CreateSurgeryArgs(
        patient_id="P101", surgery_type="Hernia Repair", surgeon_id="SG001", operating_room="OR-2",
        scheduled_date=TOMORROW, scheduled_time=time(15, 0),
        duration_minutes=None, priority=None, confirmed=True,
    )
    result = surgery_tools.create_surgery(tool_ctx, **validated.model_dump())
    assert result["status"] == "executed"
    assert result["surgery"]["duration_minutes"] == 60
    assert result["surgery"]["priority"] == "routine"
