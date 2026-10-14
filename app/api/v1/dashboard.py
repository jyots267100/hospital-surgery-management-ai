from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_container_dep
from app.dependencies import Container
from app.models.api_models import DashboardSummaryResponse

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummaryResponse)
def get_dashboard_summary(container: Container = Depends(get_container_dep)) -> DashboardSummaryResponse:
    return DashboardSummaryResponse(**container.dashboard_service.get_summary())
