"""
Unit tests for event lifecycle state machine transitions.
"""

import unittest
from ai_engine.sensor_interface.contracts import Event
from ai_engine.event_intelligence.state_machine import EventStateMachine, InvalidStateTransitionError


class TestStateMachine(unittest.TestCase):

    def setUp(self):
        self.event = Event(
            latitude=20.2961,
            longitude=85.8245,
            status="CANDIDATE"
        )

    def test_valid_forward_transitions(self):
        EventStateMachine.transition_event(self.event, "CORROBORATED")
        self.assertEqual(self.event.status, "CORROBORATED")

        EventStateMachine.transition_event(self.event, "HIGH_PRIORITY")
        self.assertEqual(self.event.status, "HIGH_PRIORITY")

        EventStateMachine.mark_repair_reported(self.event, "BMC-Division-1")
        self.assertEqual(self.event.status, "REPAIR_REPORTED")

        EventStateMachine.mark_resolved(self.event, "BMC-Inspector")
        self.assertEqual(self.event.status, "RESOLVED")

    def test_invalid_transition_raises(self):
        # CANDIDATE directly to RESOLVED without repair is forbidden
        with self.assertRaises(InvalidStateTransitionError):
            EventStateMachine.transition_event(self.event, "RESOLVED")


if __name__ == "__main__":
    unittest.main()
