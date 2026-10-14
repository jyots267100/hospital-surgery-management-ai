"""A minimal fake chat model used to unit-test the LangGraph wiring (tool
routing, multi-step loops, confirmation workflow) without calling the real
Gemini API. It duck-types the subset of BaseChatModel the graph relies on:
`.bind_tools(tools)` and `.invoke(messages)`.
"""
from __future__ import annotations

from langchain_core.messages import AIMessage


class FakeChatModel:
    def __init__(self, responses: list[AIMessage]) -> None:
        self._responses = list(responses)
        self.invocation_count = 0

    def bind_tools(self, tools):  # noqa: ARG002 - signature parity with BaseChatModel
        return self

    def invoke(self, messages):  # noqa: ARG002
        self.invocation_count += 1
        if not self._responses:
            return AIMessage(content="(fake model ran out of scripted responses)")
        return self._responses.pop(0)


def tool_call_message(name: str, args: dict, call_id: str = "call_1") -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id}])


def final_message(content: str) -> AIMessage:
    return AIMessage(content=content)
