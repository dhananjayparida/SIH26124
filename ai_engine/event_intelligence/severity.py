"""
Severity assessment rules (AI-06) — multi-domain.

Computes 3-tier severity (LOW, MEDIUM, HIGH) based on:
  - Event domain (EventType)
  - Event subtype
  - Model confidence
  - Bounding box area proxy (road damage only)

Master context §9: Each intelligence domain has distinct severity semantics.
"""

from typing import Optional
from ..sensor_interface.contracts import BoundingBox, EventType, EventSubtype


def assess_event_severity(
    event_type: str,
    event_subtype: str,
    confidence: float,
    bbox: Optional[BoundingBox] = None,
    image_width: int = 640,
    image_height: int = 480,
) -> str:
    """
    Domain-aware 3-tier severity classifier.

    Domain rules (master context §9):
      ROAD_DAMAGE   — bbox area + confidence proxy
      INFRASTRUCTURE — HIGH when missing safety markings (zebra)
      WATERLOGGING   — MEDIUM baseline, HIGH if high confidence
      ROAD_HAZARD    — MEDIUM / HIGH
      TRAFFIC        — LOW / MEDIUM (informational, not urgent)
      SAFETY         — HIGH (vulnerable users present)
      INCIDENT       — HIGH (authority escalation needed)
    """
    t = event_type.upper()
    s = event_subtype.upper()

    # ── INCIDENT: always HIGH — suspected criminal/reckless behaviour ─────────
    if t == EventType.INCIDENT:
        return "HIGH"

    # ── SAFETY: always HIGH — vulnerable person in road environment ───────────
    if t == EventType.SAFETY:
        return "HIGH"

    # ── INFRASTRUCTURE ────────────────────────────────────────────────────────
    if t == EventType.INFRASTRUCTURE:
        if s in (EventSubtype.MISSING_ZEBRA,):
            return "HIGH" if confidence >= 0.70 else "MEDIUM"
        if s == EventSubtype.ZEBRA_CROSSING:
            return "LOW"          # zebra present — informational
        return "MEDIUM"           # divider / signboard damage

    # ── WATERLOGGING ──────────────────────────────────────────────────────────
    if t == EventType.WATERLOGGING:
        return "HIGH" if confidence >= 0.75 else "MEDIUM"

    # ── ROAD_HAZARD ───────────────────────────────────────────────────────────
    if t == EventType.ROAD_HAZARD:
        return "HIGH" if confidence >= 0.80 else "MEDIUM"

    # ── TRAFFIC ───────────────────────────────────────────────────────────────
    if t == EventType.TRAFFIC:
        if s == EventSubtype.BOTTLENECK:
            return "MEDIUM"
        return "LOW"          # routine vehicle presence — informational

    # ── ROAD_DAMAGE: bbox area + confidence heuristic ─────────────────────────
    if bbox is None:
        return "MEDIUM"

    if bbox.width > 1.0 or bbox.height > 1.0:
        area_ratio = (bbox.width * bbox.height) / float(image_width * image_height)
    else:
        area_ratio = bbox.width * bbox.height

    if area_ratio >= 0.08 or (area_ratio >= 0.05 and confidence >= 0.80):
        return "HIGH"
    elif area_ratio >= 0.025 or confidence >= 0.70:
        return "MEDIUM"
    else:
        return "LOW"


# ─── Backward-compat alias used by existing callers in ingest.py ──────────────
def assess_defect_severity(
    class_name: str,
    confidence: float,
    bbox: Optional[BoundingBox] = None,
    image_width: int = 640,
    image_height: int = 480,
) -> str:
    """
    Legacy shim: maps raw class_name through ObservationClassifier and delegates
    to assess_event_severity. Existing callers continue to work unchanged.
    """
    from ..specialized.observation_classifier import classify_detection
    ev_type, ev_subtype = classify_detection(class_name)
    return assess_event_severity(ev_type, ev_subtype, confidence, bbox, image_width, image_height)

