"""
Unit tests for core schemas and validation contracts.
"""

import unittest
from ai_engine.sensor_interface.contracts import GPSReading, SensorPacket, BoundingBox, Detection, Event


class TestContracts(unittest.TestCase):

    def test_valid_gps_reading(self):
        gps = GPSReading(latitude=20.2961, longitude=85.8245, speed=25.0, heading=90.0)
        self.assertEqual(gps.latitude, 20.2961)
        self.assertEqual(gps.longitude, 85.8245)

    def test_invalid_latitude_raises(self):
        with self.assertRaises(ValueError):
            GPSReading(latitude=120.0, longitude=85.0)

    def test_invalid_longitude_raises(self):
        with self.assertRaises(ValueError):
            GPSReading(latitude=20.0, longitude=200.0)

    def test_sensor_packet_creation(self):
        gps = GPSReading(latitude=20.2961, longitude=85.8245)
        packet = SensorPacket(device_id="BUS_01", gps=gps)
        self.assertEqual(packet.device_id, "BUS_01")
        self.assertFalse(packet.is_stale_gps)


if __name__ == "__main__":
    unittest.main()
