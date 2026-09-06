"""
Sample Data Generator for Bhubaneswar Bus Fleet Demo.
Generates paired GPS telemetry logs and defect image frames along Janpath Road, Bhubaneswar.
"""

import csv
import io
import time
from pathlib import Path
from PIL import Image, ImageDraw


def generate_sample_data(output_dir: str = "data/samples"):
    """
    Creates GPS logs and defect frames for two buses traversing Janpath Road:
    - BUS_01 passes a pothole at (lat 20.29615, lon 85.82455) at step 5
    - BUS_02 passes the same pothole at step 5 slightly later
    - BUS_03 passes at step 6
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # Base coordinates: Master Canteen to Vani Vihar along Janpath, Bhubaneswar
    base_lat = 20.2920
    base_lon = 85.8210

    # 1. Generate defect frame (simulated pothole on asphalt)
    img = Image.new("RGB", (640, 480), color=(60, 62, 65))
    draw = ImageDraw.Draw(img)
    # Asphalt lane markings
    draw.line([(320, 0), (320, 480)], fill=(230, 230, 230), width=4)
    # Pothole crater
    draw.ellipse([(260, 240), (380, 320)], fill=(20, 20, 22), outline=(100, 100, 105), width=3)
    draw.text((20, 20), "BHUBANESWAR JANPATH SURVEILLANCE - BUS_FLEET", fill=(200, 200, 200))

    frame_path = out_path / "pothole_sample_frame.jpg"
    img.save(frame_path, format="JPEG", quality=85)
    print(f"[Sample Generator] Created sample frame at {frame_path}")

    # 2. Generate GPS CSV routes for BUS_01 and BUS_02
    for bus_id in ["BUS_01", "BUS_02", "BUS_03"]:
        csv_file = out_path / f"{bus_id}_gps.csv"
        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "latitude", "longitude", "speed", "heading", "accuracy", "has_defect"])

            # 12 steps along the road
            curr_lat = base_lat
            curr_lon = base_lon
            t = time.time()

            for i in range(12):
                has_defect = (i == 5)
                # Defect coordinate at step 5
                if has_defect:
                    lat = 20.29615 + (0.00005 if bus_id == "BUS_02" else 0.0)
                    lon = 85.82455 + (0.00004 if bus_id == "BUS_02" else 0.0)
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
