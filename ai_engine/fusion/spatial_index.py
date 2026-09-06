"""
Spatial utilities and Haversine distance calculations for multi-vehicle fusion.
"""

import math
from typing import Tuple


def haversine_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Computes great-circle distance between two WGS84 geographic coordinates in meters.
    """
    R = 6371000.0  # Earth's mean radius in meters

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    return R * c


def bounding_box_for_radius(lat: float, lon: float, radius_meters: float) -> Tuple[float, float, float, float]:
    """
    Returns (min_lat, max_lat, min_lon, max_lon) for rapid spatial pre-filtering.
    """
    lat_delta = radius_meters / 111139.0
    # Lon delta adjusts for latitude shrinking
    lon_delta = radius_meters / (111139.0 * max(0.01, math.cos(math.radians(lat))))

    return (
        lat - lat_delta,
        lat + lat_delta,
        lon - lon_delta,
        lon + lon_delta
    )
