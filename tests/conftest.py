from __future__ import annotations

import json
import shutil
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

import pytest

from app.repositories.event_repository import EventRepository
from app.repositories.operating_room_repository import OperatingRoomRepository
from app.repositories.patient_repository import PatientRepository
from app.repositories.surgeon_repository import SurgeonRepository
from app.repositories.surgery_repository import SurgeryRepository
from app.services.dashboard_service import DashboardService
from app.services.event_service import EventService
from app.services.operating_room_service import OperatingRoomService
from app.services.surgeon_service import SurgeonService
from app.services.surgery_service import SurgeryService
from app.tools.context import ToolContext

TODAY = date.today()
TOMORROW = TODAY + timedelta(days=1)


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    d = tmp_path / "data"
    d.mkdir()

    patients = [
        {"patient_id": "P101", "name": "Test Patient One", "age": 40, "gender": "F"},
        {"patient_id": "P102", "name": "Test Patient Two", "age": 55, "gender": "M"},
    ]
    surgeons = [
        {"surgeon_id": "SG001", "name": "Dr. Test Sharma", "specialty": "Orthopedics"},
        {"surgeon_id": "SG002", "name": "Dr. Test Mehta", "specialty": "Cardiothoracic Surgery"},
    ]
    rooms = [
        {"room_id": "OR-1", "name": "Operating Room 1", "floor": "2nd Floor"},
        {"room_id": "OR-2", "name": "Operating Room 2", "floor": "2nd Floor"},
    ]
    now = datetime.now(timezone.utc).isoformat()
    surgeries = [
        {
            "surgery_id": "S1001", "patient_id": "P101", "patient_name": "Test Patient One", "age": 40,
            "surgery_type": "Knee Replacement", "surgeon_id": "SG001", "surgeon_name": "Dr. Test Sharma",
            "operating_room": "OR-1", "scheduled_date": TODAY.isoformat(), "scheduled_time": "09:00:00",
            "duration_minutes": 60, "status": "scheduled", "priority": "routine", "delay_minutes": 0,
            "delay_reason": None, "cancellation_reason": None, "created_at": now, "updated_at": now,
        },
        {
            "surgery_id": "S1002", "patient_id": "P102", "patient_name": "Test Patient Two", "age": 55,
            "surgery_type": "Appendectomy", "surgeon_id": "SG002", "surgeon_name": "Dr. Test Mehta",
            "operating_room": "OR-2", "scheduled_date": TODAY.isoformat(), "scheduled_time": "11:00:00",
            "duration_minutes": 45, "status": "delayed", "priority": "urgent", "delay_minutes": 30,
            "delay_reason": "Preceding case overran", "cancellation_reason": None,
            "created_at": now, "updated_at": now,
        },
        {
            "surgery_id": "S1003", "patient_id": "P101", "patient_name": "Test Patient One", "age": 40,
            "surgery_type": "Cataract Surgery", "surgeon_id": "SG001", "surgeon_name": "Dr. Test Sharma",
            "operating_room": "OR-1", "scheduled_date": TOMORROW.isoformat(), "scheduled_time": "10:00:00",
            "duration_minutes": 30, "status": "scheduled", "priority": "routine", "delay_minutes": 0,
            "delay_reason": None, "cancellation_reason": None, "created_at": now, "updated_at": now,
        },
        {
            "surgery_id": "S1004", "patient_id": "P102", "patient_name": "Test Patient Two", "age": 55,
            "surgery_type": "Hip Replacement", "surgeon_id": "SG002", "surgeon_name": "Dr. Test Mehta",
            "operating_room": "OR-2", "scheduled_date": TODAY.isoformat(), "scheduled_time": "14:00:00",
            "duration_minutes": 90, "status": "completed", "priority": "routine", "delay_minutes": 0,
            "delay_reason": None, "cancellation_reason": None, "created_at": now, "updated_at": now,
        },
    ]

    (d / "patients.json").write_text(json.dumps(patients), encoding="utf-8")
    (d / "surgeons.json").write_text(json.dumps(surgeons), encoding="utf-8")
    (d / "operating_rooms.json").write_text(json.dumps(rooms), encoding="utf-8")
    (d / "surgeries.json").write_text(json.dumps(surgeries), encoding="utf-8")
    (d / "surgery_events.json").write_text(json.dumps([]), encoding="utf-8")
    return d


@pytest.fixture
def repos(data_dir: Path):
    return {
        "surgery": SurgeryRepository(data_dir),
        "surgeon": SurgeonRepository(data_dir),
        "room": OperatingRoomRepository(data_dir),
        "patient": PatientRepository(data_dir),
        "event": EventRepository(data_dir),
    }


@pytest.fixture
def event_service(repos) -> EventService:
    return EventService(repos["event"])


@pytest.fixture
def surgery_service(repos, event_service) -> SurgeryService:
    return SurgeryService(repos["surgery"], repos["surgeon"], repos["room"], repos["patient"], event_service)


@pytest.fixture
def operating_room_service(repos, surgery_service) -> OperatingRoomService:
    return OperatingRoomService(repos["room"], surgery_service)


@pytest.fixture
def surgeon_service(repos, surgery_service) -> SurgeonService:
    return SurgeonService(repos["surgeon"], surgery_service)


@pytest.fixture
def dashboard_service(surgery_service, repos) -> DashboardService:
    return DashboardService(surgery_service, repos["room"])


@pytest.fixture(scope="session")
def policy_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "policies"


@pytest.fixture(scope="session")
def policy_service(tmp_path_factory, policy_dir: Path):
    """Session-scoped: embedding model load + ingestion is expensive, and the
    policy corpus is read-only, so it's safe to share across tests."""
    from app.rag.embeddings import get_embedding_function
    from app.rag.retriever import PolicyRetriever
    from app.rag.vector_store import PolicyVectorStore
    from app.services.policy_service import PolicyService

    chroma_dir = tmp_path_factory.mktemp("chroma_test")
    embedding_fn = get_embedding_function("sentence-transformers/all-MiniLM-L6-v2")
    vector_store = PolicyVectorStore(chroma_dir, "test_policies", embedding_fn)
    retriever = PolicyRetriever(vector_store, top_k=5)
    service = PolicyService(retriever, vector_store, policy_dir, chunk_size=1000, chunk_overlap=150)
    service.reingest()
    return service


@pytest.fixture
def tool_ctx(surgery_service, operating_room_service, surgeon_service, dashboard_service, event_service, policy_service) -> ToolContext:
    return ToolContext(
        surgery_service=surgery_service,
        operating_room_service=operating_room_service,
        surgeon_service=surgeon_service,
        dashboard_service=dashboard_service,
        event_service=event_service,
        policy_service=policy_service,
        actor="test_actor",
    )
