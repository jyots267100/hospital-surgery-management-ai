"""Agent-facing tools for reading and writing surgery records.

Every write tool (cancel, create, reschedule, update_status) follows the same
two-step confirmation workflow: called with confirmed=False it validates the
request and returns a "confirmation_required" proposal describing exactly what
would happen; only a subsequent call with confirmed=True executes the change
and records an audit event. Tools never mutate data directly -- they only
translate agent intent into SurgeryService calls.
"""
from __future__ import annotations

from datetime import date, time

from app.models.schemas import SurgeryPriority, SurgeryStatus
from app.tools.context import ToolContext
from app.tools.serializers import surgery_to_dict


def get_todays_surgeries(ctx: ToolContext) -> dict:
    surgeries = ctx.surgery_service.get_todays_surgeries()
    return {"count": len(surgeries), "surgeries": [surgery_to_dict(s) for s in surgeries]}


def get_delayed_surgeries(ctx: ToolContext) -> dict:
    surgeries = ctx.surgery_service.get_delayed_surgeries()
    return {"count": len(surgeries), "surgeries": [surgery_to_dict(s) for s in surgeries]}


def get_surgery_status(ctx: ToolContext, surgery_id: str) -> dict:
    surgery = ctx.surgery_service.get_surgery(surgery_id)
    return {"surgery": surgery_to_dict(surgery)}


def cancel_surgery(ctx: ToolContext, surgery_id: str, reason: str, confirmed: bool = False) -> dict:
    eligible, eligibility_message = ctx.surgery_service.check_cancellation_eligibility(surgery_id)
    surgery = ctx.surgery_service.get_surgery(surgery_id)

    if not eligible:
        return {"status": "rejected", "reason": eligibility_message, "surgery": surgery_to_dict(surgery)}

    if not confirmed:
        return {
            "status": "confirmation_required",
            "proposed_action": "cancel_surgery",
            "surgery": surgery_to_dict(surgery),
            "eligibility": eligibility_message,
            "message": (
                f"Surgery {surgery_id} ({surgery.surgery_type} for {surgery.patient_name}, "
                f"scheduled {surgery.scheduled_date} at {surgery.scheduled_time}) is eligible for "
                f"cancellation. Reason given: '{reason}'. Do you want me to proceed with cancellation?"
            ),
        }

    updated = ctx.surgery_service.cancel_surgery(surgery_id, reason=reason, actor=ctx.actor)
    return {"status": "executed", "surgery": surgery_to_dict(updated)}


def create_surgery(
    ctx: ToolContext,
    patient_id: str,
    surgery_type: str,
    surgeon_id: str,
    operating_room: str,
    scheduled_date: date,
    scheduled_time: time,
    duration_minutes: int = 60,
    priority: str = "routine",
    confirmed: bool = False,
) -> dict:
    priority_enum = SurgeryPriority(priority)
    ctx.surgery_service.validate_new_surgery(
        patient_id, surgery_type, surgeon_id, operating_room, scheduled_date, scheduled_time, duration_minutes,
    )

    if not confirmed:
        return {
            "status": "confirmation_required",
            "proposed_action": "create_surgery",
            "proposed_surgery": {
                "patient_id": patient_id,
                "surgery_type": surgery_type,
                "surgeon_id": surgeon_id,
                "operating_room": operating_room,
                "scheduled_date": scheduled_date.isoformat(),
                "scheduled_time": scheduled_time.isoformat(),
                "duration_minutes": duration_minutes,
                "priority": priority,
            },
            "message": (
                f"Ready to schedule a {surgery_type} for patient {patient_id} with surgeon {surgeon_id} "
                f"in {operating_room} on {scheduled_date} at {scheduled_time}. No scheduling conflicts "
                f"were found. Confirm scheduling?"
            ),
        }

    created = ctx.surgery_service.create_surgery(
        patient_id=patient_id,
        surgery_type=surgery_type,
        surgeon_id=surgeon_id,
        operating_room=operating_room,
        scheduled_date=scheduled_date,
        scheduled_time=scheduled_time,
        duration_minutes=duration_minutes,
        priority=priority_enum,
        actor=ctx.actor,
    )
    return {"status": "executed", "surgery": surgery_to_dict(created)}


def reschedule_surgery(
    ctx: ToolContext,
    surgery_id: str,
    new_date: date,
    new_time: time,
    new_room: str | None = None,
    confirmed: bool = False,
) -> dict:
    current = ctx.surgery_service.validate_reschedule(surgery_id, new_date, new_time, new_room)

    if not confirmed:
        return {
            "status": "confirmation_required",
            "proposed_action": "reschedule_surgery",
            "current_surgery": surgery_to_dict(current),
            "proposed_change": {
                "new_date": new_date.isoformat(),
                "new_time": new_time.isoformat(),
                "new_room": new_room or current.operating_room,
            },
            "message": (
                f"Ready to move surgery {surgery_id} from {current.scheduled_date} {current.scheduled_time} "
                f"to {new_date} {new_time} in {new_room or current.operating_room}. No conflicts were found. "
                f"Confirm reschedule?"
            ),
        }

    updated = ctx.surgery_service.reschedule_surgery(surgery_id, new_date, new_time, new_room, actor=ctx.actor)
    return {"status": "executed", "surgery": surgery_to_dict(updated)}


def update_surgery_status(
    ctx: ToolContext,
    surgery_id: str,
    new_status: str,
    reason: str | None = None,
    delay_minutes: int | None = None,
    confirmed: bool = False,
) -> dict:
    status_enum = SurgeryStatus(new_status)
    current = ctx.surgery_service.validate_status_transition(surgery_id, status_enum)

    if not confirmed:
        return {
            "status": "confirmation_required",
            "proposed_action": "update_surgery_status",
            "current_surgery": surgery_to_dict(current),
            "proposed_new_status": status_enum.value,
            "message": (
                f"Ready to change surgery {surgery_id} status from '{current.status.value}' to "
                f"'{status_enum.value}'" + (f" (reason: {reason})" if reason else "") + ". Confirm?"
            ),
        }

    updated = ctx.surgery_service.update_status(
        surgery_id, status_enum, actor=ctx.actor, reason=reason, delay_minutes=delay_minutes,
    )
    return {"status": "executed", "surgery": surgery_to_dict(updated)}


def get_operating_room_availability(
    ctx: ToolContext, on_date: date, window_start: time, window_end: time, room_id: str | None = None,
) -> dict:
    if room_id:
        result = ctx.operating_room_service.get_availability(room_id, on_date, window_start, window_end)
        results = [result]
    else:
        results = ctx.operating_room_service.get_all_rooms_availability(on_date, window_start, window_end)

    return {
        "date": on_date.isoformat(),
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "rooms": [
            {
                "room_id": r["room_id"],
                "is_available": r["is_available"],
                "conflicting_surgeries": [surgery_to_dict(s) for s in r["conflicting_surgeries"]],
            }
            for r in results
        ],
    }


def get_surgeon_schedule(
    ctx: ToolContext, surgeon_id: str | None = None, surgeon_name: str | None = None, on_date: date | None = None,
) -> dict:
    if not surgeon_id and surgeon_name:
        matches = ctx.surgeon_service.find_by_name(surgeon_name)
        if not matches:
            return {"count": 0, "surgeries": [], "message": f"No surgeon found matching '{surgeon_name}'."}
        surgeon_id = matches[0].surgeon_id

    if not surgeon_id:
        return {"count": 0, "surgeries": [], "message": "surgeon_id or surgeon_name is required."}

    surgeries = ctx.surgeon_service.get_schedule(surgeon_id, on_date)
    return {"surgeon_id": surgeon_id, "count": len(surgeries), "surgeries": [surgery_to_dict(s) for s in surgeries]}
