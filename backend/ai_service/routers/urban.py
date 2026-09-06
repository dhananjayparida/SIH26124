"""
Urban Intelligence Router: Grid-cell road health, maintenance queues, city HUD summary, and sensing coverage.
"""

from typing import List, Dict, Any
from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session
import time

from ..database import get_db, db_event_to_pydantic
from ..models import EventDB, VehicleDB
from ai_engine.urban_intelligence.grid_health import GridHealthEngine
from ai_engine.urban_intelligence.maintenance_queue import MaintenanceQueueManager
from .ingest import registry

router = APIRouter(prefix="", tags=["Urban Intelligence"])

grid_engine = GridHealthEngine(cell_size_degrees=0.004)

# Bhubaneswar Janpath bounding box for coverage grid
BBSR_BOUNDS = {
    "min_lat": 20.270, "max_lat": 20.320,
    "min_lon": 85.810, "max_lon": 85.840
}
COVERAGE_CELL_DEG = 0.004   # ~440m cells
COVERAGE_FRESH_SEC = 300    # observed < 5min = fresh
COVERAGE_STALE_SEC = 1800   # observed < 30min = stale, else dark


@router.get("/road-segments/health")
def get_road_health(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """Returns spatial grid cells with health score [0-100] and color-coded status."""
    db_events = db.query(EventDB).all()
    events = [db_event_to_pydantic(e) for e in db_events]
    return grid_engine.compute_grid_health(events)


@router.get("/maintenance/queue")
def get_maintenance_queue(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """Returns ranked actionable maintenance tasks."""
    db_events = db.query(EventDB).all()
    events = [db_event_to_pydantic(e) for e in db_events]
    return MaintenanceQueueManager.get_queue(events)


@router.get("/maintenance/export-csv")
def export_maintenance_csv(db: Session = Depends(get_db)):
    """Exports prioritized road defect list in CSV format."""
    db_events = db.query(EventDB).all()
    events = [db_event_to_pydantic(e) for e in db_events]
    csv_content = MaintenanceQueueManager.export_csv(events)
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=bhubaneswar_road_maintenance.csv"}
    )


@router.post("/maintenance/clear")
@router.delete("/maintenance/queue")
def clear_maintenance_queue(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Clears all active items in the municipal maintenance queue:
    - Marks all open events as RESOLVED
    - Clears the persistent defect ledger
    """
    from ai_engine.perception.defect_recorder import global_defect_ledger

    open_events = db.query(EventDB).filter(~EventDB.status.in_(["RESOLVED", "REJECTED"])).all()
    count = len(open_events)
    for ev in open_events:
        ev.status = "RESOLVED"
        ev.updated_at = time.time()
    db.commit()

    global_defect_ledger.clear()

    return {
        "status": "success",
        "message": f"Successfully cleared {count} defects from the maintenance queue.",
        "cleared_count": count
    }


@router.get("/coverage/cells")
def get_coverage_cells(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """
    Returns sensing coverage grid cells for the coverage freshness layer.
    Each cell describes when it was last traversed by a sensing vehicle.
    fresh  (<5min)  -> green
    stale  (<30min) -> amber
    dark   (>30min) -> grey/absent
    """
    now = time.time()
    registry.update_all_statuses()
    vehicles = db.query(VehicleDB).filter(
        VehicleDB.latest_lat.isnot(None),
        VehicleDB.latest_lon.isnot(None)
    ).all()

    # Build a map: cell_key -> most_recent_vehicle_time
    cell_freshness: Dict[str, float] = {}
    for v in vehicles:
        lat_idx = int((v.latest_lat - BBSR_BOUNDS["min_lat"]) / COVERAGE_CELL_DEG)
        lon_idx = int((v.latest_lon - BBSR_BOUNDS["min_lon"]) / COVERAGE_CELL_DEG)
        key = f"{lat_idx}_{lon_idx}"
        last = v.last_seen or 0
        if last > cell_freshness.get(key, 0):
            cell_freshness[key] = last

    cells = []
    lat = BBSR_BOUNDS["min_lat"]
    while lat < BBSR_BOUNDS["max_lat"]:
        lon = BBSR_BOUNDS["min_lon"]
        while lon < BBSR_BOUNDS["max_lon"]:
            lat_idx = int((lat - BBSR_BOUNDS["min_lat"]) / COVERAGE_CELL_DEG)
            lon_idx = int((lon - BBSR_BOUNDS["min_lon"]) / COVERAGE_CELL_DEG)
            key = f"{lat_idx}_{lon_idx}"
            last_seen = cell_freshness.get(key, 0)
            age = now - last_seen if last_seen > 0 else float("inf")

            if age < COVERAGE_FRESH_SEC:
                color = "#10b981"  # green - fresh
                opacity = 0.35
                label = "FRESH"
            elif age < COVERAGE_STALE_SEC:
                color = "#f59e0b"  # amber - stale
                opacity = 0.20
                label = "STALE"
            else:
                # Dark cells still returned but with very low opacity for blind-spot awareness
                color = "#475569"
                opacity = 0.08
                label = "DARK"

            cells.append({
                "bounds": [
                    [lat, lon],
                    [lat + COVERAGE_CELL_DEG, lon + COVERAGE_CELL_DEG]
                ],
                "color": color,
                "opacity": opacity,
                "label": label,
                "last_seen": last_seen,
                "age_seconds": round(age, 0) if age != float("inf") else None
            })
            lon += COVERAGE_CELL_DEG
        lat += COVERAGE_CELL_DEG

    return cells


@router.get("/hud/summary")
def get_hud_summary(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Provides high-level metrics for the command center HUD strip, including MODE."""
    registry.update_all_statuses()
    devices = registry.list_devices()
    live_count = sum(1 for d in devices if d.status == "LIVE")
    stale_count = sum(1 for d in devices if d.status == "STALE")
    replay_count = sum(1 for d in devices if d.status == "REPLAY")

    db_events = db.query(EventDB).all()
    open_events = [e for e in db_events if e.status not in ["RESOLVED", "REJECTED"]]
    high_priority = sum(1 for e in open_events if e.status == "HIGH_PRIORITY")
    corroborated = sum(1 for e in open_events if e.status == "CORROBORATED")
    candidates = sum(1 for e in open_events if e.status == "CANDIDATE")

    # Determine system MODE: if any LIVE phone exists it's LIVE; if only replay it's REPLAY
    if live_count > 0:
        mode = "LIVE"
    elif replay_count > 0:
        mode = "REPLAY"
    else:
        mode = "STANDBY"

    return {
        "active_vehicles": len(devices),
        "live_sources": live_count,
        "stale_sources": stale_count,
        "replay_sources": replay_count,
        "open_events": len(open_events),
        "high_priority_events": high_priority,
        "corroborated_events": corroborated,
        "candidate_events": candidates,
        "total_observations": sum(e.observation_count for e in db_events),
        "mode": mode
    }

