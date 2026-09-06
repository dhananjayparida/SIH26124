"""
Phone source adapter for receiving live video frames and GPS telemetry from mobile PWA clients.
"""

import time
from typing import Dict, Any, Optional
from ..contracts import GPSReading, SensorPacket, SourceMetadata
from ..sync import SensorSynchronizer


class PhoneSourceAdapter:
    """Normalizes raw WebSocket or HTTP payloads from the mobile PWA into SensorPacket instances."""

    def __init__(self, synchronizer: Optional[SensorSynchronizer] = None):
        self.synchronizer = synchronizer or SensorSynchronizer()

    def parse_payload(self, raw_data: Dict[str, Any]) -> SensorPacket:
        """
        Parses JSON dictionary sent by phone PWA.
        Expected schema:
        {
            "device_id": "BUS_SIM_01",
            "frame_timestamp": 1725350000.123,
            "latitude": 20.2961,
            "longitude": 85.8245,
            "speed": 22.4,
            "heading": 85.0,
            "accuracy": 4.5,
            "frame_base64": "data:image/jpeg;base64,...",
            "extra_metadata": {}
        }
        """
        device_id = raw_data.get("device_id", "UNKNOWN_DEVICE")
        frame_timestamp = raw_data.get("frame_timestamp", time.time())
        gps_timestamp = raw_data.get("gps_timestamp", frame_timestamp)

        gps_reading = GPSReading(
            latitude=float(raw_data["latitude"]),
            longitude=float(raw_data["longitude"]),
            altitude=raw_data.get("altitude"),
            speed=raw_data.get("speed"),
            heading=raw_data.get("heading"),
            accuracy=raw_data.get("accuracy", 5.0),
            timestamp=gps_timestamp
        )

        packet = SensorPacket(
            device_id=device_id,
            frame_timestamp=frame_timestamp,
            gps=gps_reading,
            frame_base64=raw_data.get("frame_base64"),
            extra_metadata=raw_data.get("extra_metadata", {})
        )

        return self.synchronizer.process_packet(packet)
