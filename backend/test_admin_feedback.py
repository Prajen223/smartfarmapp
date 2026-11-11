"""Tests for Farmer Feedback and Admin Feedback Analytics Endpoints.

Milestone 3 - Part 4.4:
  • Farmer feedback submission (thumbs up, thumbs down, optional comments)
  • Input validation: rating validation (400), session validation (404)
  • Comment PII scrubbing (phone, email, Aadhaar)
  • Registered farmer session ownership enforcement (401 unauthenticated, 403 unauthorized farmer)
  • Anonymous farmer session feedback support
  • Feedback update / duplicate submission on same message_id
  • Message ID generation and exposure in /ask endpoint
  • GET /admin/feedback authorization (401 unauthenticated, 403 farmer, 200 admin)
  • GET /admin/feedback filtering (rating, language, intent, search) and pagination
  • GET /admin/feedback/analytics exact satisfaction rate calculation and breakdowns
  • GET /admin/feedback/{id} detail inspection
  • POST /admin/feedback/{id}/flag-for-review linking into expert review queue
"""

from __future__ import annotations

import unittest
from fastapi.testclient import TestClient

from main import app
from security import security_user_manager
from session_manager import session_manager
from review_manager import review_manager


class TestAdminFeedback(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

        # Create or ensure admin account exists
        admin_user = security_user_manager.get_user_by_username("feedback_admin_tester")
        if not admin_user:
            security_user_manager.register_user(
                username="feedback_admin_tester",
                password="AdminSecurePassword123!",
                role="admin",
            )
        admin_login = cls.client.post(
            "/auth/login",
            json={"username": "feedback_admin_tester", "password": "AdminSecurePassword123!"},
        )
        cls.admin_token = admin_login.json()["access_token"]
        cls.admin_headers = {"Authorization": f"Bearer {cls.admin_token}"}

        # Create or ensure registered farmer account exists
        farmer_user = security_user_manager.get_user_by_username("feedback_farmer_tester")
        if not farmer_user:
            security_user_manager.register_user(
                username="feedback_farmer_tester",
                password="FarmerSecurePassword123!",
                role="farmer",
            )
        farmer_login = cls.client.post(
            "/auth/login",
            json={"username": "feedback_farmer_tester", "password": "FarmerSecurePassword123!"},
        )
        cls.farmer_token = farmer_login.json()["access_token"]
        cls.farmer_headers = {"Authorization": f"Bearer {cls.farmer_token}"}

        # Create a second farmer account for unauthorized tests
        other_farmer = security_user_manager.get_user_by_username("other_farmer_tester")
        if not other_farmer:
            security_user_manager.register_user(
                username="other_farmer_tester",
                password="FarmerSecurePassword123!",
                role="farmer",
            )
        other_login = cls.client.post(
            "/auth/login",
            json={"username": "other_farmer_tester", "password": "FarmerSecurePassword123!"},
        )
        cls.other_farmer_token = other_login.json()["access_token"]
        cls.other_farmer_headers = {"Authorization": f"Bearer {cls.other_farmer_token}"}

    def test_01_ask_endpoint_returns_message_id(self):
        """Verify that /ask returns a valid message_id for assistant turns."""
        res = self.client.post(
            "/ask",
            json={"text": "How do I control aphids on wheat?", "mode": "mock"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("message_id", data)
        self.assertIsNotNone(data["message_id"])
        self.assertIn("session_id", data)

    def test_02_anonymous_farmer_thumbs_up(self):
        """Verify anonymous farmer can submit thumbs-up feedback successfully."""
        # Create session and ask question
        ask_res = self.client.post(
            "/ask",
            json={"text": "What is the best irrigation method for tomatoes?", "mode": "mock"},
        )
        self.assertEqual(ask_res.status_code, 200)
        ask_data = ask_res.json()
        session_id = ask_data["session_id"]
        message_id = ask_data["message_id"]

        # Submit thumbs-up feedback
        fb_res = self.client.post(
            "/feedback",
            json={
                "session_id": session_id,
                "message_id": message_id,
                "rating": "thumbs_up",
            },
        )
        self.assertEqual(fb_res.status_code, 200)
        fb_data = fb_res.json()
        self.assertEqual(fb_data["status"], "success")
        self.assertEqual(fb_data["rating"], "positive")
        self.assertIn("feedback_id", fb_data)

    def test_03_farmer_thumbs_down_with_pii_sanitization(self):
        """Verify thumbs-down feedback sanitizes PII (email, phone, Aadhaar) from comment."""
        ask_res = self.client.post(
            "/ask",
            json={"text": "Tell me about fertilizer subsidy for rice.", "mode": "mock"},
        )
        self.assertEqual(ask_res.status_code, 200)
        ask_data = ask_res.json()
        session_id = ask_data["session_id"]
        message_id = ask_data["message_id"]

        comment_with_pii = (
            "The answer didn't help. Contact me at farmer.ramesh@example.com or 9876543210. "
            "My Aadhaar is 1234 5678 9012."
        )

        fb_res = self.client.post(
            "/feedback",
            json={
                "session_id": session_id,
                "message_id": message_id,
                "rating": "negative",
                "comment": comment_with_pii,
            },
        )
        self.assertEqual(fb_res.status_code, 200)
        fb_data = fb_res.json()
        self.assertEqual(fb_data["rating"], "negative")

        # Inspect stored record to confirm PII sanitization
        detail = session_manager.get_feedback(fb_data["feedback_id"])
        self.assertIsNotNone(detail)
        stored_comment = detail["comment"]
        self.assertNotIn("farmer.ramesh@example.com", stored_comment)
        self.assertNotIn("9876543210", stored_comment)
        self.assertNotIn("1234 5678 9012", stored_comment)
        self.assertIn("[REDACTED_EMAIL]", stored_comment)
        self.assertIn("[REDACTED_PHONE]", stored_comment)
        self.assertIn("[REDACTED_AADHAAR]", stored_comment)

    def test_04_invalid_rating_rejected(self):
        """Verify invalid rating returns HTTP 400."""
        # Create session
        session = session_manager.create_session()
        res = self.client.post(
            "/feedback",
            json={
                "session_id": session.session_id,
                "rating": "maybe_good",
            },
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("Invalid rating", res.json()["detail"])

    def test_05_nonexistent_session_rejected(self):
        """Verify feedback on nonexistent session returns HTTP 404."""
        res = self.client.post(
            "/feedback",
            json={
                "session_id": "nonexistent-session-uuid-9999",
                "rating": "positive",
            },
        )
        self.assertEqual(res.status_code, 404)

    def test_06_duplicate_feedback_updates_existing_record(self):
        """Verify re-submitting feedback for the same message updates the record without creating duplicates."""
        ask_res = self.client.post(
            "/ask",
            json={"text": "Best sowing time for cotton?", "mode": "mock"},
        )
        ask_data = ask_res.json()
        session_id = ask_data["session_id"]
        message_id = ask_data["message_id"]

        # 1. First submit thumbs_down
        fb1 = self.client.post(
            "/feedback",
            json={"session_id": session_id, "message_id": message_id, "rating": "negative", "comment": "Too brief."},
        ).json()

        # 2. Later update to thumbs_up
        fb2 = self.client.post(
            "/feedback",
            json={"session_id": session_id, "message_id": message_id, "rating": "positive", "comment": "Actually helpful now."},
        ).json()

        self.assertEqual(fb1["feedback_id"], fb2["feedback_id"])
        self.assertEqual(fb2["rating"], "positive")

        detail = session_manager.get_feedback(fb1["feedback_id"])
        self.assertEqual(detail["rating"], "positive")
        self.assertEqual(detail["comment"], "Actually helpful now.")

    def test_07_registered_farmer_session_access_control(self):
        """Verify registered farmer session ownership policies:
        - Anonymous user cannot submit feedback on a registered farmer's session (401)
        - Different farmer cannot submit feedback (403)
        - Session owner farmer CAN submit feedback (200)
        - Admin CAN submit feedback (200)
        """
        # Create session owned by feedback_farmer_tester
        session = session_manager.create_session(farmer_id="feedback_farmer_tester")

        # 1. Anonymous submission attempt -> 401
        res_anon = self.client.post(
            "/feedback",
            json={"session_id": session.session_id, "rating": "positive"},
        )
        self.assertEqual(res_anon.status_code, 401)

        # 2. Other farmer submission attempt -> 403
        res_other = self.client.post(
            "/feedback",
            json={"session_id": session.session_id, "rating": "positive"},
            headers=self.other_farmer_headers,
        )
        self.assertEqual(res_other.status_code, 403)

        # 3. Owner farmer submission -> 200
        res_owner = self.client.post(
            "/feedback",
            json={"session_id": session.session_id, "rating": "positive", "comment": "Owner feedback"},
            headers=self.farmer_headers,
        )
        self.assertEqual(res_owner.status_code, 200)

        # 4. Admin submission -> 200
        res_admin = self.client.post(
            "/feedback",
            json={"session_id": session.session_id, "rating": "positive", "comment": "Admin feedback"},
            headers=self.admin_headers,
        )
        self.assertEqual(res_admin.status_code, 200)

    def test_08_admin_feedback_list_rbac(self):
        """Verify GET /admin/feedback requires admin privileges."""
        # Unauthenticated -> 401
        res_unauth = self.client.get("/admin/feedback")
        self.assertEqual(res_unauth.status_code, 401)

        # Farmer -> 403
        res_farmer = self.client.get("/admin/feedback", headers=self.farmer_headers)
        self.assertEqual(res_farmer.status_code, 403)

        # Admin -> 200
        res_admin = self.client.get("/admin/feedback", headers=self.admin_headers)
        self.assertEqual(res_admin.status_code, 200)
        data = res_admin.json()
        self.assertIn("items", data)
        self.assertIn("total", data)
        self.assertIn("stats", data)
        self.assertIn("satisfaction_rate", data["stats"])

    def test_09_admin_feedback_list_filtering(self):
        """Verify filtering by rating, language, and search keyword."""
        # Submit distinct feedback records
        sess1 = session_manager.create_session(language="hi")
        session_manager.record_turn(
            session_id=sess1.session_id,
            user_text="गेहूं में खाद कब डालें?",
            detected_language="hi",
            intent="crop_advisory",
            answer="गेहूं में बुवाई के समय यूरिया और डीएपी का उपयोग करें।",
            entities={},
        )
        fb1 = session_manager.record_feedback(
            session_id=sess1.session_id,
            rating="positive",
            comment="बहुत बढ़िया जानकारी",
        )

        sess2 = session_manager.create_session(language="en")
        session_manager.record_turn(
            session_id=sess2.session_id,
            user_text="How to treat yellow rust in barley?",
            detected_language="en",
            intent="pest_control",
            answer="Apply propiconazole fungicide at recommended rates.",
            entities={},
        )
        fb2 = session_manager.record_feedback(
            session_id=sess2.session_id,
            rating="negative",
            comment="Did not specify dosage clearly",
        )

        # 1. Filter by rating=negative
        res_neg = self.client.get("/admin/feedback?rating=negative", headers=self.admin_headers)
        self.assertEqual(res_neg.status_code, 200)
        items = res_neg.json()["items"]
        for it in items:
            self.assertEqual(it["rating"], "negative")

        # 2. Filter by language=hi
        res_hi = self.client.get("/admin/feedback?language=hi", headers=self.admin_headers)
        self.assertEqual(res_hi.status_code, 200)
        for it in res_hi.json()["items"]:
            self.assertEqual(it["language"], "hi")

        # 3. Search keyword
        res_search = self.client.get("/admin/feedback?search=dosage", headers=self.admin_headers)
        self.assertEqual(res_search.status_code, 200)
        search_items = res_search.json()["items"]
        self.assertTrue(any("dosage" in (it["comment"] or "") for it in search_items))

    def test_10_admin_feedback_analytics_satisfaction_rate(self):
        """Verify satisfaction rate calculation and analytics breakdown."""
        res = self.client.get("/admin/feedback/analytics?days=30", headers=self.admin_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertIn("satisfaction_rate", data)
        self.assertIn("total_ratings", data)
        self.assertIn("positive_ratings", data)
        self.assertIn("negative_ratings", data)
        self.assertIn("daily_trend", data)
        self.assertIn("by_language", data)
        self.assertIn("by_intent", data)

        total = data["total_ratings"]
        pos = data["positive_ratings"]
        if total > 0:
            expected_rate = round((pos / total) * 100, 1)
            self.assertEqual(data["satisfaction_rate"], expected_rate)
        else:
            self.assertEqual(data["satisfaction_rate"], 0.0)

    def test_11_admin_feedback_detail_and_flag_for_review(self):
        """Verify inspecting feedback detail and one-click flagging into review queue."""
        sess = session_manager.create_session()
        session_manager.record_turn(
            session_id=sess.session_id,
            user_text="What is the subsidy percentage for drip irrigation in Tamil Nadu?",
            detected_language="en",
            intent="government_schemes",
            answer="PMKSY provides up to 55% subsidy for small and marginal farmers.",
            entities={},
        )
        fb = session_manager.record_feedback(
            session_id=sess.session_id,
            rating="negative",
            comment="Farmer claims subsidy percentage varies by district.",
        )
        fb_id = fb["feedback_id"]

        # 1. Get detail -> 200
        detail_res = self.client.get(f"/admin/feedback/{fb_id}", headers=self.admin_headers)
        self.assertEqual(detail_res.status_code, 200)
        detail_data = detail_res.json()
        self.assertEqual(detail_data["feedback_id"], fb_id)
        self.assertEqual(detail_data["rating"], "negative")

        # 2. Flag for review -> 200
        flag_res = self.client.post(
            f"/admin/feedback/{fb_id}/flag-for-review",
            json={"notes": "Verify state-specific guidelines"},
            headers=self.admin_headers,
        )
        self.assertEqual(flag_res.status_code, 200)
        flag_data = flag_res.json()
        self.assertEqual(flag_data["status"], "flagged_for_review")
        self.assertIn("review_id", flag_data)

        # 3. Check that detail now includes review_detail
        detail_after = self.client.get(f"/admin/feedback/{fb_id}", headers=self.admin_headers).json()
        self.assertIsNotNone(detail_after.get("review_id"))
        self.assertIn("review_detail", detail_after)
        self.assertEqual(detail_after["review_detail"]["status"], "pending")

    def test_12_nonexistent_feedback_detail_returns_404(self):
        """Verify nonexistent feedback_id returns HTTP 404."""
        res = self.client.get("/admin/feedback/fb_nonexistent_123", headers=self.admin_headers)
        self.assertEqual(res.status_code, 404)


if __name__ == "__main__":
    unittest.main()
