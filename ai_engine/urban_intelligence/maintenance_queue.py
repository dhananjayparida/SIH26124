import io
import csv
import time
from datetime import datetime
from typing import List, Dict, Any
from .priority import rank_events
from ..sensor_interface.contracts import Event


class MaintenanceQueueManager:
    """Manages exportable maintenance repair queue with timing intelligence."""

    @staticmethod
    def get_queue(events: List[Event]) -> List[Dict[str, Any]]:
        """Returns sorted list of actionable maintenance items with exact timestamps."""
        ranked = rank_events(events)
        items = []
        now = time.time()
        for rank, ev in enumerate(ranked, start=1):
            created_dt = datetime.fromtimestamp(ev.created_at).strftime("%Y-%m-%d %H:%M:%S")
            age_sec = max(0, round(now - ev.created_at, 1))

            if age_sec < 60:
                age_str = f"{int(age_sec)}s ago"
            elif age_sec < 3600:
                age_str = f"{int(age_sec // 60)}m ago"
            elif age_sec < 86400:
                age_str = f"{int(age_sec // 3600)}h ago"
            else:
                age_str = f"{int(age_sec // 86400)}d ago"

            items.append({
                "rank": rank,
                "event_id": ev.event_id,
                "type": ev.subtype,
                "status": ev.status,
                "severity": ev.severity,
                "priority_score": ev.priority_score,
                "unique_sources": ev.unique_sources,
                "observation_count": ev.observation_count,
                "latitude": ev.latitude,
                "longitude": ev.longitude,
                "created_at": ev.created_at,
                "reported_time": created_dt,
                "age_str": age_str,
                "evidence_url": ev.evidence_uris[0] if ev.evidence_uris else None
            })
        return items

    @staticmethod
    def export_csv(events: List[Event]) -> str:
        """Generates RFC 4180 compliant CSV string for municipal dispatch."""
        queue = MaintenanceQueueManager.get_queue(events)
        output = io.StringIO()
        fieldnames = [
            "rank", "event_id", "type", "status", "severity",
            "priority_score", "unique_sources", "observation_count",
            "reported_time", "age_str", "latitude", "longitude", "evidence_url"
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for item in queue:
            writer.writerow(item)
        return output.getvalue()
