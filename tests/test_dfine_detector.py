"""
Unit and Integration Tests for Native D-FINE Perception Engine (SIH26124).
Verifies native TorchScript loading, bounding box regression, multi-class defect detection,
and RoadDefectDetector routing.
"""

import unittest
import base64
import time
from pathlib import Path
import numpy as np
from PIL import Image

import sys
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from ai_engine.sensor_interface.contracts import GPSReading, SensorPacket, DetectionResult
from ai_engine.perception.dfine_detector import DFineDetector, DFINE_CLASSES
from ai_engine.perception.detector import RoadDefectDetector


class TestDFineDetectorNative(unittest.TestCase):

    def setUp(self):
        self.model_path = BASE_DIR / "models" / "dfine_road_defect_latest.pt"

    def test_torchscript_file_validity(self):
        """Verifies dfine_road_defect_latest.pt is a genuine TorchScript model loadable without Ultralytics."""
        self.assertTrue(self.model_path.exists(), f"Model file {self.model_path} should exist")

        import torch
        # Load directly with pure torch.jit.load
        ts_model = torch.jit.load(str(self.model_path), map_location="cpu")
        ts_model.eval()

        dummy = torch.zeros((1, 3, 640, 640), dtype=torch.float32)
        with torch.no_grad():
            output = ts_model(dummy)

        self.assertIsNotNone(output, "TorchScript model should output prediction tensors")
        print(f"\n[Test] Native TorchScript loaded successfully. Output type: {type(output)}")

    def test_dfine_detector_instantiation_and_warmup(self):
        """Verifies DFineDetector loads and warms up without errors."""
        detector = DFineDetector(
            weights_path=str(self.model_path),
            confidence_threshold=0.35,
            device="cpu"
        )
        self.assertIsNotNone(detector.model)
        self.assertTrue(detector.model_version.startswith("D-FINE"))

    def test_dfine_detection_on_test_image(self):
        """Runs native D-FINE inference on a real road image and verifies structured detections."""
        detector = DFineDetector(
            weights_path=str(self.model_path),
            confidence_threshold=0.25,
            device="cpu"
        )

        # Locate sample image
        val_imgs = list((BASE_DIR / "data" / "training_dataset" / "best" / "val" / "images").glob("*.jpg"))
        if not val_imgs:
            val_imgs = list((BASE_DIR / "data" / "training_dataset" / "images").glob("*.jpg"))

        self.assertGreater(len(val_imgs), 0, "Should have sample images for inference testing")

        test_img_path = val_imgs[0]
        with open(test_img_path, "rb") as f:
            b64_str = base64.b64encode(f.read()).decode("utf-8")

        pkt = SensorPacket(
            packet_id="test_dfine_001",
            device_id="BUS_DFINE_TEST",
            frame_timestamp=time.time(),
            frame_base64=f"data:image/jpeg;base64,{b64_str}",
            gps=GPSReading(latitude=20.2961, longitude=85.8245, accuracy=3.0)
        )

        res = detector.detect(pkt)
        self.assertIsInstance(res, DetectionResult)
        self.assertGreaterEqual(res.inference_time_ms, 0.0)
        print(f"\n[Test] DFineDetector inference time: {res.inference_time_ms:.2f}ms, Detections: {len(res.detections)}")

        for d in res.detections:
            self.assertIn(d.class_name, list(DFINE_CLASSES.values()) + ["pothole", "transverse_crack", "vehicle"])
            self.assertGreaterEqual(d.confidence, 0.25)
            self.assertGreaterEqual(d.bbox.width, 0.0)
            self.assertGreaterEqual(d.bbox.height, 0.0)
            print(f"  -> {d.class_name}: conf={d.confidence:.2f}, bbox=[{d.bbox.x}, {d.bbox.y}, {d.bbox.width}, {d.bbox.height}]")

    def test_road_defect_detector_dfine_routing(self):
        """Tests that RoadDefectDetector correctly uses DFineDetector when model_type='dfine'."""
        detector = RoadDefectDetector(
            model_type="dfine",
            weights_path=str(self.model_path),
            confidence_threshold=0.30,
            device="cpu"
        )
        self.assertEqual(detector.model_type, "dfine")
        self.assertTrue(detector.model_version.startswith("D-FINE"))

        # Test fixture ingestion
        pkt = SensorPacket(
            device_id="BUS_TEST",
            gps=GPSReading(latitude=20.29, longitude=85.82),
            extra_metadata={"is_test_fixture": True, "mock_defect": {"class_name": "pothole", "confidence": 0.93}}
        )
        res = detector.detect(pkt)
        self.assertTrue(any(d.class_name == "pothole" for d in res.detections))


if __name__ == "__main__":
    unittest.main()
