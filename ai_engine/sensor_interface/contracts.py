"""
Core data contracts and Pydantic schemas for the Urban Intelligence Platform.
Defines standardized formats for GPS readings, raw sensor packets, observations, and fused events.

Event Taxonomy (master context §10):
  EventType  : ROAD_DAMAGE | INFRASTRUCTURE | WATERLOGGING | ROAD_HAZARD | TRAFFIC | SAFETY | INCIDENT
  EventSubtype: per-domain subtypes (see EventSubtype below)
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from uuid import uuid4
from pydantic import BaseModel, Field, field_validator


# ─── Urban Intelligence Event Taxonomy ───────────────────────────────────────

class EventType:
    """Top-level intelligence domain identifiers (master context §10)."""
    ROAD_DAMAGE    = "ROAD_DAMAGE"      # potholes, cracks, surface damage
    INFRASTRUCTURE = "INFRASTRUCTURE"   # missing zebra, dividers, signboards
    WATERLOGGING   = "WATERLOGGING"     # road waterlogging / flooding
    ROAD_HAZARD    = "ROAD_HAZARD"      # debris, obstacles
    TRAFFIC        = "TRAFFIC"          # vehicle density, bottlenecks, flow
    SAFETY         = "SAFETY"           # pedestrian risk, vulnerable users
    INCIDENT       = "INCIDENT"         # suspected rash-driving, hit-and-run


class EventSubtype:
    """Per-domain subtypes — add new subtypes here; do NOT duplicate into ingest logic."""
    # ROAD_DAMAGE
    POTHOLE            = "POTHOLE"
    LONGITUDINAL_CRACK = "LONGITUDINAL_CRACK"
    TRANSVERSE_CRACK   = "TRANSVERSE_CRACK"
    ALLIGATOR_CRACK    = "ALLIGATOR_CRACK"
    DAMAGED_ROAD       = "DAMAGED_ROAD"
    # INFRASTRUCTURE
    MISSING_ZEBRA      = "MISSING_ZEBRA"
    ZEBRA_CROSSING     = "ZEBRA_CROSSING"
    MISSING_DIVIDER    = "MISSING_DIVIDER"
    DAMAGED_SIGNBOARD  = "DAMAGED_SIGNBOARD"
    # WATERLOGGING
    ROAD_WATERLOGGING  = "ROAD_WATERLOGGING"
    # ROAD_HAZARD
    DEBRIS             = "DEBRIS"
    OBSTACLE           = "OBSTACLE"
    # TRAFFIC
    VEHICLE_PRESENCE   = "VEHICLE_PRESENCE"
    VEHICLE_DENSITY    = "VEHICLE_DENSITY"
    BOTTLENECK         = "BOTTLENECK"
    # SAFETY
    VULNERABLE_PEDESTRIAN = "VULNERABLE_PEDESTRIAN"
    UNSAFE_CROSSING       = "UNSAFE_CROSSING"
    # INCIDENT
    SUSPECTED_RASH_DRIVING = "SUSPECTED_RASH_DRIVING"
    SUSPECTED_HIT_AND_RUN  = "SUSPECTED_HIT_AND_RUN"
    # Fallback
    UNKNOWN            = "UNKNOWN"


class GPSReading(BaseModel):
    """Normalized GPS fix from any source (mobile phone, replay, AVL)."""
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Latitude in decimal degrees WGS84")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Longitude in decimal degrees WGS84")
    altitude: Optional[float] = Field(default=None, description="Altitude in meters above sea level")
    speed: Optional[float] = Field(default=None, ge=0.0, description="Speed in km/h or m/s")
    heading: Optional[float] = Field(default=None, ge=0.0, le=360.0, description="Compass bearing (0-360)")
    accuracy: Optional[float] = Field(default=None, ge=0.0, description="Horizontal accuracy in meters")
    timestamp: float = Field(default_factory=lambda: datetime.now(timezone.utc).timestamp())

    @field_validator("latitude")
    @classmethod
    def validate_latitude(cls, v: float) -> float:
        if abs(v) > 90.0:
            raise ValueError(f"Latitude out of bounds: {v}")
        return v

    @field_validator("longitude")
    @classmethod
    def validate_longitude(cls, v: float) -> float:
        if abs(v) > 180.0:
            raise ValueError(f"Longitude out of bounds: {v}")
        return v


class SourceMetadata(BaseModel):
    """Metadata regarding the capturing hardware node."""
    device_id: str
    source_type: str = Field(default="phone_pwa", description="phone_pwa | replay | rtsp | sim")
    route_id: Optional[str] = "Janpath-Route-1"
    target_fps: float = 2.5
    user_agent: Optional[str] = None


class SensorPacket(BaseModel):
    """Unified container for an ingested visual frame and synchronized GPS fix."""
    packet_id: str = Field(default_factory=lambda: str(uuid4()))
    device_id: str
    frame_timestamp: float = Field(default_factory=lambda: datetime.now(timezone.utc).timestamp())
    gps: GPSReading
    is_stale_gps: bool = False
    frame_base64: Optional[str] = Field(default=None, description="JPEG image as base64 string")
    frame_path: Optional[str] = Field(default=None, description="Path to on-disk frame if saved")
    extra_metadata: Dict[str, Any] = Field(default_factory=dict)


class BoundingBox(BaseModel):
    """Bounding box detection coordinates [x, y, w, h] normalized or pixel."""
    x: float
    y: float
    width: float
    height: float


class Detection(BaseModel):
    """Single raw perception output from the detector (class-name is model-native)."""
    class_name: str = Field(..., description="Raw model class: pothole | no_zebracrossing | vehicle | car | ...")
    confidence: float = Field(..., ge=0.0, le=1.0)
    bbox: BoundingBox
    model_version: str = "dfine-s"


class DetectionResult(BaseModel):
    """Result of perception inference on a single SensorPacket."""
    packet_id: str
    device_id: str
    timestamp: float
    gps: GPSReading
    detections: List[Detection] = Field(default_factory=list)
    inference_time_ms: float = 0.0


class Observation(BaseModel):
    """
    Single geolocated, timestamped observation from a specific vehicle.
    Produced by an intelligence module after perception inference.
    `observation_type` is the canonical domain-aware type from ObservationClassifier.
    `defect_type` is preserved for backward compatibility with existing DB rows.
    """
    observation_id: str = Field(default_factory=lambda: str(uuid4()))
    device_id: str
    packet_id: str
    timestamp: float
    latitude: float
    longitude: float
    # Canonical taxonomy fields (set by ObservationClassifier)
    observation_type: str = Field(default="ROAD_DAMAGE",  description="EventType domain string")
    observation_subtype: str = Field(default="POTHOLE", description="EventSubtype string")
    # Legacy alias — kept for DB backward compat (mirrors observation_subtype)
    defect_type: str = "POTHOLE"
    model_confidence: float = Field(..., ge=0.0, le=1.0)
    bbox: Optional[BoundingBox] = None
    snapshot_path: Optional[str] = None
    event_id: Optional[str] = None


class Event(BaseModel):
    """
    Fused Urban Event — the core persistent output of the Urban Intelligence platform.
    Formed by merging multi-source observations from independent vehicles over space and time.

    `type`    = EventType domain  (e.g. ROAD_DAMAGE, TRAFFIC, SAFETY)
    `subtype` = EventSubtype      (e.g. POTHOLE, BOTTLENECK, VULNERABLE_PEDESTRIAN)
    """
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    type: str = Field(default=EventType.ROAD_DAMAGE, description="EventType domain")
    subtype: str = Field(default=EventSubtype.POTHOLE, description="EventSubtype")
    latitude: float
    longitude: float
    status: str = "CANDIDATE"  # CANDIDATE | CORROBORATED | HIGH_PRIORITY | REPAIR_REPORTED | NEEDS_VERIFICATION | RESOLVED | REJECTED
    severity: str = "MEDIUM"   # LOW | MEDIUM | HIGH
    model_confidence: float = 0.5
    event_confidence: float = 0.5
    unique_sources: int = 1
    observation_count: int = 1
    source_vehicle_ids: List[str] = Field(default_factory=list)
    evidence_uris: List[str] = Field(default_factory=list)
    road_segment_id: Optional[str] = None
    priority_score: float = 0.0
    created_at: float = Field(default_factory=lambda: datetime.now(timezone.utc).timestamp())
    updated_at: float = Field(default_factory=lambda: datetime.now(timezone.utc).timestamp())
    observations: List[Observation] = Field(default_factory=list)
