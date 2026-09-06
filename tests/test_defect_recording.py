"""
Unit and Integration Tests for Video Recording, Defect Logging & Best Dataset Training (SIH26124).
"""

import unittest
import base64
import json
import time
from pathlib import Path
import numpy as np

# Ensure root workspace is on path
import sys
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from ai_engine.sensor_interface.contracts import GPSReading, SensorPacket
from ai_engine.perception.defect_recorder import DefectLedger, DefectRecord
from ai_engine.perception.video_recorder import VideoRecorder, RECORDINGS_DIR
from ai_engine.perception.detector import RoadDefectDetector
from ai_engine.training.dataset_manager import BestDatasetManager, BEST_CLASSES


class TestDefectRecordingAndTraining(unittest.TestCase):

    def setUp(self):
        self.test_log_path = BASE_DIR / "data" / "test_defect_records.json"
        self.ledger = DefectLedger(log_path=self.test_log_path)
        self.ledger.clear()

    def tearDown(self):
        if self.test_log_path.exists():
            self.test_log_path.unlink()

    def test_defect_ledger_operations(self):
        """Tests logging and querying potholes, missing zebra crossings, and vehicles."""
        # 1. Record a pothole
        r1 = self.ledger.record_defect(
            defect_type="pothole",
            confidence=0.92,
            latitude=20.2961,
            longitude=85.8245,
            device_id="BUS_01",
            severity="HIGH",
            bbox={"x": 200, "y": 250, "w": 100, "h": 80}
        )
        self.assertIsNotNone(r1.record_id)
        self.assertEqual(r1.defect_type, "pothole")

        # 2. Record missing zebra crossing
        r2 = self.ledger.record_defect(
            defect_type="no_zebracrossing",
            confidence=0.88,
            latitude=20.2970,
            longitude=85.8250,
            device_id="BUS_02",
            severity="HIGH",
            bbox={"x": 300, "y": 350, "w": 250, "h": 70}
        )
        self.assertEqual(r2.defect_type, "no_zebracrossing")

        # 3. Record vehicle detection
        r3 = self.ledger.record_defect(
            defect_type="vehicle",
            confidence=0.95,
            latitude=20.2980,
            longitude=85.8260,
            device_id="BUS_01",
            severity="LOW",
            bbox={"x": 400, "y": 200, "w": 120, "h": 90}
        )
        self.assertEqual(r3.defect_type, "vehicle")

        # 4. Query with filters
        potholes = self.ledger.list_defects(defect_type="pothole")
        self.assertEqual(len(potholes), 1)

        zebras = self.ledger.list_defects(defect_type="no_zebra")
        self.assertEqual(len(zebras), 1)

        bus1_records = self.ledger.list_defects(device_id="BUS_01")
        self.assertEqual(len(bus1_records), 2)

        # 5. Summary metrics
        summary = self.ledger.get_summary()
        self.assertEqual(summary["total_defects"], 3)
        self.assertEqual(summary["pothole_count"], 1)
        self.assertEqual(summary["no_zebracrossing_count"], 1)
        self.assertEqual(summary["vehicle_count"], 1)

    def test_multi_class_detector(self):
        """Tests that RoadDefectDetector identifies potholes, missing zebra crossings, and vehicles."""
        detector = RoadDefectDetector(confidence_threshold=0.3)

        # Ingest packet with pothole mock
        pkt1 = SensorPacket(
            device_id="BUS_TEST",
            gps=GPSReading(latitude=20.29, longitude=85.82),
            extra_metadata={"mock_defect": {"class_name": "pothole", "confidence": 0.89}}
        )
        res1 = detector.detect(pkt1)
        self.assertTrue(any(d.class_name == "pothole" for d in res1.detections))

        # Ingest packet with no_zebracrossing mock
        pkt2 = SensorPacket(
            device_id="BUS_TEST",
            gps=GPSReading(latitude=20.29, longitude=85.82),
            extra_metadata={"mock_defect": {"class_name": "no_zebracrossing", "confidence": 0.85}}
        )
        res2 = detector.detect(pkt2)
        self.assertTrue(any(d.class_name == "no_zebracrossing" for d in res2.detections))

        # Ingest packet with vehicle mock
        pkt3 = SensorPacket(
            device_id="BUS_TEST",
            gps=GPSReading(latitude=20.29, longitude=85.82),
            extra_metadata={"mock_defect": {"class_name": "vehicle", "confidence": 0.94}}
        )
        res3 = detector.detect(pkt3)
        self.assertTrue(any(d.class_name == "vehicle" for d in res3.detections))

    def test_strict_pothole_no_false_positives(self):
        """Verifies that normal road frames with shadows/textures do NOT trigger false potholes."""
        detector = RoadDefectDetector(confidence_threshold=0.5)

        # Create a frame with random dark patches / shadows
        import cv2
        frame = np.full((480, 640, 3), 80, dtype=np.uint8)
        # Add road shadow at bottom
        cv2.rectangle(frame, (100, 300), (350, 420), (20, 20, 20), -1)
        _, buf = cv2.imencode(".jpg", frame)
        b64 = f"data:image/jpeg;base64,{base64.b64encode(buf).decode('utf-8')}"

        # Ingest without enable_heuristic (normal live mode)
        normal_pkt = SensorPacket(
            device_id="BUS_LIVE",
            gps=GPSReading(latitude=20.29, longitude=85.82),
            frame_base64=b64,
            extra_metadata={"source_type": "phone_pwa"}
        )
        res = detector.detect(normal_pkt)
        potholes = [d for d in res.detections if d.class_name == "pothole"]
        self.assertEqual(len(potholes), 0, "Normal live frame should NOT trigger false positive potholes!")

        # Ingest with enable_heuristic explicitly enabled
        calib_pkt = SensorPacket(
            device_id="BUS_CALIB",
            gps=GPSReading(latitude=20.29, longitude=85.82),
            frame_base64=b64,
            extra_metadata={"enable_heuristic": True}
        )
        res_calib = detector.detect(calib_pkt)
        potholes_calib = [d for d in res_calib.detections if d.class_name == "pothole"]
        self.assertGreaterEqual(len(potholes_calib), 1, "Heuristic calibration mode should detect test patch when enabled")

    def test_video_recorder_and_overlay(self):
        """Tests frame ingestion, overlay drawing, and session finalization into an MP4 file."""
        recorder = VideoRecorder(fps=5.0, clip_duration_sec=60)
        device_id = "BUS_TEST_REC"

        # Create synthetic 480p frame
        import cv2
        canvas = np.full((480, 640, 3), 70, dtype=np.uint8)
        _, buf = cv2.imencode(".jpg", canvas)
        b64 = f"data:image/jpeg;base64,{base64.b64encode(buf).decode('utf-8')}"

        gps = {"latitude": 20.296, "longitude": 85.824, "speed": 25.0}
        detections = [
            {"class_name": "pothole", "confidence": 0.91, "bbox": {"x": 200, "y": 200, "w": 100, "h": 80}},
            {"class_name": "no_zebracrossing", "confidence": 0.87, "bbox": {"x": 300, "y": 300, "w": 200, "h": 60}},
            {"class_name": "vehicle", "confidence": 0.95, "bbox": {"x": 450, "y": 180, "w": 80, "h": 70}}
        ]

        # Ingest 3 frames
        for _ in range(3):
            recorder.ingest_frame(device_id, b64, gps, detections)

        self.assertIn(device_id, recorder.active_sessions)
        session = recorder.active_sessions[device_id]
        self.assertEqual(session["frame_count"], 3)

        # Finalize
        rec_info = recorder.finalize_session(device_id)
        self.assertIsNotNone(rec_info)
        self.assertEqual(rec_info["frame_count"], 3)
        self.assertTrue(Path(rec_info["path"]).exists())
        self.assertGreater(rec_info["size_bytes"], 0)

        # Check in list_recordings
        all_recs = recorder.list_recordings()
        self.assertTrue(any(r["filename"] == rec_info["filename"] for r in all_recs))

    def test_best_dataset_manager(self):
        """Tests that BestDatasetManager generates valid dataset splits and data.yaml."""
        test_ds_dir = BASE_DIR / "data" / "training_dataset" / "test_best"
        mgr = BestDatasetManager(dataset_dir=test_ds_dir)

        yaml_path = mgr.prepare_dataset()
        self.assertTrue(yaml_path.exists())

        # Verify YAML content
        import yaml
        with open(yaml_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)

        self.assertEqual(cfg["nc"], 5)
        self.assertEqual(cfg["names"][0], "pothole")
        self.assertEqual(cfg["names"][2], "no_zebracrossing")
        self.assertEqual(cfg["names"][4], "vehicle")

        train_imgs = list((test_ds_dir / "train" / "images").glob("*.jpg"))
        train_lbls = list((test_ds_dir / "train" / "labels").glob("*.txt"))
        self.assertGreater(len(train_imgs), 0)
        self.assertEqual(len(train_imgs), len(train_lbls))

        # Cleanup test dataset
        import shutil
        shutil.rmtree(test_ds_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
