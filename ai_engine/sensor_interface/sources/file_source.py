"""
File-based replay sources for recorded video and GPS telemetry logs.
"""

import csv
import time
from pathlib import Path
from typing import Iterator, Tuple, Dict, Any, List, Optional
from ..contracts import GPSReading


class VideoFileSource:
    """Reads recorded MP4 or simulated frame sequence."""

    def __init__(self, video_path: str, target_fps: float = 2.5):
        self.video_path = Path(video_path)
        self.target_fps = target_fps
        self._is_open = False

    def open(self) -> None:
        self._is_open = True

    def close(self) -> None:
        self._is_open = False

    def frames(self) -> Iterator[Tuple[bytes, float]]:
        """Yields (frame_bytes, timestamp). Uses OpenCV if available, else synthetic test frames."""
        self.open()
        interval = 1.0 / self.target_fps

        try:
            import cv2
            if self.video_path.exists() and self.video_path.suffix.lower() in [".mp4", ".avi", ".mov"]:
                cap = cv2.VideoCapture(str(self.video_path))
                video_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
                frame_skip = max(1, int(video_fps / self.target_fps))
                frame_idx = 0

                while cap.isOpened() and self._is_open:
                    ret, frame = cap.read()
                    if not ret:
                        break
                    if frame_idx % frame_skip == 0:
                        ret, buffer = cv2.imencode(".jpg", frame)
                        if ret:
                            yield (buffer.tobytes(), time.time())
                    frame_idx += 1
                cap.release()
                return
        except ImportError:
            pass

        # Fallback generator for test frames if no real video is on disk
        import io
        from PIL import Image, ImageDraw
        frame_count = 0
        while self._is_open and frame_count < 50:
            img = Image.new("RGB", (640, 480), color=(40, 40, 40))
            draw = ImageDraw.Draw(img)
            draw.text((20, 20), f"Frame {frame_count} - Bhubaneswar Route", fill=(255, 255, 255))
            buf = io.BytesIO()
            img.save(buf, format="JPEG")
            yield (buf.getvalue(), time.time())
            frame_count += 1
            time.sleep(interval)

    @property
    def metadata(self) -> Dict[str, Any]:
        return {"source": "video_file", "path": str(self.video_path), "fps": self.target_fps}


class GPSFileSource:
    """Reads GPS fix points from a CSV log."""

    def __init__(self, csv_path: str):
        self.csv_path = Path(csv_path)
        self._readings: List[GPSReading] = []
        self._is_open = False

    def open(self) -> None:
        self._is_open = True
        self._readings.clear()

        if self.csv_path.exists():
            with open(self.csv_path, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    self._readings.append(GPSReading(
                        latitude=float(row["latitude"]),
                        longitude=float(row["longitude"]),
                        altitude=float(row.get("altitude", 0.0) or 0.0),
                        speed=float(row.get("speed", 0.0) or 0.0),
                        heading=float(row.get("heading", 0.0) or 0.0),
                        accuracy=float(row.get("accuracy", 3.0) or 3.0),
                        timestamp=float(row.get("timestamp", time.time()) or time.time())
                    ))

    def close(self) -> None:
        self._is_open = False

    def gps_readings(self) -> Iterator[GPSReading]:
        if not self._readings:
            self.open()
        for r in self._readings:
            if not self._is_open:
                break
            yield r

    @property
    def metadata(self) -> Dict[str, Any]:
        return {"source": "gps_file", "path": str(self.csv_path), "count": len(self._readings)}
