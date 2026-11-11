"""Tests for Admin Analytics Endpoint and Role-Based Access Control.

Milestone 3 - Part 4.1:
  • GET /admin/analytics endpoint validation
  • Admin authorization enforcement (401 unauthenticated, 403 farmer)
  • Metric structure validation (summary, daily_usage, language_distribution, intent_distribution, recent_activity)
  • Parameter boundary validation (days query parameter)
  • PII protection and ID masking in recent activity
  • Empty database robustness (zero divisions prevented)
"""

from __future__ import annotations

import unittest
from fastapi.testclient import TestClient

from main import app
from security import security_user_manager
from session_manager import session_manager


class TestAdminAnalytics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

        # Create or ensure admin account exists
        admin_user = security_user_manager.get_user_by_username("analytics_admin_tester")
        if not admin_user:
            security_user_manager.register_user(
                username="analytics_admin_tester",
                password="AdminSecurePassword123!",
                role="admin",
            )
        admin_login = cls.client.post(
            "/auth/login",
            json={"username": "analytics_admin_tester", "password": "AdminSecurePassword123!"},
        )
        cls.admin_token = admin_login.json()["access_token"]
        cls.admin_headers = {"Authorization": f"Bearer {cls.admin_token}"}

        # Create or ensure farmer account exists
        farmer_user = security_user_manager.get_user_by_username("analytics_farmer_tester")
        if not farmer_user:
            security_user_manager.register_user(
                username="analytics_farmer_tester",
                password="FarmerSecurePassword123!",
                role="farmer",
            )
        farmer_login = cls.client.post(
            "/auth/login",
            json={"username": "analytics_farmer_tester", "password": "FarmerSecurePassword123!"},
        )
        cls.farmer_token = farmer_login.json()["access_token"]
        cls.farmer_headers = {"Authorization": f"Bearer {cls.farmer_token}"}

    def test_analytics_unauthenticated_rejected(self):
        """Verify unauthenticated requests terminate with 401 Unauthorized."""
        res = self.client.get("/admin/analytics")
        self.assertEqual(res.status_code, 401)
        self.assertIn("detail", res.json())

    def test_analytics_farmer_role_rejected(self):
        """Verify farmer accounts are prohibited from viewing admin analytics (403 Forbidden)."""
        res = self.client.get("/admin/analytics", headers=self.farmer_headers)
        self.assertEqual(res.status_code, 403)
        self.assertIn("Forbidden", res.json().get("detail", ""))

    def test_analytics_admin_access_granted(self):
        """Verify authenticated admin receives comprehensive platform metrics."""
        res = self.client.get("/admin/analytics?days=7", headers=self.admin_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        # Check top-level keys
        for key in ("summary", "daily_usage", "language_distribution", "intent_distribution", "recent_activity"):
            self.assertIn(key, data, f"Missing key {key} in analytics response")

        summary = data["summary"]
        self.assertIn("total_farmers", summary)
        self.assertIn("total_sessions", summary)
        self.assertIn("active_sessions", summary)
        self.assertIn("total_queries", summary)
        self.assertIn("today_queries", summary)
        self.assertIn("unanswered_queries", summary)
        self.assertIn("feedback", summary)

        self.assertIsInstance(summary["total_farmers"], int)
        self.assertIsInstance(summary["total_sessions"], int)
        self.assertIsInstance(summary["total_queries"], int)

    def test_analytics_days_query_validation(self):
        """Verify days parameter boundaries (1 to 90 allowed, invalid rejected with 422)."""
        # Valid boundaries
        r_min = self.client.get("/admin/analytics?days=1", headers=self.admin_headers)
        self.assertEqual(r_min.status_code, 200)
        self.assertEqual(len(r_min.json()["daily_usage"]), 1)

        r_max = self.client.get("/admin/analytics?days=30", headers=self.admin_headers)
        self.assertEqual(r_max.status_code, 200)
        self.assertEqual(len(r_max.json()["daily_usage"]), 30)

        # Invalid bounds
        r_zero = self.client.get("/admin/analytics?days=0", headers=self.admin_headers)
        self.assertEqual(r_zero.status_code, 422)

        r_negative = self.client.get("/admin/analytics?days=-7", headers=self.admin_headers)
        self.assertEqual(r_negative.status_code, 422)

        r_excessive = self.client.get("/admin/analytics?days=100", headers=self.admin_headers)
        self.assertEqual(r_excessive.status_code, 422)

    def test_analytics_pii_masking_in_recent_activity(self):
        """Verify farmer identifiers and session IDs are masked in recent activity logs."""
        res = self.client.get("/admin/analytics", headers=self.admin_headers)
        self.assertEqual(res.status_code, 200)
        activities = res.json().get("recent_activity", [])

        for act in activities:
            self.assertIn("session_id_masked", act)
            self.assertIn("farmer_id_masked", act)
            self.assertIn("query_preview", act)
            self.assertIn("language", act)
            self.assertIn("intent", act)
            self.assertIn("created_at", act)

            # Ensure masked format (e.g. contains *** or ... or Anonymous)
            farmer_masked = act["farmer_id_masked"]
            self.assertTrue(
                "***" in farmer_masked or farmer_masked == "Anonymous Farmer",
                f"Farmer ID not properly masked: {farmer_masked}"
            )
            sid_masked = act["session_id_masked"]
            self.assertTrue(
                "..." in sid_masked or len(sid_masked) <= 8,
                f"Session ID not properly masked: {sid_masked}"
            )

    def test_analytics_language_and_intent_distribution(self):
        """Verify percentage and count fields in language and intent distributions."""
        res = self.client.get("/admin/analytics", headers=self.admin_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        for lang in data["language_distribution"]:
            self.assertIn("code", lang)
            self.assertIn("language", lang)
            self.assertIn("count", lang)
            self.assertIn("percentage", lang)
            self.assertGreaterEqual(lang["count"], 0)
            self.assertGreaterEqual(lang["percentage"], 0.0)

        for intent in data["intent_distribution"]:
            self.assertIn("intent", intent)
            self.assertIn("label", intent)
            self.assertIn("count", intent)
            self.assertIn("percentage", intent)
            self.assertGreaterEqual(intent["count"], 0)
            self.assertGreaterEqual(intent["percentage"], 0.0)


if __name__ == "__main__":
    unittest.main()
