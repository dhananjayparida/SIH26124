"""
Temporal synchronization and GPS interpolation module.
Reconciles device clocks against server receipt time and interpolates spatial coordinates
for frames captured between GPS fixes.
"""

from datetime import datetime, timezone
from typing import Optional, Tuple
from .contracts import GPSReading, SensorPacket


class ClockSkewError(ValueError):
    """Raised when client device clock is excessively out of sync with server."""
    pass


class SensorSynchronizer:
    """Handles clock skew validation, linear GPS interpolation, and staleness detection."""

    def __init__(self, max_clock_skew_sec: float = 3.0, stale_gps_threshold_sec: float = 5.0):
        self.max_clock_skew_sec = max_clock_skew_sec
        self.stale_gps_threshold_sec = stale_gps_threshold_sec

    def validate_timestamp(self, client_timestamp: float, server_timestamp: Optional[float] = None) -> float:
        """
        Validates client timestamp against server time.
        Raises ClockSkewError if delta exceeds max_clock_skew_sec.
        """
        if server_timestamp is None:
            server_timestamp = datetime.now(timezone.utc).timestamp()

        skew = abs(server_timestamp - client_timestamp)
        if skew > self.max_clock_skew_sec:
            raise ClockSkewError(
                f"Clock skew of {skew:.2f}s exceeds allowable threshold of {self.max_clock_skew_sec}s. "
                f"Client: {client_timestamp}, Server: {server_timestamp}"
            )
        return client_timestamp

    def interpolate_gps(
        self,
        gps_before: GPSReading,
        gps_after: GPSReading,
        target_timestamp: float
    ) -> GPSReading:
        """
        Linearly interpolates geographic coordinates between two fixes.
        Requires gps_before.timestamp <= target_timestamp <= gps_after.timestamp.
        """
        t1 = gps_before.timestamp
        t2 = gps_after.timestamp

        if t1 == t2:
            return gps_before

        # Calculate fractional interpolation factor [0.0, 1.0]
        alpha = (target_timestamp - t1) / (t2 - t1)
        alpha = max(0.0, min(1.0, alpha))

        interp_lat = gps_before.latitude + alpha * (gps_after.latitude - gps_before.latitude)
        interp_lon = gps_before.longitude + alpha * (gps_after.longitude - gps_before.longitude)

        interp_alt = None
        if gps_before.altitude is not None and gps_after.altitude is not None:
            interp_alt = gps_before.altitude + alpha * (gps_after.altitude - gps_before.altitude)

        interp_speed = None
        if gps_before.speed is not None and gps_after.speed is not None:
            interp_speed = gps_before.speed + alpha * (gps_after.speed - gps_before.speed)

        # Heading angular interpolation
        interp_heading = None
        if gps_before.heading is not None and gps_after.heading is not None:
            diff = (gps_after.heading - gps_before.heading + 180.0) % 360.0 - 180.0
            interp_heading = (gps_before.heading + alpha * diff) % 360.0

        return GPSReading(
            latitude=interp_lat,
            longitude=interp_lon,
            altitude=interp_alt,
            speed=interp_speed,
            heading=interp_heading,
            accuracy=max(gps_before.accuracy or 5.0, gps_after.accuracy or 5.0),
            timestamp=target_timestamp
        )

    def process_packet(self, packet: SensorPacket, server_timestamp: Optional[float] = None) -> SensorPacket:
        """
        Validates packet timing and checks for GPS staleness.
        Modifies packet.is_stale_gps if age exceeds stale_gps_threshold_sec.
        """
        if server_timestamp is None:
            server_timestamp = datetime.now(timezone.utc).timestamp()

        # Check clock skew on frame timestamp
        self.validate_timestamp(packet.frame_timestamp, server_timestamp)

        # Check GPS age vs frame timestamp
        gps_age = abs(packet.frame_timestamp - packet.gps.timestamp)
        if gps_age > self.stale_gps_threshold_sec:
            packet.is_stale_gps = True

        return packet
