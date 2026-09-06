"""
Perception schemas for AI-02 defect detection.
"""

from typing import List, Optional
from pydantic import BaseModel, Field
from ..sensor_interface.contracts import GPSReading, BoundingBox, Detection, DetectionResult

__all__ = ["BoundingBox", "Detection", "DetectionResult"]
