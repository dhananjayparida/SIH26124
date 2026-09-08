import sys
from pathlib import Path
from PIL import Image

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from ultralytics import YOLO
from ai_engine.perception.detector import RoadDefectDetector
from ai_engine.sensor_interface.contracts import SensorPacket, GPSReading
import base64

def test_pothole_detection():
    print("=" * 60)
    print("  VERIFYING POTHOLE DETECTION CAPABILITY")
    print("=" * 60)
    
    # 1. Inspect model checkpoint
    model_path = ROOT_DIR / "models" / "best_road_defect_model.pt"
    print(f"Loading checkpoint: {model_path}")
    model = YOLO(str(model_path))
    print(f"Model classes: {model.names}")
    
    # 2. Test direct YOLO inference on pothole sample image
    pothole_img_path = ROOT_DIR / "data" / "samples" / "pothole_sample_frame.jpg"
    print(f"\nTesting direct inference on: {pothole_img_path}")
    results = model.predict(source=str(pothole_img_path), conf=0.15, verbose=False)
    
    detected = False
    for r in results:
        for box in r.boxes:
            cls_id = int(box.cls[0])
            cls_name = model.names[cls_id]
            conf = float(box.conf[0])
            xyxy = [round(float(x), 1) for x in box.xyxy[0]]
            print(f"  Direct YOLO -> Class: '{cls_name}' | Conf: {conf:.3f} | BBox: {xyxy}")
            if "pothole" in cls_name.lower():
                detected = True

    # 3. Also test on validation dataset samples
    val_images = list((ROOT_DIR / "data" / "training_dataset" / "best" / "val" / "images").glob("*.jpg"))
    print(f"\nTesting on {len(val_images)} validation dataset images:")
    for img_path in val_images[:3]:
        res = model.predict(source=str(img_path), conf=0.10, verbose=False)
        for r in res:
            for box in r.boxes:
                cls_id = int(box.cls[0])
                cls_name = model.names[cls_id]
                conf = float(box.conf[0])
                print(f"  [{img_path.name}] Detected: {cls_name} ({conf:.2f})")

    # 4. Test RoadDefectDetector end-to-end with SensorPacket
    print("\nTesting RoadDefectDetector perception engine:")
    detector = RoadDefectDetector(confidence_threshold=0.20)
    with open(pothole_img_path, "rb") as f:
        b64 = "data:image/jpeg;base64," + base64.b64encode(f.read()).decode()
    
    packet = SensorPacket(
        device_id="BUS_01",
        frame_timestamp=1788413682.0,
        gps=GPSReading(latitude=20.29615, longitude=85.82455, timestamp=1788413682.0),
        frame_base64=b64
    )
    det_result = detector.detect(packet)
    print(f"Detector returned {len(det_result.detections)} detections in {det_result.inference_time_ms:.1f}ms:")
    for d in det_result.detections:
        print(f"  Class: {d.class_name} | Confidence: {d.confidence:.3f} | Box: {d.bbox}")

    print("=" * 60)

if __name__ == "__main__":
    test_pothole_detection()
