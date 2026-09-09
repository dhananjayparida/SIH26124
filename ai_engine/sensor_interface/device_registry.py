"""
Device Registry and Source Health Tracker.
Maintains active device registrations, heartbeats, and determines LIVE/STALE/OFFLINE state.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class DeviceRecord(BaseModel):
    """Internal model for an active mobile sensing vehicle."""
    device_id: str
    source_type: str = "phone_pwa"  # phone_pwa | replay | rtsp
    registered_at: float = Field(default_factory=lambda: datetime.now(timezone.utc).timestamp())
    last_seen: float = Field(default_factory=lambda: datetime.now(timezone.utc).timestamp())
    latest_lat: Optional[float] = None
    latest_lon: Optional[float] = None
    latest_speed: Optional[float] = None
    latest_heading: Optional[float] = None
    packets_sent: int = 0
    detections_reported: int = 0
    status: str = "LIVE"  # LIVE | STALE | OFFLINE


class DeviceRegistry:
    """In-memory or persistent tracking of fleet sensing devices."""

    def __init__(self, stale_threshold_sec: float = 6.0, offline_threshold_sec: float = 20.0):
        self.stale_threshold_sec = stale_threshold_sec
        self.offline_threshold_sec = offline_threshold_sec
        self._devices: Dict[str, DeviceRecord] = {}

    def register(self, device_id: str, source_type: str = "phone_pwa") -> DeviceRecord:
        """Register or re-activate a sensing vehicle."""
        now = datetime.now(timezone.utc).timestamp()
        if device_id in self._devices:
            dev = self._devices[device_id]
            dev.last_seen = now
            dev.source_type = source_type
            dev.status = "LIVE"
            return dev

        record = DeviceRecord(
            device_id=device_id,
            source_type=source_type,
            registered_at=now,
            last_seen=now,
            status="LIVE"
        )
        self._devices[device_id] = record
        return record

    def record_activity(
        self,
        device_id: str,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        speed: Optional[float] = None,
        heading: Optional[float] = None,
        source_type: Optional[str] = None,
        is_detection: bool = False
    ) -> DeviceRecord:
        """Update last seen timestamp and latest geonav coordinates."""
        now = datetime.now(timezone.utc).timestamp()
        if device_id not in self._devices:
            self.register(device_id, source_type=source_type or "phone_pwa")

        dev = self._devices[device_id]
        if source_type:
            dev.source_type = source_type
        dev.last_seen = now
        dev.status = "LIVE"
        dev.packets_sent += 1
        if is_detection:
            dev.detections_reported += 1

        if lat is not None and lon is not None:
            dev.latest_lat = lat
            dev.latest_lon = lon
        if speed is not None:
            dev.latest_speed = speed
        if heading is not None:
            dev.latest_heading = heading

        return dev

    def update_all_statuses(self) -> None:
        """Recalculate LIVE / STALE / OFFLINE statuses across all registered fleet nodes."""
        now = datetime.now(timezone.utc).timestamp()
        for dev in self._devices.values():
            delta = now - dev.last_seen
            if delta <= self.stale_threshold_sec:
                dev.status = "LIVE"
            elif delta <= self.offline_threshold_sec:
                dev.status = "STALE"
            else:
                dev.status = "OFFLINE"

    def get_device(self, device_id: str) -> Optional[DeviceRecord]:
        self.update_all_statuses()
        return self._devices.get(device_id)

    def list_devices(self) -> List[DeviceRecord]:
        self.update_all_statuses()
        return list(self._devices.values())
