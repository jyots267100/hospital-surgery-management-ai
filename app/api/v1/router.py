from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import chat, dashboard, operating_rooms, policies, surgeons, surgeries

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(surgeries.router)
api_v1_router.include_router(operating_rooms.router)
api_v1_router.include_router(surgeons.router)
api_v1_router.include_router(dashboard.router)
api_v1_router.include_router(policies.router)
api_v1_router.include_router(chat.router)
