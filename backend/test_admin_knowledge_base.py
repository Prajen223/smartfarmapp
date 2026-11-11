"""Tests for Admin Knowledge Base Management, Vector Synchronization & RBAC.

Milestone 3 - Part 4.3:
  • GET /admin/knowledge-base (listing, search, category/crop/language filters, pagination)
  • GET /admin/knowledge-base/status (synchronization health, backend, chunk count)
  • GET /admin/knowledge-base/{record_id} (detail & 404 for invalid ID)
  • POST /admin/knowledge-base (create & vector store synchronization)
  • PUT /admin/knowledge-base/{record_id} (update & vector chunk re-indexing)
  • DELETE /admin/knowledge-base/{record_id} (delete & vector chunk purging)
  • POST /admin/knowledge-base/reindex (controlled full vector index rebuild)
  • POST /admin/knowledge-base/upload (document parsing and text preview)
  • RBAC protection (401 unauthenticated, 403 farmer, 200 admin)
  • Deduplication and validation error handling
  • PII protection in knowledge content
"""

from __future__ import annotations

import io
import unittest
from fastapi.testclient import TestClient

from main import app
from security import security_user_manager
from rag_pipeline import rag_pipeline


class TestAdminKnowledgeBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

        # Create or ensure admin account exists
        admin_user = security_user_manager.get_user_by_username("kb_admin_tester")
        if not admin_user:
            security_user_manager.register_user(
                username="kb_admin_tester",
                password="AdminPassword123!",
                role="admin",
            )
        admin_login = cls.client.post(
            "/auth/login",
            json={"username": "kb_admin_tester", "password": "AdminPassword123!"},
        )
        cls.admin_token = admin_login.json()["access_token"]
        cls.admin_headers = {"Authorization": f"Bearer {cls.admin_token}"}

        # Create or ensure farmer account exists
        farmer_user = security_user_manager.get_user_by_username("kb_farmer_tester")
        if not farmer_user:
            security_user_manager.register_user(
                username="kb_farmer_tester",
                password="FarmerPassword123!",
                role="farmer",
            )
        farmer_login = cls.client.post(
            "/auth/login",
            json={"username": "kb_farmer_tester", "password": "FarmerPassword123!"},
        )
        cls.farmer_token = farmer_login.json()["access_token"]
        cls.farmer_headers = {"Authorization": f"Bearer {cls.farmer_token}"}

    def test_unauthenticated_requests_rejected(self):
        """Verify unauthenticated requests terminate with 401 Unauthorized."""
        res_list = self.client.get("/admin/knowledge-base")
        self.assertEqual(res_list.status_code, 401)

        res_status = self.client.get("/admin/knowledge-base/status")
        self.assertEqual(res_status.status_code, 401)

        res_detail = self.client.get("/admin/knowledge-base/doc_crop_001")
        self.assertEqual(res_detail.status_code, 401)

        res_post = self.client.post("/admin/knowledge-base", json={"title": "Test"})
        self.assertEqual(res_post.status_code, 401)

        res_reindex = self.client.post("/admin/knowledge-base/reindex")
        self.assertEqual(res_reindex.status_code, 401)

    def test_farmer_role_forbidden(self):
        """Verify farmer accounts are prohibited from knowledge base management (403 Forbidden)."""
        res_list = self.client.get("/admin/knowledge-base", headers=self.farmer_headers)
        self.assertEqual(res_list.status_code, 403)
        self.assertIn("Forbidden", res_list.json().get("detail", ""))

        res_status = self.client.get("/admin/knowledge-base/status", headers=self.farmer_headers)
        self.assertEqual(res_status.status_code, 403)

        res_delete = self.client.delete(
            "/admin/knowledge-base/doc_crop_001",
            headers=self.farmer_headers,
        )
        self.assertEqual(res_delete.status_code, 403)

    def test_admin_list_records_and_stats(self):
        """Verify authenticated admin receives paginated knowledge records and sync statistics."""
        res = self.client.get("/admin/knowledge-base", headers=self.admin_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        for key in ("records", "total", "limit", "offset", "stats"):
            self.assertIn(key, data, f"Missing key {key} in response")

        stats = data["stats"]
        for stat_key in ("total_records", "category_counts", "top_crops", "vector_chunks", "vector_backend", "in_sync"):
            self.assertIn(stat_key, stats, f"Missing stat key {stat_key}")

        self.assertGreaterEqual(data["total"], 1)
        self.assertIsInstance(data["records"], list)
        self.assertTrue(stats["vector_chunks"] > 0)

    def test_filter_by_category(self):
        """Verify category filtering isolates matching domain records."""
        res = self.client.get(
            "/admin/knowledge-base?category=crops",
            headers=self.admin_headers,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        for r in data["records"]:
            self.assertEqual(r["category"], "crops")

    def test_filter_by_crop(self):
        """Verify crop filtering isolates records applicable to that crop."""
        res = self.client.get(
            "/admin/knowledge-base?crop=paddy",
            headers=self.admin_headers,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        for r in data["records"]:
            self.assertTrue(
                any("paddy" == c.lower() for c in r.get("crops_applicable", [])),
                f"Crop 'paddy' missing from {r['doc_id']}",
            )

    def test_filter_by_language(self):
        """Verify language filtering isolates records with content in that language."""
        res = self.client.get(
            "/admin/knowledge-base?language=hi",
            headers=self.admin_headers,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        for r in data["records"]:
            self.assertTrue(bool(r.get("content_hi", "").strip()))

    def test_search_filter(self):
        """Verify keyword search across titles and content."""
        res = self.client.get(
            "/admin/knowledge-base?search=water",
            headers=self.admin_headers,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertGreaterEqual(len(data["records"]), 1)

    def test_pagination(self):
        """Verify limit and offset boundary behavior."""
        res = self.client.get(
            "/admin/knowledge-base?limit=3&offset=0",
            headers=self.admin_headers,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertLessEqual(len(data["records"]), 3)
        self.assertEqual(data["limit"], 3)
        self.assertEqual(data["offset"], 0)

    def test_get_record_detail_and_not_found(self):
        """Verify retrieving specific document detail and 404 for invalid ID."""
        # Retrieve valid record
        res_list = self.client.get("/admin/knowledge-base?limit=1", headers=self.admin_headers)
        self.assertEqual(res_list.status_code, 200)
        first_id = res_list.json()["records"][0]["doc_id"]

        res_detail = self.client.get(
            f"/admin/knowledge-base/{first_id}",
            headers=self.admin_headers,
        )
        self.assertEqual(res_detail.status_code, 200)
        rec = res_detail.json()
        self.assertEqual(rec["doc_id"], first_id)
        self.assertIn("content_en", rec)
        self.assertIn("category", rec)
        self.assertIn("source_name", rec)

        # 404 for non-existent ID
        res_missing = self.client.get(
            "/admin/knowledge-base/doc_completely_nonexistent_999",
            headers=self.admin_headers,
        )
        self.assertEqual(res_missing.status_code, 404)

    def test_create_record_and_vector_sync(self):
        """Verify creating a new record updates authoritative dataset and synchronizes vector store."""
        unique_id = "doc_test_sync_001"
        # Ensure clean state
        self.client.delete(f"/admin/knowledge-base/{unique_id}?confirm=true", headers=self.admin_headers)

        payload = {
            "doc_id": unique_id,
            "category": "crops",
            "title": "Sunflower Package of Practices for Rainfed Farming",
            "sub_category": "oilseeds",
            "source_name": "ICAR-IIOR",
            "organization": "Indian Institute of Oilseeds Research",
            "official_url": "https://icar.gov.in/sunflower",
            "content_en": (
                "Sunflower Package of Practices: Sow during rabi season with 5 kg seed per hectare. "
                "Apply 60 kg N, 60 kg P2O5, and 30 kg K2O per hectare. Irrigate at buttoning, flowering, and seed development stages."
            ),
            "content_hi": "सूरजमुखी की उन्नत खेती: रबी मौसम में 5 किग्रा प्रति हेक्टेयर बीज दर रखें।",
            "crops_applicable": ["sunflower"],
            "soil_types_applicable": ["black_soil", "sandy_loam"],
            "tags": ["sunflower", "oilseed", "irrigation", "npk"],
            "guardrail_notice": "Do not allow water logging during seed filling.",
        }

        # Initial chunk count
        initial_chunks = rag_pipeline.vector_store.count()

        create_res = self.client.post(
            "/admin/knowledge-base",
            json=payload,
            headers=self.admin_headers,
        )
        self.assertEqual(create_res.status_code, 201)
        body = create_res.json()
        self.assertEqual(body["record"]["doc_id"], unique_id)

        # Verify vector store synchronized
        new_chunks = rag_pipeline.vector_store.count()
        self.assertGreater(new_chunks, initial_chunks)

        # Verify retrieval from vector store finds the new doc
        search_results = rag_pipeline.vector_store.similarity_search("Sunflower rabi fertilizer NPK", top_k=5)
        matched_docs = [c[0].doc_id for c in search_results]
        self.assertIn(unique_id, matched_docs)

        # Clean up
        self.client.delete(f"/admin/knowledge-base/{unique_id}?confirm=true", headers=self.admin_headers)

    def test_create_duplicate_record_rejected(self):
        """Verify attempting to create a record with an existing doc_id returns 409 Conflict."""
        # Using doc_crop_001 which is present in the standard dataset
        payload = {
            "doc_id": "doc_crop_001",
            "category": "crops",
            "title": "Paddy Package of Practices Duplicate",
            "source_name": "ICAR",
            "organization": "Central Rice Research",
            "official_url": "https://icar.gov.in/rice",
            "content_en": "Duplicate content for paddy package of practices with over 30 characters.",
            "guardrail_notice": "Follow official agricultural advisory.",
        }
        res = self.client.post(
            "/admin/knowledge-base",
            json=payload,
            headers=self.admin_headers,
        )
        self.assertEqual(res.status_code, 409)
        self.assertIn("already exists", res.json()["detail"].lower())

    def test_update_record_and_vector_resync(self):
        """Verify updating a record updates dataset and replaces vector store chunks."""
        test_id = "doc_test_update_001"
        # Seed record
        create_payload = {
            "doc_id": test_id,
            "category": "crops",
            "title": "Groundnut Cultivation Methods",
            "source_name": "ICAR-DGR",
            "organization": "Directorate of Groundnut Research",
            "official_url": "https://icar.gov.in/groundnut",
            "content_en": "Groundnut requires sandy loam soil with good drainage. Spacing of 30x10 cm is recommended.",
            "crops_applicable": ["groundnut"],
            "guardrail_notice": "Avoid deep sowing to ensure uniform seedling emergence.",
        }
        self.client.post("/admin/knowledge-base", json=create_payload, headers=self.admin_headers)

        update_payload = {
            "title": "Groundnut Cultivation Methods (Updated ICAR Guideline)",
            "content_en": (
                "Updated Groundnut Practices: Adopt gypsum application @ 400 kg/ha at flowering stage. "
                "Foliar spray of 0.5% Ferrous Sulphate corrects lime-induced iron chlorosis in groundnut."
            ),
            "tags": ["groundnut", "gypsum", "iron-chlorosis"],
        }

        update_res = self.client.put(
            f"/admin/knowledge-base/{test_id}",
            json=update_payload,
            headers=self.admin_headers,
        )
        self.assertEqual(update_res.status_code, 200)
        body = update_res.json()
        self.assertEqual(body["record"]["title"], "Groundnut Cultivation Methods (Updated ICAR Guideline)")

        # Verify updated content is searchable
        search_results = rag_pipeline.vector_store.similarity_search("Gypsum application for groundnut chlorosis", top_k=5)
        matched_docs = [c[0].doc_id for c in search_results]
        self.assertIn(test_id, matched_docs)

        # Clean up
        self.client.delete(f"/admin/knowledge-base/{test_id}?confirm=true", headers=self.admin_headers)

    def test_delete_record_and_purge_vector_chunks(self):
        """Verify deleting a record removes it from dataset and purges its chunks from vector store."""
        delete_id = "doc_test_delete_001"
        create_payload = {
            "doc_id": delete_id,
            "category": "soil",
            "title": "Zinc Solubilizing Biofertilizer Application",
            "source_name": "ICAR-IISS",
            "organization": "Indian Institute of Soil Science",
            "official_url": "https://icar.gov.in/soil",
            "content_en": "Zinc solubilizing bacteria (ZSB) inoculants convert insoluble zinc compounds into plant-available forms in soil.",
            "crops_applicable": ["paddy", "wheat"],
            "guardrail_notice": "Do not mix biofertilizers with chemical fungicides.",
        }
        self.client.post("/admin/knowledge-base", json=create_payload, headers=self.admin_headers)

        # Verify it exists
        self.assertEqual(self.client.get(f"/admin/knowledge-base/{delete_id}", headers=self.admin_headers).status_code, 200)

        del_res = self.client.delete(
            f"/admin/knowledge-base/{delete_id}?confirm=true",
            headers=self.admin_headers,
        )
        self.assertEqual(del_res.status_code, 200)
        body = del_res.json()
        self.assertGreaterEqual(body["deleted_chunks"], 1)

        # Verify record no longer exists
        get_res = self.client.get(f"/admin/knowledge-base/{delete_id}", headers=self.admin_headers)
        self.assertEqual(get_res.status_code, 404)

        # Verify deleted doc chunks are no longer returned
        search_results = rag_pipeline.vector_store.similarity_search("Zinc solubilizing bacteria biofertilizer", top_k=10)
        matched_docs = [c[0].doc_id for c in search_results]
        self.assertNotIn(delete_id, matched_docs)

    def test_delete_without_confirm_rejected(self):
        """Verify deletion requires explicit confirm query parameter."""
        res = self.client.delete(
            "/admin/knowledge-base/doc_crop_001?confirm=false",
            headers=self.admin_headers,
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("confirmation", res.json()["detail"].lower())

    def test_reindex_endpoint(self):
        """Verify controlled full re-indexing of all knowledge documents."""
        res = self.client.post("/admin/knowledge-base/reindex", headers=self.admin_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        for key in ("status", "records_processed", "chunks_indexed", "duration_ms", "backend"):
            self.assertIn(key, data)

        self.assertEqual(data["status"], "completed")
        self.assertGreaterEqual(data["records_processed"], 20)
        self.assertGreaterEqual(data["chunks_indexed"], 20)
        self.assertGreater(data["duration_ms"], 0)

    def test_status_endpoint(self):
        """Verify synchronization health status inspection."""
        res = self.client.get("/admin/knowledge-base/status", headers=self.admin_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        for key in ("backend", "total_records", "total_chunks", "is_synchronized", "categories", "crops", "languages_supported"):
            self.assertIn(key, data)

        self.assertTrue(data["is_synchronized"])
        self.assertIn("en", data["languages_supported"])
        self.assertIn("crops", data["categories"])

    def test_upload_preview_text_document(self):
        """Verify uploading a document returns plain text extraction and metadata preview."""
        sample_doc = (
            "# Black Gram (Urdbean) Yellow Mosaic Virus Management\n\n"
            "Yellow Mosaic Disease in Urdbean is transmitted by Whitefly (Bemisia tabaci).\n"
            "Management Practices:\n"
            "1. Seed treatment with Imidacloprid 70 WS @ 5 g/kg seed.\n"
            "2. Install yellow sticky traps (15 per acre).\n"
            "3. Spray Thiamethoxam 25 WG @ 0.2 g/litre if whitefly threshold exceeds 5 per plant.\n"
        )
        file_bytes = sample_doc.encode("utf-8")

        res = self.client.post(
            "/admin/knowledge-base/upload",
            files={"file": ("urdbean_guideline.md", io.BytesIO(file_bytes), "text/markdown")},
            headers=self.admin_headers,
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("preview", data)
        preview = data["preview"]
        self.assertEqual(preview["filename"], "urdbean_guideline.md")
        self.assertIn("Yellow Mosaic", preview["extracted_text"])
        self.assertGreater(preview["word_count"], 10)
        self.assertEqual(preview["suggested_category"], "diseases")

    def test_upload_empty_or_unsupported_rejected(self):
        """Verify empty files or disallowed extensions are safely rejected."""
        # Empty file
        empty_res = self.client.post(
            "/admin/knowledge-base/upload",
            files={"file": ("empty.txt", io.BytesIO(b""), "text/plain")},
            headers=self.admin_headers,
        )
        self.assertEqual(empty_res.status_code, 400)

        # Disallowed binary extension
        disallowed_res = self.client.post(
            "/admin/knowledge-base/upload",
            files={"file": ("script.exe", io.BytesIO(b"MZ123"), "application/octet-stream")},
            headers=self.admin_headers,
        )
        self.assertEqual(disallowed_res.status_code, 400)
        self.assertIn("unsupported", disallowed_res.json()["detail"].lower())

    def test_pii_sanitization_in_knowledge_content(self):
        """Verify farmer phone/email in submitted knowledge content is automatically redacted."""
        test_id = "doc_test_pii_001"
        payload = {
            "doc_id": test_id,
            "category": "farming_practices",
            "title": "KVK Contact and Sprayer Calibration",
            "content_en": "Contact officer Raman at 9876543210 or email raman.kvk@gov.in for nozzle calibration. Package of practices must be followed.",
            "source_name": "ICAR-KVK",
            "organization": "Krishi Vigyan Kendra",
            "official_url": "https://icar.gov.in/kvk",
            "guardrail_notice": "Do not operate sprayers without protective gear.",
        }
        res = self.client.post(
            "/admin/knowledge-base",
            json=payload,
            headers=self.admin_headers,
        )
        self.assertEqual(res.status_code, 201)
        created = res.json()["record"]
        self.assertNotIn("9876543210", created["content_en"])
        self.assertNotIn("raman.kvk@gov.in", created["content_en"])
        self.assertIn("[REDACTED_PHONE]", created["content_en"])
        self.assertIn("[REDACTED_EMAIL]", created["content_en"])

        # Clean up
        self.client.delete(f"/admin/knowledge-base/{test_id}?confirm=true", headers=self.admin_headers)
