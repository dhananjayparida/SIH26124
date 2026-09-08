---
name: simplify-video-analysis
description: "Convert verbose road-defect video analysis JSON into a compact, human-friendly summary JSON. Use when reviewing video_result files, extracting pothole or road-defect timestamps, or preparing AI detections for frontend, reports, or APIs."
argument-hint: "Provide the source video analysis JSON and the desired output path."
user-invocable: true
disable-model-invocation: false
---

# Simplify Video Analysis

## What This Produces

Create a small JSON file that is easy to read and consume. Keep the video-level totals and flatten each detected defect into a short record.

```json
{
  "video": "video1.mp4",
  "duration_sec": 28.53,
  "frames_sampled": 57,
  "total_detections": 15,
  "fused_events": 1,
  "defect_types": ["pothole"],
  "detections": [
    { "time_sec": 5.005, "type": "pothole", "confidence": 0.503 }
  ]
}
```

## Procedure

1. Read the source JSON and inspect its `meta`, `detections`, and fused-event sections.
2. Copy `video_file`, `video_duration_sec`, `frames_sampled`, `total_detections`, and `total_events` into the compact names shown above.
3. For every nested detection, create one record with `video_time_sec` as `time_sec`, `class_name` as `type`, and `confidence` rounded to three decimal places.
4. Build `defect_types` from the unique detection types, preserving first-seen order.
5. Add the source `frame_index` to each compact detection record.
6. When frame images are requested, use [extract_snapshots.py](../../../replay_engine/extract_snapshots.py) to save one annotated JPEG per detection and add its `snapshot_path`.
7. Omit packet IDs, timestamps, inference timings, bounding boxes, and GPS fields unless the user specifically asks for them.
8. Keep zero-detection runs valid by returning an empty `detections` array and empty `defect_types` array.
9. Write valid UTF-8 JSON with two-space indentation and verify that the detection count equals `total_detections`.

## Decision Rules

- Treat `total_events` as fused events, not raw frame detections.
- Do not treat repeated detections across nearby frames as separate incidents; retain them as observations and preserve the source `fused_events` total.
- Keep GPS out of the compact output when the source coordinates are `0, 0`, because that represents an unavailable location in this project.
- Preserve source values rather than inventing severity, address, or maintenance status.

## Completion Checks

- The output parses as JSON.
- `detections.length` equals `total_detections`.
- Every detection has `time_sec`, `type`, and `confidence`.
- When snapshots are requested, every detection has a readable `snapshot_path`.
- The source JSON remains unchanged.
