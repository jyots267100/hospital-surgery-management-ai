"""Top-level entry point for running one agent turn: wires a fresh ToolContext
(so the authenticated actor is correctly scoped) and the compiled LangGraph,
then converts chat history into LangChain messages and back.

The chat API is stateless (the client round-trips `history`), but the history
must preserve the FULL message structure -- including tool calls and tool
results, not just the final text -- across HTTP turns. Without that, a model
asked to confirm a pending write (e.g. "yes, cancel it") sees only its own
prior plain-text message and has no structured record that it already called
cancel_surgery(confirmed=false); it then has no reliable way to know it should
call the same tool again with confirmed=true. So `history` here round-trips
HumanMessage / AIMessage(+tool_calls) / ToolMessage faithfully, not a
simplified {role, content} pair.
"""
from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage

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
        role = turn.get("role")
        if role == "user":
            messages.append(HumanMessage(content=turn.get("content") or ""))
        elif role == "assistant":
            tool_calls = turn.get("tool_calls") or []
            messages.append(AIMessage(content=turn.get("content") or "", tool_calls=tool_calls))
        elif role == "tool":
            messages.append(ToolMessage(
                content=turn.get("content") or "",
                tool_call_id=turn.get("tool_call_id") or "",
                name=turn.get("name"),
            ))
    return messages


def _messages_to_history(messages: list[BaseMessage]) -> list[dict]:
    history: list[dict] = []
    for msg in messages:
        if isinstance(msg, SystemMessage):
            continue  # re-added automatically by agent_node; never round-tripped
        if isinstance(msg, HumanMessage):
            history.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            entry = {"role": "assistant", "content": msg.content}
            if msg.tool_calls:
                entry["tool_calls"] = [
                    {"id": c["id"], "name": c["name"], "args": c["args"]} for c in msg.tool_calls
                ]
            history.append(entry)
        elif isinstance(msg, ToolMessage):
            history.append({
                "role": "tool", "content": msg.content, "tool_call_id": msg.tool_call_id, "name": msg.name,
            })
    return history


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

    new_history = _messages_to_history(final_state["messages"])

    return ChatTurnResult(
        final_response=final_response,
        citations=citations,
        pending_action=final_state.get("pending_action"),
        confirmation_status=final_state.get("confirmation_status", "none"),
        error=final_state.get("error"),
        history=new_history,
    )
