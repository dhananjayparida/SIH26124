"""
Observation Classifier — Single source of truth for mapping raw detector
class-names to the Urban Intelligence taxonomy (EventType / EventSubtype).

Any new detection class should be added HERE only. The ingest pipeline,
severity rules, and frontend all derive domain from this mapping.

Master context §10: the architecture must support multiple domain types without
redesigning the pipeline for each one.
"""

from __future__ import annotations
from typing import Tuple

from ..sensor_interface.contracts import EventType, EventSubtype

# ─── Raw-class → (EventType, EventSubtype) mapping ──────────────────────────
#
# Keys are lowercased raw detector class names (as they come from YOLO/D-FINE).
# Add new detector classes here as the perception stack expands.
_CLASS_MAP: dict[str, Tuple[str, str]] = {
    # ── ROAD_DAMAGE ───────────────────────────────────────────────────────────
    "pothole":             (EventType.ROAD_DAMAGE,    EventSubtype.POTHOLE),
    "crack":               (EventType.ROAD_DAMAGE,    EventSubtype.LONGITUDINAL_CRACK),
    "longitudinal_crack":  (EventType.ROAD_DAMAGE,    EventSubtype.LONGITUDINAL_CRACK),
    "transverse_crack":    (EventType.ROAD_DAMAGE,    EventSubtype.TRANSVERSE_CRACK),
    "alligator_crack":     (EventType.ROAD_DAMAGE,    EventSubtype.ALLIGATOR_CRACK),
    "damaged_road":        (EventType.ROAD_DAMAGE,    EventSubtype.DAMAGED_ROAD),
    "d40":                 (EventType.ROAD_DAMAGE,    EventSubtype.POTHOLE),   # RDD2022
    "d00":                 (EventType.ROAD_DAMAGE,    EventSubtype.LONGITUDINAL_CRACK),
    "d10":                 (EventType.ROAD_DAMAGE,    EventSubtype.TRANSVERSE_CRACK),
    "d20":                 (EventType.ROAD_DAMAGE,    EventSubtype.ALLIGATOR_CRACK),

    # ── INFRASTRUCTURE ────────────────────────────────────────────────────────
    "no_zebracrossing":    (EventType.INFRASTRUCTURE, EventSubtype.MISSING_ZEBRA),
    "no_zebra_crossing":   (EventType.INFRASTRUCTURE, EventSubtype.MISSING_ZEBRA),
    "missing_zebra":       (EventType.INFRASTRUCTURE, EventSubtype.MISSING_ZEBRA),
    "zebra_crossing":      (EventType.INFRASTRUCTURE, EventSubtype.ZEBRA_CROSSING),
    "crosswalk":           (EventType.INFRASTRUCTURE, EventSubtype.ZEBRA_CROSSING),
    "missing_divider":     (EventType.INFRASTRUCTURE, EventSubtype.MISSING_DIVIDER),
    "damaged_signboard":   (EventType.INFRASTRUCTURE, EventSubtype.DAMAGED_SIGNBOARD),

    # ── WATERLOGGING ──────────────────────────────────────────────────────────
    "waterlogging":        (EventType.WATERLOGGING,   EventSubtype.ROAD_WATERLOGGING),
    "water":               (EventType.WATERLOGGING,   EventSubtype.ROAD_WATERLOGGING),
    "flood":               (EventType.WATERLOGGING,   EventSubtype.ROAD_WATERLOGGING),

    # ── ROAD_HAZARD ───────────────────────────────────────────────────────────
    "debris":              (EventType.ROAD_HAZARD,    EventSubtype.DEBRIS),
    "obstacle":            (EventType.ROAD_HAZARD,    EventSubtype.OBSTACLE),

    # ── TRAFFIC ───────────────────────────────────────────────────────────────
    "vehicle":             (EventType.TRAFFIC,        EventSubtype.VEHICLE_PRESENCE),
    "car":                 (EventType.TRAFFIC,        EventSubtype.VEHICLE_PRESENCE),
    "bus":                 (EventType.TRAFFIC,        EventSubtype.VEHICLE_PRESENCE),
    "truck":               (EventType.TRAFFIC,        EventSubtype.VEHICLE_PRESENCE),
    "motorcycle":          (EventType.TRAFFIC,        EventSubtype.VEHICLE_PRESENCE),
    "bicycle":             (EventType.TRAFFIC,        EventSubtype.VEHICLE_PRESENCE),
    "traffic_jam":         (EventType.TRAFFIC,        EventSubtype.BOTTLENECK),
    "bottleneck":          (EventType.TRAFFIC,        EventSubtype.BOTTLENECK),

    # ── SAFETY ────────────────────────────────────────────────────────────────
    "person":              (EventType.SAFETY,         EventSubtype.VULNERABLE_PEDESTRIAN),
    "pedestrian":          (EventType.SAFETY,         EventSubtype.VULNERABLE_PEDESTRIAN),
    "child":               (EventType.SAFETY,         EventSubtype.VULNERABLE_PEDESTRIAN),
    "unsafe_crossing":     (EventType.SAFETY,         EventSubtype.UNSAFE_CROSSING),

    # ── INCIDENT ─────────────────────────────────────────────────────────────
    "rash_driving":        (EventType.INCIDENT,       EventSubtype.SUSPECTED_RASH_DRIVING),
    "hit_and_run":         (EventType.INCIDENT,       EventSubtype.SUSPECTED_HIT_AND_RUN),
}

# Classes that should NOT produce persistent events (supporting detections only)
_NON_EVENT_CLASSES: frozenset[str] = frozenset()


def classify_detection(class_name: str) -> Tuple[str, str]:
    """
    Maps a raw detector class name to (EventType, EventSubtype).

    Returns (EventType.ROAD_DAMAGE, EventSubtype.UNKNOWN) for unrecognised classes
    so the pipeline never silently drops unknown detections.

    Usage:
        event_type, event_subtype = classify_detection("pothole")
        # -> ("ROAD_DAMAGE", "POTHOLE")

        event_type, event_subtype = classify_detection("no_zebracrossing")
        # -> ("INFRASTRUCTURE", "MISSING_ZEBRA")
    """
    key = class_name.strip().lower()
    return _CLASS_MAP.get(key, (EventType.ROAD_DAMAGE, EventSubtype.UNKNOWN))


def is_fusable(class_name: str) -> bool:
    """
    Returns True when a detection should enter the fusion pipeline as an Observation/Event.
    Returns False for supporting detections (e.g., reference objects) that should NOT
    create persistent events but may inform other modules.

    Currently all mapped classes are fusable.  Add classes to _NON_EVENT_CLASSES if needed.
    """
    return class_name.strip().lower() not in _NON_EVENT_CLASSES


def get_all_mappings() -> dict[str, Tuple[str, str]]:
    """Returns the full class→taxonomy mapping for introspection / testing."""
    return dict(_CLASS_MAP)
