"""
Perception Detector Module (AI-02).
Wraps YOLOv8 and D-FINE for multi-class urban defect and hazard detection:
- Road defects (potholes, cracks, damaged road)
- Missing zebra crossings (no_zebracrossing) & zebra crossings
- Other vehicles (cars, buses, trucks, motorcycles)
"""

import base64
import io
import time
from pathlib import Path
from typing import List, Optional, Dict, Any
import numpy as np
from PIL import Image

from ..sensor_interface.contracts import (
    SensorPacket,
    DetectionResult,
    Detection,
    BoundingBox,
)
from .dfine_detector import DFineDetector

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_TARGET_CLASSES = [
    "pothole",
    "damaged_road",
    "crack",
    "open_manhole",
    "no_zebracrossing",
    "zebra_crossing",
    "vehicle",
    "car",
    "bus",
    "truck",
    "motorcycle",
]

COCO_VEHICLE_NAMES = {"car", "bus", "truck", "motorcycle", "bicycle"}


class RoadDefectDetector:
    """
    Multi-class perception engine for road defects, missing zebra crossings,
    and vehicle detection using fine-tuned models and YOLOv8 fallback.
    """

    def __init__(
        self,
        model_type: str = "yolov8",
        weights_path: Optional[str] = None,
        confidence_threshold: float = 0.40,
        target_classes: Optional[List[str]] = None,
        device: str = "cpu"
    ):
        self.model_type = model_type.lower()
        self.confidence_threshold = confidence_threshold
        self.target_classes = [c.lower() for c in (target_classes or DEFAULT_TARGET_CLASSES)]
        self.device = device
        self.dfine = DFineDetector(weights_path=weights_path, confidence_threshold=confidence_threshold, device=device)
        self.model = None
        self.model_version = "yolov8n-multiclass"

        # Check for best trained model in models/
        best_checkpoint = BASE_DIR / "models" / "best_road_defect_model.pt"
        dfine_checkpoint = BASE_DIR / "models" / "dfine_road_defect_latest.pt"
        yolo_base = BASE_DIR / "yolov8n.pt"

        chosen_weights = weights_path
        if not chosen_weights or not Path(chosen_weights).exists():
            if best_checkpoint.exists():
                chosen_weights = str(best_checkpoint)
            elif dfine_checkpoint.exists():
                chosen_weights = str(dfine_checkpoint)
            elif yolo_base.exists():
                chosen_weights = str(yolo_base)

        self._load_yolo(chosen_weights)

    def _load_yolo(self, weights_path: Optional[str]):
        """Initializes or reloads the YOLO model."""
        try:
            from ultralytics import YOLO
            if weights_path and Path(weights_path).exists():
                self.model = YOLO(weights_path)
                self.model_version = Path(weights_path).stem
                print(f"[RoadDefectDetector] Loaded model weights from: {weights_path}")
            else:
                self.model = YOLO("yolov8n.pt")
                self.model_version = "yolov8n-default"
                print("[RoadDefectDetector] Loaded default YOLOv8n weights")
        except Exception as e:
            print(f"[RoadDefectDetector] Model initialization warning: {e}")
            self.model = None

    def reload_model(self, weights_path: str) -> bool:
        """Dynamically switches active model weights to newly fine-tuned checkpoint."""
        if Path(weights_path).exists():
            self._load_yolo(weights_path)
            return True
        return False

    def _decode_frame(self, packet: SensorPacket) -> Optional[Image.Image]:
        """Decodes raw base64 JPEG or loads file from disk."""
        if packet.frame_base64:
            data = packet.frame_base64
            if "," in data:
                data = data.split(",", 1)[1]
            image_bytes = base64.b64decode(data)
            return Image.open(io.BytesIO(image_bytes)).convert("RGB")
        elif packet.frame_path and Path(packet.frame_path).exists():
            return Image.open(packet.frame_path).convert("RGB")
        return None

    def detect(self, packet: SensorPacket) -> DetectionResult:
        """
        Performs multi-class perception inference on the SensorPacket.
        Detects potholes, missing zebra crossings, and vehicles.
        """
        start_t = time.perf_counter()
        detections: List[Detection] = []

        # 1. Injected Mock Defect (for test fixtures / replay demonstrations)
        if "mock_defect" in packet.extra_metadata:
            mock = packet.extra_metadata["mock_defect"]
            cls_name = mock.get("class_name", "pothole").lower()
            detections.append(Detection(
                class_name=cls_name,
                confidence=float(mock.get("confidence", 0.88)),
                bbox=BoundingBox(
                    x=float(mock.get("x", 200)),
                    y=float(mock.get("y", 260)),
                    width=float(mock.get("w", 120)),
                    height=float(mock.get("h", 90))
                ),
                model_version=f"{self.model_version}-sim"
            ))

        # Check for multiple mock defects
        if "mock_defects" in packet.extra_metadata:
            for mock in packet.extra_metadata["mock_defects"]:
                cls_name = mock.get("class_name", "pothole").lower()
                detections.append(Detection(
                    class_name=cls_name,
                    confidence=float(mock.get("confidence", 0.85)),
                    bbox=BoundingBox(
                        x=float(mock.get("x", 200)),
                        y=float(mock.get("y", 260)),
                        width=float(mock.get("w", 120)),
                        height=float(mock.get("h", 90))
                    ),
                    model_version=f"{self.model_version}-sim"
                ))

        frame = self._decode_frame(packet)

        # 2. Run Real YOLO Model Inference
        if self.model and frame:
            try:
                results = self.model.predict(
                    source=frame,
                    conf=self.confidence_threshold,
                    device=self.device,
                    imgsz=640,
                    verbose=False
                )
                for r in results:
                    boxes = r.boxes
                    for box in boxes:
                        cls_idx = int(box.cls[0].item())
                        cls_raw = r.names.get(cls_idx, f"class_{cls_idx}").lower()
                        conf = float(box.conf[0].item())
                        xywh = box.xywh[0].tolist()

                        # Determine mapped category
                        normalized_class = None
                        if "pothole" in cls_raw:
                            normalized_class = "pothole"
                        elif "crack" in cls_raw or "damaged" in cls_raw:
                            normalized_class = "damaged_road"
                        elif "no_zebra" in cls_raw:
                            normalized_class = "no_zebracrossing"
                        elif "zebra" in cls_raw or "crosswalk" in cls_raw:
                            normalized_class = "zebra_crossing"
                        elif "open_manhole" in cls_raw or "open manhole" in cls_raw:
                            normalized_class = "open_manhole"
                        elif cls_raw in COCO_VEHICLE_NAMES or "vehicle" in cls_raw:
                            normalized_class = "vehicle"
                        elif cls_raw in self.target_classes:
                            normalized_class = cls_raw

                        # Strict pothole validation
                        if normalized_class == "pothole":
                            # Require strict confidence (>= 0.60)
                            if conf < 0.60:
                                continue
                            # Geometric road perspective check: pothole must be in lower 65% of image
                            if xywh[1] < (frame.height * 0.35):
                                continue
                            # Aspect ratio check: avoid long thin vertical or horizontal artifacts
                            aspect = xywh[2] / max(1.0, xywh[3])
                            if aspect < 0.3 or aspect > 3.5:
                                continue
                            # Size check: must not be a tiny speck or cover half the screen
                            area_ratio = (xywh[2] * xywh[3]) / float(frame.width * frame.height)
                            if area_ratio < 0.003 or area_ratio > 0.40:
                                continue

                        if normalized_class:
                            detections.append(Detection(
                                class_name=normalized_class,
                                confidence=conf,
                                bbox=BoundingBox(
                                    x=xywh[0],
                                    y=xywh[1],
                                    width=xywh[2],
                                    height=xywh[3]
                                ),
                                model_version=self.model_version
                            ))
            except Exception as e:
                print(f"[RoadDefectDetector] Inference error: {e}")

        # 3. Heuristic Visual & Marking Inspection (STRICT: ONLY for testing/fixtures when explicitly enabled)
        if frame and packet.extra_metadata.get("enable_heuristic", False):
            try:
                arr = np.array(frame.convert("L"))
                h, w = arr.shape
                road_view = arr[int(h * 0.35):, :]
                mean_b = np.mean(road_view)

                # Pothole dark crater check (only in explicit calibration/test mode)
                dark_mask = road_view < (mean_b * 0.40)
                if np.sum(dark_mask) > (road_view.size * 0.05) and not any(d.class_name == "pothole" for d in detections):
                    y_idx, x_idx = np.nonzero(dark_mask)
                    if len(x_idx) > 80:
                        min_x, max_x = int(np.min(x_idx)), int(np.max(x_idx))
                        min_y, max_y = int(np.min(y_idx)) + int(h * 0.35), int(np.max(y_idx)) + int(h * 0.35)
                        detections.append(Detection(
                            class_name="pothole",
                            confidence=0.88,
                            bbox=BoundingBox(
                                x=float((min_x + max_x) // 2),
                                y=float((min_y + max_y) // 2),
                                width=float(max(40, max_x - min_x)),
                                height=float(max(30, max_y - min_y))
                            ),
                            model_version=f"{self.model_version}-heuristic"
                        ))

                # Missing zebra crossing check (when road intersection is flagged or requested in metadata)
                if packet.extra_metadata.get("check_crossing", False) or packet.extra_metadata.get("pedestrian_zone", False):
                    # Check for alternating white stripes
                    bright_mask = road_view > (mean_b * 1.5)
                    has_stripes = np.sum(bright_mask) > (road_view.size * 0.08)
                    if not has_stripes:
                        # Alert: pedestrian crossing hazard / missing zebra crossing
                        detections.append(Detection(
                            class_name="no_zebracrossing",
                            confidence=0.86,
                            bbox=BoundingBox(
                                x=float(w // 2),
                                y=float(int(h * 0.7)),
                                width=float(w * 0.7),
                                height=float(h * 0.25)
                            ),
                            model_version=f"{self.model_version}-crosswalk-rule"
                        ))
                    else:
                        detections.append(Detection(
                            class_name="zebra_crossing",
                            confidence=0.91,
                            bbox=BoundingBox(
                                x=float(w // 2),
                                y=float(int(h * 0.7)),
                                width=float(w * 0.7),
                                height=float(h * 0.25)
                            ),
                            model_version=f"{self.model_version}-crosswalk-rule"
                        ))
            except Exception:
                pass

        elapsed_ms = (time.perf_counter() - start_t) * 1000.0

        return DetectionResult(
            packet_id=packet.packet_id,
            device_id=packet.device_id,
            timestamp=packet.frame_timestamp,
            gps=packet.gps,
            detections=detections,
            inference_time_ms=elapsed_ms
        )
