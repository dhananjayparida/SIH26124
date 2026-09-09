"""
SQLite database session management and repository operations.
"""

import os
from pathlib import Path
from typing import List, Optional
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, Session
from .models import Base, VehicleDB, EventDB, ObservationDB, RepairDB
from ai_engine.sensor_interface.contracts import Event, Observation

# Use DATABASE_URL when explicitly provided; the application default is local SQLite.
DB_DIR = Path("data")
DB_DIR.mkdir(parents=True, exist_ok=True)
SQLITE_PATH = DB_DIR / "urban_intel.db"

DEFAULT_DB_URL = f"sqlite:///{SQLITE_PATH.absolute()}"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DB_URL)

connect_args = {"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initializes tables and applies additive SQLite observation columns."""
    Base.metadata.create_all(bind=engine)
    if engine.dialect.name == "sqlite":
        existing = {column["name"] for column in inspect(engine).get_columns("observations")}
        additions = {
            "model_name": "VARCHAR(64)",
            "model_version": "VARCHAR(128)",
            "source_type": "VARCHAR(32)",
            "evidence_status": "VARCHAR(32) DEFAULT 'MISSING'",
        }
        with engine.begin() as connection:
            for name, definition in additions.items():
                if name not in existing:
                    connection.execute(text(f"ALTER TABLE observations ADD COLUMN {name} {definition}"))

# Auto-initialize tables
init_db()


def get_db():
    """FastAPI dependency for database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def db_event_to_pydantic(db_ev: EventDB) -> Event:
    """Converts SQLAlchemy EventDB to Pydantic Event schema."""
    obs_list = []
    if db_ev.observations:
        for o in db_ev.observations:
            obs_list.append(Observation(
                observation_id=o.id,
                device_id=o.device_id,
                packet_id=o.packet_id,
                timestamp=o.timestamp,
                latitude=o.latitude,
                longitude=o.longitude,
                defect_type=o.defect_type,
                model_confidence=o.model_confidence,
                bbox=o.bbox,
                snapshot_path=o.snapshot_path,
                model_name=o.model_name,
                model_version=o.model_version,
                source_type=o.source_type,
                evidence_status=o.evidence_status or "MISSING",
                event_id=o.event_id
            ))

    return Event(
        event_id=db_ev.id,
        type=db_ev.type,
        subtype=db_ev.subtype,
        latitude=db_ev.latitude,
        longitude=db_ev.longitude,
        status=db_ev.status,
        severity=db_ev.severity,
        model_confidence=db_ev.model_confidence,
        event_confidence=db_ev.event_confidence,
        unique_sources=db_ev.unique_sources,
        observation_count=db_ev.observation_count,
        source_vehicle_ids=db_ev.source_vehicle_ids or [],
        evidence_uris=db_ev.evidence_uris or [],
        road_segment_id=db_ev.road_segment_id,
        priority_score=db_ev.priority_score,
        created_at=db_ev.created_at,
        updated_at=db_ev.updated_at,
        observations=obs_list
    )


def save_pydantic_event(db: Session, event: Event) -> EventDB:
    """Persists or updates an event and its observations in SQL."""
    db_ev = db.query(EventDB).filter(EventDB.id == event.event_id).first()
    if not db_ev:
        db_ev = EventDB(
            id=event.event_id,
            type=event.type,
            subtype=event.subtype,
            latitude=event.latitude,
            longitude=event.longitude,
            status=event.status,
            severity=event.severity,
            model_confidence=event.model_confidence,
            event_confidence=event.event_confidence,
            unique_sources=event.unique_sources,
            observation_count=event.observation_count,
            source_vehicle_ids=event.source_vehicle_ids,
            evidence_uris=event.evidence_uris,
            road_segment_id=event.road_segment_id,
            priority_score=event.priority_score,
            created_at=event.created_at,
            updated_at=event.updated_at,
        )
        db.add(db_ev)
    else:
        db_ev.latitude = event.latitude
        db_ev.longitude = event.longitude
        db_ev.status = event.status
        db_ev.severity = event.severity
        db_ev.model_confidence = event.model_confidence
        db_ev.event_confidence = event.event_confidence
        db_ev.unique_sources = event.unique_sources
        db_ev.observation_count = event.observation_count
        db_ev.source_vehicle_ids = event.source_vehicle_ids
        db_ev.evidence_uris = event.evidence_uris
        db_ev.priority_score = event.priority_score
        db_ev.updated_at = event.updated_at

    # Add any missing observations
    existing_obs_ids = set(o.id for o in db.query(ObservationDB.id).filter(ObservationDB.event_id == event.event_id).all())
    for obs in event.observations:
        if obs.observation_id not in existing_obs_ids:
            db_obs = ObservationDB(
                id=obs.observation_id,
                event_id=event.event_id,
                device_id=obs.device_id,
                packet_id=obs.packet_id,
                timestamp=obs.timestamp,
                latitude=obs.latitude,
                longitude=obs.longitude,
                defect_type=obs.defect_type,
                model_confidence=obs.model_confidence,
                bbox=obs.bbox.model_dump() if obs.bbox else None,
                snapshot_path=obs.snapshot_path,
                model_name=obs.model_name,
                model_version=obs.model_version,
                source_type=obs.source_type,
                evidence_status=obs.evidence_status,
            )
            db.add(db_obs)

    db.commit()
    db.refresh(db_ev)
    return db_ev
