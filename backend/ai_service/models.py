"""
SQLAlchemy database models for the Urban Intelligence Platform.
Compatible with SQLite (default) and PostgreSQL / PostGIS.
"""

import time
from sqlalchemy import (
    Column,
    String,
    Float,
    Integer,
    Boolean,
    Text,
    ForeignKey,
    JSON,
    DateTime,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class VehicleDB(Base):
    __tablename__ = "vehicles"

    id = Column(String(64), primary_key=True)
    device_id = Column(String(64), unique=True, index=True, nullable=False)
    source_type = Column(String(32), default="phone_pwa")
    registered_at = Column(Float, default=time.time)
    last_seen = Column(Float, default=time.time)
    latest_lat = Column(Float, nullable=True)
    latest_lon = Column(Float, nullable=True)
    latest_speed = Column(Float, nullable=True)
    latest_heading = Column(Float, nullable=True)
    status = Column(String(16), default="LIVE")  # LIVE | STALE | OFFLINE


class EventDB(Base):
    __tablename__ = "events"

    id = Column(String(64), primary_key=True)
    type = Column(String(32), default="road_defect", index=True)
    subtype = Column(String(32), default="pothole", index=True)
    latitude = Column(Float, nullable=False, index=True)
    longitude = Column(Float, nullable=False, index=True)
    status = Column(String(32), default="CANDIDATE", index=True)
    severity = Column(String(16), default="MEDIUM")
    model_confidence = Column(Float, default=0.5)
    event_confidence = Column(Float, default=0.5)
    unique_sources = Column(Integer, default=1)
    observation_count = Column(Integer, default=1)
    source_vehicle_ids = Column(JSON, default=list)
    evidence_uris = Column(JSON, default=list)
    road_segment_id = Column(String(64), nullable=True)
    priority_score = Column(Float, default=0.0)
    created_at = Column(Float, default=time.time)
    updated_at = Column(Float, default=time.time, index=True)

    observations = relationship("ObservationDB", back_populates="event", cascade="all, delete-orphan")


class ObservationDB(Base):
    __tablename__ = "observations"

    id = Column(String(64), primary_key=True)
    event_id = Column(String(64), ForeignKey("events.id"), nullable=True, index=True)
    device_id = Column(String(64), nullable=False, index=True)
    packet_id = Column(String(64), nullable=False)
    timestamp = Column(Float, default=time.time, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    defect_type = Column(String(32), default="pothole")
    model_confidence = Column(Float, default=0.5)
    bbox = Column(JSON, nullable=True)
    snapshot_path = Column(String(256), nullable=True)

    event = relationship("EventDB", back_populates="observations")


class RepairDB(Base):
    __tablename__ = "repairs"

    id = Column(String(64), primary_key=True)
    event_id = Column(String(64), ForeignKey("events.id"), nullable=False, index=True)
    reported_at = Column(Float, default=time.time)
    reported_by = Column(String(64), default="authority")
    status = Column(String(32), default="REPAIR_REPORTED")
    notes = Column(Text, nullable=True)
    resolved_at = Column(Float, nullable=True)
