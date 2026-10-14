from __future__ import annotations

from fastapi import APIRouter, Depends

from app.agent.service import run_chat_turn
from app.api.deps import get_container_dep
from app.dependencies import Container
from app.models.api_models import ChatRequest, ChatResponse

router = APIRouter(tags=["agent"])


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, container: Container = Depends(get_container_dep)) -> ChatResponse:
    history = [turn.model_dump() for turn in payload.history]
    result = run_chat_turn(container, payload.message, history, payload.actor)
    return ChatResponse(
        response=result.final_response,
        citations=result.citations,
        pending_action=result.pending_action,
        confirmation_status=result.confirmation_status,
        history=result.history,
    )
