"""Extract annotated still images for detections listed in a compact video summary."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2


def extract_snapshots(video_path: Path, source_json: Path, summary_json: Path, output_dir: Path) -> None:
    source = json.loads(source_json.read_text(encoding="utf-8"))
    summary = json.loads(summary_json.read_text(encoding="utf-8"))
    source_by_frame = {
        entry["frame_index"]: entry
        for entry in source["detections"]
        if entry.get("detections")
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")

    try:
        for item in summary["detections"]:
            frame_index = item["frame_index"]
            source_entry = source_by_frame[frame_index]
            capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ok, frame = capture.read()
            if not ok:
                raise RuntimeError(f"Cannot read frame {frame_index} from {video_path}")

            height, width = frame.shape[:2]
            for detection in source_entry["detections"]:
                box = detection["bbox"]
                x1 = max(0, int(box["x"] - box["width"] / 2))
                y1 = max(0, int(box["y"] - box["height"] / 2))
                x2 = min(width, int(box["x"] + box["width"] / 2))
                y2 = min(height, int(box["y"] + box["height"] / 2))
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 238), 3)
                label = f'{detection["class_name"]} {detection["confidence"]:.2f}'
                cv2.putText(
                    frame,
                    label,
                    (x1, max(30, y1 - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.9,
                    (0, 0, 238),
                    2,
                    cv2.LINE_AA,
                )

            cv2.putText(
                frame,
                f"Frame {frame_index} | {item['time_sec']:.3f}s",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )
            filename = f"{item['type']}_frame_{frame_index:05d}.jpg"
            image_path = output_dir / filename
            if not cv2.imwrite(str(image_path), frame):
                raise RuntimeError(f"Cannot write snapshot: {image_path}")
            item["snapshot_path"] = str(image_path).replace("\\", "/")
    finally:
        capture.release()

    summary_json.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {len(summary['detections'])} snapshots to {output_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    extract_snapshots(args.video, args.source, args.summary, args.output_dir)


if __name__ == "__main__":
    main()
