"""
Standalone AI Engine Runner — SIH26124 Urban Intelligence Platform.

Runs the full pipeline for ALL 10 SIH defect categories:
  1. potholes
  2. longitudinal_crack
  3. transverse_crack
  4. alligator_crack
  5. damaged_road  (damaged road surfaces)
  6. missing_divider (missing road dividers)
  7. no_zebracrossing (missing / failed zebra crossings)
  8. damaged_signboard (damaged or missing traffic signboards)
  9. waterlogging
 10. debris

Pipeline:
  1. Loads GPS waypoints from data/samples/BUS_0X_gps.csv
  2. Distributes the 10 defect mock injections across `has_defect` waypoints
     in round-robin order so every class appears at least once in the output
  3. Runs RoadDefectDetector (YOLOv8 / D-FINE perception)
  4. Fuses detections through SpatioTemporalFusionEngine
  5. Writes detections + fused events to output/ai_engine_output.json

Usage:
  python run_ai_engine.py [--buses 1,2,3] [--output output/ai_engine_output.json] [--no-image]

Requirements:
  pip install ultralytics pillow pydantic numpy
"""

from __future__ import annotations

import argparse
import base64
import csv
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

# ─── AI Engine Imports ────────────────────────────────────────────────────────
from ai_engine.sensor_interface.contracts import (
    SensorPacket,
    GPSReading,
    DetectionResult,
    Observation,
    Event,
)
from ai_engine.perception.detector import RoadDefectDetector
from ai_engine.fusion.engine import SpatioTemporalFusionEngine
from ai_engine.specialized.observation_classifier import classify_detection

# ─── Paths ────────────────────────────────────────────────────────────────────
SAMPLES_DIR = ROOT_DIR / "data" / "samples"
POTHOLE_IMG  = SAMPLES_DIR / "pothole_sample_frame.jpg"
OUTPUT_DIR   = ROOT_DIR / "output"

# ─── SIH26124 — All 10 required defect classes ───────────────────────────────
# Each entry drives a mock injection via packet.extra_metadata["mock_defects"].
# Bounding box coordinates are in pixels for a 640×480 reference frame.
# Confidence values are varied to exercise fusion scoring.
SIH_DEFECT_CLASSES: list[dict] = [
    {
        "class_name": "pothole",
        "confidence": 0.91,
        "x": 320, "y": 380, "w": 130, "h": 95,
        "description": "Pothole — deep road cavity",
    },
    {
        "class_name": "longitudinal_crack",
        "confidence": 0.84,
        "x": 310, "y": 300, "w": 200, "h": 18,
        "description": "Longitudinal crack — parallel to road axis",
    },
    {
        "class_name": "transverse_crack",
        "confidence": 0.82,
        "x": 320, "y": 310, "w": 18, "h": 180,
        "description": "Transverse crack — perpendicular to road axis",
    },
    {
        "class_name": "alligator_crack",
        "confidence": 0.87,
        "x": 300, "y": 350, "w": 160, "h": 110,
        "description": "Alligator / fatigue cracking — interconnected network",
    },
    {
        "class_name": "damaged_road",
        "confidence": 0.79,
        "x": 280, "y": 330, "w": 220, "h": 140,
        "description": "Damaged road surface — general surface deterioration",
    },
    {
        "class_name": "missing_divider",
        "confidence": 0.76,
        "x": 320, "y": 240, "w": 60, "h": 200,
        "description": "Missing road divider — absent median or lane separator",
    },
    {
        "class_name": "no_zebracrossing",
        "confidence": 0.85,
        "x": 320, "y": 340, "w": 450, "h": 120,
        "description": "Missing / failed zebra crossing — no visible pedestrian markings",
    },
    {
        "class_name": "damaged_signboard",
        "confidence": 0.78,
        "x": 100, "y": 150, "w": 90, "h": 110,
        "description": "Damaged or missing traffic signboard",
    },
    {
        "class_name": "waterlogging",
        "confidence": 0.88,
        "x": 320, "y": 360, "w": 300, "h": 160,
        "description": "Waterlogging — standing water on road surface",
    },
    {
        "class_name": "debris",
        "confidence": 0.81,
        "x": 250, "y": 370, "w": 110, "h": 80,
        "description": "Debris on road — loose material, rubble, or litter",
    },
]

# All SIH classes that should enter the fusion pipeline
FUSABLE_CLASSES: frozenset[str] = frozenset(
    d["class_name"] for d in SIH_DEFECT_CLASSES
)


# Deterministic waypoint index -> SIH defect class mapping.
# Shared waypoints across buses receive identical defect types, enabling
# realistic Spatio-Temporal corroboration and lifecycle status promotion!
WAYPOINT_DEFECT_MAP: dict[int, dict] = {
    1: SIH_DEFECT_CLASSES[1],  # longitudinal_crack  (seen by BUS_01, BUS_02 -> CORROBORATED)
    2: SIH_DEFECT_CLASSES[2],  # transverse_crack    (seen by BUS_02, BUS_03 -> CORROBORATED)
    3: SIH_DEFECT_CLASSES[4],  # damaged_road        (seen by BUS_01 -> CANDIDATE)
    4: SIH_DEFECT_CLASSES[5],  # missing_divider     (seen by BUS_01, BUS_03 -> CORROBORATED)
    5: SIH_DEFECT_CLASSES[0],  # pothole             (seen by BUS_01, BUS_02, BUS_03 -> HIGH_PRIORITY)
    6: SIH_DEFECT_CLASSES[6],  # no_zebracrossing    (seen by BUS_02 -> CANDIDATE)
    7: SIH_DEFECT_CLASSES[3],  # alligator_crack     (seen by BUS_01, BUS_02 -> CORROBORATED)
    8: SIH_DEFECT_CLASSES[7],  # damaged_signboard   (seen by BUS_03 -> CANDIDATE)
    9: SIH_DEFECT_CLASSES[8],  # waterlogging        (seen by BUS_01, BUS_02, BUS_03 -> HIGH_PRIORITY)
    10: SIH_DEFECT_CLASSES[9], # debris              (seen by BUS_01, BUS_03 -> CORROBORATED)
}


# ─── Helpers ─────────────────────────────────────────────────────────────────

def load_gps_csv(bus_id: str) -> list[dict]:
    """Reads GPS waypoints for a given bus CSV."""
    csv_path = SAMPLES_DIR / f"BUS_{bus_id:0>2}_gps.csv"
    if not csv_path.exists():
        print(f"  [WARN] GPS file not found: {csv_path}")
        return []
    rows = []
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def encode_image_b64(path: Path) -> str | None:
    """Returns base64-encoded JPEG data-URI, or None if file is missing."""
    if not path.exists():
        return None
    with open(path, "rb") as f:
        return "data:image/jpeg;base64," + base64.b64encode(f.read()).decode()


def build_sensor_packet(
    bus_id: str,
    row: dict,
    sample_image_b64: str | None,
    defect_injection: dict | None,
) -> SensorPacket:
    """
    Constructs a SensorPacket, optionally injecting a specific mock defect dict
    (one of the SIH_DEFECT_CLASSES entries).
    """
    gps = GPSReading(
        latitude=float(row["latitude"]),
        longitude=float(row["longitude"]),
        speed=float(row.get("speed", 0)),
        heading=float(row.get("heading", 0)),
        accuracy=float(row.get("accuracy", 5.0)),
        timestamp=float(row["timestamp"]),
    )

    extra: dict = {}
    frame_b64: str | None = sample_image_b64

    if defect_injection:
        # Inject the designated SIH defect class as a mock detection
        extra["mock_defects"] = [defect_injection]

    return SensorPacket(
        device_id=f"BUS_{bus_id:0>2}",
        frame_timestamp=float(row["timestamp"]),
        gps=gps,
        frame_base64=frame_b64,
        extra_metadata=extra,
    )


# ─── Pipeline ─────────────────────────────────────────────────────────────────

def run_pipeline(bus_ids: list[str], use_image: bool) -> dict:
    """
    Executes the full perception + fusion pipeline across all specified buses.
    Distributes all 10 SIH defect types across `has_defect=1` waypoints using
    round-robin so every class appears at least once across the fleet.
    Returns a dict with 'meta', 'class_summary', 'detections', and 'events'.
    """
    print("\n[AI Engine] Initialising RoadDefectDetector (YOLOv8)...")
    detector = RoadDefectDetector(confidence_threshold=0.40)

    print("[AI Engine] Initialising SpatioTemporalFusionEngine...")
    fused_events: list[Event] = []
    fusion_engine = SpatioTemporalFusionEngine(
        spatial_radius_meters=30.0,
        temporal_window_sec=30 * 86400,  # 30-day corroboration window
    )

    all_detections: list[dict] = []
    defect_injection_counter = 0   # cycles through SIH_DEFECT_CLASSES

    sample_b64: str | None = None
    if use_image and POTHOLE_IMG.exists():
        print(f"[AI Engine] Loading sample image: {POTHOLE_IMG.name}")
        sample_b64 = encode_image_b64(POTHOLE_IMG)
    elif use_image:
        print(f"[AI Engine] Sample image not found at {POTHOLE_IMG}, skipping real-image inference.")

    for bus_id in bus_ids:
        rows = load_gps_csv(bus_id)
        if not rows:
            continue

        print(f"\n[AI Engine] Processing BUS_{bus_id:0>2} — {len(rows)} waypoints")

        for i, row in enumerate(rows):
            has_defect_flag = int(row.get("has_defect", 0)) == 1

            # Assign defect class deterministically by waypoint index so shared waypoints
            # across multiple buses observe the exact same defect for fusion corroboration
            if has_defect_flag:
                defect_injection = WAYPOINT_DEFECT_MAP.get(
                    i, SIH_DEFECT_CLASSES[defect_injection_counter % len(SIH_DEFECT_CLASSES)]
                )
                defect_injection_counter += 1
            else:
                defect_injection = None

            packet = build_sensor_packet(bus_id, row, sample_b64, defect_injection)

            # ── Perception ─────────────────────────────────────────────────
            result: DetectionResult = detector.detect(packet)

            det_entry = {
                "packet_id": result.packet_id,
                "device_id": result.device_id,
                "timestamp": result.timestamp,
                "timestamp_iso": datetime.fromtimestamp(
                    result.timestamp, tz=timezone.utc
                ).isoformat(),
                "latitude": result.gps.latitude,
                "longitude": result.gps.longitude,
                "speed_kmh": packet.gps.speed,
                "inference_time_ms": round(result.inference_time_ms, 2),
                "detections": [d.model_dump() for d in result.detections],
            }
            all_detections.append(det_entry)

            if result.detections:
                summary = ", ".join(
                    f"{d.class_name}({d.confidence:.2f})" for d in result.detections
                )
                print(
                    f"  WP {i+1:02d} | lat={packet.gps.latitude:.5f} "
                    f"lon={packet.gps.longitude:.5f} | {len(result.detections)} det: {summary}"
                )
            else:
                print(
                    f"  WP {i+1:02d} | lat={packet.gps.latitude:.5f} "
                    f"lon={packet.gps.longitude:.5f} | No defects"
                )

            # ── Fusion ────────────────────────────────────────────────────
            for detection in result.detections:
                if detection.class_name not in FUSABLE_CLASSES:
                    continue

                # Derive canonical EventType / EventSubtype from the classifier
                ev_type, ev_subtype = classify_detection(detection.class_name)

                obs = Observation(
                    device_id=result.device_id,
                    packet_id=result.packet_id,
                    timestamp=result.timestamp,
                    latitude=result.gps.latitude,
                    longitude=result.gps.longitude,
                    observation_type=ev_type,
                    observation_subtype=ev_subtype,
                    defect_type=ev_subtype,          # legacy alias
                    model_confidence=detection.confidence,
                    bbox=detection.bbox,
                )
                event, is_new = fusion_engine.fuse_observation(obs, fused_events)
                if is_new:
                    fused_events.append(event)

    # ── Per-class detection summary ────────────────────────────────────────────
    class_summary: dict[str, dict] = {}
    for det_entry in all_detections:
        for d in det_entry["detections"]:
            cls = d["class_name"]
            if cls not in class_summary:
                ev_type, ev_subtype = classify_detection(cls)
                class_summary[cls] = {
                    "class_name": cls,
                    "event_type": ev_type,
                    "event_subtype": ev_subtype,
                    "detection_count": 0,
                    "max_confidence": 0.0,
                    "min_confidence": 1.0,
                    "avg_confidence": 0.0,
                    "_conf_sum": 0.0,
                }
            entry = class_summary[cls]
            conf = d["confidence"]
            entry["detection_count"] += 1
            entry["_conf_sum"] += conf
            entry["max_confidence"] = round(max(entry["max_confidence"], conf), 3)
            entry["min_confidence"] = round(min(entry["min_confidence"], conf), 3)

    for entry in class_summary.values():
        n = entry["detection_count"]
        entry["avg_confidence"] = round(entry["_conf_sum"] / n, 3) if n else 0.0
        del entry["_conf_sum"]

    # ── Serialise events ───────────────────────────────────────────────────────
    events_out = []
    for ev in fused_events:
        ev_dict = ev.model_dump()
        ev_dict["observations"] = [
            {
                "observation_id": o["observation_id"],
                "device_id": o["device_id"],
                "timestamp": o["timestamp"],
                "timestamp_iso": datetime.fromtimestamp(
                    o["timestamp"], tz=timezone.utc
                ).isoformat(),
                "latitude": o["latitude"],
                "longitude": o["longitude"],
                "observation_type": o.get("observation_type", ""),
                "observation_subtype": o.get("observation_subtype", ""),
                "defect_type": o["defect_type"],
                "model_confidence": o["model_confidence"],
            }
            for o in ev_dict["observations"]
        ]
        events_out.append(ev_dict)

    return {
        "meta": {
            "platform": "SIH26124 — Urban Intelligence Platform",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "buses_processed": [f"BUS_{b:0>2}" for b in bus_ids],
            "total_packets": len(all_detections),
            "total_detections": sum(len(d["detections"]) for d in all_detections),
            "total_events": len(events_out),
            "sih_defect_classes_covered": [d["class_name"] for d in SIH_DEFECT_CLASSES],
        },
        "class_summary": list(class_summary.values()),
        "detections": all_detections,
        "events": events_out,
    }


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Run the SIH26124 AI Engine (10-class) and export results as JSON."
    )
    parser.add_argument(
        "--buses",
        default="1,2,3",
        help="Comma-separated bus IDs to process (default: 1,2,3)",
    )
    parser.add_argument(
        "--output",
        default=str(ROOT_DIR / "output" / "ai_engine_output.json"),
        help="Path for the output JSON file",
    )
    parser.add_argument(
        "--no-image",
        action="store_true",
        help="Skip loading the sample image (faster, mock-only mode)",
    )
    args = parser.parse_args()

    bus_ids = [b.strip() for b in args.buses.split(",") if b.strip()]
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print("=" * 65)
    print("  SIH26124 — AI ENGINE STANDALONE RUNNER  (10-class mode)")
    print("=" * 65)
    print(f"  Buses      : {[f'BUS_{b:0>2}' for b in bus_ids]}")
    print(f"  Output     : {output_path}")
    print(f"  Use image  : {not args.no_image}")
    print()
    print("  SIH Defect Classes:")
    for idx, d in enumerate(SIH_DEFECT_CLASSES, 1):
        print(f"    {idx:>2}. {d['class_name']:<22} — {d['description']}")
    print("=" * 65)

    t0 = time.perf_counter()
    result = run_pipeline(bus_ids, use_image=not args.no_image)
    elapsed = time.perf_counter() - t0

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 65)
    print(f"  DONE in {elapsed:.2f}s")
    print(f"  Packets processed : {result['meta']['total_packets']}")
    print(f"  Total detections  : {result['meta']['total_detections']}")
    print(f"  Fused events      : {result['meta']['total_events']}")
    print()
    print("  Detection class breakdown:")
    for summary in sorted(result["class_summary"], key=lambda x: -x["detection_count"]):
        print(
            f"    {summary['class_name']:<22} | "
            f"count={summary['detection_count']:>2} | "
            f"avg_conf={summary['avg_confidence']:.2f} | "
            f"type={summary['event_type']}"
        )
    print()
    print(f"  Output saved to   : {output_path}")
    print("=" * 65)


if __name__ == "__main__":
    main()
