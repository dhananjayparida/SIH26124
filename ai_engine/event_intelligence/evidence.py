"""
Evidence packaging module (AI-06).
Stores and manages defect image frames for audit trails and municipal dispatch.
"""

import base64
from pathlib import Path
from typing import Optional


class EvidenceManager:
    """Handles persistent storage of evidence frames."""

    def __init__(self, storage_dir: str = "data/evidence"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def save_base64_snapshot(
        self,
        base64_str: str,
        event_id: str,
        observation_id: str,
        bbox: Optional[list] = None,
        defect_type: Optional[str] = None,
        confidence: Optional[float] = None
    ) -> Optional[str]:
        """
        Decodes and writes JPEG frame to disk with optional bounding box annotations.
        Returns the web-accessible URI path (e.g. /evidence/<filename>.jpg).
        """
        if not base64_str:
            return None

        try:
            data = base64_str
            if "," in data:
                data = data.split(",", 1)[1]
            raw_bytes = base64.b64decode(data)

            filename = f"{event_id[:8]}_{observation_id[:8]}.jpg"
            target_path = self.storage_dir / filename

            # Extract bbox coordinates safely
            x1, y1, x2, y2 = None, None, None, None
            if bbox is not None:
                if hasattr(bbox, "x") and hasattr(bbox, "width"):
                    # BoundingBox object: center (x, y) with width and height
                    bx, by, bw, bh = float(bbox.x), float(bbox.y), float(bbox.width), float(bbox.height)
                    x1 = bx - bw / 2.0
                    y1 = by - bh / 2.0
                    x2 = bx + bw / 2.0
                    y2 = by + bh / 2.0
                elif isinstance(bbox, dict):
                    if "x1" in bbox and "x2" in bbox:
                        x1, y1, x2, y2 = float(bbox["x1"]), float(bbox.get("y1", 0)), float(bbox["x2"]), float(bbox.get("y2", 0))
                    else:
                        bx, by = float(bbox.get("x", 0)), float(bbox.get("y", 0))
                        bw, bh = float(bbox.get("width", bbox.get("w", 0))), float(bbox.get("height", bbox.get("h", 0)))
                        x1 = bx - bw / 2.0
                        y1 = by - bh / 2.0
                        x2 = bx + bw / 2.0
                        y2 = by + bh / 2.0
                elif isinstance(bbox, (list, tuple)) and len(bbox) == 4:
                    x1, y1, x2, y2 = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])

            # Draw visual defect box and label if bbox is available
            if x1 is not None and x2 is not None:
                try:
                    import cv2
                    import numpy as np

                    nparr = np.frombuffer(raw_bytes, np.uint8)
                    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

                    if img is not None:
                        h, w = img.shape[:2]
                        if max(x1, y1, x2, y2) <= 1.05:
                            px1, py1, px2, py2 = int(x1 * w), int(y1 * h), int(x2 * w), int(y2 * h)
                        else:
                            px1, py1, px2, py2 = int(x1), int(y1), int(x2), int(y2)

                        px1, py1 = max(0, px1), max(0, py1)
                        px2, py2 = min(w - 1, px2), min(h - 1, py2)

                        color_map = {
                            "pothole": (0, 0, 238),            # High-visibility Red
                            "no_zebracrossing": (0, 165, 255),  # Amber
                            "zebra_crossing": (0, 200, 0),      # Green
                            "vehicle": (235, 140, 0),          # Cyan / Blue
                            "crack": (0, 100, 255)              # Orange
                        }
                        color = color_map.get(str(defect_type).lower(), (0, 0, 255))

                        # Draw defect rectangle
                        cv2.rectangle(img, (px1, py1), (px2, py2), color, 3)

                        # Tactical corner brackets
                        corner_len = min(20, max(6, (px2 - px1) // 4), max(6, (py2 - py1) // 4))
                        cv2.line(img, (px1, py1), (px1 + corner_len, py1), (255, 255, 255), 3)
                        cv2.line(img, (px1, py1), (px1, py1 + corner_len), (255, 255, 255), 3)
                        cv2.line(img, (px2, py2), (px2 - corner_len, py2), (255, 255, 255), 3)
                        cv2.line(img, (px2, py2), (px2, py2 - corner_len), (255, 255, 255), 3)

                        # Label badge
                        conf_str = f" {int(confidence * 100)}%" if confidence is not None else ""
                        label_text = f"{(defect_type or 'DEFECT').upper()}{conf_str}"

                        font = cv2.FONT_HERSHEY_SIMPLEX
                        font_scale = 0.5
                        thickness = 1
                        (text_w, text_h), _ = cv2.getTextSize(label_text, font, font_scale, thickness)

                        label_y1 = max(0, py1 - text_h - 8)
                        label_y2 = py1
                        cv2.rectangle(img, (px1, label_y1), (px1 + text_w + 10, label_y2), color, -1)
                        cv2.putText(
                            img,
                            label_text,
                            (px1 + 5, label_y2 - 4),
                            font,
                            font_scale,
                            (255, 255, 255),
                            thickness,
                            cv2.LINE_AA
                        )

                        cv2.imwrite(str(target_path), img)
                        return f"/evidence/{filename}"
                except Exception as draw_err:
                    print(f"[EvidenceManager] Annotation drawing note: {draw_err}")

            with open(target_path, "wb") as f:
                f.write(raw_bytes)

            return f"/evidence/{filename}"
        except Exception as e:
            print(f"[EvidenceManager] Failed to write snapshot: {e}")
            return None
