"""Regression tests for additive fleet identity and lifecycle behavior."""

import time
import unittest

from ai_engine.sensor_interface.device_registry import DeviceRegistry
from ai_engine.sensor_interface.contracts import Observation
from ai_engine.fusion.engine import SpatioTemporalFusionEngine


class TestDeviceLifecycle(unittest.TestCase):
    def test_devices_keep_independent_identity_and_source_type(self):
        registry = DeviceRegistry(stale_threshold_sec=5.0, offline_threshold_sec=10.0)
        first = registry.record_activity("BUS_01", lat=20.1, lon=85.8, source_type="phone_pwa")
        second = registry.record_activity("BUS_02", lat=20.2, lon=85.9, source_type="replay")

        self.assertNotEqual(first.device_id, second.device_id)
        self.assertEqual(first.source_type, "phone_pwa")
        self.assertEqual(second.source_type, "replay")

    def test_lifecycle_recalculates_from_last_activity(self):
        registry = DeviceRegistry(stale_threshold_sec=5.0, offline_threshold_sec=10.0)
        device = registry.record_activity("BUS_01", source_type="phone_pwa")
        device.last_seen = time.time() - 6.0
        registry.update_all_statuses()
        self.assertEqual(registry.get_device("BUS_01").status, "STALE")

        device.last_seen = time.time() - 11.0
        registry.update_all_statuses()
        self.assertEqual(registry.get_device("BUS_01").status, "OFFLINE")


class TestDistinctSourceCorroboration(unittest.TestCase):
    @staticmethod
    def observation(device_id, timestamp):
        return Observation(
            device_id=device_id, packet_id=f"{device_id}-{timestamp}", timestamp=timestamp,
            latitude=20.2961, longitude=85.8245, defect_type="pothole", model_confidence=0.90,
        )

    def test_same_bus_repeats_do_not_become_multiple_sources(self):
        engine = SpatioTemporalFusionEngine(spatial_radius_meters=25.0)
        event, _ = engine.fuse_observation(self.observation("BUS_01", 1000.0), [])
        event, _ = engine.fuse_observation(self.observation("BUS_01", 1001.0), [event])
        self.assertEqual(event.observation_count, 2)
        self.assertEqual(event.unique_sources, 1)
        self.assertEqual(event.status, "CANDIDATE")

    def test_second_bus_is_an_independent_source(self):
        engine = SpatioTemporalFusionEngine(spatial_radius_meters=25.0)
        event, _ = engine.fuse_observation(self.observation("BUS_01", 1000.0), [])
        event, _ = engine.fuse_observation(self.observation("BUS_02", 1001.0), [event])
        self.assertEqual(event.unique_sources, 2)
        self.assertEqual(event.source_vehicle_ids, ["BUS_01", "BUS_02"])
        self.assertEqual(event.status, "CORROBORATED")


if __name__ == "__main__":
    unittest.main()
