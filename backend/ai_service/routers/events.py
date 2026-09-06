"""
Events Router: Query and manage fused urban defect events.
Implements Urban Memory timeline and municipal maintenance workflows.
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from uuid import uuid4
import time

from ..database import get_db, db_event_to_pydantic, save_pydantic_event
from ..models import EventDB, RepairDB
from ai_engine.event_intelligence.state_machine import EventStateMachine, InvalidStateTransitionError

router = APIRouter(prefix="/events", tags=["Events"])


@router.get("")
def list_events(
    status: Optional[str] = None,
    type: Optional[str] = None,
    min_sources: Optional[int] = None,
    bbox: Optional[str] = None,  # "min_lat,min_lon,max_lat,max_lon"
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """Lists fused events with spatial and status filtering."""
    query = db.query(EventDB)

    if status:
        query = query.filter(EventDB.status == status)
    if type:
        query = query.filter(EventDB.subtype == type)
    if min_sources:
        query = query.filter(EventDB.unique_sources >= min_sources)

    if bbox:
        try:
            min_lat, min_lon, max_lat, max_lon = map(float, bbox.split(","))
            query = query.filter(
                EventDB.latitude >= min_lat,
                EventDB.latitude <= max_lat,
                EventDB.longitude >= min_lon,
                EventDB.longitude <= max_lon
            )
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid bbox format. Use min_lat,min_lon,max_lat,max_lon")

    db_events = query.order_by(EventDB.updated_at.desc()).all()
    results = []
    for ev in db_events:
        results.append({
            "event_id": ev.id,
            "type": ev.type,
            "subtype": ev.subtype,
            "latitude": ev.latitude,
            "longitude": ev.longitude,
            "status": ev.status,
            "severity": ev.severity,
            "model_confidence": ev.model_confidence,
            "event_confidence": ev.event_confidence,
            "unique_sources": ev.unique_sources,
            "observation_count": ev.observation_count,
            "source_vehicle_ids": ev.source_vehicle_ids,
            "evidence_uris": ev.evidence_uris,
            "priority_score": ev.priority_score,
            "created_at": ev.created_at,
            "updated_at": ev.updated_at
        })
    return results


@router.get("/{event_id}")
def get_event_detail(event_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Returns full event profile including Urban Memory:
    complete chronological trail of all contributing vehicle observations.
    """
    db_ev = db.query(EventDB).filter(EventDB.id == event_id).first()
    if not db_ev:
        raise HTTPException(status_code=404, detail="Event not found")

    event = db_event_to_pydantic(db_ev)

    # Sort observations chronologically for Urban Memory timeline
    sorted_obs = sorted(event.observations, key=lambda x: x.timestamp)
    timeline = []
    for obs in sorted_obs:
        timeline.append({
            "observation_id": obs.observation_id,
            "device_id": obs.device_id,
            "timestamp": obs.timestamp,
            "latitude": obs.latitude,
            "longitude": obs.longitude,
            "model_confidence": obs.model_confidence,
            "snapshot_path": obs.snapshot_path
        })

    # Fetch repairs log
    repairs = db.query(RepairDB).filter(RepairDB.event_id == event_id).order_by(RepairDB.reported_at.desc()).all()
    repair_history = [
        {
            "id": r.id,
            "reported_at": r.reported_at,
            "reported_by": r.reported_by,
            "status": r.status,
            "notes": r.notes,
            "resolved_at": r.resolved_at
        }
        for r in repairs
    ]

    return {
        "event_id": event.event_id,
        "type": event.type,
        "subtype": event.subtype,
        "latitude": event.latitude,
        "longitude": event.longitude,
        "status": event.status,
        "severity": event.severity,
        "model_confidence": event.model_confidence,
        "event_confidence": event.event_confidence,
        "unique_sources": event.unique_sources,
        "observation_count": event.observation_count,
        "source_vehicle_ids": event.source_vehicle_ids,
        "evidence_uris": event.evidence_uris,
        "priority_score": event.priority_score,
        "created_at": event.created_at,
        "updated_at": event.updated_at,
        "urban_memory_timeline": timeline,
        "repair_history": repair_history
    }


@router.post("/{event_id}/repair-report")
def report_repair(
    event_id: str,
    payload: Optional[Dict[str, Any]] = None,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Municipal authority marks a repair order issued."""
    db_ev = db.query(EventDB).filter(EventDB.id == event_id).first()
    if not db_ev:
        raise HTTPException(status_code=404, detail="Event not found")

    event = db_event_to_pydantic(db_ev)
    authority = (payload or {}).get("authority", "BMC-Road-Division-4")
    notes = (payload or {}).get("notes", "Repair crew scheduled")

    try:
        EventStateMachine.mark_repair_reported(event, authority_name=authority)
    except InvalidStateTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))

    save_pydantic_event(db, event)

    # Log repair record
    repair = RepairDB(
        id=str(uuid4()),
        event_id=event_id,
        reported_at=time.time(),
        reported_by=authority,
        status="REPAIR_REPORTED",
        notes=notes
    )
    db.add(repair)
    db.commit()

    return {"status": "success", "event_status": event.status, "event_id": event_id}


@router.post("/{event_id}/resolve")
def resolve_event(
    event_id: str,
    payload: Optional[Dict[str, Any]] = None,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Authority marks defect as resolved and verified."""
    db_ev = db.query(EventDB).filter(EventDB.id == event_id).first()
    if not db_ev:
        raise HTTPException(status_code=404, detail="Event not found")

    event = db_event_to_pydantic(db_ev)
    authority = (payload or {}).get("authority", "BMC-Inspector")

    try:
        EventStateMachine.mark_resolved(event, authority_name=authority)
    except InvalidStateTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))

    save_pydantic_event(db, event)

    # Update latest repair
    latest_repair = db.query(RepairDB).filter(RepairDB.event_id == event_id).order_by(RepairDB.reported_at.desc()).first()
    if latest_repair:
        latest_repair.status = "RESOLVED"
        latest_repair.resolved_at = time.time()
        db.commit()

    return {"status": "success", "event_status": event.status, "event_id": event_id}
