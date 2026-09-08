"""
Core Innovation: Spatio-Temporal Evidence Fusion Engine (AI-05).
Transforms noisy, single-camera defect observations from distributed vehicles into
persistent, corroborated, confidence-scored urban road events.
"""

from datetime import datetime, timezone
from typing import List, Tuple, Optional, Callable
from .spatial_index import haversine_distance_meters, bounding_box_for_radius
from ..sensor_interface.contracts import Observation, Event
from ..specialized.observation_classifier import classify_detection
from ..event_intelligence.severity import assess_event_severity
from ..urban_intelligence.priority import calculate_priority_score


class SpatioTemporalFusionEngine:
    """
    Fuses multiple mobile vehicle observations into unified urban events.
    Enforces strict independent-source corroboration and duplicate suppression.
    """

    def __init__(
        self,
        spatial_radius_meters: float = 25.0,
        temporal_window_sec: float = 30 * 86400.0,  # 30 days for road defects
        on_event_updated: Optional[Callable[[Event, str], None]] = None
    ):
        self.spatial_radius_meters = spatial_radius_meters
        self.temporal_window_sec = temporal_window_sec
        self.on_event_updated = on_event_updated

    def compute_confidence(self, event: Event) -> float:
        """
        Computes multi-source fused event confidence:
        Base = mean(model_confidence across all observations)
        Corroboration Bonus = min(0.3, 0.1 * (unique_sources - 1))
        Final = min(1.0, base + corroboration_bonus)
        """
        if not event.observations:
            return event.model_confidence

        base = sum(o.model_confidence for o in event.observations) / len(event.observations)
        corroboration_bonus = min(0.3, 0.1 * max(0, event.unique_sources - 1))
        return round(min(1.0, base + corroboration_bonus), 3)

    def promote_status(self, event: Event) -> str:
        """
        Advances the event state machine based on independent corroboration.
        If an authority flagged REPAIR_REPORTED and a new observation arrives,
        flip to NEEDS_VERIFICATION.
        """
        if event.status == "REPAIR_REPORTED":
            return "NEEDS_VERIFICATION"
        if event.status in ["RESOLVED", "REJECTED"]:
            # Can remain resolved or reopen as verification needed if re-observed
            return "NEEDS_VERIFICATION"

        if event.unique_sources >= 3:
            return "HIGH_PRIORITY"
        elif event.unique_sources >= 2:
            return "CORROBORATED"
        return "CANDIDATE"

    def find_best_candidate(
        self,
        obs: Observation,
        candidates: List[Event]
    ) -> Tuple[Optional[Event], float]:
        """Finds the nearest spatial candidate event within spatial_radius_meters."""
        best_event = None
        min_dist = float("inf")

        # Derive canonical taxonomy for this observation for robust matching
        raw_obs_name = obs.observation_subtype or obs.defect_type or ""
        canon_type, canon_subtype = classify_detection(raw_obs_name)
        obs_subtypes = {
            (obs.observation_subtype or "").upper(),
            (obs.defect_type or "").upper(),
            (obs.observation_type or "").upper(),
            canon_subtype.upper(),
            canon_type.upper(),
        }

        for event in candidates:
            # Match on observation subtype (canonical or raw class name, case-insensitive)
            cand_subtypes = {
                (event.subtype or "").upper(),
                (event.type or "").upper(),
            }
            if not (cand_subtypes & obs_subtypes):
                continue

            # Check temporal window against latest observation
            time_delta = abs(obs.timestamp - event.updated_at)
            if time_delta > self.temporal_window_sec:
                continue

            dist = haversine_distance_meters(obs.latitude, obs.longitude, event.latitude, event.longitude)
            if dist <= self.spatial_radius_meters and dist < min_dist:
                min_dist = dist
                best_event = event

        return best_event, min_dist

    def fuse_observation(
        self,
        obs: Observation,
        existing_events: List[Event]
    ) -> Tuple[Event, bool]:
        """
        Main fusion entry point:
        Matches an observation against active events.
        If matched, appends observation, recomputes sources and confidence, and advances status.
        If not matched, spawns a new CANDIDATE event.
        Returns (event, is_new).
        """
        now = obs.timestamp or datetime.now(timezone.utc).timestamp()
        matched_event, dist = self.find_best_candidate(obs, existing_events)

        if matched_event is None:
            # Derive canonical taxonomy for this detection
            raw_name = obs.observation_subtype or obs.defect_type or ""
            event_type, event_subtype = classify_detection(raw_name)
            severity = assess_event_severity(
                event_type=event_type,
                event_subtype=event_subtype,
                confidence=obs.model_confidence,
                bbox=obs.bbox
            )
            # Create new CANDIDATE event
            new_event = Event(
                type=event_type,
                subtype=event_subtype,
                latitude=obs.latitude,
                longitude=obs.longitude,
                status="CANDIDATE",
                severity=severity,
                model_confidence=round(obs.model_confidence, 3),
                event_confidence=round(obs.model_confidence, 3),
                unique_sources=1,
                observation_count=1,
                source_vehicle_ids=[obs.device_id],
                evidence_uris=[obs.snapshot_path] if obs.snapshot_path else [],
                created_at=now,
                updated_at=now,
                observations=[obs]
            )
            new_event.priority_score = calculate_priority_score(new_event, current_time=now)
            obs.event_id = new_event.event_id
            if self.on_event_updated:
                self.on_event_updated(new_event, "CREATED")
            return new_event, True
        else:
            # Append observation to matched event
            obs.event_id = matched_event.event_id
            matched_event.observations.append(obs)

            # Recompute distinct unique sources (Duplicate Prevention)
            unique_devs = list(dict.fromkeys(o.device_id for o in matched_event.observations))
            matched_event.source_vehicle_ids = unique_devs
            matched_event.unique_sources = len(unique_devs)
            matched_event.observation_count = len(matched_event.observations)

            # Smooth centroid coordinate towards new observation fix
            n = matched_event.observation_count
            matched_event.latitude = round((matched_event.latitude * (n - 1) + obs.latitude) / n, 6)
            matched_event.longitude = round((matched_event.longitude * (n - 1) + obs.longitude) / n, 6)

            # Update evidence if new snapshot is available
            if obs.snapshot_path and obs.snapshot_path not in matched_event.evidence_uris:
                matched_event.evidence_uris.append(obs.snapshot_path)

            # Recompute confidence and lifecycle status
            matched_event.model_confidence = round(
                sum(o.model_confidence for o in matched_event.observations) / n, 3
            )
            matched_event.event_confidence = self.compute_confidence(matched_event)
            old_status = matched_event.status
            matched_event.status = self.promote_status(matched_event)
            matched_event.severity = assess_event_severity(
                event_type=matched_event.type,
                event_subtype=matched_event.subtype,
                confidence=matched_event.model_confidence,
                bbox=obs.bbox
            )
            matched_event.updated_at = now
            matched_event.priority_score = calculate_priority_score(matched_event, current_time=now)

            transition = f"{old_status}->{matched_event.status}" if old_status != matched_event.status else "UPDATED"
            if self.on_event_updated:
                self.on_event_updated(matched_event, transition)

            return matched_event, False
