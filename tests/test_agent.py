from __future__ import annotations

from langchain_core.messages import HumanMessage

from app.agent.graph import build_agent_graph
from tests.fakes import FakeChatModel, final_message, tool_call_message


def _initial_state(user_text: str) -> dict:
    return {
        "messages": [HumanMessage(content=user_text)],
        "user_query": user_text,
        "iteration_count": 0,
        "confirmation_required": False,
        "confirmation_status": "none",
        "pending_action": None,
        "retrieved_context": None,
        "error": None,
    }


def test_agent_routes_to_correct_tool_with_correct_arguments(tool_ctx):
    fake = FakeChatModel([
        tool_call_message("get_surgery_status", {"surgery_id": "S1001"}),
        final_message("Surgery S1001 is scheduled."),
    ])
    graph = build_agent_graph(fake, tool_ctx)
    final_state = graph.invoke(_initial_state("What's the status of S1001?"))

    assert final_state["final_response"] == "Surgery S1001 is scheduled."
    assert final_state["tool_result"]["surgery"]["surgery_id"] == "S1001"


def test_agent_multi_step_tool_then_final_answer(tool_ctx):
    fake = FakeChatModel([
        tool_call_message("get_todays_surgeries", {}),
        final_message("There are 3 surgeries scheduled today."),
    ])
    graph = build_agent_graph(fake, tool_ctx)
    final_state = graph.invoke(_initial_state("What surgeries are today?"))

    assert fake.invocation_count == 2
    assert "3 surgeries" in final_state["final_response"]


def test_agent_direct_response_without_tool_call(tool_ctx):
    fake = FakeChatModel([final_message("I can help with surgery scheduling questions.")])
    graph = build_agent_graph(fake, tool_ctx)
    final_state = graph.invoke(_initial_state("Hello, what can you do?"))

    assert fake.invocation_count == 1
    assert "help with surgery scheduling" in final_state["final_response"]


def test_confirmation_workflow_first_call_does_not_execute(tool_ctx):
    fake = FakeChatModel([
        tool_call_message("cancel_surgery", {"surgery_id": "S1001", "reason": "patient request", "confirmed": False}),
        final_message("S1001 is eligible for cancellation. Shall I proceed?"),
    ])
    graph = build_agent_graph(fake, tool_ctx)
    final_state = graph.invoke(_initial_state("Cancel surgery S1001."))

    assert final_state["confirmation_required"] is True
    assert final_state["confirmation_status"] == "pending"
    assert final_state["pending_action"]["status"] == "confirmation_required"

    status = tool_ctx.surgery_service.get_surgery("S1001").status.value
    assert status == "scheduled"  # not actually cancelled yet


def test_confirmation_workflow_second_call_executes(tool_ctx):
    fake = FakeChatModel([
        tool_call_message("cancel_surgery", {"surgery_id": "S1001", "reason": "patient request", "confirmed": True}),
        final_message("S1001 has been cancelled."),
    ])
    graph = build_agent_graph(fake, tool_ctx)
    graph.invoke(_initial_state("Yes, cancel it."))

    status = tool_ctx.surgery_service.get_surgery("S1001").status.value
    assert status == "cancelled"


def test_agent_handles_unknown_surgery_gracefully(tool_ctx):
    fake = FakeChatModel([
        tool_call_message("get_surgery_status", {"surgery_id": "S9999"}),
        final_message("I couldn't find a surgery with that ID."),
    ])
    graph = build_agent_graph(fake, tool_ctx)
    final_state = graph.invoke(_initial_state("What's the status of S9999?"))

    assert final_state["error"] is not None
    assert "couldn't find" in final_state["final_response"]


def test_agent_search_policy_populates_retrieved_context(tool_ctx):
    fake = FakeChatModel([
        tool_call_message("search_hospital_policy", {"query": "Can a completed surgery be cancelled?"}),
        final_message("No, completed surgeries cannot be cancelled [Hospital Cancellation Policy]."),
    ])
    graph = build_agent_graph(fake, tool_ctx)
    final_state = graph.invoke(_initial_state("Can a completed surgery be cancelled?"))

    assert final_state["retrieved_context"]["sufficient_evidence"] is True
    assert len(final_state["retrieved_context"]["citations"]) > 0


def test_agent_iteration_limit_prevents_infinite_loop(tool_ctx):
    # Script far more tool calls than MAX_ITERATIONS allows, with no final answer.
    responses = [tool_call_message("get_todays_surgeries", {}) for _ in range(10)]
    fake = FakeChatModel(responses)
    graph = build_agent_graph(fake, tool_ctx)
    final_state = graph.invoke(_initial_state("loop forever"))

    assert final_state["iteration_count"] <= 6
