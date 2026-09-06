"""
Replay Engine Player (SIH26124 Section 19).
Deterministic playback of recorded / simulated video & GPS pairs at real-time speed.
Demonstrates multi-class defect detection:
- Potholes
- Missing zebra crossings (no_zebracrossing)
- Vehicle detection
Saves dashcam video recordings and logs defect records into the AI engine.
"""

import base64
import csv
import json
import sys
import time
import argparse
import threading
from pathlib import Path
import urllib.request
import urllib.error

# Ensure root workspace is on Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ai_engine.sensor_interface.contracts import GPSReading, SensorPacket


class ReplayPlayer:
    """Streams synchronized SensorPackets from recorded files into the AI backend."""

    def __init__(
        self,
        device_id: str,
        gps_csv_path: str,
        frame_image_path: str,
        backend_url: str = "http://127.0.0.1:8000",
        speed_multiplier: float = 1.0,
        defect_mode: str = "all"  # "all" | "pothole" | "no_zebracrossing" | "vehicle"
    ):
        self.device_id = device_id
        self.gps_csv_path = Path(gps_csv_path)
        self.frame_image_path = Path(frame_image_path)
        self.backend_url = backend_url
        self.speed_multiplier = max(0.1, speed_multiplier)
        self.defect_mode = defect_mode
        self._frame_base64 = None

    def _load_base64_frame(self) -> str:
        if self._frame_base64 is None and self.frame_image_path.exists():
            with open(self.frame_image_path, "rb") as f:
                raw = f.read()
                self._frame_base64 = f"data:image/jpeg;base64,{base64.b64encode(raw).decode('utf-8')}"
        return self._frame_base64 or ""

    def play(self):
        """Replays packets at real-time paced intervals using virtual demo clock."""
        if not self.gps_csv_path.exists():
            print(f"[ReplayPlayer] Error: GPS log not found at {self.gps_csv_path}")
            return

        with open(self.gps_csv_path, mode="r", encoding="utf-8") as f:
            reader = list(csv.DictReader(f))

        if not reader:
            print("[ReplayPlayer] Empty GPS log")
            return

        print(f"\n[Replay] Starting playback for {self.device_id} ({len(reader)} fixes, {self.speed_multiplier}x speed, Mode: {self.defect_mode})...")
        frame_b64 = self._load_base64_frame()

        for idx, row in enumerate(reader):
            has_defect = int(row.get("has_defect", 0)) == 1
            now = time.time()

            extra_meta = {"source_type": "replay"}

            # Configure multi-class defect injection based on row index and mode
            if has_defect or self.defect_mode == "all":
                mock_defects = []

                if self.defect_mode in ["pothole", "all"] and (has_defect or idx % 3 == 0):
                    mock_defects.append({
                        "class_name": "pothole",
                        "confidence": 0.89,
                        "x": 280,
                        "y": 280,
                        "w": 130,
                        "h": 85
                    })

                if self.defect_mode in ["no_zebracrossing", "all"] and (idx % 3 == 1 or idx == 2):
                    mock_defects.append({
                        "class_name": "no_zebracrossing",
                        "confidence": 0.86,
                        "x": 320,
                        "y": 360,
                        "w": 260,
                        "h": 70
                    })

                if self.defect_mode in ["vehicle", "all"] and (idx % 2 == 0 or idx == 1):
                    mock_defects.append({
                        "class_name": "vehicle",
                        "confidence": 0.93,
                        "x": 420,
                        "y": 210,
                        "w": 100,
                        "h": 75
                    })

                if mock_defects:
                    extra_meta["mock_defect"] = mock_defects[0]
                    if len(mock_defects) > 1:
                        extra_meta["mock_defects"] = mock_defects

            gps = GPSReading(
                latitude=float(row["latitude"]),
                longitude=float(row["longitude"]),
                speed=float(row.get("speed", 22.0)),
                heading=float(row.get("heading", 80.0)),
                accuracy=float(row.get("accuracy", 3.0)),
                timestamp=now
            )

            packet = SensorPacket(
                packet_id=f"pkt_{self.device_id}_{idx}_{int(now*1000)}",
                device_id=self.device_id,
                frame_timestamp=now,
                gps=gps,
                frame_base64=frame_b64,
                extra_metadata=extra_meta
            )

            try:
                payload_bytes = json.dumps(packet.model_dump()).encode('utf-8')
                req = urllib.request.Request(
                    f"{self.backend_url}/ingest/packet",
                    data=payload_bytes,
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=5.0) as response:
                    if response.status == 200:
                        data = json.loads(response.read().decode('utf-8'))
                        fused = data.get("fused_events", [])
                        det_cnt = data.get("detections_count", 0)
                        if fused:
                            ev = fused[0]
                            print(f"  [{self.device_id}] Fix {idx+1}/{len(reader)} -> DETECTED {det_cnt} items! "
                                  f"Event: {ev['event_id'][:8]} Status: {ev['status']} Sources: {ev['unique_sources']} Conf: {ev['confidence']}")
                        else:
                            print(f"  [{self.device_id}] Fix {idx+1}/{len(reader)} -> lat: {gps.latitude:.5f}, lon: {gps.longitude:.5f} (Detections: {det_cnt})")
                    else:
                        print(f"  [{self.device_id}] Ingest error {response.status}")
            except Exception as e:
                print(f"  [{self.device_id}] Request failed: {e}")

            time.sleep(1.0 / self.speed_multiplier)

        # Finalize and save recording on completion
        self._finalize_recording()
        print(f"[Replay] Completed playback for {self.device_id}\n")

    def _finalize_recording(self):
        """Notifies backend to finalize and flush video recording to disk."""
        try:
            req = urllib.request.Request(
                f"{self.backend_url}/model/recordings/finalize",
                data=b"{}",
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=5.0) as res:
                if res.status == 200:
                    print(f"  [{self.device_id}] Video recording saved & indexed successfully.")
        except Exception:
            pass


def run_multi_vehicle_demo(backend_url: str = "http://127.0.0.1:5000", speed: float = 2.0, defect_mode: str = "all"):
    """
    Executes the multi-bus corroboration demo with all defect types running concurrently.
    """
    sample_dir = Path("data/samples")
    frame_path = sample_dir / "pothole_sample_frame.jpg"

    p1 = ReplayPlayer("BUS_01", str(sample_dir / "BUS_01_gps.csv"), str(frame_path), backend_url, speed, defect_mode)
    p2 = ReplayPlayer("BUS_02", str(sample_dir / "BUS_02_gps.csv"), str(frame_path), backend_url, speed, defect_mode)
    p3 = ReplayPlayer("BUS_03", str(sample_dir / "BUS_03_gps.csv"), str(frame_path), backend_url, speed, defect_mode)

    print("==================================================================")
    print("  SIH26124 MULTI-VEHICLE DEFECT & VIDEO RECORDING REPLAY")
    print(f"  Mode: {defect_mode} (potholes, missing zebra crossing, vehicles)")
    print("  Running BUS_01, BUS_02, BUS_03 concurrently on Janpath Corridor...")
    print("==================================================================")

    threads = [
        threading.Thread(target=p1.play, name="BUS_01_Worker"),
        threading.Thread(target=p2.play, name="BUS_02_Worker"),
        threading.Thread(target=p3.play, name="BUS_03_Worker"),
    ]

    for t in threads:
        t.start()
        time.sleep(0.3)  # Stagger fixes slightly for realistic traffic flow

    for t in threads:
        t.join()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Urban Intelligence Replay Player")
    parser.add_argument("--multi", action="store_true", help="Run multi-bus corroboration demo")
    parser.add_argument("--bus", type=str, default="BUS_01", help="Bus ID to replay")
    parser.add_argument("--speed", type=float, default=2.0, help="Playback speed multiplier")
    parser.add_argument("--url", type=str, default="http://127.0.0.1:5000", help="Gateway or FastAPI URL")
    parser.add_argument("--defect-mode", type=str, default="all", choices=["all", "pothole", "no_zebracrossing", "vehicle"], help="Defect type to simulate")
    args = parser.parse_args()

    if args.multi:
        run_multi_vehicle_demo(args.url, args.speed, args.defect_mode)
    else:
        sample_dir = Path("data/samples")
        gps_path = sample_dir / f"{args.bus}_gps.csv"
        frame_path = sample_dir / "pothole_sample_frame.jpg"
        player = ReplayPlayer(args.bus, str(gps_path), str(frame_path), args.url, args.speed, args.defect_mode)
        player.play()
