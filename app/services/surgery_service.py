"""Business rules for surgery scheduling, rescheduling, status transitions and
cancellation. This is the only layer allowed to enforce scheduling conflicts and
status-transition rules; repositories only persist, tools only translate agent
intent into calls here.
"""
from __future__ import annotations

import uuid
from datetime import date as date_type
from datetime import datetime, time, timedelta, timezone

from app.core.exceptions import ConflictError, InvalidStateTransitionError, NotFoundError, ValidationError
from app.models.schemas import ALLOWED_STATUS_TRANSITIONS, Surgery, SurgeryPriority, SurgeryStatus
from app.repositories.operating_room_repository import OperatingRoomRepository
from app.repositories.patient_repository import PatientRepository
from app.repositories.surgeon_repository import SurgeonRepository
from app.repositories.surgery_repository import SurgeryRepository
from app.services.event_service import EventService

ACTIVE_STATUSES = {
    SurgeryStatus.SCHEDULED,
    SurgeryStatus.CONFIRMED,
    SurgeryStatus.DELAYED,
    SurgeryStatus.IN_PROGRESS,
}


def _time_ranges_overlap(start_a: time, duration_a: int, start_b: time, duration_b: int) -> bool:
    today = date_type.today()
    a_start = datetime.combine(today, start_a)
    a_end = a_start + timedelta(minutes=duration_a)
    b_start = datetime.combine(today, start_b)
    b_end = b_start + timedelta(minutes=duration_b)
    return a_start < b_end and b_start < a_end


class SurgeryService:
    def __init__(
        self,
        surgery_repo: SurgeryRepository,
        surgeon_repo: SurgeonRepository,
        room_repo: OperatingRoomRepository,
        patient_repo: PatientRepository,
        event_service: EventService,
    ) -> None:
        self._surgery_repo = surgery_repo
        self._surgeon_repo = surgeon_repo
        self._room_repo = room_repo
        self._patient_repo = patient_repo
        self._event_service = event_service

    # ---------- reads ----------

    def list_surgeries(self, status: SurgeryStatus | None = None) -> list[Surgery]:
        surgeries = self._surgery_repo.list_all()
        if status is not None:
            surgeries = [s for s in surgeries if s.status == status]
        return sorted(surgeries, key=lambda s: (s.scheduled_date, s.scheduled_time))

    def get_surgery(self, surgery_id: str) -> Surgery:
        if not surgery_id or not surgery_id.strip():
            raise ValidationError("surgery_id must not be empty")
        surgery = self._surgery_repo.get_by_id(surgery_id.strip())
        if surgery is None:
            raise NotFoundError(f"No surgery found with id '{surgery_id}'", surgery_id=surgery_id)
        return surgery

    def get_todays_surgeries(self) -> list[Surgery]:
        today = date_type.today().isoformat()
        surgeries = self._surgery_repo.find_by_date(today)
        return sorted(surgeries, key=lambda s: s.scheduled_time)

    def get_delayed_surgeries(self) -> list[Surgery]:
        surgeries = [s for s in self._surgery_repo.list_all() if s.status == SurgeryStatus.DELAYED]
        return sorted(surgeries, key=lambda s: s.delay_minutes, reverse=True)

    def get_surgeries_for_surgeon(self, surgeon_id: str, on_date: date_type | None = None) -> list[Surgery]:
        self._require_surgeon(surgeon_id)
        surgeries = self._surgery_repo.find_by_surgeon(surgeon_id)
        if on_date is not None:
            surgeries = [s for s in surgeries if s.scheduled_date == on_date]
        return sorted(surgeries, key=lambda s: (s.scheduled_date, s.scheduled_time))

    def get_room_schedule(self, room_id: str, on_date: date_type) -> list[Surgery]:
        self._require_room(room_id)
        surgeries = [
            s for s in self._surgery_repo.find_by_room(room_id)
            if s.scheduled_date == on_date and s.status in ACTIVE_STATUSES
        ]
        return sorted(surgeries, key=lambda s: s.scheduled_time)

    def check_room_conflict(
        self, room_id: str, on_date: date_type, start: time, duration_minutes: int,
        exclude_surgery_id: str | None = None,
    ) -> Surgery | None:
        for s in self.get_room_schedule(room_id, on_date):
            if s.surgery_id == exclude_surgery_id:
                continue
            if _time_ranges_overlap(start, duration_minutes, s.scheduled_time, s.duration_minutes):
                return s
        return None

    def check_surgeon_conflict(
        self, surgeon_id: str, on_date: date_type, start: time, duration_minutes: int,
        exclude_surgery_id: str | None = None,
    ) -> Surgery | None:
        for s in self.get_surgeries_for_surgeon(surgeon_id, on_date):
            if s.surgery_id == exclude_surgery_id or s.status not in ACTIVE_STATUSES:
                continue
            if _time_ranges_overlap(start, duration_minutes, s.scheduled_time, s.duration_minutes):
                return s
        return None

    # ---------- validation helpers ----------

    def _require_surgeon(self, surgeon_id: str) -> None:
        if self._surgeon_repo.get_by_id(surgeon_id) is None:
            raise NotFoundError(f"No surgeon found with id '{surgeon_id}'", surgeon_id=surgeon_id)

    def _require_room(self, room_id: str) -> None:
        if self._room_repo.get_by_id(room_id) is None:
            raise NotFoundError(f"No operating room found with id '{room_id}'", room_id=room_id)

    def _require_patient(self, patient_id: str):
        patient = self._patient_repo.get_by_id(patient_id)
        if patient is None:
            raise NotFoundError(f"No patient found with id '{patient_id}'", patient_id=patient_id)
        return patient

    # ---------- writes ----------

    def validate_new_surgery(
        self,
        patient_id: str,
        surgery_type: str,
        surgeon_id: str,
        operating_room: str,
        scheduled_date: date_type,
        scheduled_time: time,
        duration_minutes: int = 60,
    ) -> None:
        """Runs every check create_surgery would, without writing anything. Lets the
        agent validate a proposed surgery before asking the user for confirmation."""
        if not surgery_type or not surgery_type.strip():
            raise ValidationError("surgery_type is required")
        if duration_minutes <= 0 or duration_minutes > 600:
            raise ValidationError("duration_minutes must be between 1 and 600")

        self._require_patient(patient_id)
        self._require_surgeon(surgeon_id)
        self._require_room(operating_room)

        room_conflict = self.check_room_conflict(operating_room, scheduled_date, scheduled_time, duration_minutes)
        if room_conflict is not None:
            raise ConflictError(
                f"Operating room {operating_room} is already booked for surgery "
                f"{room_conflict.surgery_id} at {room_conflict.scheduled_time}",
                conflicting_surgery_id=room_conflict.surgery_id,
            )
        surgeon_conflict = self.check_surgeon_conflict(surgeon_id, scheduled_date, scheduled_time, duration_minutes)
        if surgeon_conflict is not None:
            raise ConflictError(
                f"Surgeon {surgeon_id} already has surgery {surgeon_conflict.surgery_id} "
                f"at {surgeon_conflict.scheduled_time}",
                conflicting_surgery_id=surgeon_conflict.surgery_id,
            )

    def create_surgery(
        self,
        patient_id: str,
        surgery_type: str,
        surgeon_id: str,
        operating_room: str,
        scheduled_date: date_type,
        scheduled_time: time,
        duration_minutes: int = 60,
        priority: SurgeryPriority = SurgeryPriority.ROUTINE,
        actor: str = "agent",
    ) -> Surgery:
        self.validate_new_surgery(
            patient_id, surgery_type, surgeon_id, operating_room, scheduled_date, scheduled_time, duration_minutes,
        )
        patient = self._require_patient(patient_id)
        surgeon = self._surgeon_repo.get_by_id(surgeon_id)
        now = datetime.now(timezone.utc)
        surgery = Surgery(
            surgery_id=f"S{uuid.uuid4().hex[:8].upper()}",
            patient_id=patient.patient_id,
            patient_name=patient.name,
            age=patient.age,
            surgery_type=surgery_type.strip(),
            surgeon_id=surgeon_id,
            surgeon_name=surgeon.name if surgeon else surgeon_id,
            operating_room=operating_room,
            scheduled_date=scheduled_date,
            scheduled_time=scheduled_time,
            duration_minutes=duration_minutes,
            status=SurgeryStatus.SCHEDULED,
            priority=priority,
            created_at=now,
            updated_at=now,
        )
        created = self._surgery_repo.create(surgery)
        self._event_service.add_event(
            surgery_id=created.surgery_id,
            event_type="surgery_created",
            description=f"Surgery scheduled: {surgery_type} for {patient.name} with {surgery.surgeon_name} "
                        f"in {operating_room} on {scheduled_date} at {scheduled_time}.",
            actor=actor,
            new_value=SurgeryStatus.SCHEDULED.value,
        )
        return created

    def validate_reschedule(
        self, surgery_id: str, new_date: date_type, new_time: time, new_room: str | None = None,
    ) -> Surgery:
        """Runs every check reschedule_surgery would, without writing. Returns the
        current surgery record so the caller can build a confirmation proposal."""
        surgery = self.get_surgery(surgery_id)
        if surgery.status == SurgeryStatus.CANCELLED:
            raise InvalidStateTransitionError(
                f"Surgery {surgery_id} is cancelled and cannot be rescheduled", surgery_id=surgery_id,
            )
        if surgery.status == SurgeryStatus.COMPLETED:
            raise InvalidStateTransitionError(
                f"Surgery {surgery_id} is already completed and cannot be rescheduled", surgery_id=surgery_id,
            )

        target_room = new_room or surgery.operating_room
        if new_room is not None:
            self._require_room(new_room)

        room_conflict = self.check_room_conflict(
            target_room, new_date, new_time, surgery.duration_minutes, exclude_surgery_id=surgery_id,
        )
        if room_conflict is not None:
            raise ConflictError(
                f"Operating room {target_room} is already booked for surgery {room_conflict.surgery_id}",
                conflicting_surgery_id=room_conflict.surgery_id,
            )
        surgeon_conflict = self.check_surgeon_conflict(
            surgery.surgeon_id, new_date, new_time, surgery.duration_minutes, exclude_surgery_id=surgery_id,
        )
        if surgeon_conflict is not None:
            raise ConflictError(
                f"Surgeon {surgery.surgeon_id} already has surgery {surgeon_conflict.surgery_id} at that time",
                conflicting_surgery_id=surgeon_conflict.surgery_id,
            )
        return surgery

    def reschedule_surgery(
        self,
        surgery_id: str,
        new_date: date_type,
        new_time: time,
        new_room: str | None = None,
        actor: str = "agent",
    ) -> Surgery:
        surgery = self.validate_reschedule(surgery_id, new_date, new_time, new_room)
        target_room = new_room or surgery.operating_room

        previous = f"{surgery.scheduled_date} {surgery.scheduled_time} in {surgery.operating_room}"
        surgery.scheduled_date = new_date
        surgery.scheduled_time = new_time
        surgery.operating_room = target_room
        surgery.status = SurgeryStatus.SCHEDULED
        surgery.updated_at = datetime.now(timezone.utc)
        updated = self._surgery_repo.update(surgery_id, surgery)

        new_value = f"{new_date} {new_time} in {target_room}"
        self._event_service.add_event(
            surgery_id=surgery_id,
            event_type="surgery_rescheduled",
            description=f"Surgery {surgery_id} rescheduled from {previous} to {new_value}.",
            actor=actor,
            previous_value=previous,
            new_value=new_value,
        )
        return updated

    def validate_status_transition(self, surgery_id: str, new_status: SurgeryStatus) -> Surgery:
        """Checks the transition is legal without writing. Returns the current surgery."""
        surgery = self.get_surgery(surgery_id)
        current = surgery.status
        allowed = ALLOWED_STATUS_TRANSITIONS.get(current, set())
        if new_status == current:
            raise InvalidStateTransitionError(
                f"Surgery {surgery_id} is already '{current.value}'", surgery_id=surgery_id,
            )
        if new_status not in allowed:
            raise InvalidStateTransitionError(
                f"Cannot transition surgery {surgery_id} from '{current.value}' to '{new_status.value}'. "
                f"Allowed next statuses: {sorted(s.value for s in allowed) or 'none'}.",
                surgery_id=surgery_id, from_status=current.value, to_status=new_status.value,
            )
        return surgery

    def update_status(
        self,
        surgery_id: str,
        new_status: SurgeryStatus,
        actor: str = "agent",
        reason: str | None = None,
        delay_minutes: int | None = None,
    ) -> Surgery:
        surgery = self.validate_status_transition(surgery_id, new_status)
        previous_value = surgery.status.value
        surgery.status = new_status
        surgery.updated_at = datetime.now(timezone.utc)

        if new_status == SurgeryStatus.DELAYED:
            surgery.delay_minutes = delay_minutes or 0
            surgery.delay_reason = reason
        if new_status == SurgeryStatus.CANCELLED:
            surgery.cancellation_reason = reason

        updated = self._surgery_repo.update(surgery_id, surgery)
        self._event_service.add_event(
            surgery_id=surgery_id,
            event_type="status_changed" if new_status != SurgeryStatus.CANCELLED else "surgery_cancelled",
            description=f"Surgery {surgery_id} status changed from '{previous_value}' to '{new_status.value}'"
                        + (f": {reason}" if reason else "") + ".",
            actor=actor,
            previous_value=previous_value,
            new_value=new_status.value,
        )
        return updated

    def check_cancellation_eligibility(self, surgery_id: str) -> tuple[bool, str]:
        """Returns (eligible, reason). Does not mutate state -- used by the agent to
        decide whether to propose cancellation before asking for confirmation."""
        surgery = self.get_surgery(surgery_id)
        if surgery.status == SurgeryStatus.COMPLETED:
            return False, "Completed surgeries cannot be cancelled."
        if surgery.status == SurgeryStatus.CANCELLED:
            return False, "Surgery is already cancelled."
        if surgery.status == SurgeryStatus.IN_PROGRESS:
            return False, "Surgery is currently in progress and cannot be cancelled."
        return True, "Eligible for cancellation."

    def cancel_surgery(self, surgery_id: str, reason: str, actor: str = "agent") -> Surgery:
        eligible, message = self.check_cancellation_eligibility(surgery_id)
        if not eligible:
            raise InvalidStateTransitionError(message, surgery_id=surgery_id)
        return self.update_status(surgery_id, SurgeryStatus.CANCELLED, actor=actor, reason=reason)

    def delete_surgery_record(self, surgery_id: str) -> None:
        """Administrative hard-delete of a synthetic/test record. NOT used for normal
        cancellation -- see docs/api.md for the DELETE-vs-cancel design decision."""
        self.get_surgery(surgery_id)  # raises NotFoundError if missing
        self._surgery_repo.delete(surgery_id)
