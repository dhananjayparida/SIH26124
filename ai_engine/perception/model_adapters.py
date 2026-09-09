"""Model adapters which normalize model output into the existing contracts."""

import base64
import io
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional

from PIL import Image

from ..sensor_interface.contracts import BoundingBox, Detection, DetectionResult, SensorPacket
from .dfine_detector import DFineDetector


BASE_DIR = Path(__file__).resolve().parent.parent.parent
COCO_VEHICLE_NAMES = {"car", "bus", "truck", "motorcycle", "bicycle"}


class ModelAdapter(ABC):
    """The only model-specific boundary used by RoadDefectDetector."""

    name: str
    version: str
    checkpoint: Optional[str]

    @abstractmethod
    def detect(self, packet: SensorPacket) -> DetectionResult:
        raise NotImplementedError

    def metadata(self) -> Dict[str, object]:
        return {
            "model_name": self.name,
            "model_version": self.version,
            "checkpoint": self.checkpoint,
        }


class DFineModelAdapter(ModelAdapter):
    def __init__(self, checkpoint: Optional[str], confidence_threshold: float, device: str, input_size: int):
        self.name = "dfine"
        self.detector = DFineDetector(
            weights_path=checkpoint,
            confidence_threshold=confidence_threshold,
            device=device,
            imgsz=input_size,
        )
        self.version = self.detector.model_version
        self.checkpoint = self.detector.weights_path

    def detect(self, packet: SensorPacket) -> DetectionResult:
        return self.detector.detect(packet)


class YoloModelAdapter(ModelAdapter):
    def __init__(self, checkpoint: Optional[str], confidence_threshold: float, device: str, input_size: int):
        self.name = "yolo"
        self.confidence_threshold = confidence_threshold
        self.device = device
        self.input_size = input_size
        self.model = None
        self.checkpoint = checkpoint
        self.version = "yolov8n-unavailable"
        self._load()

    def _load(self) -> None:
        try:
            from ultralytics import YOLO
            if self.checkpoint and Path(self.checkpoint).exists():
                self.model = YOLO(self.checkpoint)
                self.version = Path(self.checkpoint).stem
            else:
                self.model = YOLO("yolov8n.pt")
                self.checkpoint = "yolov8n.pt"
                self.version = "yolov8n-default"
        except Exception as exc:
            print(f"[YoloModelAdapter] Model initialization warning: {exc}")

    @staticmethod
    def _decode_frame(packet: SensorPacket) -> Optional[Image.Image]:
        try:
            if packet.frame_base64:
                data = packet.frame_base64.split(",", 1)[-1]
                return Image.open(io.BytesIO(base64.b64decode(data))).convert("RGB")
            if packet.frame_path and Path(packet.frame_path).exists():
                return Image.open(packet.frame_path).convert("RGB")
        except Exception as exc:
            print(f"[YoloModelAdapter] Frame decode warning: {exc}")
        return None

    @staticmethod
    def _normalize_class(raw: str) -> Optional[str]:
        value = raw.lower()
        direct = {
            "pothole", "longitudinal_crack", "transverse_crack", "alligator_crack",
            "damaged_road", "missing_divider", "no_zebracrossing", "damaged_signboard",
            "waterlogging", "debris", "vehicle",
        }
        if value in direct:
            return value
        if value == "d40" or "pothole" in value:
            return "pothole"
        if value == "d00" or "longitudinal" in value:
            return "longitudinal_crack"
        if value == "d10" or "transverse" in value:
            return "transverse_crack"
        if value == "d20" or "alligator" in value:
            return "alligator_crack"
        if "damaged_road" in value or "damaged road" in value:
            return "damaged_road"
        if "crack" in value:
            return "longitudinal_crack"
        if "no_zebra" in value or "missing_zebra" in value or "zebra" in value:
            return "no_zebracrossing"
        if "divider" in value:
            return "missing_divider"
        if "sign" in value:
            return "damaged_signboard"
        if "water" in value or "flood" in value:
            return "waterlogging"
        if "debris" in value or "obstacle" in value:
            return "debris"
        if value in COCO_VEHICLE_NAMES or "vehicle" in value:
            return "vehicle"
        return None

    def detect(self, packet: SensorPacket) -> DetectionResult:
        started = time.perf_counter()
        detections: List[Detection] = []
        if packet.extra_metadata.get("is_test_fixture", False):
            fixtures = packet.extra_metadata.get("mock_defects")
            if not isinstance(fixtures, list):
                fixture = packet.extra_metadata.get("mock_defect")
                fixtures = [fixture] if isinstance(fixture, dict) else []
            for fixture in fixtures:
                detections.append(Detection(
                    class_name=fixture.get("class_name", "pothole").lower(),
                    confidence=float(fixture.get("confidence", 0.88)),
                    bbox=BoundingBox(x=float(fixture.get("x", 200)), y=float(fixture.get("y", 260)),
                                     width=float(fixture.get("w", 120)), height=float(fixture.get("h", 90))),
                    model_version=f"{self.version}-test-fixture",
                ))
            return DetectionResult(packet_id=packet.packet_id, device_id=packet.device_id,
                                   timestamp=packet.frame_timestamp, gps=packet.gps,
                                   detections=detections, inference_time_ms=0.0)
        frame = self._decode_frame(packet)
        if self.model is not None and frame is not None:
            try:
                for result in self.model.predict(source=frame, conf=self.confidence_threshold,
                                                 device=self.device, imgsz=self.input_size, verbose=False):
                    for box in result.boxes:
                        normalized = self._normalize_class(result.names.get(int(box.cls[0].item()), ""))
                        if not normalized:
                            continue
                        xywh = box.xywh[0].tolist()
                        detections.append(Detection(
                            class_name=normalized,
                            confidence=round(float(box.conf[0].item()), 4),
                            bbox=BoundingBox(x=xywh[0], y=xywh[1], width=xywh[2], height=xywh[3]),
                            model_version=self.version,
                        ))
            except Exception as exc:
                print(f"[YoloModelAdapter] Inference warning: {exc}")
        return DetectionResult(
            packet_id=packet.packet_id, device_id=packet.device_id, timestamp=packet.frame_timestamp,
            gps=packet.gps, detections=detections,
            inference_time_ms=(time.perf_counter() - started) * 1000.0,
        )


def resolve_checkpoint(model_name: str, requested: Optional[str]) -> Optional[str]:
    """Resolve shipped checkpoints while allowing an explicit fine-tuned checkpoint."""
    if requested and Path(requested).exists():
        return requested
    if model_name == "dfine":
        candidate = BASE_DIR / "models" / "dfine_road_defect_latest.pt"
    else:
        candidate = BASE_DIR / "models" / "best_road_defect_model.pt"
    return str(candidate) if candidate.exists() else None


def create_model_adapter(model_name: str, checkpoint: Optional[str], confidence_threshold: float,
                         device: str, input_size: int) -> ModelAdapter:
    resolved = resolve_checkpoint(model_name, checkpoint)
    if model_name == "dfine":
        return DFineModelAdapter(resolved, confidence_threshold, device, input_size)
    return YoloModelAdapter(resolved, confidence_threshold, device, input_size)
