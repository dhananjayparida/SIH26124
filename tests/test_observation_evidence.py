"""Regression coverage for additive observation/evidence traceability."""

import tempfile
import unittest
from pathlib import Path

from ai_engine.event_intelligence.evidence import EvidenceManager
from ai_engine.sensor_interface.contracts import BoundingBox, Observation


class TestObservationTraceability(unittest.TestCase):
    def test_historical_packet_model_and_evidence_metadata_are_retained(self):
        observation = Observation(
            observation_id="obs-contract-1",
            event_id="event-contract-1",
            device_id="BUS_01",
            packet_id="packet-101",
            timestamp=1725350100.25,
            latitude=20.2961,
            longitude=85.8245,
            observation_type="ROAD_DAMAGE",
            observation_subtype="POTHOLE",
            defect_type="POTHOLE",
            model_name="yolo",
            model_version="road-defect-v1",
            model_confidence=0.91,
            bbox=BoundingBox(x=320, y=240, width=120, height=80),
            snapshot_path="/evidence/pending_obs-cont.jpg",
            source_type="phone_pwa",
            evidence_status="AVAILABLE",
        )

        self.assertEqual(observation.device_id, "BUS_01")
        self.assertEqual(observation.packet_id, "packet-101")
        self.assertEqual(observation.timestamp, 1725350100.25)
        self.assertEqual((observation.latitude, observation.longitude), (20.2961, 85.8245))
        self.assertEqual(observation.model_name, "yolo")
        self.assertEqual(observation.model_version, "road-defect-v1")
        self.assertEqual(observation.evidence_status, "AVAILABLE")


class TestEvidenceSelection(unittest.TestCase):
    def test_default_policy_preserves_capture_per_detection(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = EvidenceManager(directory)
            self.assertTrue(manager.should_capture("BUS_01", "pothole", 0.20, 1000.0))
            self.assertTrue(manager.should_capture("BUS_01", "pothole", 0.20, 1001.0))

    def test_interval_policy_only_throttles_same_device_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = EvidenceManager(directory)
            manager.interval_seconds = 10.0
            self.assertTrue(manager.should_capture("BUS_01", "pothole", 0.90, 1000.0))
            self.assertFalse(manager.should_capture("BUS_01", "pothole", 0.90, 1005.0))
            self.assertTrue(manager.should_capture("BUS_02", "pothole", 0.90, 1005.0))

    def test_low_confidence_policy_does_not_claim_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = EvidenceManager(directory)
            manager.min_confidence = 0.80
            self.assertFalse(manager.should_capture("BUS_01", "pothole", 0.79, 1000.0))


if __name__ == "__main__":
    unittest.main()
