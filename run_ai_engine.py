"""
Standalone AI Engine Runner — SIH26124 Urban Intelligence Platform.

Runs the full pipeline:
  1. Loads GPS waypoints from data/samples/BUS_0X_gps.csv
  2. Builds SensorPackets (injects the pothole sample image at defect waypoints)
  3. Runs RoadDefectDetector (YOLOv8 perception)
  4. Fuses detections through SpatioTemporalFusionEngine
  5. Writes all raw detections + fused events to  output/ai_engine_output.json

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

# ─── Paths ────────────────────────────────────────────────────────────────────
SAMPLES_DIR = ROOT_DIR / "data" / "samples"
POTHOLE_IMG = SAMPLES_DIR / "pothole_sample_frame.jpg"
OUTPUT_DIR = ROOT_DIR / "output"


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
    use_mock_defect: bool,
) -> SensorPacket:
    """Constructs a SensorPacket from a CSV row."""
    gps = GPSReading(
        latitude=float(row["latitude"]),
        longitude=float(row["longitude"]),
        speed=float(row.get("speed", 0)),
        heading=float(row.get("heading", 0)),
        accuracy=float(row.get("accuracy", 5.0)),
        timestamp=float(row["timestamp"]),
    )

    extra: dict = {}
    frame_b64: str | None = None

    if use_mock_defect:
        # Inject a mock defect so detector always returns a pothole detection
        extra["mock_defect"] = {
            "class_name": "pothole",
            "confidence": 0.87,
            "x": 320,
            "y": 300,
            "w": 130,
            "h": 95,
        }
        frame_b64 = sample_image_b64  # real image if available (for YOLO too)

    elif sample_image_b64:
        frame_b64 = sample_image_b64

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
    Returns a dict with 'meta', 'detections', and 'events'.
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
            packet = build_sensor_packet(bus_id, row, sample_b64, has_defect_flag)

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
            FUSABLE_CLASSES = {"pothole", "damaged_road", "crack", "no_zebracrossing"}
            for detection in result.detections:
                if detection.class_name not in FUSABLE_CLASSES:
                    continue
                obs = Observation(
                    device_id=result.device_id,
                    packet_id=result.packet_id,
                    timestamp=result.timestamp,
                    latitude=result.gps.latitude,
                    longitude=result.gps.longitude,
                    defect_type=detection.class_name,
                    model_confidence=detection.confidence,
                    bbox=detection.bbox,
                )
                event, is_new = fusion_engine.fuse_observation(obs, fused_events)
                if is_new:
                    fused_events.append(event)

    # ── Serialise events ───────────────────────────────────────────────────────
    events_out = []
    for ev in fused_events:
        ev_dict = ev.model_dump()
        # Replace nested Observation objects with a compact summary
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
                "defect_type": o["defect_type"],
                "model_confidence": o["model_confidence"],
            }
            for o in ev_dict["observations"]
        ]
        events_out.append(ev_dict)

    return {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "buses_processed": [f"BUS_{b:0>2}" for b in bus_ids],
            "total_packets": len(all_detections),
            "total_detections": sum(len(d["detections"]) for d in all_detections),
            "total_events": len(events_out),
        },
        "detections": all_detections,
        "events": events_out,
    }


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Run the SIH26124 AI Engine and export results as JSON."
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
        help="Skip loading the pothole sample image (faster, mock-only mode)",
    )
    args = parser.parse_args()

    bus_ids = [b.strip() for b in args.buses.split(",") if b.strip()]
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("  SIH26124 — AI ENGINE STANDALONE RUNNER")
    print("=" * 60)
    print(f"  Buses      : {[f'BUS_{b:0>2}' for b in bus_ids]}")
    print(f"  Output     : {output_path}")
    print(f"  Use image  : {not args.no_image}")
    print("=" * 60)

    t0 = time.perf_counter()
    result = run_pipeline(bus_ids, use_image=not args.no_image)
    elapsed = time.perf_counter() - t0

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print(f"  DONE in {elapsed:.2f}s")
    print(f"  Packets processed : {result['meta']['total_packets']}")
    print(f"  Total detections  : {result['meta']['total_detections']}")
    print(f"  Fused events      : {result['meta']['total_events']}")
    print(f"  Output saved to   : {output_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
