"""Sensor Interface module for the Urban Intelligence Platform."""
from .contracts import (
    GPSReading,
    SourceMetadata,
    SensorPacket,
    BoundingBox,
    Detection,
    DetectionResult,
    Observation,
    Event,
)

__all__ = [
    "GPSReading",
    "SourceMetadata",
    "SensorPacket",
    "BoundingBox",
    "Detection",
    "DetectionResult",
    "Observation",
    "Event",
]
