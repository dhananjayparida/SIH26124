"""
Abstract protocols for Video and GPS data sources.
"""

from typing import Protocol, Iterator, Tuple, Dict, Any
from ..contracts import GPSReading, SensorPacket


class VideoSource(Protocol):
    """Protocol for streaming or reading video frames."""
    def open(self) -> None: ...
    def close(self) -> None: ...
    def frames(self) -> Iterator[Tuple[bytes, float]]:
        """Yields (jpeg_bytes, frame_timestamp)."""
        ...
    @property
    def metadata(self) -> Dict[str, Any]: ...


class GPSSource(Protocol):
    """Protocol for streaming or reading GPS fixes."""
    def open(self) -> None: ...
    def close(self) -> None: ...
    def gps_readings(self) -> Iterator[GPSReading]:
        """Yields GPSReading objects."""
        ...
    @property
    def metadata(self) -> Dict[str, Any]: ...
