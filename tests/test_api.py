"""
End-to-end API integration tests for FastAPI AI service.
Verifies packet ingestion, event querying, fleet status, and urban intelligence endpoints.
"""

import unittest
from fastapi.testclient import TestClient
from backend.ai_service.main import app


class TestAPIService(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_root_health(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "online")

    def test_ingest_packet_and_fusion_flow(self):
        import time
        # Generate fresh unique test coordinate
        t_off = (time.time() % 100) * 0.001
        test_lat = 21.1000 + t_off
        test_lon = 86.1000 + t_off

        # 1. Ingest packet from BUS_01 with simulated defect at isolated test coordinate
        packet_bus1 = {
            "packet_id": f"pkt_test_1_{time.time()}",
            "device_id": "BUS_SIM_TEST_01",
            "frame_timestamp": 1725350000.0,
            "gps": {
                "latitude": test_lat,
                "longitude": test_lon,
                "speed": 22.0,
                "heading": 80.0,
                "accuracy": 3.0,
                "timestamp": 1725350000.0
            },
            "extra_metadata": {
                "is_test_fixture": True,
                "mock_defect": {
                    "class_name": "pothole",
                    "confidence": 0.85,
                    "x": 300,
                    "y": 250,
                    "w": 120,
                    "h": 80
                }
            }
        }
        res1 = self.client.post("/ingest/packet", json=packet_bus1)
        self.assertEqual(res1.status_code, 200)
        data1 = res1.json()
        self.assertEqual(data1["detections_count"], 1)
        ev1 = data1["fused_events"][0]
        self.assertEqual(ev1["status"], "CANDIDATE")
        self.assertEqual(ev1["unique_sources"], 1)
        event_id = ev1["event_id"]

        # 2. Ingest packet from BUS_02 corroborating the same pothole
        packet_bus2 = {
            "packet_id": f"pkt_test_2_{time.time()}",
            "device_id": "BUS_SIM_TEST_02",
            "frame_timestamp": 1725350005.0,
            "gps": {
                "latitude": test_lat + 0.00003,  # ~3m away
                "longitude": test_lon + 0.00002,
                "speed": 24.0,
                "heading": 82.0,
                "accuracy": 3.0,
                "timestamp": 1725350005.0
            },
            "extra_metadata": {
                "is_test_fixture": True,
                "mock_defect": {
                    "class_name": "pothole",
                    "confidence": 0.88,
                    "x": 310,
                    "y": 255,
                    "w": 115,
                    "h": 85
                }
            }
        }
        res2 = self.client.post("/ingest/packet", json=packet_bus2)
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()
        ev2 = data2["fused_events"][0]
        # Must corroborate same event into CORROBORATED
        self.assertEqual(ev2["event_id"], event_id)
        self.assertEqual(ev2["status"], "CORROBORATED")
        self.assertEqual(ev2["unique_sources"], 2)

        # 3. Query event details & verify Urban Memory timeline
        detail_res = self.client.get(f"/events/{event_id}")
        self.assertEqual(detail_res.status_code, 200)
        detail = detail_res.json()
        self.assertEqual(len(detail["urban_memory_timeline"]), 2)
        self.assertEqual(detail["status"], "CORROBORATED")

        # 4. Municipal workflow: mark repair reported
        repair_res = self.client.post(f"/events/{event_id}/repair-report", json={"authority": "BMC Crew #4"})
        self.assertEqual(repair_res.status_code, 200)
        self.assertEqual(repair_res.json()["event_status"], "REPAIR_REPORTED")

        # 5. Verify HUD summary
        hud_res = self.client.get("/hud/summary")
        self.assertEqual(hud_res.status_code, 200)
        hud = hud_res.json()
        self.assertGreaterEqual(hud["open_events"], 1)

        # 6. Verify Maintenance Queue & CSV export
        q_res = self.client.get("/maintenance/queue")
        self.assertEqual(q_res.status_code, 200)
        self.assertIsInstance(q_res.json(), list)

        csv_res = self.client.get("/maintenance/export-csv")
        self.assertEqual(csv_res.status_code, 200)
        self.assertIn("rank,event_id,type", csv_res.text)

    def test_defect_and_recording_api_endpoints(self):
        """Verifies /model/recordings, /model/defect-records, and training status endpoints."""
        # 1. Defect records query
        defects_res = self.client.get("/model/defect-records")
        self.assertEqual(defects_res.status_code, 200)
        self.assertIn("records", defects_res.json())

        # 2. Defect records summary
        summary_res = self.client.get("/model/defect-records/summary")
        self.assertEqual(summary_res.status_code, 200)
        s_data = summary_res.json()
        self.assertIn("total_defects", s_data)
        self.assertIn("pothole_count", s_data)
        self.assertIn("no_zebracrossing_count", s_data)
        self.assertIn("vehicle_count", s_data)

        # 3. Video recordings list
        rec_res = self.client.get("/model/recordings")
        self.assertEqual(rec_res.status_code, 200)
        self.assertIn("recordings", rec_res.json())

        # 4. Finalize recordings
        fin_res = self.client.post("/model/recordings/finalize")
        self.assertEqual(fin_res.status_code, 200)

        # 5. Training status
        status_res = self.client.get("/model/training-status")
        self.assertEqual(status_res.status_code, 200)
        self.assertIn("is_training", status_res.json())


if __name__ == "__main__":
    unittest.main()
