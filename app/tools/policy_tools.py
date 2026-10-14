from __future__ import annotations

from app.tools.context import ToolContext


def search_hospital_policy(ctx: ToolContext, query: str) -> dict:
    result = ctx.policy_service.search(query)
    if not result["sufficient_evidence"]:
        return {
            "sufficient_evidence": False,
            "citations": [],
            "message": (
                "No hospital policy documents provided sufficiently relevant evidence "
                "for this question. Do not answer from general knowledge -- state that "
                "the policy corpus does not cover this."
            ),
        }
    return {
        "sufficient_evidence": True,
        "citations": result["citations"],
        "context": result["context"],
    }
