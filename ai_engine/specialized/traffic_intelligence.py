"""
Traffic Intelligence Module — Stub (P1).

Converts vehicle-class detections from the perception stack into
TRAFFIC domain Observations. Wired into the ingest pipeline behind
the ENABLE_TRAFFIC_INTELLIGENCE feature flag.

Master context §9.2: Traffic intelligence reuses D-FINE general vehicle
classes and converts them to compatible Observations/Events — NOT a
separate subsystem.

Future: integrate ByteTrack for vehicle counting, density, flow estimation.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import List
from uuid import uuid4

from ..sensor_interface.contracts import (
    DetectionResult, Observation, EventType, EventSubtype, GPSReading
)
from ..specialized.observation_classifier import classify_detection

# Feature flag — set ENABLE_TRAFFIC_INTELLIGENCE=true to activate
TRAFFIC_ENABLED = os.getenv("ENABLE_TRAFFIC_INTELLIGENCE", "true").lower() == "true"

# Traffic-domain class names (subset of classifier map)
_TRAFFIC_CLASSES = {
    "vehicle", "car", "bus", "truck", "motorcycle", "bicycle",
    "traffic_jam", "bottleneck"
}


class TrafficIntelligence:
    """
    Processes a DetectionResult and extracts TRAFFIC domain Observations.

    In the stub phase this simply promotes vehicle detections into
    TRAFFIC / VEHICLE_PRESENCE observations so they appear on the
    Traffic layer of the command center.

    Future phases will add:
    - ByteTrack vehicle identity across frames
    - ROI-based vehicle counting
    - Speed/density/flow proxies
    - Bottleneck detection when queue length exceeds threshold
    """

    def __init__(self, confidence_threshold: float = 0.50):
        self.confidence_threshold = confidence_threshold

    def process(self, result: DetectionResult) -> List[Observation]:
        """
        Produces TRAFFIC Observations from vehicle-class detections.
        Returns an empty list when the feature flag is off.
        """
        if not TRAFFIC_ENABLED:
            return []

        traffic_obs: List[Observation] = []

        for det in result.detections:
            if det.class_name.lower() not in _TRAFFIC_CLASSES:
                continue
            if det.confidence < self.confidence_threshold:
                continue

            ev_type, ev_subtype = classify_detection(det.class_name)

            obs = Observation(
                observation_id=str(uuid4()),
                device_id=result.device_id,
                packet_id=result.packet_id,
                timestamp=result.timestamp,
                latitude=result.gps.latitude,
                longitude=result.gps.longitude,
                observation_type=ev_type,
                observation_subtype=ev_subtype,
                defect_type=ev_subtype,  # legacy alias
                model_confidence=det.confidence,
                bbox=det.bbox,
            )
            traffic_obs.append(obs)

        return traffic_obs

    @staticmethod
    def is_enabled() -> bool:
        return TRAFFIC_ENABLED


# Module-level singleton
global_traffic_intelligence = TrafficIntelligence()
