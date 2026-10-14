"""Typed LangGraph state for the Hospital Surgery Management Agent."""
from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    # Full conversation history (user, assistant, tool messages). `add_messages`
    # appends new messages rather than overwriting, so multi-turn confirmation
    # flows keep their context across graph invocations.
    messages: Annotated[list[BaseMessage], add_messages]

    # The raw text of the user's most recent message, for logging/introspection.
    user_query: str

    # Name of the tool the LLM most recently decided to call (if any).
    selected_tool: str | None

    # Arguments the LLM supplied for that tool call.
    tool_arguments: dict[str, Any] | None

    # Raw result of the most recently executed tool.
    tool_result: dict[str, Any] | None

    # Policy context retrieved via search_hospital_policy, if any (for citations in the API response).
    retrieved_context: dict[str, Any] | None

    # The proposed action from a tool that returned status="confirmation_required".
    pending_action: dict[str, Any] | None

    # Whether the most recent tool call is awaiting explicit user confirmation.
    confirmation_required: bool

    # "pending" | "confirmed" | "none" -- surfaced to the API/UI for a clear confirmation step.
    confirmation_status: str

    # Final natural-language response to return to the user.
    final_response: str | None

    # Populated when a tool or LLM call failed in a way the user should be told about.
    error: str | None

    # Guards against unbounded agent <-> tool loops.
    iteration_count: int
