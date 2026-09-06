"""
Event Lifecycle State Machine (AI-06).
Governs allowable transitions:
CANDIDATE -> CORROBORATED -> HIGH_PRIORITY -> REPAIR_REPORTED -> NEEDS_VERIFICATION -> RESOLVED
Any -> REJECTED
"""

from typing import Set, Dict
from ..sensor_interface.contracts import Event


class InvalidStateTransitionError(ValueError):
    pass


class EventStateMachine:
    """Validates and executes lifecycle state transitions."""

    # Allowed forward transitions
    TRANSITIONS: Dict[str, Set[str]] = {
        "CANDIDATE": {"CORROBORATED", "HIGH_PRIORITY", "REPAIR_REPORTED", "REJECTED"},
        "CORROBORATED": {"HIGH_PRIORITY", "REPAIR_REPORTED", "REJECTED"},
        "HIGH_PRIORITY": {"REPAIR_REPORTED", "REJECTED"},
        "REPAIR_REPORTED": {"NEEDS_VERIFICATION", "RESOLVED", "REJECTED"},
        "NEEDS_VERIFICATION": {"REPAIR_REPORTED", "RESOLVED", "REJECTED"},
        "RESOLVED": {"NEEDS_VERIFICATION", "CANDIDATE"},
        "REJECTED": {"CANDIDATE"}
    }

    @classmethod
    def can_transition(cls, current_status: str, next_status: str) -> bool:
        if current_status == next_status:
            return True
        allowed = cls.TRANSITIONS.get(current_status, set())
        return next_status in allowed

    @classmethod
    def transition_event(cls, event: Event, next_status: str, actor: str = "system") -> Event:
        if not cls.can_transition(event.status, next_status):
            raise InvalidStateTransitionError(
                f"Cannot transition event {event.event_id} from {event.status} to {next_status}"
            )
        event.status = next_status
        return event

    @classmethod
    def mark_repair_reported(cls, event: Event, authority_name: str) -> Event:
        """Called when municipal authority marks a work order issued or repair dispatched."""
        return cls.transition_event(event, "REPAIR_REPORTED", actor=authority_name)

    @classmethod
    def mark_resolved(cls, event: Event, authority_name: str) -> Event:
        """Called when municipal authority confirms repair is complete and verified."""
        return cls.transition_event(event, "RESOLVED", actor=authority_name)

    @classmethod
    def mark_rejected(cls, event: Event, reason: str = "false_positive") -> Event:
        """Called when inspector rejects defect as non-actionable or false detection."""
        return cls.transition_event(event, "REJECTED", actor=reason)
