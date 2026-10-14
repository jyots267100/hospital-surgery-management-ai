"""Central dependency-injection wiring: settings -> repositories -> services ->
RAG components -> tools/agent. Built once per process as cached singletons and
exposed to FastAPI routes via Depends(...).
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from app.config import Settings, get_settings
from app.rag.embeddings import get_embedding_function
from app.rag.retriever import PolicyRetriever
from app.rag.vector_store import PolicyVectorStore
from app.repositories.event_repository import EventRepository
from app.repositories.operating_room_repository import OperatingRoomRepository
from app.repositories.patient_repository import PatientRepository
from app.repositories.surgeon_repository import SurgeonRepository
from app.repositories.surgery_repository import SurgeryRepository
from app.services.dashboard_service import DashboardService
from app.services.event_service import EventService
from app.services.operating_room_service import OperatingRoomService
from app.services.policy_service import PolicyService
from app.services.surgeon_service import SurgeonService
from app.services.surgery_service import SurgeryService


class Container:
    """Holds all wired singletons for the application's lifetime."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        data_dir = settings.data_path

        self.surgery_repo = SurgeryRepository(data_dir)
        self.surgeon_repo = SurgeonRepository(data_dir)
        self.room_repo = OperatingRoomRepository(data_dir)
        self.patient_repo = PatientRepository(data_dir)
        self.event_repo = EventRepository(data_dir)

        self.event_service = EventService(self.event_repo)
        self.surgery_service = SurgeryService(
            self.surgery_repo, self.surgeon_repo, self.room_repo, self.patient_repo, self.event_service,
        )
        self.operating_room_service = OperatingRoomService(self.room_repo, self.surgery_service)
        self.surgeon_service = SurgeonService(self.surgeon_repo, self.surgery_service)
        self.dashboard_service = DashboardService(self.surgery_service, self.room_repo)

        embedding_fn = get_embedding_function(settings.embedding_model)
        self.vector_store = PolicyVectorStore(
            persist_directory=Path(settings.chroma_persist_directory),
            collection_name=settings.chroma_collection_name,
            embedding_fn=embedding_fn,
        )
        self.retriever = PolicyRetriever(self.vector_store, top_k=settings.retrieval_top_k)
        self.policy_service = PolicyService(
            self.retriever, self.vector_store, settings.policy_docs_path,
            settings.chunk_size, settings.chunk_overlap,
        )


@lru_cache
def get_container() -> Container:
    return Container(get_settings())
