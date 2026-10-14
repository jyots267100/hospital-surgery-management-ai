from __future__ import annotations

from app.tools.context import ToolContext
from app.tools.serializers import event_to_dict


def add_surgery_event(ctx: ToolContext, surgery_id: str, event_type: str, description: str) -> dict:
    # Validate the surgery exists before attaching an event to it.
    ctx.surgery_service.get_surgery(surgery_id)
    event = ctx.event_service.add_event(
        surgery_id=surgery_id, event_type=event_type, description=description, actor=ctx.actor,
    )
    return {"event": event_to_dict(event)}
