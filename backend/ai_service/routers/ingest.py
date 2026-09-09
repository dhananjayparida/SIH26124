"""
Ingestion Router: Entry point for visual frames and GPS telemetry.
Runs AI-02 Perception, AI-05 Spatio-Temporal Fusion, and updates DB.
"""

from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import uuid4

from ..database import get_db, save_pydantic_event, db_event_to_pydantic
from ..models import EventDB, VehicleDB
from ai_engine.sensor_interface.contracts import SensorPacket, Observation, Event
from ai_engine.sensor_interface.device_registry import DeviceRegistry
from ai_engine.perception.service import ConfiguredPerceptionDetector
from ai_engine.fusion.engine import SpatioTemporalFusionEngine
from ai_engine.fusion.spatial_index import bounding_box_for_radius
from ai_engine.event_intelligence.severity import assess_event_severity
from ai_engine.event_intelligence.evidence import EvidenceManager
from ai_engine.urban_intelligence.priority import calculate_priority_score
from ai_engine.specialized.observation_classifier import classify_detection, is_fusable
from ai_engine.specialized.traffic_intelligence import global_traffic_intelligence

router = APIRouter(prefix="/ingest", tags=["Ingest"])

# Shared engine instances
detector = ConfiguredPerceptionDetector()
fusion_engine = SpatioTemporalFusionEngine(spatial_radius_meters=25.0)
evidence_manager = EvidenceManager(storage_dir="data/evidence")
registry = DeviceRegistry()


@router.post("/packet")
async def ingest_packet(packet: SensorPacket, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Ingests a single SensorPacket from phone PWA, replay engine, or edge device.
    1. Records vehicle telemetry in registry & database.
    2. Runs AI-02 defect perception detector.
    3. Fuses detections against existing events using AI-05 Spatio-Temporal fusion.
    """
    # 1. Update device status
    registry.record_activity(
        device_id=packet.device_id,
        lat=packet.gps.latitude,
        lon=packet.gps.longitude,
        speed=packet.gps.speed,
        heading=packet.gps.heading,
        source_type=packet.extra_metadata.get("source_type", "phone_pwa"),
        is_detection=False
    )

    # Sync vehicle record in DB
    db_veh = db.query(VehicleDB).filter(VehicleDB.device_id == packet.device_id).first()
    if not db_veh:
        db_veh = VehicleDB(
            id=str(uuid4()),
            device_id=packet.device_id,
            source_type=packet.extra_metadata.get("source_type", "phone_pwa"),
            registered_at=packet.frame_timestamp,
            last_seen=packet.frame_timestamp,
            latest_lat=packet.gps.latitude,
            latest_lon=packet.gps.longitude,
            latest_speed=packet.gps.speed,
            latest_heading=packet.gps.heading,
            status="LIVE"
        )
        db.add(db_veh)
    else:
        db_veh.source_type = packet.extra_metadata.get("source_type", db_veh.source_type)
        db_veh.last_seen = packet.frame_timestamp
        db_veh.latest_lat = packet.gps.latitude
        db_veh.latest_lon = packet.gps.longitude
        db_veh.latest_speed = packet.gps.speed
        db_veh.latest_heading = packet.gps.heading
        db_veh.status = "LIVE"
    db.commit()

    # 2. Run perception inference
    detection_res = detector.detect(packet)
    fused_results = []
    detector_metadata = getattr(detector, "metadata", {})
    source_type = packet.extra_metadata.get("source_type", "phone_pwa")

    # Auto-save video frame and dataset sample
    if packet.frame_base64:
        try:
            from ai_engine.perception.video_recorder import global_video_recorder
            dets_dict = [d.dict() if hasattr(d, "dict") else d.model_dump() for d in detection_res.detections]
            gps_dict = packet.gps.dict() if hasattr(packet.gps, "dict") else packet.gps.model_dump()
            global_video_recorder.ingest_frame(
                device_id=packet.device_id,
                frame_base64=packet.frame_base64,
                gps=gps_dict,
                detections=dets_dict
            )
        except Exception as e:
            pass

    if detection_res.detections:
        registry.record_activity(device_id=packet.device_id, is_detection=True)

        for det in detection_res.detections:
            # ── Classify into domain taxonomy ─────────────────────────────────
            ev_type, ev_subtype = classify_detection(det.class_name)

            # Skip classes marked as non-fusable (e.g. reference objects)
            if not is_fusable(det.class_name):
                continue

            obs_id = str(uuid4())
            obs = Observation(
                observation_id=obs_id,
                device_id=packet.device_id,
                packet_id=packet.packet_id,
                timestamp=packet.frame_timestamp,
                latitude=packet.gps.latitude,
                longitude=packet.gps.longitude,
                observation_type=ev_type,
                observation_subtype=ev_subtype,
                defect_type=ev_subtype,   # legacy alias
                model_confidence=det.confidence,
                bbox=det.bbox,
                model_name=detector_metadata.get("model_name"),
                model_version=det.model_version or detector_metadata.get("model_version"),
                source_type=source_type,
                evidence_status="MISSING",
            )

            # Evidence is selected independently of fusion.  Defaults preserve
            # current capture-on-detection behavior; configured throttling only
            # suppresses redundant same-device evidence writes.
            if packet.frame_base64 and evidence_manager.should_capture(
                packet.device_id, det.class_name, det.confidence, packet.frame_timestamp
            ):
                snapshot_uri = evidence_manager.save_base64_snapshot(
                    base64_str=packet.frame_base64,
                    event_id="pending",
                    observation_id=obs_id,
                    bbox=det.bbox,
                    defect_type=det.class_name,
                    confidence=det.confidence
                )
                obs.snapshot_path = snapshot_uri
                obs.evidence_status = "AVAILABLE" if snapshot_uri else "MISSING"
            elif packet.frame_base64:
                obs.evidence_status = "NOT_CAPTURED_POLICY"

            # Spatial pre-filtering query: candidate events within search radius
            min_lat, max_lat, min_lon, max_lon = bounding_box_for_radius(
                obs.latitude, obs.longitude, radius_meters=fusion_engine.spatial_radius_meters * 1.5
            )

            candidate_rows = db.query(EventDB).filter(
                EventDB.latitude >= min_lat,
                EventDB.latitude <= max_lat,
                EventDB.longitude >= min_lon,
                EventDB.longitude <= max_lon,
                EventDB.status != "RESOLVED"
            ).all()

            candidate_events = [db_event_to_pydantic(row) for row in candidate_rows]

            # Fuse observation
            fused_event, is_new = fusion_engine.fuse_observation(obs, candidate_events)

            # Set taxonomy on newly created events
            if is_new:
                fused_event.type = ev_type
                fused_event.subtype = ev_subtype

            # Domain-aware severity
            fused_event.severity = assess_event_severity(
                event_type=ev_type,
                event_subtype=ev_subtype,
                confidence=det.confidence,
                bbox=det.bbox
            )

            # Re-evaluate priority score
            fused_event.priority_score = calculate_priority_score(fused_event)

            # Persist to database
            save_pydantic_event(db, fused_event)

            fused_results.append({
                "event_id": fused_event.event_id,
                "status": fused_event.status,
                "unique_sources": fused_event.unique_sources,
                "observation_count": fused_event.observation_count,
                "confidence": fused_event.event_confidence,
                "severity": fused_event.severity,
                "is_new": is_new
            })

    # ── Traffic Intelligence Pass (feature-flagged) ────────────────────────────
    traffic_obs_list = global_traffic_intelligence.process(detection_res)
    for t_obs in traffic_obs_list:
        t_obs.source_type = source_type
        t_obs.model_name = detector_metadata.get("model_name")
        t_obs.model_version = detector_metadata.get("model_version")
        t_obs.evidence_status = "MISSING"
        ev_type = t_obs.observation_type
        ev_subtype = t_obs.observation_subtype
        min_lat2, max_lat2, min_lon2, max_lon2 = bounding_box_for_radius(
            t_obs.latitude, t_obs.longitude, radius_meters=fusion_engine.spatial_radius_meters * 1.5
        )
        candidate_rows2 = db.query(EventDB).filter(
            EventDB.latitude >= min_lat2, EventDB.latitude <= max_lat2,
            EventDB.longitude >= min_lon2, EventDB.longitude <= max_lon2,
            EventDB.status != "RESOLVED"
        ).all()
        candidate_events2 = [db_event_to_pydantic(row) for row in candidate_rows2]
        t_event, t_is_new = fusion_engine.fuse_observation(t_obs, candidate_events2)
        if t_is_new:
            t_event.type = ev_type
            t_event.subtype = ev_subtype
        t_event.severity = assess_event_severity(ev_type, ev_subtype, t_obs.model_confidence)
        t_event.priority_score = calculate_priority_score(t_event)
        save_pydantic_event(db, t_event)
        if t_is_new:
            fused_results.append({
                "event_id": t_event.event_id,
                "status": t_event.status,
                "type": ev_type,
                "subtype": ev_subtype,
                "unique_sources": t_event.unique_sources,
                "observation_count": t_event.observation_count,
                "confidence": t_event.event_confidence,
                "severity": t_event.severity,
                "is_new": t_is_new
            })

    return {
        "packet_id": packet.packet_id,
        "device_id": packet.device_id,
        "detections_count": len(detection_res.detections),
        "detections": [
            {
                "class_name": d.class_name,
                "confidence": round(d.confidence, 4),
                "bbox": d.bbox.model_dump() if hasattr(d.bbox, "model_dump") else d.bbox.dict(),
                "model_version": d.model_version
            }
            for d in detection_res.detections
        ],
        "detections_reported": registry.get_device(packet.device_id).detections_reported,
        "fused_events": fused_results,
        "inference_time_ms": detection_res.inference_time_ms
    }
