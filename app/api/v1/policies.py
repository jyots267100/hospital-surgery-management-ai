from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_container_dep
from app.dependencies import Container
from app.models.api_models import PolicyIngestResponse, PolicySearchRequest, PolicySearchResponse

router = APIRouter(prefix="/policies", tags=["policies"])


@router.post("/search", response_model=PolicySearchResponse)
def search_policies(payload: PolicySearchRequest, container: Container = Depends(get_container_dep)) -> PolicySearchResponse:
    result = container.policy_service.search(payload.query)
    return PolicySearchResponse(
        sufficient_evidence=result["sufficient_evidence"],
        citations=result["citations"],
        context=result["context"] or None,
    )


@router.post("/ingest", response_model=PolicyIngestResponse)
def ingest_policies(container: Container = Depends(get_container_dep)) -> PolicyIngestResponse:
    result = container.policy_service.reingest()
    return PolicyIngestResponse(**result)
