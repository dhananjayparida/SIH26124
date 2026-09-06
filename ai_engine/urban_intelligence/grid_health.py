"""
Grid-cell road health scoring and hotspot detection (AI-07).
Provides a lightweight spatial grid proxy for road segment condition awareness.
"""

from typing import List, Dict, Any
from ..sensor_interface.contracts import Event


class GridHealthEngine:
    """Calculates road health index per geographic grid cell."""

    def __init__(self, cell_size_degrees: float = 0.004):  # ~400m cells
        self.cell_size = cell_size_degrees

    def _get_cell_key(self, lat: float, lon: float) -> str:
        grid_lat = round(lat / self.cell_size) * self.cell_size
        grid_lon = round(lon / self.cell_size) * self.cell_size
        return f"{grid_lat:.4f}_{grid_lon:.4f}"

    def compute_grid_health(self, events: List[Event]) -> List[Dict[str, Any]]:
        """
        Computes health score [0 - 100] for each active spatial grid cell.
        100 = Excellent road conditions (0 defects)
        50-75 = Moderate degradation (warning/yellow)
        < 50 = Severe degradation (critical/red)
        """
        cells: Dict[str, Dict[str, Any]] = {}

        for ev in events:
            if ev.status in ["RESOLVED", "REJECTED"]:
                continue

            key = self._get_cell_key(ev.latitude, ev.longitude)
            if key not in cells:
                lat_center = float(key.split("_")[0])
                lon_center = float(key.split("_")[1])
                half = self.cell_size / 2.0
                cells[key] = {
                    "cell_id": key,
                    "center": [lat_center, lon_center],
                    "bounds": [
                        [lat_center - half, lon_center - half],
                        [lat_center + half, lon_center + half]
                    ],
                    "event_count": 0,
                    "high_priority_count": 0,
                    "defect_types": set(),
                    "events": []
                }

            c = cells[key]
            c["event_count"] += 1
            if ev.status == "HIGH_PRIORITY" or ev.severity == "HIGH":
                c["high_priority_count"] += 1
            c["defect_types"].add(ev.subtype)
            c["events"].append(ev.event_id)

        results = []
        for cell in cells.values():
            # Heuristic health deduction
            deduction = (cell["event_count"] * 12) + (cell["high_priority_count"] * 18)
            health_score = max(10, 100 - deduction)

            status = "GOOD"
            color = "#10b981"  # Emerald green
            if health_score < 50:
                status = "CRITICAL"
                color = "#ef4444"  # Red
            elif health_score < 75:
                status = "WARNING"
                color = "#f59e0b"  # Amber

            results.append({
                "cell_id": cell["cell_id"],
                "center": cell["center"],
                "bounds": cell["bounds"],
                "health_score": health_score,
                "status": status,
                "color": color,
                "event_count": cell["event_count"],
                "high_priority_count": cell["high_priority_count"],
                "defect_types": list(cell["defect_types"])
            })

        return sorted(results, key=lambda x: x["health_score"])
