"""
Fleet Router: Monitor sensing vehicle nodes, live GPS positions, and device freshness.
"""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import time

from ..database import get_db
from ..models import VehicleDB
from .ingest import registry

router = APIRouter(prefix="/fleet", tags=["Fleet"])


@router.get("/status")
def get_fleet_status(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """Returns active sensing vehicles with truthful LIVE / STALE / OFFLINE / REPLAY source health."""
    registry.update_all_statuses()
    cached_devices = {d.device_id: d for d in registry.list_devices()}

    db_vehicles = db.query(VehicleDB).all()
    now = time.time()
    results = []

    for v in db_vehicles:
        rec = cached_devices.get(v.device_id)
        last_seen = rec.last_seen if rec else v.last_seen
        lat = rec.latest_lat if (rec and rec.latest_lat is not None) else v.latest_lat
        lon = rec.latest_lon if (rec and rec.latest_lon is not None) else v.latest_lon
        seconds_ago = round(now - last_seen, 1)

        # Compute truthful status from age, never trust stale in-memory flags
        source_type = v.source_type or "phone_pwa"
        if source_type == "replay":
            # Replay packets shown as REPLAY, not LIVE
            status = "REPLAY" if seconds_ago < 60 else "OFFLINE"
        elif seconds_ago > 60:
            status = "OFFLINE"
        elif seconds_ago > 15:
            status = "STALE"
        else:
            status = "LIVE"

        results.append({
            "device_id": v.device_id,
            "source_type": source_type,
            "latitude": lat,
            "longitude": lon,
            "speed": rec.latest_speed if rec else v.latest_speed,
            "heading": rec.latest_heading if rec else v.latest_heading,
            "status": status,
            "last_seen": last_seen,
            "seconds_since_seen": seconds_ago,
            "packets_sent": rec.packets_sent if rec else 0,
            "detections_reported": rec.detections_reported if rec else 0
        })

    return results



@router.post("/heartbeat")
def record_heartbeat(
    payload: Dict[str, Any],
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Lightweight 5s ping from edge sensing nodes."""
    device_id = payload.get("device_id")
    if not device_id:
        return {"status": "error", "message": "device_id required"}

    rec = registry.record_activity(
        device_id=device_id,
        lat=payload.get("latitude"),
        lon=payload.get("longitude"),
        speed=payload.get("speed"),
        heading=payload.get("heading"),
        is_detection=False
    )

    db_veh = db.query(VehicleDB).filter(VehicleDB.device_id == device_id).first()
    if not db_veh:
        from uuid import uuid4
        db_veh = VehicleDB(
            id=str(uuid4()),
            device_id=device_id,
            source_type=payload.get("source_type", "phone_pwa"),
            registered_at=rec.last_seen,
            last_seen=rec.last_seen,
            latest_lat=rec.latest_lat or 20.2961,
            latest_lon=rec.latest_lon or 85.8245,
            latest_speed=rec.latest_speed or 0.0,
            latest_heading=rec.latest_heading or 0.0,
            status="LIVE"
        )
        db.add(db_veh)
    else:
        db_veh.last_seen = rec.last_seen
        db_veh.latest_lat = rec.latest_lat
        db_veh.latest_lon = rec.latest_lon
        db_veh.status = "LIVE"
    db.commit()

    return {"status": "ok", "device_id": device_id, "node_status": rec.status}
