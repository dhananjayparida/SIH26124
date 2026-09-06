"""
Core Innovation Tests: Spatio-Temporal Evidence Fusion Engine.
Verifies:
1. Single vehicle observation -> CANDIDATE
2. Duplicate prevention (same vehicle twice) -> remains 1 unique source, remains CANDIDATE
3. Independent second vehicle -> promoted to CORROBORATED with confidence bonus
4. Independent third vehicle -> promoted to HIGH_PRIORITY
5. Spatially distant defect -> separate CANDIDATE event created
"""

import unittest
from ai_engine.sensor_interface.contracts import Observation
from ai_engine.fusion.engine import SpatioTemporalFusionEngine


class TestSpatioTemporalFusion(unittest.TestCase):

    def setUp(self):
        self.fusion = SpatioTemporalFusionEngine(spatial_radius_meters=25.0)
        self.events_db = []

    def test_multi_vehicle_corroboration_lifecycle(self):
        # 1. Bus 01 records pothole at Janpath (lat: 20.29615, lon: 85.82455)
        obs1 = Observation(
            device_id="BUS_01",
            packet_id="pkt_1",
            timestamp=1000.0,
            latitude=20.29615,
            longitude=85.82455,
            defect_type="pothole",
            model_confidence=0.80
        )
        ev1, is_new1 = self.fusion.fuse_observation(obs1, self.events_db)
        self.assertTrue(is_new1)
        self.assertEqual(ev1.status, "CANDIDATE")
        self.assertEqual(ev1.unique_sources, 1)
        self.assertEqual(ev1.observation_count, 1)
        self.assertEqual(ev1.event_confidence, 0.80)
        self.events_db.append(ev1)

        # 2. Duplicate Check: Bus 01 passes again on return trip and detects the same pothole
        obs1_repeat = Observation(
            device_id="BUS_01",
            packet_id="pkt_2",
            timestamp=1200.0,
            latitude=20.29616,  # 1 meter away
            longitude=85.82454,
            defect_type="pothole",
            model_confidence=0.82
        )
        ev_dup, is_new_dup = self.fusion.fuse_observation(obs1_repeat, self.events_db)
        self.assertFalse(is_new_dup)
        self.assertEqual(ev_dup.event_id, ev1.event_id)
        # CRITICAL TEST: Unique sources MUST stay 1, status MUST stay CANDIDATE
        self.assertEqual(ev_dup.unique_sources, 1)
        self.assertEqual(ev_dup.observation_count, 2)
        self.assertEqual(ev_dup.status, "CANDIDATE")

        # 3. Corroboration: Bus 02 (independent vehicle) detects the pothole
        obs2 = Observation(
            device_id="BUS_02",
            packet_id="pkt_3",
            timestamp=1400.0,
            latitude=20.29620,  # ~7 meters away
            longitude=85.82458,
            defect_type="pothole",
            model_confidence=0.85
        )
        ev_corrob, is_new2 = self.fusion.fuse_observation(obs2, self.events_db)
        self.assertFalse(is_new2)
        self.assertEqual(ev_corrob.event_id, ev1.event_id)
        self.assertEqual(ev_corrob.unique_sources, 2)
        self.assertEqual(ev_corrob.observation_count, 3)
        self.assertEqual(ev_corrob.status, "CORROBORATED")
        # Confidence should receive corroboration bonus (+0.1)
        self.assertGreater(ev_corrob.event_confidence, 0.85)

        # 4. High Priority: Bus 03 (third independent vehicle) corroborates
        obs3 = Observation(
            device_id="BUS_03",
            packet_id="pkt_4",
            timestamp=1600.0,
            latitude=20.29618,  # ~4 meters away
            longitude=85.82456,
            defect_type="pothole",
            model_confidence=0.88
        )
        ev_high, is_new3 = self.fusion.fuse_observation(obs3, self.events_db)
        self.assertFalse(is_new3)
        self.assertEqual(ev_high.event_id, ev1.event_id)
        self.assertEqual(ev_high.unique_sources, 3)
        self.assertEqual(ev_high.status, "HIGH_PRIORITY")
        # Confidence should receive 2x corroboration bonus (+0.2)
        self.assertGreater(ev_high.event_confidence, 0.95)

        # 5. Out of bounds detection: Bus 01 spots a defect 500m away at Master Canteen
        obs_far = Observation(
            device_id="BUS_01",
            packet_id="pkt_5",
            timestamp=1800.0,
            latitude=20.29100,  # ~570 meters away
            longitude=85.82000,
            defect_type="pothole",
            model_confidence=0.75
        )
        ev_far, is_new_far = self.fusion.fuse_observation(obs_far, self.events_db)
        self.assertTrue(is_new_far)
        self.assertNotEqual(ev_far.event_id, ev1.event_id)
        self.assertEqual(ev_far.status, "CANDIDATE")
        self.assertEqual(ev_far.unique_sources, 1)


if __name__ == "__main__":
    unittest.main()
