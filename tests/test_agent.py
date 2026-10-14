from __future__ import annotations

import types

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

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


def test_message_history_roundtrip_preserves_tool_call_structure():
    """Regression test: the stateless /api/v1/chat endpoint round-trips chat
    history as plain dicts between HTTP calls. Earlier, that history only kept
    {role, content}, silently dropping the AIMessage.tool_calls and ToolMessage
    data -- so on the next turn the LLM had no structured record that it had
    already called e.g. cancel_surgery(confirmed=false), and (observed against
    the real Gemini API) would sometimes fail to re-invoke the tool with
    confirmed=true even when the user clearly confirmed. The fix serializes/
    deserializes the full message structure; this test locks that in."""
    from app.agent.service import _history_to_messages, _messages_to_history

    original = [
        SystemMessage(content="system prompt, should never be round-tripped"),
        HumanMessage(content="Cancel surgery S1001."),
        AIMessage(content="", tool_calls=[
            {"name": "cancel_surgery", "args": {"surgery_id": "S1001", "confirmed": False}, "id": "call_1"},
        ]),
        ToolMessage(content='{"status": "confirmation_required"}', tool_call_id="call_1", name="cancel_surgery"),
        AIMessage(content="Do you want me to proceed?"),
    ]

    history = _messages_to_history(original)
    assert all(h["role"] != "system" for h in history)  # system message dropped

    reconstructed = _history_to_messages(history)

    assert isinstance(reconstructed[0], HumanMessage)
    assert reconstructed[0].content == "Cancel surgery S1001."

    ai_with_call = reconstructed[1]
    assert isinstance(ai_with_call, AIMessage)
    assert ai_with_call.tool_calls[0]["name"] == "cancel_surgery"
    assert ai_with_call.tool_calls[0]["args"] == {"surgery_id": "S1001", "confirmed": False}
    assert ai_with_call.tool_calls[0]["id"] == "call_1"

    tool_msg = reconstructed[2]
    assert isinstance(tool_msg, ToolMessage)
    assert tool_msg.tool_call_id == "call_1"
    assert tool_msg.name == "cancel_surgery"
    assert "confirmation_required" in tool_msg.content

    assert isinstance(reconstructed[3], AIMessage)
    assert reconstructed[3].content == "Do you want me to proceed?"


def test_chat_service_confirmation_survives_a_stateless_http_roundtrip(tool_ctx, monkeypatch):
    """End-to-end through app.agent.service.run_chat_turn (what the /chat API
    actually calls), across two separate calls simulating two HTTP requests,
    passing only the serialized `history` back in -- exactly like a real
    client would. The second call's tool call only succeeds in mutating state
    because the first call's tool_calls/ToolMessage survived the round-trip."""
    from app.agent.service import run_chat_turn

    fake_turn_1 = FakeChatModel([
        tool_call_message("cancel_surgery", {"surgery_id": "S1001", "reason": "patient request", "confirmed": False}),
        final_message("S1001 is eligible for cancellation. Proceed?"),
    ])
    container = types.SimpleNamespace(
        settings=object(),
        surgery_service=tool_ctx.surgery_service,
        operating_room_service=tool_ctx.operating_room_service,
        surgeon_service=tool_ctx.surgeon_service,
        dashboard_service=tool_ctx.dashboard_service,
        event_service=tool_ctx.event_service,
        policy_service=tool_ctx.policy_service,
    )

    monkeypatch.setattr("app.agent.service._get_chat_model", lambda c: fake_turn_1)
    result_1 = run_chat_turn(container, "Cancel surgery S1001.", history=None, actor="test_actor")

    assert result_1.confirmation_status == "pending"
    assert tool_ctx.surgery_service.get_surgery("S1001").status.value == "scheduled"

    fake_turn_2 = FakeChatModel([
        tool_call_message("cancel_surgery", {"surgery_id": "S1001", "reason": "patient request", "confirmed": True}),
        final_message("S1001 has been cancelled."),
    ])
    monkeypatch.setattr("app.agent.service._get_chat_model", lambda c: fake_turn_2)
    # Only `result_1.history` (plain dicts, as sent over HTTP) is passed forward --
    # no in-memory graph state survives between these two calls.
    run_chat_turn(container, "Yes, proceed.", history=result_1.history, actor="test_actor")

    assert tool_ctx.surgery_service.get_surgery("S1001").status.value == "cancelled"
