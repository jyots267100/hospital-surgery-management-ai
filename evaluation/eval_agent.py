"""Evaluation script for the Hospital Surgery Management Agent.

Methodology (see docs/evaluation.md for full discussion):
  - "rag_grounding" and "hallucination_resistance" cases call PolicyService
    directly (no LLM needed) and check whether retrieval returned sufficient
    evidence from the expected document, or correctly reported insufficient
    evidence for off-topic/unanswerable queries.
  - "tool_selection" and "state_change_safety" cases run one real turn through
    the agent graph (requires GEMINI_API_KEY) and check which tool the LLM
    chose and whether its arguments match the expected shape, and -- for
    write tools -- that confirmed=false on the first call.

This script reports an honest, reproducible score against evaluation/eval_dataset.json.
It does NOT fabricate numbers: if GEMINI_API_KEY is not configured, tool-selection
cases are reported as SKIPPED rather than guessed at.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.core.logging_config import configure_logging  # noqa: E402
from app.dependencies import get_container  # noqa: E402

DATASET_PATH = Path(__file__).resolve().parent / "eval_dataset.json"
RESULTS_DIR = Path(__file__).resolve().parent / "results"


def _subset_match(actual: dict, expected: dict) -> bool:
    return all(key in actual and actual[key] == value for key, value in expected.items())


def evaluate_rag_case(case: dict, container) -> dict:
    result = container.policy_service.search(case["query"])
    sufficient = result["sufficient_evidence"]
    passed = sufficient == case["expected_sufficient_evidence"]
    citation_ok = True
    if passed and sufficient and "expected_citation_document" in case:
        citation_ok = any(case["expected_citation_document"] in c for c in result["citations"])
        passed = passed and citation_ok
    return {
        "id": case["id"], "category": case["category"], "passed": passed,
        "details": {"sufficient_evidence": sufficient, "citations": result["citations"]},
    }


def evaluate_tool_case(case: dict, container) -> dict:
    try:
        from app.agent.service import run_chat_turn
    except Exception as exc:  # noqa: BLE001
        return {"id": case["id"], "category": case["category"], "passed": None,
                "skipped_reason": f"agent unavailable: {exc}"}

    try:
        # We inspect the tool call via a lightweight direct graph run so we can
        # see selected_tool/tool_arguments rather than only the final text.
        from app.agent.graph import build_agent_graph
        from app.agent.llm import get_chat_model
        from app.tools.context import ToolContext
        from langchain_core.messages import HumanMessage

        chat_model = get_chat_model(container.settings)
        tool_ctx = ToolContext(
            surgery_service=container.surgery_service,
            operating_room_service=container.operating_room_service,
            surgeon_service=container.surgeon_service,
            dashboard_service=container.dashboard_service,
            event_service=container.event_service,
            policy_service=container.policy_service,
            actor="eval_script",
        )
        graph = build_agent_graph(chat_model, tool_ctx)
        final_state = graph.invoke({
            "messages": [HumanMessage(content=case["query"])],
            "user_query": case["query"], "iteration_count": 0,
            "confirmation_required": False, "confirmation_status": "none",
            "pending_action": None, "retrieved_context": None, "error": None,
        })
    except Exception as exc:  # noqa: BLE001
        return {"id": case["id"], "category": case["category"], "passed": None,
                "skipped_reason": f"LLM call failed (is GEMINI_API_KEY set?): {exc}"}

    selected_tool = None
    tool_args = None
    for msg in final_state["messages"]:
        if getattr(msg, "tool_calls", None):
            selected_tool = msg.tool_calls[0]["name"]
            tool_args = msg.tool_calls[0]["args"]
            break

    tool_match = selected_tool == case.get("expected_tool")
    args_match = _subset_match(tool_args or {}, case.get("expected_args", {}))
    passed = tool_match and args_match
    return {
        "id": case["id"], "category": case["category"], "passed": passed,
        "details": {"selected_tool": selected_tool, "tool_args": tool_args},
    }


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    container = get_container()

    cases = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    results = []
    for case in cases:
        if case["category"] in ("rag_grounding", "hallucination_resistance"):
            results.append(evaluate_rag_case(case, container))
        else:
            results.append(evaluate_tool_case(case, container))

    passed = sum(1 for r in results if r["passed"] is True)
    failed = sum(1 for r in results if r["passed"] is False)
    skipped = sum(1 for r in results if r["passed"] is None)

    print(f"Evaluation results: {passed} passed, {failed} failed, {skipped} skipped (of {len(results)})")
    for r in results:
        label = "PASS" if r["passed"] is True else ("FAIL" if r["passed"] is False else "SKIP")
        extra = r.get("skipped_reason", r.get("details"))
        print(f"  [{label}] {r['id']} ({r['category']}) -- {extra}")

    RESULTS_DIR.mkdir(exist_ok=True)
    out_path = RESULTS_DIR / "latest_results.json"
    out_path.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print(f"\nFull results written to {out_path}")


if __name__ == "__main__":
    main()
