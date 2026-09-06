"""
Defect Recording Ledger (SIH26124).
Persistently records, indexes, and queries defect instances:
- Potholes & road damage
- Missing zebra crossings (no_zebracrossing)
- Detected vehicles (traffic presence / density)
"""

import json
import time
import threading
from pathlib import Path
from typing import List, Dict, Any, Optional
from uuid import uuid4

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
DEFECT_LOG_PATH = DATA_DIR / "defect_records.json"

DATA_DIR.mkdir(parents=True, exist_ok=True)


class DefectRecord:
    """Represents a single recorded defective road or safety event."""

    def __init__(
        self,
        defect_type: str,
        confidence: float,
        latitude: float,
        longitude: float,
        device_id: str,
        record_id: Optional[str] = None,
        severity: str = "MEDIUM",
        bbox: Optional[Dict[str, float]] = None,
        speed: Optional[float] = None,
        heading: Optional[float] = None,
        snapshot_uri: Optional[str] = None,
        video_clip: Optional[str] = None,
        timestamp: Optional[float] = None,
        notes: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ):
        self.record_id = record_id or f"def_{uuid4().hex[:12]}"
        self.defect_type = defect_type.lower()
        self.severity = severity.upper()
        self.confidence = round(float(confidence), 3)
        self.latitude = float(latitude)
        self.longitude = float(longitude)
        self.speed = float(speed) if speed is not None else 0.0
        self.heading = float(heading) if heading is not None else 0.0
        self.device_id = device_id
        self.bbox = bbox or {}
        self.snapshot_uri = snapshot_uri
        self.video_clip = video_clip
        self.timestamp = timestamp or time.time()
        self.notes = notes or ""
        self.extra = extra or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "defect_type": self.defect_type,
            "severity": self.severity,
            "confidence": self.confidence,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "speed": self.speed,
            "heading": self.heading,
            "device_id": self.device_id,
            "bbox": self.bbox,
            "snapshot_uri": self.snapshot_uri,
            "video_clip": self.video_clip,
            "timestamp": self.timestamp,
            "timestamp_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.timestamp)),
            "notes": self.notes,
            "extra": self.extra,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DefectRecord":
        return cls(
            record_id=d.get("record_id"),
            defect_type=d.get("defect_type", "pothole"),
            severity=d.get("severity", "MEDIUM"),
            confidence=d.get("confidence", 0.8),
            latitude=d.get("latitude", 0.0),
            longitude=d.get("longitude", 0.0),
            device_id=d.get("device_id", "unknown"),
            bbox=d.get("bbox"),
            speed=d.get("speed"),
            heading=d.get("heading"),
            snapshot_uri=d.get("snapshot_uri"),
            video_clip=d.get("video_clip"),
            timestamp=d.get("timestamp"),
            notes=d.get("notes"),
            extra=d.get("extra"),
        )


class DefectLedger:
    """
    Thread-safe ledger for recording defective observations and querying defect analytics.
    """

    def __init__(self, log_path: Path = DEFECT_LOG_PATH):
        self.log_path = log_path
        self._lock = threading.Lock()
        self._records: List[DefectRecord] = []
        self._load()

    def _load(self):
        with self._lock:
            if self.log_path.exists():
                try:
                    with open(self.log_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        self._records = [DefectRecord.from_dict(r) for r in data]
                except Exception as e:
                    print(f"[DefectLedger] Error loading log: {e}")
                    self._records = []
            else:
                self._records = []

    def _save(self):
        try:
            with open(self.log_path, "w", encoding="utf-8") as f:
                json.dump([r.to_dict() for r in self._records], f, indent=2)
        except Exception as e:
            print(f"[DefectLedger] Error saving log: {e}")

    def record_defect(
        self,
        defect_type: str,
        confidence: float,
        latitude: float,
        longitude: float,
        device_id: str,
        severity: str = "MEDIUM",
        bbox: Optional[Dict[str, float]] = None,
        speed: Optional[float] = None,
        heading: Optional[float] = None,
        snapshot_uri: Optional[str] = None,
        video_clip: Optional[str] = None,
        notes: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> DefectRecord:
        """Appends a new defect record and persists to disk."""
        record = DefectRecord(
            defect_type=defect_type,
            confidence=confidence,
            latitude=latitude,
            longitude=longitude,
            device_id=device_id,
            severity=severity,
            bbox=bbox,
            speed=speed,
            heading=heading,
            snapshot_uri=snapshot_uri,
            video_clip=video_clip,
            notes=notes,
            extra=extra,
        )
        with self._lock:
            self._records.append(record)
            self._save()
        return record

    def list_defects(
        self,
        defect_type: Optional[str] = None,
        severity: Optional[str] = None,
        device_id: Optional[str] = None,
        min_confidence: float = 0.0,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Queries recorded defects with filtering options."""
        with self._lock:
            filtered = self._records[:]

        if defect_type:
            filtered = [r for r in filtered if defect_type.lower() in r.defect_type.lower()]
        if severity:
            filtered = [r for r in filtered if r.severity.upper() == severity.upper()]
        if device_id:
            filtered = [r for r in filtered if r.device_id == device_id]
        if min_confidence > 0.0:
            filtered = [r for r in filtered if r.confidence >= min_confidence]

        # Order by newest first
        filtered.sort(key=lambda r: r.timestamp, reverse=True)
        paginated = filtered[offset : offset + limit]
        return [r.to_dict() for r in paginated]

    def get_summary(self) -> Dict[str, Any]:
        """Returns aggregated summary counts of all defect recordings."""
        with self._lock:
            records = self._records[:]

        total = len(records)
        by_type: Dict[str, int] = {}
        by_severity: Dict[str, int] = {}
        by_device: Dict[str, int] = {}

        pothole_count = 0
        no_zebracrossing_count = 0
        vehicle_count = 0

        for r in records:
            # Count by type
            by_type[r.defect_type] = by_type.get(r.defect_type, 0) + 1
            # Count by severity
            by_severity[r.severity] = by_severity.get(r.severity, 0) + 1
            # Count by device
            by_device[r.device_id] = by_device.get(r.device_id, 0) + 1

            if "pothole" in r.defect_type:
                pothole_count += 1
            elif "no_zebra" in r.defect_type or "zebra" in r.defect_type:
                no_zebracrossing_count += 1
            elif "vehicle" in r.defect_type or r.defect_type in ["car", "bus", "truck", "motorcycle"]:
                vehicle_count += 1

        return {
            "total_defects": total,
            "pothole_count": pothole_count,
            "no_zebracrossing_count": no_zebracrossing_count,
            "vehicle_count": vehicle_count,
            "by_type": by_type,
            "by_severity": by_severity,
            "by_device": by_device,
            "latest_record_time": records[-1].timestamp if records else None,
        }

    def clear(self):
        """Clears all records (used for testing)."""
        with self._lock:
            self._records = []
            self._save()


# Global singleton instance
global_defect_ledger = DefectLedger()
