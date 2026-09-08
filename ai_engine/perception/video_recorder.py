"""
Video Recording & Active Learning Dataset Generator (SIH26124).
Captures incoming mobile dashcam frames, compiles timestamped video clips with
real-time defect and vehicle annotations, and updates the persistent defect ledger.
"""

import os
import json
import time
import base64
import numpy as np
from pathlib import Path
from typing import Optional, List, Dict, Any

try:
    import cv2
except ImportError:
    cv2 = None

from .defect_recorder import global_defect_ledger

BASE_DIR = Path(__file__).resolve().parent.parent.parent
RECORDINGS_DIR = BASE_DIR / "data" / "video_recordings"
DATASET_DIR = BASE_DIR / "data" / "training_dataset"
IMAGES_DIR = DATASET_DIR / "images"
LABELS_DIR = DATASET_DIR / "labels"
INDEX_FILE = RECORDINGS_DIR / "recordings_index.json"

RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
LABELS_DIR.mkdir(parents=True, exist_ok=True)

# Defect and object class mapping (5 core classes)
CLASS_MAP = {
    "pothole": 0,
    "crack": 1,
    "damaged_road": 1,
    "no_zebracrossing": 2,
    "no_zebra_crossing": 2,
    "zebra_crossing": 3,
    "vehicle": 4,
    "car": 4,
    "bus": 4,
    "truck": 4,
    "motorcycle": 4,
}

# Distinct visual colors in BGR for video overlays
CLASS_COLORS = {
    "pothole": (0, 0, 238),           # Bright Red
    "crack": (220, 0, 220),           # Purple / Magenta
    "damaged_road": (220, 0, 220),    # Purple
    "no_zebracrossing": (0, 140, 255),# Amber / Orange Warning
    "no_zebra_crossing": (0, 140, 255),
    "zebra_crossing": (0, 220, 0),    # Green
    "vehicle": (255, 180, 0),         # Cyan / Blue
    "car": (255, 180, 0),
    "bus": (255, 140, 0),
    "truck": (255, 100, 0),
    "motorcycle": (255, 200, 0),
}


class VideoRecorder:
    """
    Manages live dashcam video recording sessions, burns in real-time defect overlays,
    and logs defect occurrences into the central DefectLedger.
    """

    def __init__(self, fps: float = 2.5, clip_duration_sec: int = 30, annotate_video: bool = True, min_confidence: float = 0.20):
        self.fps = fps
        self.clip_duration_sec = clip_duration_sec
        self.annotate_video = annotate_video
        self.min_confidence = min_confidence
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        self._recordings_index: List[Dict[str, Any]] = []
        self._load_index()

    def _load_index(self):
        if INDEX_FILE.exists():
            try:
                with open(INDEX_FILE, "r", encoding="utf-8") as f:
                    self._recordings_index = json.load(f)
            except Exception as e:
                print(f"[VideoRecorder] Error loading recordings index: {e}")
                self._recordings_index = []
        else:
            self._recordings_index = []

    def _save_index(self):
        try:
            with open(INDEX_FILE, "w", encoding="utf-8") as f:
                json.dump(self._recordings_index, f, indent=2)
        except Exception as e:
            print(f"[VideoRecorder] Error saving recordings index: {e}")

    def _decode_frame(self, frame_base64: str) -> Optional[np.ndarray]:
        """Decode base64 JPEG to OpenCV BGR image."""
        try:
            if "," in frame_base64:
                frame_base64 = frame_base64.split(",", 1)[1]
            raw_bytes = base64.b64decode(frame_base64)
            np_arr = np.frombuffer(raw_bytes, np.uint8)
            if cv2 is not None:
                img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                return img
        except Exception as e:
            print(f"[VideoRecorder] Frame decode error: {e}")
        return None

    def _draw_overlay(
        self,
        img: np.ndarray,
        device_id: str,
        gps: Dict[str, Any],
        detections: List[Dict[str, Any]],
        defect_counts: Dict[str, int]
    ) -> np.ndarray:
        """
        Draws HUD banner and defect/vehicle bounding boxes on frame for saved video.
        """
        if cv2 is None:
            return img

        frame = img.copy()
        h, w, _ = frame.shape

        # 1. Top HUD Header Banner
        hud_h = 42
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, hud_h), (20, 20, 25), -1)
        cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)

        # Telemetry string
        lat = gps.get("latitude", 0.0)
        lon = gps.get("longitude", 0.0)
        raw_speed = float(gps.get("speed", 0.0) or 0.0)
        speed_kmh = raw_speed * 3.6 if (0.0 < raw_speed < 18.0) else raw_speed
        time_str = time.strftime("%H:%M:%S")

        line1 = f"[{device_id}] GPS: {lat:.5f}, {lon:.5f} | Speed: {speed_kmh:.1f} km/h | {time_str}"
        p_cnt = defect_counts.get("pothole", 0)
        z_cnt = defect_counts.get("no_zebracrossing", 0)
        v_cnt = defect_counts.get("vehicle", 0)
        line2 = f"DEFECTS: Potholes: {p_cnt} | No Zebra: {z_cnt} | Vehicles: {v_cnt}"

        cv2.putText(frame, line1, (10, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (240, 240, 240), 1, cv2.LINE_AA)
        cv2.putText(frame, line2, (10, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 220, 255), 1, cv2.LINE_AA)

        # 2. Draw Bounding Boxes for Detections
        for det in detections:
            cls_name = det.get("class_name", "pothole").lower()
            conf = det.get("confidence", 0.8)
            if conf < self.min_confidence:
                continue
            bbox = det.get("bbox", {})

            # Support dict or object
            if hasattr(bbox, "x"):
                bx, by, bw, bh = bbox.x, bbox.y, bbox.width, bbox.height
            elif isinstance(bbox, dict):
                bx = bbox.get("x", 100)
                by = bbox.get("y", 100)
                bw = bbox.get("width", bbox.get("w", 80))
                bh = bbox.get("height", bbox.get("h", 60))
            else:
                continue

            # Convert to top-left and bottom-right
            # If coordinates are center (YOLO format) or top-left
            # Check if bbox is normalized (0-1)
            if bw <= 1.0 and bh <= 1.0:
                bx, by, bw, bh = bx * w, by * h, bw * w, bh * h

            x1 = int(max(0, bx))
            y1 = int(max(0, by))
            x2 = int(min(w, bx + bw))
            y2 = int(min(h, by + bh))

            color = CLASS_COLORS.get(cls_name, (0, 255, 255))

            # Draw rectangle
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

            # Label text
            if "no_zebra" in cls_name:
                display_label = f"! NO ZEBRACROSSING [{conf:.2f}]"
            elif cls_name == "zebra_crossing":
                display_label = f"Zebra Crossing [{conf:.2f}]"
            elif "pothole" in cls_name:
                display_label = f"Pothole [{conf:.2f}]"
            elif cls_name in ["vehicle", "car", "bus", "truck", "motorcycle"]:
                display_label = f"Vehicle: {cls_name} [{conf:.2f}]"
            else:
                display_label = f"{cls_name.upper()} [{conf:.2f}]"

            (lw, lh), _ = cv2.getTextSize(display_label, cv2.FONT_HERSHEY_SIMPLEX, 0.42, 1)
            label_y1 = max(hud_h + 2, y1 - lh - 6)
            cv2.rectangle(frame, (x1, label_y1), (x1 + lw + 8, label_y1 + lh + 6), color, -1)
            cv2.putText(
                frame,
                display_label,
                (x1 + 4, label_y1 + lh + 1),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.42,
                (255, 255, 255) if color != (0, 220, 255) else (0, 0, 0),
                1,
                cv2.LINE_AA
            )

        return frame

    def ingest_frame(
        self,
        device_id: str,
        frame_base64: str,
        gps: Dict[str, Any],
        detections: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[str]:
        """
        Appends frame to active device's video recording, burns in overlay,
        logs detected defects to DefectLedger, and saves training samples.
        """
        img = self._decode_frame(frame_base64)
        if img is None:
            return None

        h, w, _ = img.shape
        now = time.time()
        detections = detections or []

        # Check or initialize active video writer for device
        if device_id not in self.active_sessions:
            clip_name = f"{device_id}_{int(now)}.mp4"
            clip_path = RECORDINGS_DIR / clip_name

            # Use mp4v or universal codec fallback
            writer = None
            if cv2 is not None:
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                writer = cv2.VideoWriter(str(clip_path), fourcc, self.fps, (w, h))
                if not writer.isOpened():
                    # Fallback to XVID / AVI if mp4v fails on current system
                    fourcc = cv2.VideoWriter_fourcc(*'XVID')
                    clip_name = f"{device_id}_{int(now)}.avi"
                    clip_path = RECORDINGS_DIR / clip_name
                    writer = cv2.VideoWriter(str(clip_path), fourcc, self.fps, (w, h))

            self.active_sessions[device_id] = {
                "writer": writer,
                "clip_name": clip_name,
                "clip_path": clip_path,
                "start_time": now,
                "frame_count": 0,
                "defect_counts": {"pothole": 0, "no_zebracrossing": 0, "vehicle": 0, "other": 0}
            }

        session = self.active_sessions[device_id]

        # Update session defect counts
        for det in detections:
            c = det.get("class_name", "").lower()
            if "pothole" in c:
                session["defect_counts"]["pothole"] += 1
            elif "no_zebra" in c or "zebra" in c:
                session["defect_counts"]["no_zebracrossing"] += 1
            elif c in ["vehicle", "car", "bus", "truck", "motorcycle"]:
                session["defect_counts"]["vehicle"] += 1
            else:
                session["defect_counts"]["other"] += 1

        # Draw overlays on frame for video recording
        recorded_frame = self._draw_overlay(img, device_id, gps, detections, session["defect_counts"]) if self.annotate_video else img

        if session["writer"] is not None and session["writer"].isOpened():
            session["writer"].write(recorded_frame)
            session["frame_count"] += 1

        # Check if clip rotation needed
        if now - session["start_time"] >= self.clip_duration_sec:
            self.finalize_session(device_id)

        # Record defects in persistent DefectLedger & save training samples
        saved_sample_path = None
        if detections:
            sample_id = f"sample_{device_id}_{int(now * 1000)}"
            img_path = IMAGES_DIR / f"{sample_id}.jpg"
            lbl_path = LABELS_DIR / f"{sample_id}.txt"

            if cv2 is not None:
                cv2.imwrite(str(img_path), img)

            # Write YOLO/D-FINE format annotations
            with open(lbl_path, "w", encoding="utf-8") as f:
                for det in detections:
                    cls_name = det.get("class_name", "pothole").lower()
                    cls_id = CLASS_MAP.get(cls_name, 0)
                    conf = det.get("confidence", 0.85)
                    bbox = det.get("bbox", {})

                    if hasattr(bbox, "x"):
                        x, y, bw, bh = bbox.x, bbox.y, bbox.width, bbox.height
                    elif isinstance(bbox, dict):
                        x = bbox.get("x", 100)
                        y = bbox.get("y", 100)
                        bw = bbox.get("width", bbox.get("w", 100))
                        bh = bbox.get("height", bbox.get("h", 80))
                    else:
                        continue

                    # Normalize
                    xc = (x + bw / 2.0) / float(w)
                    yc = (y + bh / 2.0) / float(h)
                    n_w = bw / float(w)
                    n_h = bh / float(h)

                    xc = max(0.0, min(1.0, xc))
                    yc = max(0.0, min(1.0, yc))
                    n_w = max(0.0, min(1.0, n_w))
                    n_h = max(0.0, min(1.0, n_h))

                    f.write(f"{cls_id} {xc:.6f} {yc:.6f} {n_w:.6f} {n_h:.6f}\n")

                    # Log each defect into the persistent DefectLedger
                    global_defect_ledger.record_defect(
                        defect_type=cls_name,
                        confidence=conf,
                        latitude=gps.get("latitude", 0.0),
                        longitude=gps.get("longitude", 0.0),
                        device_id=device_id,
                        severity="HIGH" if ("pothole" in cls_name or "no_zebra" in cls_name) else "MEDIUM",
                        bbox={"x": float(x), "y": float(y), "w": float(bw), "h": float(bh)},
                        speed=gps.get("speed"),
                        heading=gps.get("heading"),
                        snapshot_uri=str(img_path.relative_to(BASE_DIR)).replace("\\", "/"),
                        video_clip=session["clip_name"],
                    )

            saved_sample_path = str(img_path)

        return saved_sample_path

    def finalize_session(self, device_id: str) -> Optional[Dict[str, Any]]:
        """
        Releases and closes the video writer for a given device,
        indexes the clip metadata, and returns recording details.
        """
        if device_id in self.active_sessions:
            session = self.active_sessions.pop(device_id)
            if session["writer"] is not None:
                session["writer"].release()

            clip_path = session["clip_path"]
            duration = round(time.time() - session["start_time"], 2)
            size_bytes = clip_path.stat().st_size if clip_path.exists() else 0

            rec_info = {
                "filename": session["clip_name"],
                "device_id": device_id,
                "path": str(clip_path),
                "frame_count": session["frame_count"],
                "duration_sec": duration,
                "fps": self.fps,
                "size_bytes": size_bytes,
                "defect_counts": session["defect_counts"],
                "created_at": session["start_time"],
                "created_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(session["start_time"]))
            }

            # Update index
            self._recordings_index = [r for r in self._recordings_index if r.get("filename") != session["clip_name"]]
            self._recordings_index.insert(0, rec_info)
            self._save_index()

            print(f"[VideoRecorder] Saved dashcam recording: {clip_path.name} "
                  f"({session['frame_count']} frames, {duration}s, {size_bytes} bytes, "
                  f"Defects: {session['defect_counts']})")

            return rec_info
        return None

    def finalize_all(self):
        """Finalizes all active recording sessions."""
        active_ids = list(self.active_sessions.keys())
        for dev_id in active_ids:
            self.finalize_session(dev_id)

    def list_recordings(self) -> List[Dict[str, Any]]:
        """Lists all saved video recordings with rich metadata."""
        # Ensure any newly created video files are represented in index
        existing_files = {f.name: f for f in RECORDINGS_DIR.glob("*.*") if f.suffix.lower() in [".mp4", ".avi", ".webm"]}
        indexed_names = {r["filename"] for r in self._recordings_index}

        for fname, fpath in existing_files.items():
            if fname not in indexed_names:
                self._recordings_index.append({
                    "filename": fname,
                    "device_id": fname.split("_")[0] if "_" in fname else "unknown",
                    "path": str(fpath),
                    "frame_count": 0,
                    "duration_sec": 0,
                    "fps": self.fps,
                    "size_bytes": fpath.stat().st_size,
                    "defect_counts": {"pothole": 0, "no_zebracrossing": 0, "vehicle": 0, "other": 0},
                    "created_at": fpath.stat().st_ctime,
                    "created_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(fpath.stat().st_ctime))
                })

        self._recordings_index.sort(key=lambda x: x.get("created_at", 0), reverse=True)
        self._save_index()
        return self._recordings_index


# Singleton instance
global_video_recorder = VideoRecorder(fps=2.5, clip_duration_sec=30, annotate_video=True, min_confidence=0.20)
