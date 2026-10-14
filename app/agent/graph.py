"""LangGraph StateGraph wiring for the Hospital Surgery Management Agent.

    START -> agent (LLM, tools bound)
              |--- tool_calls present & under iteration limit ---> tools -> agent (loop)
              |--- no tool_calls, or iteration limit reached     ---> END

The LLM never mutates data directly: every state-changing action goes through a
tool, which goes through the service layer (see app/tools/surgery_tools.py). The
agent only decides WHICH tool to call and WHAT arguments to pass.
"""
from __future__ import annotations

import json
import logging

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langgraph.graph import END, StateGraph
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.agent.prompts import render_system_prompt
from app.agent.state import AgentState
from app.core.exceptions import DomainError
from app.core.logging_config import Timer, log_event
from app.tools.context import ToolContext
from app.tools.registry import build_tools

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 6


class TransientLLMError(Exception):
    """Raised for retryable LLM call failures (timeouts, rate limits)."""


@retry(
    retry=retry_if_exception_type(TransientLLMError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    reraise=True,
)
def _invoke_llm_with_retry(model, messages):
    try:
        return model.invoke(messages)
    except Exception as exc:  # noqa: BLE001
        message = str(exc).lower()
        if any(token in message for token in ("timeout", "rate limit", "429", "503", "deadline")):
            raise TransientLLMError(str(exc)) from exc
        raise


def build_agent_graph(chat_model: BaseChatModel, tool_ctx: ToolContext):
    tools = build_tools(tool_ctx)
    tools_by_name = {t.name: t for t in tools}
    model_with_tools = chat_model.bind_tools(tools)

    def agent_node(state: AgentState) -> dict:
        messages = state["messages"]
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=render_system_prompt()), *messages]

        try:
            with Timer() as timer:
                response: AIMessage = _invoke_llm_with_retry(model_with_tools, messages)
            log_event(logger, logging.INFO, "llm_call", latency_ms=timer.elapsed_ms, success=True)
        except Exception as exc:  # noqa: BLE001
            log_event(logger, logging.ERROR, "llm_call_failed", error=str(exc))
            return {
                "messages": [AIMessage(content=(
                    "I'm having trouble reaching the language model right now. "
                    "Please try again in a moment."
                ))],
                "error": f"LLM call failed: {exc}",
                "final_response": "I'm having trouble reaching the language model right now. Please try again in a moment.",
                "iteration_count": state.get("iteration_count", 0) + 1,
            }

        update: dict = {"messages": [response], "iteration_count": state.get("iteration_count", 0) + 1}
        if response.tool_calls:
            call = response.tool_calls[0]
            update["selected_tool"] = call["name"]
            update["tool_arguments"] = call["args"]
        else:
            update["final_response"] = response.content
            update["selected_tool"] = None
        return update

    def tools_node(state: AgentState) -> dict:
        last_message = state["messages"][-1]
        tool_messages = []
        latest_tool_result: dict | None = None
        pending_action = None
        confirmation_required = False
        retrieved_context = state.get("retrieved_context")
        error: str | None = None

        for call in last_message.tool_calls:
            tool = tools_by_name.get(call["name"])
            if tool is None:
                content = {"error": f"Unknown tool '{call['name']}'"}
            else:
                try:
                    with Timer() as timer:
                        result = tool.invoke(call["args"])
                    log_event(
                        logger, logging.INFO, "tool_call",
                        tool=call["name"], latency_ms=timer.elapsed_ms, success=True,
                    )
                    content = result
                except DomainError as exc:
                    log_event(logger, logging.WARNING, "tool_call_domain_error", tool=call["name"], error=exc.message)
                    content = {"error": exc.message, **exc.context}
                    error = exc.message
                except Exception as exc:  # noqa: BLE001
                    log_event(logger, logging.ERROR, "tool_call_unexpected_error", tool=call["name"], error=str(exc))
                    content = {"error": f"Unexpected error while running '{call['name']}': {exc}"}
                    error = content["error"]

            if isinstance(content, dict):
                latest_tool_result = content
                if content.get("status") == "confirmation_required":
                    pending_action = content
                    confirmation_required = True
                if call["name"] == "search_hospital_policy":
                    retrieved_context = content

            tool_messages.append(ToolMessage(
                content=json.dumps(content, default=str),
                tool_call_id=call["id"],
                name=call["name"],
            ))

        return {
            "messages": tool_messages,
            "tool_result": latest_tool_result,
            "pending_action": pending_action,
            "confirmation_required": confirmation_required,
            "confirmation_status": "pending" if confirmation_required else "none",
            "retrieved_context": retrieved_context,
            "error": error,
        }

    def route_after_agent(state: AgentState) -> str:
        last_message = state["messages"][-1]
        if state.get("iteration_count", 0) >= MAX_ITERATIONS:
            return END
        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            return "tools"
        return END

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tools_node)
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", route_after_agent, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")
    return graph.compile()
