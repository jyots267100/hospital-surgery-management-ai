"""Top-level entry point for running one agent turn: wires a fresh ToolContext
(so the authenticated actor is correctly scoped) and the compiled LangGraph,
then converts chat history into LangChain messages and back.
"""
from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from app.agent.graph import build_agent_graph
from app.dependencies import Container
from app.tools.context import ToolContext

_chat_model_cache: dict[int, BaseChatModel] = {}


def _get_chat_model(container: Container) -> BaseChatModel:
    from app.agent.llm import get_chat_model

    key = id(container.settings)
    if key not in _chat_model_cache:
        _chat_model_cache[key] = get_chat_model(container.settings)
    return _chat_model_cache[key]


class ChatTurnResult:
    def __init__(
        self,
        final_response: str,
        citations: list[str],
        pending_action: dict | None,
        confirmation_status: str,
        error: str | None,
        history: list[dict],
    ) -> None:
        self.final_response = final_response
        self.citations = citations
        self.pending_action = pending_action
        self.confirmation_status = confirmation_status
        self.error = error
        self.history = history


def _history_to_messages(history: list[dict]) -> list[BaseMessage]:
    messages: list[BaseMessage] = []
    for turn in history:
        if turn["role"] == "user":
            messages.append(HumanMessage(content=turn["content"]))
        elif turn["role"] == "assistant":
            messages.append(AIMessage(content=turn["content"]))
    return messages


def run_chat_turn(container: Container, message: str, history: list[dict] | None, actor: str) -> ChatTurnResult:
    chat_model = _get_chat_model(container)
    tool_ctx = ToolContext(
        surgery_service=container.surgery_service,
        operating_room_service=container.operating_room_service,
        surgeon_service=container.surgeon_service,
        dashboard_service=container.dashboard_service,
        event_service=container.event_service,
        policy_service=container.policy_service,
        actor=actor,
    )
    graph = build_agent_graph(chat_model, tool_ctx)

    messages = _history_to_messages(history or [])
    messages.append(HumanMessage(content=message))

    initial_state = {
        "messages": messages,
        "user_query": message,
        "iteration_count": 0,
        "confirmation_required": False,
        "confirmation_status": "none",
        "pending_action": None,
        "retrieved_context": None,
        "error": None,
    }

    final_state = graph.invoke(initial_state)

    final_response = final_state.get("final_response")
    if not final_response:
        for msg in reversed(final_state["messages"]):
            if isinstance(msg, AIMessage) and msg.content:
                final_response = msg.content
                break
        else:
            final_response = (
                "I wasn't able to complete this request within the allowed number of "
                "steps. Please try rephrasing or breaking it into smaller requests."
            )

    retrieved_context = final_state.get("retrieved_context") or {}
    citations = retrieved_context.get("citations", []) if isinstance(retrieved_context, dict) else []

    new_history = list(history or [])
    new_history.append({"role": "user", "content": message})
    new_history.append({"role": "assistant", "content": final_response})

    return ChatTurnResult(
        final_response=final_response,
        citations=citations,
        pending_action=final_state.get("pending_action"),
        confirmation_status=final_state.get("confirmation_status", "none"),
        error=final_state.get("error"),
        history=new_history,
    )
