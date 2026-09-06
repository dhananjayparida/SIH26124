"""
Unit tests for sensor synchronization and GPS interpolation.
"""

import unittest
from ai_engine.sensor_interface.contracts import GPSReading, SensorPacket
from ai_engine.sensor_interface.sync import SensorSynchronizer, ClockSkewError


class TestSync(unittest.TestCase):

    def setUp(self):
        self.sync = SensorSynchronizer(max_clock_skew_sec=3.0, stale_gps_threshold_sec=5.0)

    def test_clock_skew_within_limits(self):
        client_t = 1000.0
        server_t = 1001.5
        validated = self.sync.validate_timestamp(client_t, server_t)
        self.assertEqual(validated, 1000.0)

    def test_clock_skew_exceeded(self):
        client_t = 1000.0
        server_t = 1005.0
        with self.assertRaises(ClockSkewError):
            self.sync.validate_timestamp(client_t, server_t)

    def test_gps_interpolation(self):
        gps1 = GPSReading(latitude=20.0, longitude=85.0, speed=10.0, timestamp=100.0)
        gps2 = GPSReading(latitude=20.002, longitude=85.002, speed=20.0, timestamp=110.0)
        target_t = 105.0  # Midpoint

        interp = self.sync.interpolate_gps(gps1, gps2, target_t)
        self.assertAlmostEqual(interp.latitude, 20.001, places=5)
        self.assertAlmostEqual(interp.longitude, 85.001, places=5)
        self.assertAlmostEqual(interp.speed, 15.0, places=2)

    def test_stale_gps_flagging(self):
        gps = GPSReading(latitude=20.0, longitude=85.0, timestamp=100.0)
        packet = SensorPacket(
            device_id="BUS_01",
            frame_timestamp=107.0,  # 7s later (> 5s threshold)
            gps=gps
        )
        processed = self.sync.process_packet(packet, server_timestamp=107.0)
        self.assertTrue(processed.is_stale_gps)


if __name__ == "__main__":
    unittest.main()
