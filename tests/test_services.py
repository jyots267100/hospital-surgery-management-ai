from __future__ import annotations

from datetime import time

import pytest

from app.core.exceptions import ConflictError, InvalidStateTransitionError, NotFoundError, ValidationError
from app.models.schemas import SurgeryStatus
from tests.conftest import TODAY, TOMORROW


def test_get_todays_surgeries(surgery_service):
    surgeries = surgery_service.get_todays_surgeries()
    ids = {s.surgery_id for s in surgeries}
    assert ids == {"S1001", "S1002", "S1004"}


def test_get_delayed_surgeries(surgery_service):
    delayed = surgery_service.get_delayed_surgeries()
    assert len(delayed) == 1
    assert delayed[0].surgery_id == "S1002"


def test_get_surgery_not_found_raises(surgery_service):
    with pytest.raises(NotFoundError):
        surgery_service.get_surgery("S9999")


def test_get_surgery_malformed_id_raises(surgery_service):
    with pytest.raises(ValidationError):
        surgery_service.get_surgery("   ")


def test_room_conflict_detected(surgery_service):
    conflict = surgery_service.check_room_conflict("OR-1", TODAY, time(9, 15), 30)
    assert conflict is not None and conflict.surgery_id == "S1001"


def test_room_conflict_excludes_self(surgery_service):
    conflict = surgery_service.check_room_conflict("OR-1", TODAY, time(9, 15), 30, exclude_surgery_id="S1001")
    assert conflict is None


def test_create_surgery_rejects_room_conflict(surgery_service):
    with pytest.raises(ConflictError):
        surgery_service.create_surgery(
            patient_id="P101", surgery_type="Hernia Repair", surgeon_id="SG002",
            operating_room="OR-1", scheduled_date=TODAY, scheduled_time=time(9, 15), duration_minutes=30,
        )


def test_create_surgery_rejects_surgeon_conflict(surgery_service):
    with pytest.raises(ConflictError):
        surgery_service.create_surgery(
            patient_id="P101", surgery_type="Hernia Repair", surgeon_id="SG001",
            operating_room="OR-2", scheduled_date=TODAY, scheduled_time=time(9, 15), duration_minutes=30,
        )


def test_create_surgery_unknown_patient_raises(surgery_service):
    with pytest.raises(NotFoundError):
        surgery_service.create_surgery(
            patient_id="P999", surgery_type="Hernia Repair", surgeon_id="SG001",
            operating_room="OR-2", scheduled_date=TOMORROW, scheduled_time=time(15, 0),
        )


def test_create_surgery_success(surgery_service):
    created = surgery_service.create_surgery(
        patient_id="P101", surgery_type="Hernia Repair", surgeon_id="SG001",
        operating_room="OR-2", scheduled_date=TOMORROW, scheduled_time=time(15, 0), duration_minutes=45,
    )
    assert created.status == SurgeryStatus.SCHEDULED
    assert surgery_service.get_surgery(created.surgery_id) is not None


def test_reschedule_rejects_conflict(surgery_service):
    with pytest.raises(ConflictError):
        surgery_service.reschedule_surgery("S1003", TODAY, time(9, 15), new_room="OR-1")


def test_reschedule_success(surgery_service):
    updated = surgery_service.reschedule_surgery("S1003", TOMORROW, time(16, 0))
    assert updated.scheduled_time == time(16, 0)


def test_reschedule_cancelled_surgery_fails(surgery_service):
    surgery_service.update_status("S1001", SurgeryStatus.CANCELLED, reason="test")
    with pytest.raises(InvalidStateTransitionError):
        surgery_service.reschedule_surgery("S1001", TOMORROW, time(9, 0))


def test_status_transition_valid(surgery_service):
    updated = surgery_service.update_status("S1001", SurgeryStatus.CONFIRMED)
    assert updated.status == SurgeryStatus.CONFIRMED


def test_status_transition_invalid_jump_rejected(surgery_service):
    with pytest.raises(InvalidStateTransitionError):
        surgery_service.update_status("S1001", SurgeryStatus.COMPLETED)


def test_completed_cannot_transition(surgery_service):
    with pytest.raises(InvalidStateTransitionError):
        surgery_service.update_status("S1004", SurgeryStatus.SCHEDULED)


def test_cancel_completed_surgery_rejected(surgery_service):
    eligible, _ = surgery_service.check_cancellation_eligibility("S1004")
    assert eligible is False
    with pytest.raises(InvalidStateTransitionError):
        surgery_service.cancel_surgery("S1004", reason="test")


def test_cancel_eligible_surgery_succeeds(surgery_service):
    updated = surgery_service.cancel_surgery("S1001", reason="patient request")
    assert updated.status == SurgeryStatus.CANCELLED
    assert updated.cancellation_reason == "patient request"


def test_cancel_creates_audit_event(surgery_service, event_service):
    surgery_service.cancel_surgery("S1001", reason="patient request")
    events = event_service.get_history("S1001")
    assert any(e.event_type == "surgery_cancelled" for e in events)


def test_operating_room_availability(operating_room_service):
    result = operating_room_service.get_availability("OR-1", TODAY, time(9, 0), time(10, 0))
    assert result["is_available"] is False
    assert any(s.surgery_id == "S1001" for s in result["conflicting_surgeries"])


def test_operating_room_availability_free_window(operating_room_service):
    result = operating_room_service.get_availability("OR-1", TODAY, time(12, 0), time(13, 0))
    assert result["is_available"] is True


def test_surgeon_schedule(surgeon_service):
    surgeries = surgeon_service.get_schedule("SG001")
    assert {s.surgery_id for s in surgeries} == {"S1001", "S1003"}


def test_dashboard_summary(dashboard_service):
    summary = dashboard_service.get_summary()
    assert summary["total_surgeries"] == 4
    assert summary["todays_surgery_count"] == 3
    assert summary["status_breakdown"]["delayed"] == 1
