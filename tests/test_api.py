from __future__ import annotations

import types

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_container_dep
from app.main import app
from tests.conftest import TODAY, TOMORROW


@pytest.fixture
def client(surgery_service, operating_room_service, surgeon_service, dashboard_service, event_service, policy_service):
    test_container = types.SimpleNamespace(
        surgery_service=surgery_service,
        operating_room_service=operating_room_service,
        surgeon_service=surgeon_service,
        dashboard_service=dashboard_service,
        event_service=event_service,
        policy_service=policy_service,
    )
    app.dependency_overrides[get_container_dep] = lambda: test_container
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_health_endpoint(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_list_surgeries(client):
    resp = client.get("/api/v1/surgeries")
    assert resp.status_code == 200
    assert len(resp.json()) == 4


def test_list_todays_surgeries(client):
    resp = client.get("/api/v1/surgeries", params={"today_only": True})
    assert resp.status_code == 200
    assert len(resp.json()) == 3


def test_get_surgery_found(client):
    resp = client.get("/api/v1/surgeries/S1001")
    assert resp.status_code == 200
    assert resp.json()["surgery_id"] == "S1001"


def test_get_surgery_not_found_returns_404(client):
    resp = client.get("/api/v1/surgeries/S9999")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"] == "NotFoundError"


def test_create_surgery_success(client):
    resp = client.post("/api/v1/surgeries", json={
        "patient_id": "P101", "surgery_type": "Hernia Repair", "surgeon_id": "SG001",
        "operating_room": "OR-2", "scheduled_date": TOMORROW.isoformat(), "scheduled_time": "15:00:00",
    })
    assert resp.status_code == 201
    assert resp.json()["status"] == "scheduled"


def test_create_surgery_conflict_returns_409(client):
    resp = client.post("/api/v1/surgeries", json={
        "patient_id": "P101", "surgery_type": "Hernia Repair", "surgeon_id": "SG002",
        "operating_room": "OR-1", "scheduled_date": TODAY.isoformat(), "scheduled_time": "09:15:00",
    })
    assert resp.status_code == 409


def test_create_surgery_validation_error_returns_422(client):
    resp = client.post("/api/v1/surgeries", json={
        "patient_id": "P101", "surgery_type": "Hernia Repair", "surgeon_id": "SG001",
        "operating_room": "OR-2", "scheduled_date": "not-a-date", "scheduled_time": "15:00:00",
    })
    assert resp.status_code == 422


def test_update_status_endpoint(client):
    resp = client.patch("/api/v1/surgeries/S1001/status", json={"status": "confirmed"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "confirmed"


def test_update_status_invalid_transition_returns_409(client):
    resp = client.patch("/api/v1/surgeries/S1004/status", json={"status": "scheduled"})
    assert resp.status_code == 409


def test_cancel_via_status_endpoint_is_the_supported_path(client):
    resp = client.patch("/api/v1/surgeries/S1001/status", json={"status": "cancelled", "reason": "patient request"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


def test_reschedule_endpoint(client):
    resp = client.patch("/api/v1/surgeries/S1003/reschedule", json={
        "new_date": TOMORROW.isoformat(), "new_time": "16:00:00",
    })
    assert resp.status_code == 200
    assert resp.json()["scheduled_time"] == "16:00:00"


def test_add_event_endpoint(client):
    resp = client.post("/api/v1/surgeries/S1001/events", json={
        "event_type": "note_added", "description": "Pre-op checklist complete.",
    })
    assert resp.status_code == 201
    assert resp.json()["event_type"] == "note_added"


def test_get_events_endpoint(client):
    client.post("/api/v1/surgeries/S1001/events", json={"event_type": "note_added", "description": "x"})
    resp = client.get("/api/v1/surgeries/S1001/events")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


def test_delete_surgery_endpoint_admin_removal(client):
    resp = client.delete("/api/v1/surgeries/S1001")
    assert resp.status_code == 204
    resp2 = client.get("/api/v1/surgeries/S1001")
    assert resp2.status_code == 404


def test_list_operating_rooms(client):
    resp = client.get("/api/v1/operating-rooms")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_room_availability_endpoint(client):
    resp = client.get("/api/v1/operating-rooms/OR-1/availability", params={
        "on_date": TODAY.isoformat(), "window_start": "09:00:00", "window_end": "10:00:00",
    })
    assert resp.status_code == 200
    assert resp.json()["is_available"] is False


def test_list_surgeons(client):
    resp = client.get("/api/v1/surgeons")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_surgeon_schedule_endpoint(client):
    resp = client.get("/api/v1/surgeons/SG001/schedule")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_surgeon_not_found_returns_404(client):
    resp = client.get("/api/v1/surgeons/SGXXX")
    assert resp.status_code == 404


def test_dashboard_summary_endpoint(client):
    resp = client.get("/api/v1/dashboard/summary")
    assert resp.status_code == 200
    assert resp.json()["total_surgeries"] == 4


def test_policy_search_endpoint(client):
    resp = client.post("/api/v1/policies/search", json={"query": "Can a completed surgery be cancelled?"})
    assert resp.status_code == 200
    assert resp.json()["sufficient_evidence"] is True
