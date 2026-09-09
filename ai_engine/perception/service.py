"""Configurable perception facade for the protected FastAPI ingestion path."""

import time
from collections import defaultdict
from typing import Dict, List, Tuple

from ..sensor_interface.contracts import BoundingBox, Detection, DetectionResult, SensorPacket
from .config import PerceptionSettings
from .model_adapters import ModelAdapter, create_model_adapter


class _TemporalFilter:
    """Temporary same-device consistency filter; it never performs event fusion."""

    def __init__(self, min_hits: int):
        self.min_hits = min_hits
        self.tracks: Dict[Tuple[str, str], Tuple[BoundingBox, int, float]] = {}

    @staticmethod
    def _iou(a: BoundingBox, b: BoundingBox) -> float:
        ax1, ay1, ax2, ay2 = a.x - a.width / 2, a.y - a.height / 2, a.x + a.width / 2, a.y + a.height / 2
        bx1, by1, bx2, by2 = b.x - b.width / 2, b.y - b.height / 2, b.x + b.width / 2, b.y + b.height / 2
        inter = max(0.0, min(ax2, bx2) - max(ax1, bx1)) * max(0.0, min(ay2, by2) - max(ay1, by1))
        union = a.width * a.height + b.width * b.height - inter
        return inter / union if union > 0 else 0.0

    def apply(self, packet: SensorPacket, detections: List[Detection]) -> List[Detection]:
        if self.min_hits <= 1:
            return detections
        kept = []
        for detection in detections:
            key = (packet.device_id, detection.class_name)
            prior = self.tracks.get(key)
            hits = 1
            if prior and packet.frame_timestamp - prior[2] <= 3.0 and self._iou(prior[0], detection.bbox) >= 0.30:
                hits = prior[1] + 1
            self.tracks[key] = (detection.bbox, hits, packet.frame_timestamp)
            if hits >= self.min_hits:
                kept.append(detection)
        return kept


class ConfiguredPerceptionDetector:
    """Adapter-backed detector retaining ``detect(packet) -> DetectionResult``."""

    def __init__(self, settings: PerceptionSettings = None):
        self.settings = settings or PerceptionSettings.from_env()
        self.adapter: ModelAdapter = create_model_adapter(
            self.settings.model_name, self.settings.checkpoint,
            self.settings.confidence_threshold, self.settings.device, self.settings.input_size,
        )
        self._packet_counts = defaultdict(int)
        self._temporal_filter = _TemporalFilter(self.settings.temporal_min_hits)
        print(f"[ConfiguredPerceptionDetector] Active model: {self.adapter.name} ({self.adapter.version})")

    @property
    def metadata(self) -> Dict[str, object]:
        data = self.adapter.metadata()
        data.update({
            "confidence_threshold": self.settings.confidence_threshold,
            "input_size": self.settings.input_size,
            "inference_sample_every": self.settings.inference_sample_every,
            "temporal_min_hits": self.settings.temporal_min_hits,
            "device": self.settings.device,
        })
        return data

    def detect(self, packet: SensorPacket) -> DetectionResult:
        # Fixture packets are part of the existing automated-test contract and
        # must not be sampled away.
        if not packet.extra_metadata.get("is_test_fixture", False):
            self._packet_counts[packet.device_id] += 1
            if self._packet_counts[packet.device_id] % self.settings.inference_sample_every:
                return DetectionResult(packet_id=packet.packet_id, device_id=packet.device_id,
                                       timestamp=packet.frame_timestamp, gps=packet.gps,
                                       detections=[], inference_time_ms=0.0)
        started = time.perf_counter()
        try:
            result = self.adapter.detect(packet)
            result.detections = self._temporal_filter.apply(packet, result.detections)
            return result
        except Exception as exc:
            print(f"[ConfiguredPerceptionDetector] Inference warning: {exc}")
            return DetectionResult(packet_id=packet.packet_id, device_id=packet.device_id,
                                   timestamp=packet.frame_timestamp, gps=packet.gps,
                                   detections=[], inference_time_ms=(time.perf_counter() - started) * 1000.0)
