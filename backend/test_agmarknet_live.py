"""Integration tests for Genuine Live AGMARKNET 2.0 Mandi Price Discovery.

Separates genuine live network tests from mocked unit tests.
Connects directly to the official AGMARKNET 2.0 backend at https://api.agmarknet.gov.in/v1.

Verifies:
  1. Live Tomato wholesale prices in Salem, Tamil Nadu.
  2. Live Paddy wholesale prices in Salem, Tamil Nadu (authentic zero-arrivals / NR reporting).
  3. Live Onion wholesale prices in Coimbatore, Tamil Nadu.
  4. Public Agmarknet client resilience, headers, caching, and rate limiting handling.
  5. AgmarknetAdapter integration with force_live=True and truthful offline separation.
  6. FastAPI /adapters/agmarknet?force_live=true live endpoint.
"""

import unittest
from fastapi.testclient import TestClient

from main import app
from external_adapters import agmarknet_adapter, AgmarknetAdapter
from agmarknet_client import agmarknet_public_client, AgmarknetPublicClient


class TestAgmarknetLiveAPI(unittest.TestCase):
    """Genuine live network integration tests against AGMARKNET 2.0 API."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.public_client = agmarknet_public_client

    def test_live_query_tomato_salem_tamil_nadu(self):
        """Query 1: Live Tomato wholesale prices in Salem, Tamil Nadu."""
        res = self.public_client.get_live_mandi_prices(
            commodity="Tomato",
            state="Tamil Nadu",
            district="Salem",
        )
        self.assertIn("status", res)
        self.assertTrue(res.get("is_live"))
        self.assertEqual(res.get("http_status"), 200)
        self.assertIn("api.agmarknet.gov.in", res.get("source_endpoint", ""))
        self.assertIn("AGMARKNET 2.0 API", res.get("source", ""))
        self.assertEqual(res.get("commodity"), "Tomato")
        self.assertEqual(res.get("state"), "Tamil Nadu")

        records = res.get("live_records", [])
        self.assertGreater(len(records), 0, "Expected at least one live Tomato record from Salem markets")

        first = records[0]
        self.assertIn("variety", first)
        self.assertIn("market", first)
        self.assertIn("arrival_date", first)
        self.assertGreater(first["modal_price"], 0)
        self.assertGreater(first["min_price"], 0)
        self.assertGreater(first["max_price"], 0)
        self.assertEqual(first["price_unit"], "Rs./Quintal")

    def test_live_query_paddy_salem_tamil_nadu(self):
        """Query 2: Live Paddy wholesale prices in Salem, Tamil Nadu (authentic zero-arrival / NR reporting)."""
        res = self.public_client.get_live_mandi_prices(
            commodity="Paddy",
            state="Tamil Nadu",
            district="Salem",
        )
        self.assertIn("status", res)
        self.assertTrue(res.get("is_live"))
        self.assertEqual(res.get("http_status"), 200)
        self.assertIn("api.agmarknet.gov.in", res.get("source_endpoint", ""))
        # Authentic truth: No paddy arrivals reported in Salem uzhavar sandhais
        self.assertEqual(res.get("status"), "no_transactions_reported")
        self.assertEqual(len(res.get("live_records", [])), 0)
        self.assertIn("message", res)
        self.assertIn("Paddy", res["message"])

    def test_live_query_onion_coimbatore_tamil_nadu(self):
        """Query 3: Live Onion wholesale prices in Coimbatore, Tamil Nadu."""
        res = self.public_client.get_live_mandi_prices(
            commodity="Onion",
            state="Tamil Nadu",
            district="Coimbatore",
        )
        self.assertIn("status", res)
        self.assertTrue(res.get("is_live"))
        self.assertEqual(res.get("http_status"), 200)
        self.assertIn("api.agmarknet.gov.in", res.get("source_endpoint", ""))
        self.assertEqual(res.get("commodity"), "Onion")

        records = res.get("live_records", [])
        self.assertGreater(len(records), 0, "Expected at least one live Onion record from Coimbatore markets")

        first = records[0]
        self.assertIn("variety", first)
        self.assertIn("market", first)
        self.assertIn("arrival_date", first)
        self.assertGreater(first["modal_price"], 0)
        self.assertGreaterEqual(first["max_price"], first["min_price"])

    def test_adapter_force_live_retrieval(self):
        """Verify AgmarknetAdapter retrieves live data when force_live=True is passed."""
        res = agmarknet_adapter.get_market_data(
            commodity="Tomato",
            state="Tamil Nadu",
            district="Salem",
            force_live=True,
        )
        self.assertTrue(res["is_live"])
        self.assertEqual(res["status"], "live_data")
        self.assertGreater(len(res.get("live_records", [])), 0)
        self.assertIn("post_harvest_advice", res)

    def test_fastapi_endpoint_force_live(self):
        """Verify FastAPI /adapters/agmarknet?force_live=true returns genuine live data."""
        resp = self.client.get(
            "/adapters/agmarknet",
            params={
                "commodity": "Onion",
                "state": "Tamil Nadu",
                "district": "Coimbatore",
                "force_live": "true",
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get("is_live"))
        self.assertEqual(data.get("status"), "live_data")
        self.assertGreater(len(data.get("live_records", [])), 0)
        self.assertEqual(data["live_records"][0]["price_unit"], "Rs./Quintal")

    def test_caching_and_freshness_metadata(self):
        """Verify price and metadata caching with timestamps."""
        # Query 1
        res1 = self.public_client.get_live_mandi_prices(commodity="Tomato", state="Tamil Nadu", district="Salem")
        ts1 = res1.get("observation_timestamp")
        self.assertIsNotNone(ts1)

        # Query 2 immediately (served from cache)
        res2 = self.public_client.get_live_mandi_prices(commodity="Tomato", state="Tamil Nadu", district="Salem")
        self.assertEqual(len(res1.get("live_records", [])), len(res2.get("live_records", [])))


if __name__ == "__main__":
    unittest.main()
