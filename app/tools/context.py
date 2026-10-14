"""Dependency bundle passed to every tool so tool functions stay thin translators
between agent intent and the service layer, never touching data directly.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.services.dashboard_service import DashboardService
from app.services.event_service import EventService
from app.services.operating_room_service import OperatingRoomService
from app.services.policy_service import PolicyService
from app.services.surgeon_service import SurgeonService
from app.services.surgery_service import SurgeryService


@dataclass
class ToolContext:
    surgery_service: SurgeryService
    operating_room_service: OperatingRoomService
    surgeon_service: SurgeonService
    dashboard_service: DashboardService
    event_service: EventService
    policy_service: PolicyService
    actor: str = "staff_user"
