"""Perception package for defect detection."""
from .schemas import BoundingBox, Detection, DetectionResult
from .detector import RoadDefectDetector

__all__ = ["BoundingBox", "Detection", "DetectionResult", "RoadDefectDetector"]
