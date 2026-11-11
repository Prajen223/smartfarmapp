"""Tests for Admin Unanswered Query Management, Review Console & RBAC.

Milestone 3 - Part 4.2:
  • GET /admin/unanswered-queries with multi-factor filters (status, language, intent, search)
  • Pagination (limit, offset, total) and status summary stats
  • GET /admin/unanswered-queries/{query_id} (detail & 404 on missing)
  • PATCH /admin/unanswered-queries/{query_id} (approve, reject, correct)
  • Validation on correction (corrected_answer required)
  • POST /admin/unanswered-queries/{query_id}/approve, /reject, /correct action routes
  • RBAC protection (401 unauthenticated, 403 farmer, 200 admin)
  • PII sanitization in review storage (email, phone, Aadhaar)
"""

from __future__ import annotations

import unittest
from fastapi.testclient import TestClient

from main import app
from security import security_user_manager
from review_manager import review_manager, sanitize_pii_for_review, ReviewRecord


class TestAdminUnansweredQueries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

        # Create or ensure admin account exists
        admin_user = security_user_manager.get_user_by_username("query_admin_tester")
        if not admin_user:
            security_user_manager.register_user(
                username="query_admin_tester",
                password="AdminPassword123!",
                role="admin",
            )
        admin_login = cls.client.post(
            "/auth/login",
            json={"username": "query_admin_tester", "password": "AdminPassword123!"},
        )
        cls.admin_token = admin_login.json()["access_token"]
        cls.admin_headers = {"Authorization": f"Bearer {cls.admin_token}"}

        # Create or ensure farmer account exists
        farmer_user = security_user_manager.get_user_by_username("query_farmer_tester")
        if not farmer_user:
            security_user_manager.register_user(
                username="query_farmer_tester",
                password="FarmerPassword123!",
                role="farmer",
            )
        farmer_login = cls.client.post(
            "/auth/login",
            json={"username": "query_farmer_tester", "password": "FarmerPassword123!"},
        )
        cls.farmer_token = farmer_login.json()["access_token"]
        cls.farmer_headers = {"Authorization": f"Bearer {cls.farmer_token}"}

        # Seed a test review item if the review manager has none
        if not review_manager._reviews:
            test_rec = ReviewRecord(
                review_id="rev_test_seed_001",
                created_at="2026-11-10T10:00:00Z",
                query="How much water for wheat in rabi season?",
                canonical_text="How much water for wheat in rabi season?",
                intent="irrigation",
                confidence=0.45,
                quality_score=0.40,
                source_reliability=0.30,
                evidence_grounding_score=0.25,
                status="pending",
                original_answer="Insufficient information for wheat irrigation.",
                flag_reason="Low retrieval confidence",
                language="en",
                sources=["ICAR-Wheat-Handbook"],
            )
            review_manager._reviews[test_rec.review_id] = test_rec

    def test_unauthenticated_requests_rejected(self):
        """Verify unauthenticated requests terminate with 401 Unauthorized."""
        res_list = self.client.get("/admin/unanswered-queries")
        self.assertEqual(res_list.status_code, 401)

        res_detail = self.client.get("/admin/unanswered-queries/rev_test_seed_001")
        self.assertEqual(res_detail.status_code, 401)

        res_patch = self.client.patch(
            "/admin/unanswered-queries/rev_test_seed_001",
            json={"status": "approved"},
        )
        self.assertEqual(res_patch.status_code, 401)

    def test_farmer_role_forbidden(self):
        """Verify farmer accounts are prohibited with 403 Forbidden."""
        res_list = self.client.get("/admin/unanswered-queries", headers=self.farmer_headers)
        self.assertEqual(res_list.status_code, 403)
        self.assertIn("Forbidden", res_list.json().get("detail", ""))

        res_detail = self.client.get(
            "/admin/unanswered-queries/rev_test_seed_001",
            headers=self.farmer_headers,
        )
        self.assertEqual(res_detail.status_code, 403)

    def test_admin_list_queries_structure(self):
        """Verify admin can list queries and payload conforms to specification."""
        res = self.client.get("/admin/unanswered-queries", headers=self.admin_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        for key in ("queries", "total", "limit", "offset", "stats"):
            self.assertIn(key, data, f"Missing key {key} in response")

        stats = data["stats"]
        for stat_key in ("total", "pending", "approved", "corrected", "rejected"):
            self.assertIn(stat_key, stats, f"Missing stat key {stat_key}")
            self.assertIsInstance(stats[stat_key], int)

        self.assertGreaterEqual(data["total"], 1)
        self.assertIsInstance(data["queries"], list)

    def test_filter_by_status(self):
        """Verify status filter isolates records with matching status."""
        res = self.client.get(
            "/admin/unanswered-queries?status=pending&limit=50",
            headers=self.admin_headers,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        for q in data["queries"]:
            self.assertEqual(q["status"], "pending")

    def test_filter_by_intent(self):
        """Verify filtering by agricultural intent."""
        res = self.client.get(
            "/admin/unanswered-queries?intent=irrigation",
            headers=self.admin_headers,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        for q in data["queries"]:
            self.assertEqual(q["intent"], "irrigation")

    def test_filter_by_language(self):
        """Verify filtering by query language."""
        res = self.client.get(
            "/admin/unanswered-queries?language=en",
            headers=self.admin_headers,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        for q in data["queries"]:
            self.assertEqual(q["language"], "en")

    def test_search_filter(self):
        """Verify keyword search across questions and answers."""
        res = self.client.get(
            "/admin/unanswered-queries?search=wheat",
            headers=self.admin_headers,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        for q in data["queries"]:
            in_q = "wheat" in q["query"].lower()
            in_a = "wheat" in (q.get("original_answer") or "").lower()
            self.assertTrue(in_q or in_a, "Keyword 'wheat' not found in item")

    def test_pagination(self):
        """Verify limit and offset boundary behavior."""
        res = self.client.get(
            "/admin/unanswered-queries?limit=3&offset=0",
            headers=self.admin_headers,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertLessEqual(len(data["queries"]), 3)
        self.assertEqual(data["limit"], 3)
        self.assertEqual(data["offset"], 0)

    def test_get_query_detail_success_and_not_found(self):
        """Verify retrieving specific query details and 404 for nonexistent id."""
        # Find any valid ID
        res_list = self.client.get("/admin/unanswered-queries?limit=1", headers=self.admin_headers)
        self.assertEqual(res_list.status_code, 200)
        first_id = res_list.json()["queries"][0]["review_id"]

        # Detail success
        res_detail = self.client.get(
            f"/admin/unanswered-queries/{first_id}",
            headers=self.admin_headers,
        )
        self.assertEqual(res_detail.status_code, 200)
        detail = res_detail.json()
        self.assertEqual(detail["review_id"], first_id)
        self.assertIn("query", detail)
        self.assertIn("flag_reason", detail)
        self.assertIn("confidence", detail)

        # 404 for invalid ID
        res_missing = self.client.get(
            "/admin/unanswered-queries/rev_completely_invalid_999",
            headers=self.admin_headers,
        )
        self.assertEqual(res_missing.status_code, 404)

    def test_patch_review_status_approved(self):
        """Verify approving a query status with reviewer notes."""
        # Create a dedicated record for clean testing
        test_id = "rev_unit_test_approve"
        review_manager._reviews[test_id] = ReviewRecord(
            review_id=test_id,
            created_at="2026-11-10T12:00:00Z",
            query="Can I spray urea during flowering?",
            canonical_text="Can I spray urea during flowering?",
            intent="crop_advisory",
            confidence=0.55,
            quality_score=0.50,
            source_reliability=0.60,
            evidence_grounding_score=0.40,
            status="pending",
            original_answer="Avoid foliar spray of urea during peak flowering.",
            flag_reason="Low confidence score",
            language="en",
        )

        patch_res = self.client.patch(
            f"/admin/unanswered-queries/{test_id}",
            json={
                "status": "approved",
                "reviewer_notes": "Agronomist verified correct practice.",
            },
            headers=self.admin_headers,
        )
        self.assertEqual(patch_res.status_code, 200)
        body = patch_res.json()
        self.assertEqual(body["status"], "approved")
        self.assertEqual(body["record"]["status"], "approved")
        self.assertEqual(body["record"]["reviewer_notes"], "Agronomist verified correct practice.")
        self.assertEqual(body["record"]["reviewer_username"], "query_admin_tester")
        self.assertIsNotNone(body["record"]["reviewed_at"])

    def test_patch_review_status_rejected(self):
        """Verify rejecting a query answer."""
        test_id = "rev_unit_test_reject"
        review_manager._reviews[test_id] = ReviewRecord(
            review_id=test_id,
            created_at="2026-11-10T12:00:00Z",
            query="Is salt water good for paddy irrigation?",
            canonical_text="Is salt water good for paddy irrigation?",
            intent="irrigation",
            confidence=0.30,
            quality_score=0.20,
            source_reliability=0.20,
            evidence_grounding_score=0.10,
            status="pending",
            original_answer="Yes, salt water can be used sparingly.",
            flag_reason="Harmful advice",
            language="en",
        )

        patch_res = self.client.patch(
            f"/admin/unanswered-queries/{test_id}",
            json={
                "status": "rejected",
                "reviewer_notes": "Saline water causes soil toxicity; harmful recommendation.",
            },
            headers=self.admin_headers,
        )
        self.assertEqual(patch_res.status_code, 200)
        body = patch_res.json()
        self.assertEqual(body["status"], "rejected")
        self.assertEqual(body["record"]["status"], "rejected")

    def test_patch_review_status_corrected_requires_answer(self):
        """Verify marking as 'corrected' requires a non-empty corrected_answer."""
        test_id = "rev_unit_test_correct"
        review_manager._reviews[test_id] = ReviewRecord(
            review_id=test_id,
            created_at="2026-11-10T12:00:00Z",
            query="What is the seed rate for chickpea?",
            canonical_text="What is the seed rate for chickpea?",
            intent="crop_advisory",
            confidence=0.45,
            quality_score=0.40,
            source_reliability=0.50,
            evidence_grounding_score=0.30,
            status="pending",
            original_answer="Information not found in database.",
            flag_reason="Low confidence score",
            language="en",
        )

        # Missing answer -> 400
        fail_res = self.client.patch(
            f"/admin/unanswered-queries/{test_id}",
            json={
                "status": "corrected",
                "reviewer_notes": "Added seed rate",
                "corrected_answer": "   ",
            },
            headers=self.admin_headers,
        )
        self.assertEqual(fail_res.status_code, 400)
        self.assertIn("corrected_answer", fail_res.json()["detail"].lower())

        # With answer -> 200
        success_res = self.client.patch(
            f"/admin/unanswered-queries/{test_id}",
            json={
                "status": "corrected",
                "reviewer_notes": "Standard ICAR recommendation",
                "corrected_answer": "Recommended seed rate for desi chickpea is 65-75 kg/ha; for kabuli chickpea 100-120 kg/ha.",
            },
            headers=self.admin_headers,
        )
        self.assertEqual(success_res.status_code, 200)
        body = success_res.json()
        self.assertEqual(body["status"], "corrected")
        self.assertEqual(
            body["record"]["corrected_answer"],
            "Recommended seed rate for desi chickpea is 65-75 kg/ha; for kabuli chickpea 100-120 kg/ha.",
        )

    def test_action_convenience_endpoints(self):
        """Verify approve, reject, and correct action endpoints."""
        action_id = "rev_unit_test_actions"
        review_manager._reviews[action_id] = ReviewRecord(
            review_id=action_id,
            created_at="2026-11-10T13:00:00Z",
            query="Tomato leaf curl management",
            canonical_text="Tomato leaf curl management",
            intent="pest_control",
            confidence=0.50,
            quality_score=0.50,
            source_reliability=0.50,
            evidence_grounding_score=0.50,
            status="pending",
            original_answer="Control whitefly vectors using yellow sticky traps.",
            flag_reason="Low quality score",
            language="en",
        )

        # Approve
        res_app = self.client.post(
            f"/admin/unanswered-queries/{action_id}/approve",
            json={"notes": "Standard IPM practice"},
            headers=self.admin_headers,
        )
        self.assertEqual(res_app.status_code, 200)
        self.assertEqual(res_app.json()["status"], "approved")

        # Reject
        res_rej = self.client.post(
            f"/admin/unanswered-queries/{action_id}/reject",
            json={"notes": "Need more specific vector control details"},
            headers=self.admin_headers,
        )
        self.assertEqual(res_rej.status_code, 200)
        self.assertEqual(res_rej.json()["status"], "rejected")

        # Correct without answer -> 400
        res_cor_fail = self.client.post(
            f"/admin/unanswered-queries/{action_id}/correct",
            json={"notes": "Updated answer", "corrected_answer": ""},
            headers=self.admin_headers,
        )
        self.assertEqual(res_cor_fail.status_code, 400)

        # Correct with answer -> 200
        res_cor_ok = self.client.post(
            f"/admin/unanswered-queries/{action_id}/correct",
            json={
                "notes": "Added imidacloprid IPM guideline",
                "corrected_answer": "Install yellow sticky traps (10-12/acre) and spray Imidacloprid 17.8 SL @ 0.3 ml/L if threshold exceeded.",
            },
            headers=self.admin_headers,
        )
        self.assertEqual(res_cor_ok.status_code, 200)
        self.assertEqual(res_cor_ok.json()["status"], "corrected")

    def test_pii_sanitization_for_reviews(self):
        """Verify PII (phone, email, Aadhaar) is cleanly sanitized for review records."""
        sample_query = "Farmer Ramesh, phone 9876543210, email ramesh.kumar@example.com, aadhaar 1234 5678 9012 needs urea."
        sanitized = sanitize_pii_for_review(sample_query)

        self.assertNotIn("9876543210", sanitized)
        self.assertNotIn("ramesh.kumar@example.com", sanitized)
        self.assertNotIn("1234 5678 9012", sanitized)
        self.assertIn("[REDACTED_PHONE]", sanitized)
        self.assertIn("[REDACTED_EMAIL]", sanitized)
        self.assertIn("[REDACTED_AADHAAR]", sanitized)
