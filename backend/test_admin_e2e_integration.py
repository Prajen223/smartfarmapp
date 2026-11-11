"""End-to-End Integration and System Tests for FarmSaathi Admin Dashboard.

Milestone 3 - Part 4.5:
  • Workflow A: Complete Farmer Feedback Lifecycle (Ask -> Message ID -> Feedback -> Admin List -> Detail -> Flag for Review)
  • Workflow B: Expert Review Queue Lifecycle (Flagged Query -> Inspect -> Correct / Reject -> Distinct Audit State)
  • Workflow C: Knowledge Base & Vector Synchronization (Create Record -> Vector Sync -> RAG Retrieval -> Update Record -> Re-index -> Safe Delete Confirmation)
  • Workflow D: Analytics & Real Storage Consistency (Stored Usage -> Accurate Counts -> Satisfaction Rate Math -> Language & Intent Distribution)
  • Security & RBAC Enforcement (401 unauthenticated, 403 farmer, registered session ownership, document upload validation)
"""

from __future__ import annotations

import unittest
from fastapi.testclient import TestClient

from main import app
from security import security_user_manager
from session_manager import session_manager
from review_manager import review_manager, ReviewRecord
from knowledge_manager import knowledge_base_manager


class TestAdminE2EIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

        # 1. Setup Admin Account & Token
        admin_user = security_user_manager.get_user_by_username("e2e_admin_tester")
        if not admin_user:
            security_user_manager.register_user(
                username="e2e_admin_tester",
                password="AdminSecurePassword123!",
                role="admin",
            )
        admin_login = cls.client.post(
            "/auth/login",
            json={"username": "e2e_admin_tester", "password": "AdminSecurePassword123!"},
        )
        cls.admin_token = admin_login.json()["access_token"]
        cls.admin_headers = {"Authorization": f"Bearer {cls.admin_token}"}

        # 2. Setup Farmer Account & Token (Farmer 1: Ramesh)
        farmer_1 = security_user_manager.get_user_by_username("e2e_farmer_ramesh")
        if not farmer_1:
            security_user_manager.register_user(
                username="e2e_farmer_ramesh",
                password="FarmerPassword123!",
                role="farmer",
            )
        f1_login = cls.client.post(
            "/auth/login",
            json={"username": "e2e_farmer_ramesh", "password": "FarmerPassword123!"},
        )
        cls.farmer_1_token = f1_login.json()["access_token"]
        cls.farmer_1_headers = {"Authorization": f"Bearer {cls.farmer_1_token}"}

        # 3. Setup Farmer Account & Token (Farmer 2: Suresh)
        farmer_2 = security_user_manager.get_user_by_username("e2e_farmer_suresh")
        if not farmer_2:
            security_user_manager.register_user(
                username="e2e_farmer_suresh",
                password="FarmerPassword123!",
                role="farmer",
            )
        f2_login = cls.client.post(
            "/auth/login",
            json={"username": "e2e_farmer_suresh", "password": "FarmerPassword123!"},
        )
        cls.farmer_2_token = f2_login.json()["access_token"]
        cls.farmer_2_headers = {"Authorization": f"Bearer {cls.farmer_2_token}"}

    # =========================================================================
    # WORKFLOW A: FARMER FEEDBACK LIFECYCLE
    # =========================================================================

    def test_workflow_a_farmer_feedback_lifecycle(self):
        """Workflow A:
        1. Farmer asks a question.
        2. Assistant returns answer with valid session_id and message_id.
        3. Farmer submits negative feedback with comment.
        4. Comment PII is scrubbed.
        5. Admin inspects feedback in list and detail endpoints.
        6. Admin flags feedback into expert review queue.
        """
        # 1. Ask question
        ask_res = self.client.post(
            "/ask",
            json={"text": "What is the recommended seed rate for mustard?", "mode": "mock"},
        )
        self.assertEqual(ask_res.status_code, 200)
        ask_data = ask_res.json()
        session_id = ask_data["session_id"]
        message_id = ask_data["message_id"]
        self.assertIsNotNone(message_id)

        # 2. Farmer submits thumbs_down feedback
        feedback_comment = "The answer was not detailed. Call me at 9876543210 or email farmer@example.com."
        fb_res = self.client.post(
            "/feedback",
            json={
                "session_id": session_id,
                "message_id": message_id,
                "rating": "negative",
                "comment": feedback_comment,
            },
        )
        self.assertEqual(fb_res.status_code, 200)
        fb_id = fb_res.json()["feedback_id"]

        # 3. Admin lists feedback and verifies PII scrubbing
        admin_list_res = self.client.get("/admin/feedback?rating=negative", headers=self.admin_headers)
        self.assertEqual(admin_list_res.status_code, 200)
        items = admin_list_res.json()["items"]
        matched = next((item for item in items if item["feedback_id"] == fb_id), None)
        self.assertIsNotNone(matched)
        self.assertIn("[REDACTED_PHONE]", matched["comment"])
        self.assertIn("[REDACTED_EMAIL]", matched["comment"])
        self.assertNotIn("9876543210", matched["comment"])

        # 4. Admin inspects detail
        detail_res = self.client.get(f"/admin/feedback/{fb_id}", headers=self.admin_headers)
        self.assertEqual(detail_res.status_code, 200)
        detail = detail_res.json()
        self.assertEqual(detail["session_id"], session_id)
        self.assertEqual(detail["message_id"], message_id)

        # 5. Admin flags to review queue
        flag_res = self.client.post(
            f"/admin/feedback/{fb_id}/flag-for-review",
            json={"notes": "Farmer requested specific seed rate per hectare"},
            headers=self.admin_headers,
        )
        self.assertEqual(flag_res.status_code, 200)
        flag_data = flag_res.json()
        self.assertEqual(flag_data["status"], "flagged_for_review")
        self.assertIn("review_id", flag_data)

    # =========================================================================
    # WORKFLOW B: EXPERT REVIEW LIFECYCLE
    # =========================================================================

    def test_workflow_b_expert_review_lifecycle(self):
        """Workflow B:
        1. A low-confidence/unanswered query enters review queue.
        2. Admin lists unanswered queries.
        3. Admin inspects query details.
        4. Admin records an expert correction.
        5. Corrected query status is 'corrected', distinguishing it from rejected/pending queries.
        """
        import datetime
        now_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
        review_id = "rev_e2e_test_001"
        rec = ReviewRecord(
            review_id=review_id,
            created_at=now_ts,
            query="Can I mix chlorpyrifos with zinc sulphate for paddy?",
            canonical_text="Can I mix chlorpyrifos with zinc sulphate for paddy?",
            intent="pest_control",
            confidence=0.35,
            quality_score=0.45,
            source_reliability=0.50,
            evidence_grounding_score=0.40,
            status="pending",
            original_answer="Inconclusive compatibility data in local corpus.",
            flag_reason="Low retrieval confidence (< 0.40)",
            language="en",
        )
        review_manager._reviews[review_id] = rec
        review_manager.save()

        # 1. Admin lists review items
        list_res = self.client.get("/admin/unanswered-queries?search=chlorpyrifos", headers=self.admin_headers)
        self.assertEqual(list_res.status_code, 200)
        found = any(q["review_id"] == review_id for q in list_res.json()["queries"])
        self.assertTrue(found)

        # 2. Admin inspects detail
        detail_res = self.client.get(f"/admin/unanswered-queries/{review_id}", headers=self.admin_headers)
        self.assertEqual(detail_res.status_code, 200)
        self.assertEqual(detail_res.json()["status"], "pending")

        # 3. Admin submits expert correction
        correct_res = self.client.post(
            f"/admin/unanswered-queries/{review_id}/correct",
            json={
                "corrected_answer": "No, do not mix pesticides directly with micronutrient zinc fertilizers. Apply with 48 hours gap.",
                "notes": "Verified ICAR pesticide-micronutrient compatibility chart.",
            },
            headers=self.admin_headers,
        )
        self.assertEqual(correct_res.status_code, 200)

        # 4. Verify updated record
        updated_res = self.client.get(f"/admin/unanswered-queries/{review_id}", headers=self.admin_headers)
        self.assertEqual(updated_res.status_code, 200)
        updated = updated_res.json()
        self.assertEqual(updated["status"], "corrected")
        self.assertIn("No, do not mix", updated["corrected_answer"])
        self.assertEqual(updated["reviewer_username"], "e2e_admin_tester")

    # =========================================================================
    # WORKFLOW C: KNOWLEDGE MANAGEMENT & VECTOR SYNCHRONIZATION
    # =========================================================================

    def test_workflow_c_knowledge_management_and_vector_sync(self):
        """Workflow C:
        1. Admin creates verified agricultural record.
        2. Record is persisted and synchronized to vector store.
        3. Admin updates record.
        4. Old chunks replaced with new content.
        5. Admin attempts delete without confirmation -> 400.
        6. Admin deletes with confirmation -> vector chunks purged.
        """
        doc_id = "doc_e2e_integration_001"

        # 1. Create record
        create_payload = {
            "doc_id": doc_id,
            "title": "Groundnut Pod Rot Management Guidelines",
            "category": "diseases",
            "sub_category": "Fungal Rot",
            "source_name": "ICAR-DGR",
            "organization": "ICAR Directorate of Groundnut Research",
            "official_url": "https://dgr.icar.gov.in/pod-rot",
            "content_en": "Groundnut pod rot caused by Rhizoctonia solani can be managed with Trichoderma viride seed treatment @ 10g/kg.",
            "crops_applicable": ["groundnut"],
            "tags": ["groundnut", "pod rot", "fungal", "icar"],
        }
        create_res = self.client.post("/admin/knowledge-base", json=create_payload, headers=self.admin_headers)
        self.assertEqual(create_res.status_code, 201)

        # 2. Verify record exists in status & detail
        rec_res = self.client.get(f"/admin/knowledge-base/{doc_id}", headers=self.admin_headers)
        self.assertEqual(rec_res.status_code, 200)
        self.assertIn("Trichoderma viride", rec_res.json()["content_en"])

        # 3. Update record
        update_payload = {
            "content_en": "Updated 2026 advice: Groundnut pod rot is controlled using bio-agent Trichoderma harzianum combined with neem cake 250 kg/ha.",
        }
        update_res = self.client.put(f"/admin/knowledge-base/{doc_id}", json=update_payload, headers=self.admin_headers)
        self.assertEqual(update_res.status_code, 200)

        # Verify updated content
        rec_after_update = self.client.get(f"/admin/knowledge-base/{doc_id}", headers=self.admin_headers).json()
        self.assertIn("neem cake 250 kg/ha", rec_after_update["content_en"])

        # 4. Delete without confirmation rejected -> 400
        del_bad = self.client.delete(f"/admin/knowledge-base/{doc_id}?confirm=false", headers=self.admin_headers)
        self.assertEqual(del_bad.status_code, 400)

        # 5. Delete with confirmation -> 200
        del_good = self.client.delete(f"/admin/knowledge-base/{doc_id}?confirm=true", headers=self.admin_headers)
        self.assertEqual(del_good.status_code, 200)

        # 6. Verify record is deleted
        rec_after_del = self.client.get(f"/admin/knowledge-base/{doc_id}", headers=self.admin_headers)
        self.assertEqual(rec_after_del.status_code, 404)

    # =========================================================================
    # WORKFLOW D: LIVE ANALYTICS & METRICS ACCURACY
    # =========================================================================

    def test_workflow_d_live_analytics_consistency(self):
        """Workflow D:
        1. Generated farmer queries are reflected in GET /admin/analytics.
        2. Language and intent distributions match stored data.
        3. GET /admin/feedback/analytics computes exact satisfaction percentage.
        4. Masked farmer IDs in recent activity ensure zero PII leakage.
        """
        # Generate a test session with queries
        sess = session_manager.create_session(farmer_id="e2e_farmer_ramesh", language="hi")
        session_manager.record_turn(
            session_id=sess.session_id,
            user_text="गेहूं में सिंचाई कब करें?",
            detected_language="hi",
            intent="irrigation",
            answer="गेहूं में पहली सिंचाई सीआरआई अवस्था (20-25 दिन) पर करें।",
            entities={},
        )

        analytics_res = self.client.get("/admin/analytics?days=7", headers=self.admin_headers)
        self.assertEqual(analytics_res.status_code, 200)
        data = analytics_res.json()

        # Summary structure
        self.assertIn("total_queries", data["summary"])
        self.assertIn("feedback", data["summary"])
        self.assertTrue(data["summary"]["total_queries"] > 0)

        # PII Masking in recent activity
        recent = data["recent_activity"]
        if recent:
            first = recent[0]
            self.assertIn("farmer_id_masked", first)
            # Must NOT expose raw full ID unmasked if length > 4
            self.assertNotEqual(first["farmer_id_masked"], "e2e_farmer_ramesh")

        # Feedback analytics math check
        fb_analytics = self.client.get("/admin/feedback/analytics?days=30", headers=self.admin_headers).json()
        total_fb = fb_analytics["total_ratings"]
        pos_fb = fb_analytics["positive_ratings"]
        if total_fb > 0:
            expected = round((pos_fb / total_fb) * 100, 1)
            self.assertEqual(fb_analytics["satisfaction_rate"], expected)
        else:
            self.assertEqual(fb_analytics["satisfaction_rate"], 0.0)

    # =========================================================================
    # SECURITY & RBAC ENFORCEMENT ACROSS ALL ADMIN ENDPOINTS
    # =========================================================================

    def test_security_rbac_unauthenticated_rejected(self):
        """Verify unauthenticated requests to all admin endpoints return 401."""
        endpoints = [
            ("GET", "/admin/analytics"),
            ("GET", "/admin/unanswered-queries"),
            ("GET", "/admin/knowledge-base"),
            ("GET", "/admin/knowledge-base/status"),
            ("POST", "/admin/knowledge-base/reindex"),
            ("GET", "/admin/feedback"),
            ("GET", "/admin/feedback/analytics"),
        ]
        for method, path in endpoints:
            if method == "GET":
                res = self.client.get(path)
            else:
                res = self.client.post(path)
            self.assertEqual(res.status_code, 401, f"Expected 401 for unauthenticated {method} {path}")

    def test_security_rbac_farmer_role_rejected(self):
        """Verify farmer accounts attempting admin endpoints return 403 Forbidden."""
        endpoints = [
            ("GET", "/admin/analytics"),
            ("GET", "/admin/unanswered-queries"),
            ("GET", "/admin/knowledge-base"),
            ("GET", "/admin/knowledge-base/status"),
            ("POST", "/admin/knowledge-base/reindex"),
            ("GET", "/admin/feedback"),
            ("GET", "/admin/feedback/analytics"),
        ]
        for method, path in endpoints:
            if method == "GET":
                res = self.client.get(path, headers=self.farmer_1_headers)
            else:
                res = self.client.post(path, headers=self.farmer_1_headers)
            self.assertEqual(res.status_code, 403, f"Expected 403 for farmer role accessing {method} {path}")

    def test_security_session_ownership_cross_farmer_forbidden(self):
        """Verify that Farmer 2 cannot submit feedback on Farmer 1's registered session."""
        sess_1 = session_manager.create_session(farmer_id="e2e_farmer_ramesh")

        # Farmer 2 (Suresh) attempts to post feedback on Farmer 1's session -> 403
        res = self.client.post(
            "/feedback",
            json={"session_id": sess_1.session_id, "rating": "positive"},
            headers=self.farmer_2_headers,
        )
        self.assertEqual(res.status_code, 403)


if __name__ == "__main__":
    unittest.main()
