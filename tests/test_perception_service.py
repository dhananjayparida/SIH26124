"""Non-mutating regression tests for the adapter-backed ingest detector."""

import unittest

from ai_engine.perception.config import PerceptionSettings
from ai_engine.perception.model_adapters import YoloModelAdapter
from ai_engine.perception.service import _TemporalFilter
from ai_engine.sensor_interface.contracts import BoundingBox, Detection, GPSReading, SensorPacket


def packet(timestamp=1000.0):
    return SensorPacket(
        packet_id=f"pkt_{timestamp}", device_id="BUS_TEST",
        frame_timestamp=timestamp,
        gps=GPSReading(latitude=20.2961, longitude=85.8245),
    )


class TestPerceptionSettings(unittest.TestCase):
    def test_defaults_preserve_current_ingest_behavior(self):
        settings = PerceptionSettings.from_env()
        self.assertEqual(settings.model_name, "yolo")
        self.assertEqual(settings.confidence_threshold, 0.10)
        self.assertEqual(settings.inference_sample_every, 1)
        self.assertEqual(settings.temporal_min_hits, 1)


class TestAdapterSafety(unittest.TestCase):
    def test_invalid_frame_returns_empty_result_without_crashing(self):
        adapter = YoloModelAdapter.__new__(YoloModelAdapter)
        adapter.name = "yolo"
        adapter.version = "test"
        adapter.checkpoint = None
        adapter.model = None
        adapter.confidence_threshold = 0.10
        adapter.device = "cpu"
        adapter.input_size = 640
        bad_packet = packet()
        bad_packet.frame_base64 = "data:image/jpeg;base64,not-valid-base64"

        result = adapter.detect(bad_packet)
        self.assertEqual(result.packet_id, bad_packet.packet_id)
        self.assertEqual(result.device_id, bad_packet.device_id)
        self.assertEqual(result.detections, [])

    def test_fixture_keeps_raw_confidence_and_model_version(self):
        adapter = YoloModelAdapter.__new__(YoloModelAdapter)
        adapter.name = "yolo"
        adapter.version = "checkpoint-v1"
        adapter.checkpoint = "models/custom.pt"
        adapter.model = None
        fixture = packet()
        fixture.extra_metadata = {"is_test_fixture": True, "mock_defect": {
            "class_name": "pothole", "confidence": 0.8732, "x": 10, "y": 20, "w": 30, "h": 40,
        }}

        result = adapter.detect(fixture)
        self.assertEqual(result.detections[0].confidence, 0.8732)
        self.assertEqual(result.detections[0].model_version, "checkpoint-v1-test-fixture")
        self.assertEqual(adapter.metadata()["checkpoint"], "models/custom.pt")


class TestTemporalFilter(unittest.TestCase):
    def test_same_source_requires_repeated_overlapping_detection_when_enabled(self):
        filter_ = _TemporalFilter(min_hits=2)
        detection = Detection(
            class_name="pothole", confidence=0.85,
            bbox=BoundingBox(x=100, y=100, width=30, height=30),
        )

        self.assertEqual(filter_.apply(packet(1000.0), [detection]), [])
        stable = filter_.apply(packet(1001.0), [detection])
        self.assertEqual(len(stable), 1)
        self.assertEqual(stable[0].confidence, 0.85)

    def test_default_temporal_filter_never_withholds_detection(self):
        filter_ = _TemporalFilter(min_hits=1)
        detection = Detection(
            class_name="pothole", confidence=0.85,
            bbox=BoundingBox(x=100, y=100, width=30, height=30),
        )
        self.assertEqual(filter_.apply(packet(), [detection]), [detection])


if __name__ == "__main__":
    unittest.main()
