"""
Sample Data Generator for Bhubaneswar Bus Fleet Demo.
Generates paired GPS telemetry logs and defect image frames.
"""

import csv
import io
import time
import shutil
from pathlib import Path
from PIL import Image, ImageDraw


def generate_sample_data(output_dir: str = "data/samples"):
    """
    Creates GPS logs and defect frames for buses:
    - BUS_01 passes a pothole at (lat 20.18150, lon 85.74050) at step 5 — GITA College Road
    - BUS_02 passes the same pothole at step 5 slightly later
    - BUS_03 passes at step 6
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    base_lat = 20.1800
    base_lon = 85.7380

    # 1. Provide genuine defect frame for perception model
    frame_path = out_path / "pothole_sample_frame.jpg"
    real_sample = Path("data/training_dataset/images/sample_BUS_LIVE_01_1788792545373.jpg")
    if real_sample.exists():
        shutil.copyfile(real_sample, frame_path)
        print(f"[Sample Generator] Copied genuine road defect frame from {real_sample} to {frame_path}")
    else:
        # Fallback realistic road texture frame
        img = Image.new("RGB", (640, 480), color=(50, 52, 55))
        draw = ImageDraw.Draw(img)
        draw.line([(320, 0), (320, 480)], fill=(220, 220, 220), width=4)
        draw.ellipse([(240, 220), (400, 340)], fill=(18, 18, 20), outline=(80, 80, 85), width=4)
        img.save(frame_path, format="JPEG", quality=90)
        print(f"[Sample Generator] Created fallback frame at {frame_path}")

    # 2. Generate GPS CSV routes for BUS_01, BUS_02, BUS_03
    for bus_id in ["BUS_01", "BUS_02", "BUS_03"]:
        csv_file = out_path / f"{bus_id}_gps.csv"
        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "latitude", "longitude", "speed", "heading", "accuracy", "has_defect"])

            curr_lat = base_lat
            curr_lon = base_lon
            t = time.time()

            for i in range(12):
                has_defect = (i == 5)
                # Defect coordinate at step 5
                if has_defect:
                    lat = 20.18150 + (0.00005 if bus_id == "BUS_02" else 0.0)
                    lon = 85.74050 + (0.00004 if bus_id == "BUS_02" else 0.0)
                else:
                    lat = curr_lat
                    lon = curr_lon

                writer.writerow([
                    round(t + (i * 2.0), 3),
                    round(lat, 6),
                    round(lon, 6),
                    round(24.5 + (i % 3), 1),
                    82.0,
                    3.5,
                    1 if has_defect else 0
                ])

                curr_lat += 0.0008
                curr_lon += 0.0007

        print(f"[Sample Generator] Created GPS route for {bus_id} at {csv_file}")


if __name__ == "__main__":
    generate_sample_data()
