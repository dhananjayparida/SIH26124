"""
Priority scoring and ranking module (AI-07).
Heuristic priority formula:
priority_score = 0.4 * severity + 0.4 * unique_sources + 0.2 * (1 / days_since_last_observation)
"""

import time
from typing import Dict, List
from ..sensor_interface.contracts import Event

SEVERITY_WEIGHTS: Dict[str, float] = {
    "LOW": 0.33,
    "MEDIUM": 0.66,
    "HIGH": 1.0
}


def calculate_priority_score(event: Event, current_time: float = None) -> float:
    """Computes normalized priority ranking score [0.0, 1.0] for municipal dispatch."""
    if current_time is None:
        current_time = time.time()

    # Severity factor [0.33, 1.0]
    sev_weight = SEVERITY_WEIGHTS.get(event.severity, 0.5)

    # Unique sources corroboration factor [0.33, 1.0]
    sources_factor = min(1.0, max(0.33, event.unique_sources / 3.0))

    # Recency factor: 1 / days_since_last_seen
    delta_days = max(0.1, (current_time - event.updated_at) / 86400.0)
    recency_factor = min(1.0, 1.0 / delta_days)

    score = 0.4 * sev_weight + 0.4 * sources_factor + 0.2 * recency_factor
    return round(score, 3)


def rank_events(events: List[Event]) -> List[Event]:
    """Sorts open events by descending priority score."""
    open_events = [e for e in events if e.status not in ["RESOLVED", "REJECTED"]]
    for e in open_events:
        e.priority_score = calculate_priority_score(e)
    return sorted(open_events, key=lambda x: x.priority_score, reverse=True)
