"""Generates synthetic hospital data (patients, surgeons, operating rooms, surgeries,
surgery events) as JSON files under ./data.

Surgery dates are generated RELATIVE TO THE CURRENT DATE so that "today's surgeries"
and "delayed surgeries" demos are always meaningful. Re-run this script to refresh
the dataset relative to a new "today" (e.g. `python scripts/generate_synthetic_data.py`).

All data is synthetic and fictional. No real patient information is used.
"""
from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

SURGEONS = [
    {"surgeon_id": "SG001", "name": "Dr. Ananya Sharma", "specialty": "Orthopedics"},
    {"surgeon_id": "SG002", "name": "Dr. Rohan Mehta", "specialty": "Cardiothoracic Surgery"},
    {"surgeon_id": "SG003", "name": "Dr. Kavita Nair", "specialty": "General Surgery"},
    {"surgeon_id": "SG004", "name": "Dr. Vikram Rao", "specialty": "Neurosurgery"},
    {"surgeon_id": "SG005", "name": "Dr. Priya Iyer", "specialty": "ENT Surgery"},
    {"surgeon_id": "SG006", "name": "Dr. Arjun Kapoor", "specialty": "Urology"},
]

OPERATING_ROOMS = [
    {"room_id": "OR-1", "name": "Operating Room 1", "floor": "2nd Floor"},
    {"room_id": "OR-2", "name": "Operating Room 2", "floor": "2nd Floor"},
    {"room_id": "OR-3", "name": "Operating Room 3", "floor": "3rd Floor"},
    {"room_id": "OR-4", "name": "Operating Room 4", "floor": "3rd Floor"},
    {"room_id": "OR-5", "name": "Operating Room 5 (Emergency)", "floor": "Ground Floor"},
]

PATIENT_NAMES = [
    ("Ramesh Gupta", 58, "M"), ("Sunita Verma", 45, "F"), ("Arvind Joshi", 67, "M"),
    ("Meena Pillai", 34, "F"), ("Deepak Chawla", 72, "M"), ("Lakshmi Reddy", 51, "F"),
    ("Sanjay Bhatt", 39, "M"), ("Anita Desai", 63, "F"), ("Manoj Tiwari", 29, "M"),
    ("Pooja Malhotra", 48, "F"), ("Ravi Kulkarni", 55, "M"), ("Shalini Menon", 41, "F"),
    ("Suresh Yadav", 60, "M"), ("Geeta Agarwal", 37, "F"), ("Naveen Shetty", 66, "M"),
    ("Kiran Bedi Rao", 44, "F"), ("Ashok Pandey", 71, "M"), ("Rekha Saxena", 33, "F"),
    ("Vijay Kumar", 54, "M"), ("Nisha Thakur", 49, "F"),
]

SURGERY_TYPES = [
    "Knee Replacement", "Coronary Artery Bypass", "Appendectomy", "Craniotomy",
    "Tonsillectomy", "Kidney Stone Removal", "Hip Replacement", "Gallbladder Removal",
    "Cataract Surgery", "Hernia Repair", "Spinal Fusion", "Cystoscopy",
]

STATUS_SCHEDULED = "scheduled"
STATUS_CONFIRMED = "confirmed"
STATUS_IN_PROGRESS = "in_progress"
STATUS_COMPLETED = "completed"
STATUS_DELAYED = "delayed"
STATUS_CANCELLED = "cancelled"


def build_patients() -> list[dict]:
    patients = []
    for i, (name, age, gender) in enumerate(PATIENT_NAMES, start=1):
        patients.append({
            "patient_id": f"P{100 + i}",
            "name": name,
            "age": age,
            "gender": gender,
        })
    return patients


def iso_now() -> str:
    # Timezone-aware (UTC), matching EventService.add_event -- mixing naive and
    # aware datetimes in the same list breaks sorting (see event_repository.py's
    # find_by_surgery, which sorts by timestamp across seed + live-written events).
    return datetime.now(timezone.utc).isoformat()


def build_surgeries(patients: list[dict]) -> tuple[list[dict], list[dict]]:
    today = date.today()
    surgeries: list[dict] = []
    events: list[dict] = []
    seq = 0

    def add_surgery(
        offset_days: int,
        hour: int,
        minute: int,
        surgeon_idx: int,
        room_idx: int,
        surgery_type: str,
        patient: dict,
        status: str,
        priority: str = "routine",
        delay_minutes: int = 0,
        delay_reason: str | None = None,
        duration_minutes: int = 60,
        cancellation_reason: str | None = None,
    ) -> dict:
        nonlocal seq
        seq += 1
        surgery_id = f"S{1000 + seq}"
        surgeon = SURGEONS[surgeon_idx]
        room = OPERATING_ROOMS[room_idx]
        scheduled_date = today + timedelta(days=offset_days)
        created_at = datetime.combine(
            scheduled_date - timedelta(days=3), time(9, 0), tzinfo=timezone.utc,
        ).isoformat()
        record = {
            "surgery_id": surgery_id,
            "patient_id": patient["patient_id"],
            "patient_name": patient["name"],
            "age": patient["age"],
            "surgery_type": surgery_type,
            "surgeon_id": surgeon["surgeon_id"],
            "surgeon_name": surgeon["name"],
            "operating_room": room["room_id"],
            "scheduled_date": scheduled_date.isoformat(),
            "scheduled_time": f"{hour:02d}:{minute:02d}:00",
            "duration_minutes": duration_minutes,
            "status": status,
            "priority": priority,
            "delay_minutes": delay_minutes,
            "delay_reason": delay_reason,
            "cancellation_reason": cancellation_reason,
            "created_at": created_at,
            "updated_at": created_at,
        }
        surgeries.append(record)
        events.append({
            "event_id": f"E{2000 + seq}",
            "surgery_id": surgery_id,
            "timestamp": created_at,
            "event_type": "surgery_created",
            "description": f"Surgery {surgery_id} scheduled for {patient['name']} ({surgery_type}) "
                            f"with {surgeon['name']} in {room['room_id']}.",
            "actor": "system_seed",
            "previous_value": None,
            "new_value": status,
        })
        if status == STATUS_DELAYED:
            events.append({
                "event_id": f"E{2000 + seq}D",
                "surgery_id": surgery_id,
                "timestamp": iso_now(),
                "event_type": "surgery_delayed",
                "description": f"Surgery {surgery_id} delayed by {delay_minutes} minutes: {delay_reason}",
                "actor": "system_seed",
                "previous_value": STATUS_SCHEDULED,
                "new_value": STATUS_DELAYED,
            })
        if status == STATUS_CANCELLED:
            events.append({
                "event_id": f"E{2000 + seq}C",
                "surgery_id": surgery_id,
                "timestamp": iso_now(),
                "event_type": "surgery_cancelled",
                "description": f"Surgery {surgery_id} cancelled: {cancellation_reason}",
                "actor": "system_seed",
                "previous_value": STATUS_SCHEDULED,
                "new_value": STATUS_CANCELLED,
            })
        if status == STATUS_COMPLETED:
            events.append({
                "event_id": f"E{2000 + seq}P",
                "surgery_id": surgery_id,
                "timestamp": iso_now(),
                "event_type": "status_changed",
                "description": f"Surgery {surgery_id} marked completed.",
                "actor": "system_seed",
                "previous_value": STATUS_IN_PROGRESS,
                "new_value": STATUS_COMPLETED,
            })
        return record

    p = patients

    # --- Yesterday: completed + one cancelled (history/audit demo) ---
    add_surgery(-1, 9, 0, 0, 0, "Knee Replacement", p[0], STATUS_COMPLETED, duration_minutes=120)
    add_surgery(-1, 11, 30, 2, 2, "Appendectomy", p[1], STATUS_COMPLETED, duration_minutes=60)
    add_surgery(-1, 14, 0, 1, 1, "Coronary Artery Bypass", p[2], STATUS_CANCELLED,
                 cancellation_reason="Patient developed fever; rescheduled per Surgery Cancellation Policy.")

    # --- Today: mix of statuses, including delayed (for get_delayed_surgeries demo) ---
    add_surgery(0, 8, 0, 0, 0, "Hip Replacement", p[3], STATUS_IN_PROGRESS, priority="urgent", duration_minutes=150)
    add_surgery(0, 9, 30, 2, 2, "Hernia Repair", p[4], STATUS_DELAYED, delay_minutes=45,
                 delay_reason="Preceding emergency case overran in OR-3.")
    add_surgery(0, 10, 0, 4, 3, "Tonsillectomy", p[5], STATUS_CONFIRMED, duration_minutes=45)
    add_surgery(0, 11, 0, 1, 1, "Coronary Artery Bypass", p[6], STATUS_DELAYED, priority="urgent", delay_minutes=30,
                 delay_reason="Awaiting updated cardiology clearance.")
    add_surgery(0, 13, 0, 5, 4, "Kidney Stone Removal", p[7], STATUS_SCHEDULED, duration_minutes=60)
    add_surgery(0, 14, 30, 3, 3, "Craniotomy", p[8], STATUS_SCHEDULED, priority="emergency", duration_minutes=180)
    add_surgery(0, 15, 0, 0, 0, "Spinal Fusion", p[9], STATUS_SCHEDULED, duration_minutes=150)
    add_surgery(0, 16, 0, 2, 2, "Cataract Surgery", p[10], STATUS_CONFIRMED, duration_minutes=30)

    # --- Tomorrow: for reschedule / availability demos ---
    add_surgery(1, 9, 0, 0, 1, "Knee Replacement", p[11], STATUS_SCHEDULED, duration_minutes=120)
    add_surgery(1, 10, 0, 4, 3, "Tonsillectomy", p[12], STATUS_SCHEDULED, duration_minutes=45)
    add_surgery(1, 11, 0, 5, 4, "Cystoscopy", p[13], STATUS_SCHEDULED, duration_minutes=45)
    add_surgery(1, 13, 30, 1, 1, "Coronary Artery Bypass", p[14], STATUS_SCHEDULED, priority="urgent", duration_minutes=180)

    # --- Day after tomorrow / this week: more variety, multiple surgeons/ORs ---
    add_surgery(2, 9, 0, 2, 2, "Gallbladder Removal", p[15], STATUS_SCHEDULED, duration_minutes=90)
    add_surgery(2, 10, 30, 3, 3, "Craniotomy", p[16], STATUS_SCHEDULED, duration_minutes=180)
    add_surgery(3, 9, 0, 0, 0, "Hip Replacement", p[17], STATUS_SCHEDULED, duration_minutes=150)
    add_surgery(3, 14, 0, 5, 4, "Kidney Stone Removal", p[18], STATUS_SCHEDULED, duration_minutes=60)
    add_surgery(4, 9, 0, 4, 3, "Tonsillectomy", p[19], STATUS_SCHEDULED, duration_minutes=45)

    return surgeries, events


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    patients = build_patients()
    surgeries, events = build_surgeries(patients)

    (DATA_DIR / "patients.json").write_text(json.dumps(patients, indent=2), encoding="utf-8")
    (DATA_DIR / "surgeons.json").write_text(json.dumps(SURGEONS, indent=2), encoding="utf-8")
    (DATA_DIR / "operating_rooms.json").write_text(json.dumps(OPERATING_ROOMS, indent=2), encoding="utf-8")
    (DATA_DIR / "surgeries.json").write_text(json.dumps(surgeries, indent=2), encoding="utf-8")
    (DATA_DIR / "surgery_events.json").write_text(json.dumps(events, indent=2), encoding="utf-8")

    print(f"Generated {len(patients)} patients, {len(SURGEONS)} surgeons, "
          f"{len(OPERATING_ROOMS)} operating rooms, {len(surgeries)} surgeries, "
          f"{len(events)} events into {DATA_DIR}")


if __name__ == "__main__":
    main()
