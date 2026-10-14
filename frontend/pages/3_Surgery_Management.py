import datetime as dt

import pandas as pd
import streamlit as st
from utils.api_client import api_call, get, patch, post

st.set_page_config(page_title="Surgery Management - Hospital Surgery AI", page_icon="🗓️", layout="wide")
st.title("🗓️ Surgery Management")

tab_search, tab_create, tab_reschedule, tab_status, tab_cancel = st.tabs(
    ["Search", "Create", "Reschedule", "Update Status", "Cancel"]
)

# ---------------- Search ----------------
with tab_search:
    surgery_id = st.text_input("Surgery ID", placeholder="e.g. S1004", key="search_id")
    if st.button("Search", key="search_btn") and surgery_id:
        surgery, err = api_call(get, f"/api/v1/surgeries/{surgery_id}")
        if err:
            st.error(err)
        else:
            st.json(surgery)

# ---------------- Create ----------------
with tab_create:
    surgeons, _ = api_call(get, "/api/v1/surgeons")
    rooms, _ = api_call(get, "/api/v1/operating-rooms")
    surgeon_options = {f"{s['name']} ({s['surgeon_id']})": s["surgeon_id"] for s in (surgeons or [])}
    room_options = {f"{r['room_id']} - {r['name']}": r["room_id"] for r in (rooms or [])}

    with st.form("create_surgery_form"):
        patient_id = st.text_input("Patient ID", placeholder="e.g. P102")
        surgery_type = st.text_input("Surgery type", placeholder="e.g. Knee Replacement")
        surgeon_label = st.selectbox("Surgeon", options=list(surgeon_options.keys()) or ["(none available)"])
        room_label = st.selectbox("Operating room", options=list(room_options.keys()) or ["(none available)"])
        c1, c2, c3 = st.columns(3)
        new_date = c1.date_input("Date", value=dt.date.today() + dt.timedelta(days=1))
        new_time = c2.time_input("Time", value=dt.time(9, 0))
        duration = c3.number_input("Duration (minutes)", min_value=15, max_value=480, value=60, step=15)
        priority = st.selectbox("Priority", ["routine", "urgent", "emergency"])
        reviewed = st.form_submit_button("Review")

    if reviewed:
        st.session_state["create_preview"] = {
            "patient_id": patient_id,
            "surgery_type": surgery_type,
            "surgeon_id": surgeon_options.get(surgeon_label, surgeon_label),
            "operating_room": room_options.get(room_label, room_label),
            "scheduled_date": new_date.isoformat(),
            "scheduled_time": new_time.isoformat(),
            "duration_minutes": int(duration),
            "priority": priority,
        }

    preview = st.session_state.get("create_preview")
    if preview:
        st.info("Review the proposed surgery before confirming:")
        st.json(preview)
        if st.button("✅ Confirm & Create"):
            created, err = api_call(post, "/api/v1/surgeries", json=preview)
            if err:
                st.error(err)
            else:
                st.success(f"Surgery {created['surgery_id']} created.")
                st.json(created)
                st.session_state["create_preview"] = None

# ---------------- Reschedule ----------------
with tab_reschedule:
    r_id = st.text_input("Surgery ID to reschedule", key="resched_id")
    c1, c2, c3 = st.columns(3)
    r_date = c1.date_input("New date", value=dt.date.today() + dt.timedelta(days=1), key="resched_date")
    r_time = c2.time_input("New time", value=dt.time(9, 0), key="resched_time")
    r_room = c3.text_input("New room (optional)", key="resched_room")

    if st.button("Review reschedule"):
        st.session_state["reschedule_preview"] = {
            "surgery_id": r_id,
            "new_date": r_date.isoformat(),
            "new_time": r_time.isoformat(),
            "new_room": r_room or None,
        }

    preview = st.session_state.get("reschedule_preview")
    if preview:
        st.info("Review the proposed reschedule before confirming:")
        st.json(preview)
        if st.button("✅ Confirm & Reschedule"):
            body = {k: v for k, v in preview.items() if k != "surgery_id"}
            updated, err = api_call(patch, f"/api/v1/surgeries/{preview['surgery_id']}/reschedule", json=body)
            if err:
                st.error(err)
            else:
                st.success(f"Surgery {updated['surgery_id']} rescheduled.")
                st.json(updated)
                st.session_state["reschedule_preview"] = None

# ---------------- Update Status ----------------
with tab_status:
    s_id = st.text_input("Surgery ID", key="status_id")
    new_status = st.selectbox(
        "New status", ["confirmed", "in_progress", "completed", "delayed", "cancelled"], key="status_value",
    )
    reason = st.text_input("Reason (required for delayed/cancelled)", key="status_reason")
    delay_minutes = None
    if new_status == "delayed":
        delay_minutes = st.number_input("Delay (minutes)", min_value=1, max_value=600, value=15)

    if st.button("Review status change"):
        st.session_state["status_preview"] = {
            "surgery_id": s_id,
            "status": new_status,
            "reason": reason or None,
            "delay_minutes": int(delay_minutes) if delay_minutes else None,
        }

    preview = st.session_state.get("status_preview")
    if preview:
        st.info("Review the proposed status change before confirming:")
        st.json(preview)
        if st.button("✅ Confirm & Update Status"):
            body = {k: v for k, v in preview.items() if k != "surgery_id"}
            updated, err = api_call(patch, f"/api/v1/surgeries/{preview['surgery_id']}/status", json=body)
            if err:
                st.error(err)
            else:
                st.success(f"Surgery {updated['surgery_id']} status updated to {updated['status']}.")
                st.json(updated)
                st.session_state["status_preview"] = None

# ---------------- Cancel ----------------
with tab_cancel:
    cancel_id = st.text_input("Surgery ID to cancel", key="cancel_id")
    cancel_reason = st.text_input("Cancellation reason", key="cancel_reason")

    if st.button("Review cancellation"):
        surgery, err = api_call(get, f"/api/v1/surgeries/{cancel_id}") if cancel_id else (None, "Enter a surgery ID.")
        if err:
            st.error(err)
        else:
            st.session_state["cancel_preview"] = {"surgery_id": cancel_id, "reason": cancel_reason, "surgery": surgery}

    preview = st.session_state.get("cancel_preview")
    if preview:
        st.warning(
            f"About to cancel surgery {preview['surgery_id']} "
            f"({preview['surgery']['surgery_type']}, status={preview['surgery']['status']})."
        )
        st.json(preview["surgery"])
        if st.button("🛑 Confirm & Cancel"):
            updated, err = api_call(
                patch, f"/api/v1/surgeries/{preview['surgery_id']}/status",
                json={"status": "cancelled", "reason": preview["reason"] or "Cancelled via Surgery Management UI"},
            )
            if err:
                st.error(err)
            else:
                st.success(f"Surgery {updated['surgery_id']} cancelled.")
                st.json(updated)
                st.session_state["cancel_preview"] = None
