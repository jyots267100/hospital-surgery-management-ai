from __future__ import annotations

from app.tools.context import ToolContext


def get_surgery_dashboard(ctx: ToolContext) -> dict:
    summary = ctx.dashboard_service.get_summary()
    return {**summary, "as_of_date": summary["as_of_date"].isoformat()}
