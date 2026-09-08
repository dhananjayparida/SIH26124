"""
Video AI Engine Runner — SIH26124 Urban Intelligence Platform.

Reads a video file frame by frame, runs the full AI pipeline on each frame,
and writes all detections + fused events to a JSON file.

Usage:
  python run_video_ai.py --video path/to/video.mp4
    python run_video_ai.py --video path/to/video.mp4 --model dfine --output output/video_result.json
  python run_video_ai.py --video path/to/video.mp4 --lat 20.2961 --lon 85.8245
  python run_video_ai.py --video path/to/video.mp4 --device BUS_CAM_01 --fps 3 --annotated

Arguments:
  --video      Path to input video file (mp4, avi, mov, mkv …)
    --fps        Frames to sample per second of video (default: 4)
    --model      Model checkpoint: dfine, best, or yolo (default: dfine)
    --output     Output JSON path (default: output/video_ai_output.json)
  --device     Device/camera ID tag in output (default: VIDEO_CAM)
  --lat        Starting GPS latitude  (default: 0.0 — no GPS)
  --lon        Starting GPS longitude (default: 0.0 — no GPS)
  --annotated  Also write an annotated output video with bounding-box overlays
    --conf       Detection confidence threshold (default: 0.20)
    --fusion-radius  Distance in meters used to group detections (default: 30)
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

from ai_engine.sensor_interface.contracts import (
    SensorPacket, GPSReading, DetectionResult, Observation, Event
)
from ai_engine.perception.detector import RoadDefectDetector
from ai_engine.fusion.engine import SpatioTemporalFusionEngine

OUTPUT_DIR = ROOT_DIR / "output"
MODEL_PATHS = {
    "dfine": ROOT_DIR / "models" / "dfine_road_defect_latest.pt",
    "best": ROOT_DIR / "models" / "best_road_defect_model.pt",
    "yolo": ROOT_DIR / "yolov8n.pt",
}

# BGR colors for annotation overlay
CLASS_COLORS = {
    "pothole":         (0,   0, 238),
    "crack":           (220, 0, 220),
    "damaged_road":    (220, 0, 220),
    "no_zebracrossing":(0, 140, 255),
    "zebra_crossing":  (0, 220,   0),
    "vehicle":         (255,180,   0),
    "car":             (255,180,   0),
    "bus":             (255,140,   0),
    "truck":           (255,100,   0),
    "motorcycle":      (255,200,   0),
}


def frame_to_b64(frame_bgr: np.ndarray) -> str:
    """Convert a BGR numpy frame to base64 JPEG data-URI."""
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(rgb)
    buf = io.BytesIO()
    pil_img.save(buf, format="JPEG", quality=85)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def annotate_frame(frame: np.ndarray, result: DetectionResult, min_conf: float = 0.20) -> np.ndarray:
    """Draw bounding boxes + labels on a copy of the frame for detections >= min_conf."""
    annotated = frame.copy()
    h, w = annotated.shape[:2]
    visible_detections = [det for det in result.detections if det.confidence >= min_conf]
    for det in visible_detections:
        color = CLASS_COLORS.get(det.class_name, (0, 255, 0))
        bx = det.bbox
        # bbox is [cx, cy, bw, bh] in pixels
        x1 = int(bx.x - bx.width / 2)
        y1 = int(bx.y - bx.height / 2)
        x2 = int(bx.x + bx.width / 2)
        y2 = int(bx.y + bx.height / 2)
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)

        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
        label = f"{det.class_name} {det.confidence:.2f}"
        (lw, lh), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
        cv2.rectangle(annotated, (x1, y1 - lh - 6), (x1 + lw + 4, y1), color, -1)
        cv2.putText(annotated, label, (x1 + 2, y1 - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)

    # Frame info overlay
    ts_str = datetime.fromtimestamp(result.timestamp, tz=timezone.utc).strftime("%H:%M:%S UTC")
    det_count = len(visible_detections)
    cv2.putText(annotated, f"Detections: {det_count}  |  {ts_str}",
                (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
    return annotated


def run_video_pipeline(
    video_path: Path,
    sample_fps: float,
    device_id: str,
    start_lat: float,
    start_lon: float,
    conf_threshold: float,
    fusion_radius_meters: float,
    model_name: str,
    model_path: Path,
    write_annotated: bool,
    output_path: Path,
) -> dict:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")

    video_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration_sec = total_frames / video_fps
    frame_step = max(1, int(round(video_fps / sample_fps)))

    print(f"\n[Video] {video_path.name}")
    print(f"  Source FPS    : {video_fps:.1f}")
    print(f"  Total frames  : {total_frames}")
    print(f"  Duration      : {duration_sec:.1f}s")
    print(f"  Sample every  : {frame_step} frames  ({sample_fps:.1f} FPS effective)")

    # Annotated writer setup
    writer = None
    annotated_path = None
    if write_annotated:
        fw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        fh = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        annotated_path = output_path.parent / (output_path.stem + "_annotated.mp4")
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(annotated_path), fourcc, sample_fps, (fw, fh))

    print("\n[AI Engine] Initialising RoadDefectDetector...")
    detector = RoadDefectDetector(
        model_type=model_name,
        weights_path=str(model_path),
        confidence_threshold=conf_threshold,
    )

    print("[AI Engine] Initialising SpatioTemporalFusionEngine...")
    fused_events: list[Event] = []
    fusion_engine = SpatioTemporalFusionEngine(spatial_radius_meters=fusion_radius_meters)

    all_detections: list[dict] = []
    frame_idx = 0
    sampled = 0
    start_wall = time.perf_counter()
    now_epoch = datetime.now(timezone.utc).timestamp()

    FUSABLE = {"pothole", "damaged_road", "crack", "no_zebracrossing"}

    print("\n[AI Engine] Processing frames...\n")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % frame_step != 0:
            frame_idx += 1
            continue

        sampled += 1
        video_time_sec = frame_idx / video_fps
        frame_ts = now_epoch + video_time_sec  # wall-clock equivalent timestamp

        # Build SensorPacket
        frame_b64 = frame_to_b64(frame)
        gps = GPSReading(
            latitude=start_lat,
            longitude=start_lon,
            timestamp=frame_ts,
        )
        packet = SensorPacket(
            device_id=device_id,
            frame_timestamp=frame_ts,
            gps=gps,
            frame_base64=frame_b64,
        )

        # Perception
        result: DetectionResult = detector.detect(packet)

        progress_pct = int((frame_idx / max(1, total_frames)) * 100)
        if result.detections:
            summary = ", ".join(
                f"{d.class_name}({d.confidence:.2f})" for d in result.detections
            )
            print(
                f"  [{progress_pct:3d}%] Frame {frame_idx:05d} | t={video_time_sec:.2f}s | "
                f"{len(result.detections)} DETECTION(S): {summary}"
            )
        else:
            if sampled % 10 == 0:  # only print clean frames every 10 to avoid spam
                print(f"  [{progress_pct:3d}%] Frame {frame_idx:05d} | t={video_time_sec:.2f}s | No defects")

        det_entry = {
            "frame_index": frame_idx,
            "video_time_sec": round(video_time_sec, 3),
            "packet_id": result.packet_id,
            "device_id": result.device_id,
            "timestamp": result.timestamp,
            "timestamp_iso": datetime.fromtimestamp(result.timestamp, tz=timezone.utc).isoformat(),
            "latitude": result.gps.latitude,
            "longitude": result.gps.longitude,
            "inference_time_ms": round(result.inference_time_ms, 2),
            "detections": [d.model_dump() for d in result.detections],
        }
        all_detections.append(det_entry)

        # Fusion
        for det in result.detections:
            if det.class_name not in FUSABLE:
                continue
            obs = Observation(
                device_id=result.device_id,
                packet_id=result.packet_id,
                timestamp=result.timestamp,
                latitude=result.gps.latitude,
                longitude=result.gps.longitude,
                defect_type=det.class_name,
                model_confidence=det.confidence,
                bbox=det.bbox,
            )
            event, is_new = fusion_engine.fuse_observation(obs, fused_events)
            if is_new:
                fused_events.append(event)

        # Annotated output
        if writer:
            annotated = annotate_frame(frame, result, min_conf=conf_threshold)
            writer.write(annotated)

        frame_idx += 1

    cap.release()
    if writer:
        writer.release()

    elapsed = time.perf_counter() - start_wall

    # Serialise events
    events_out = []
    for ev in fused_events:
        ev_dict = ev.model_dump()
        ev_dict["observations"] = [
            {
                "observation_id": o["observation_id"],
                "device_id": o["device_id"],
                "timestamp": o["timestamp"],
                "timestamp_iso": datetime.fromtimestamp(o["timestamp"], tz=timezone.utc).isoformat(),
                "latitude": o["latitude"],
                "longitude": o["longitude"],
                "defect_type": o["defect_type"],
                "model_confidence": o["model_confidence"],
            }
            for o in ev_dict["observations"]
        ]
        events_out.append(ev_dict)

    output = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "video_file": video_path.name,
            "video_fps": video_fps,
            "video_duration_sec": round(duration_sec, 2),
            "total_video_frames": total_frames,
            "frames_sampled": sampled,
            "sample_fps": sample_fps,
            "device_id": device_id,
            "gps_origin": {"latitude": start_lat, "longitude": start_lon},
            "conf_threshold": conf_threshold,
            "model": model_name,
            "model_weights": str(model_path),
            "processing_time_sec": round(elapsed, 2),
            "total_detections": sum(len(d["detections"]) for d in all_detections),
            "total_events": len(events_out),
            "annotated_video": str(annotated_path) if annotated_path else None,
        },
        "detections": all_detections,
        "events": events_out,
    }

    return output


def main():
    parser = argparse.ArgumentParser(
        description="Run the SIH26124 AI Engine on a video file and export results as JSON."
    )
    parser.add_argument("--video",    required=True, help="Path to input video file")
    parser.add_argument("--model",    choices=MODEL_PATHS, default="dfine",
                        help="Model checkpoint: dfine, best, or yolo (default: dfine)")
    parser.add_argument("--fps",      type=float, default=4.0,
                        help="Frames to sample per second (default: 4)")
    parser.add_argument("--output",   default=str(OUTPUT_DIR / "video_ai_output.json"),
                        help="Output JSON path")
    parser.add_argument("--device",   default="VIDEO_CAM", help="Device ID tag (default: VIDEO_CAM)")
    parser.add_argument("--lat",      type=float, default=0.0,  help="GPS latitude")
    parser.add_argument("--lon",      type=float, default=0.0,  help="GPS longitude")
    parser.add_argument("--annotated", action="store_true",
                        help="Also write annotated output video with bounding boxes")
    parser.add_argument("--conf",     type=float, default=0.20,
                        help="Detection confidence threshold (default: 0.20)")
    parser.add_argument("--fusion-radius", type=float, default=30.0,
                        help="Fusion radius in meters (default: 30)")
    args = parser.parse_args()

    video_path = Path(args.video)
    if not video_path.exists():
        print(f"[ERROR] Video not found: {video_path}")
        sys.exit(1)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    model_path = MODEL_PATHS[args.model]
    if not model_path.exists():
        print(f"[ERROR] Model checkpoint not found: {model_path}")
        sys.exit(1)

    print("=" * 60)
    print("  SIH26124 — VIDEO AI ENGINE RUNNER")
    print("=" * 60)
    print(f"  Video    : {video_path}")
    print(f"  Model    : {args.model} ({model_path})")
    print(f"  Sample   : {args.fps} FPS")
    print(f"  Device   : {args.device}")
    print(f"  GPS      : lat={args.lat}, lon={args.lon}")
    print(f"  Output   : {output_path}")
    print(f"  Annotated: {args.annotated}")
    print(f"  Conf     : {args.conf}")
    print(f"  Fusion   : {args.fusion_radius} m")
    print("=" * 60)

    result = run_video_pipeline(
        video_path=video_path,
        sample_fps=args.fps,
        device_id=args.device,
        start_lat=args.lat,
        start_lon=args.lon,
        conf_threshold=args.conf,
        fusion_radius_meters=args.fusion_radius,
        model_name=args.model,
        model_path=model_path,
        write_annotated=args.annotated,
        output_path=output_path,
    )

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print(f"  DONE in {result['meta']['processing_time_sec']}s")
    print(f"  Frames sampled    : {result['meta']['frames_sampled']}")
    print(f"  Total detections  : {result['meta']['total_detections']}")
    print(f"  Fused events      : {result['meta']['total_events']}")
    print(f"  JSON saved to     : {output_path}")
    if result["meta"]["annotated_video"]:
        print(f"  Annotated video   : {result['meta']['annotated_video']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
