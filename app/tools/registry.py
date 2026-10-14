"""Builds the list of LangChain StructuredTools bound to a given ToolContext.

This is the single place that maps the ~12 agent-facing tools to their argument
schemas and underlying implementations, so the LangGraph agent node can bind
them to the LLM with `llm.bind_tools(tools)`.
"""
from __future__ import annotations

from langchain_core.tools import StructuredTool

from app.tools import dashboard_tools, event_tools, policy_tools, surgery_tools
from app.tools.context import ToolContext
from app.tools.schema import (
    AddSurgeryEventArgs,
    CancelSurgeryArgs,
    CreateSurgeryArgs,
    GetDelayedSurgeriesArgs,
    GetOperatingRoomAvailabilityArgs,
    GetSurgeonScheduleArgs,
    GetSurgeryDashboardArgs,
    GetSurgeryStatusArgs,
    GetTodaysSurgeriesArgs,
    RescheduleSurgeryArgs,
    SearchHospitalPolicyArgs,
    UpdateSurgeryStatusArgs,
)


def build_tools(ctx: ToolContext) -> list[StructuredTool]:
    return [
        StructuredTool.from_function(
            name="get_todays_surgeries",
            description="Get all surgeries scheduled for today, with status, surgeon, room and time.",
            func=lambda: surgery_tools.get_todays_surgeries(ctx),
            args_schema=GetTodaysSurgeriesArgs,
        ),
        StructuredTool.from_function(
            name="get_delayed_surgeries",
            description="Get all surgeries currently marked as delayed, with delay duration and reason.",
            func=lambda: surgery_tools.get_delayed_surgeries(ctx),
            args_schema=GetDelayedSurgeriesArgs,
        ),
        StructuredTool.from_function(
            name="get_surgery_status",
            description="Look up the current status and details of a single surgery by its surgery_id.",
            func=lambda surgery_id: surgery_tools.get_surgery_status(ctx, surgery_id),
            args_schema=GetSurgeryStatusArgs,
        ),
        StructuredTool.from_function(
            name="search_hospital_policy",
            description=(
                "Search the hospital's policy documents (cancellation, scheduling, delay, "
                "operating room, emergency, patient preparation policies) for grounded, "
                "citable answers. Use this for any question about hospital rules or policy."
            ),
            func=lambda query: policy_tools.search_hospital_policy(ctx, query),
            args_schema=SearchHospitalPolicyArgs,
        ),
        StructuredTool.from_function(
            name="cancel_surgery",
            description=(
                "Propose or execute cancelling a surgery. ALWAYS call with confirmed=false first to "
                "get a proposal; only call again with confirmed=true after the user has explicitly "
                "agreed to the cancellation in their most recent message."
            ),
            func=lambda surgery_id, reason, confirmed=False: surgery_tools.cancel_surgery(
                ctx, surgery_id, reason, confirmed,
            ),
            args_schema=CancelSurgeryArgs,
        ),
        StructuredTool.from_function(
            name="create_surgery",
            description=(
                "Propose or execute scheduling a new surgery. ALWAYS call with confirmed=false first "
                "to validate and get a proposal; only call again with confirmed=true after the user "
                "has explicitly confirmed."
            ),
            func=lambda **kwargs: surgery_tools.create_surgery(ctx, **kwargs),
            args_schema=CreateSurgeryArgs,
        ),
        StructuredTool.from_function(
            name="reschedule_surgery",
            description=(
                "Propose or execute moving a surgery to a new date/time/room. ALWAYS call with "
                "confirmed=false first to validate and get a proposal; only call again with "
                "confirmed=true after explicit user confirmation."
            ),
            func=lambda **kwargs: surgery_tools.reschedule_surgery(ctx, **kwargs),
            args_schema=RescheduleSurgeryArgs,
        ),
        StructuredTool.from_function(
            name="update_surgery_status",
            description=(
                "Propose or execute a surgery status transition (scheduled, confirmed, in_progress, "
                "completed, delayed, cancelled). ALWAYS call with confirmed=false first; only call "
                "again with confirmed=true after explicit user confirmation."
            ),
            func=lambda **kwargs: surgery_tools.update_surgery_status(ctx, **kwargs),
            args_schema=UpdateSurgeryStatusArgs,
        ),
        StructuredTool.from_function(
            name="get_operating_room_availability",
            description="Check which operating room(s) are available on a given date and time window.",
            func=lambda **kwargs: surgery_tools.get_operating_room_availability(ctx, **kwargs),
            args_schema=GetOperatingRoomAvailabilityArgs,
        ),
        StructuredTool.from_function(
            name="get_surgeon_schedule",
            description="Get a surgeon's scheduled surgeries, optionally filtered to a specific date.",
            func=lambda **kwargs: surgery_tools.get_surgeon_schedule(ctx, **kwargs),
            args_schema=GetSurgeonScheduleArgs,
        ),
        StructuredTool.from_function(
            name="get_surgery_dashboard",
            description="Get operational dashboard metrics: counts by status, average delay, OR utilization.",
            func=lambda: dashboard_tools.get_surgery_dashboard(ctx),
            args_schema=GetSurgeryDashboardArgs,
        ),
        StructuredTool.from_function(
            name="add_surgery_event",
            description="Add a free-form audit/note event to a surgery's history (e.g. a note, not a status change).",
            func=lambda **kwargs: event_tools.add_surgery_event(ctx, **kwargs),
            args_schema=AddSurgeryEventArgs,
        ),
    ]
