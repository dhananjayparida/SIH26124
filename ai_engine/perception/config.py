"""Environment-backed settings for the existing perception boundary."""

from dataclasses import dataclass
import os
from typing import Optional


def _positive_int(value: str, default: int) -> int:
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return default


def _threshold(value: str, default: float) -> float:
    try:
        return min(1.0, max(0.0, float(value)))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class PerceptionSettings:
    """Configuration without changing the SensorPacket or API contracts."""

    model_name: str = "yolo"
    checkpoint: Optional[str] = None
    confidence_threshold: float = 0.10
    device: str = "cpu"
    input_size: int = 640
    inference_sample_every: int = 1
    temporal_min_hits: int = 1

    @classmethod
    def from_env(cls) -> "PerceptionSettings":
        checkpoint = os.getenv("AI_MODEL_CHECKPOINT") or None
        return cls(
            model_name=os.getenv("AI_MODEL", "yolo").strip().lower(),
            checkpoint=checkpoint,
            confidence_threshold=_threshold(os.getenv("AI_CONFIDENCE_THRESHOLD", "0.10"), 0.10),
            device=os.getenv("AI_DEVICE", "cpu").strip() or "cpu",
            input_size=_positive_int(os.getenv("AI_INPUT_SIZE", "640"), 640),
            inference_sample_every=_positive_int(os.getenv("AI_INFERENCE_SAMPLE_EVERY", "1"), 1),
            temporal_min_hits=_positive_int(os.getenv("AI_TEMPORAL_MIN_HITS", "1"), 1),
        )
