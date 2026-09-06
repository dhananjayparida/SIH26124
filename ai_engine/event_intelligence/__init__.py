"""Event intelligence package for lifecycle state transitions, severity, and evidence."""
from .state_machine import EventStateMachine, InvalidStateTransitionError
from .severity import assess_defect_severity
from .evidence import EvidenceManager

__all__ = [
    "EventStateMachine",
    "InvalidStateTransitionError",
    "assess_defect_severity",
    "EvidenceManager",
]
