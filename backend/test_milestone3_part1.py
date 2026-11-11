"""Comprehensive Automated Test Suite for FarmSaathi Milestone 3 – Part 1.

Verifies:
  1. Session creation (POST /sessions, manager.create_session).
  2. Session retrieval (GET /sessions/{session_id}, manager.get_session).
  3. Session deletion / deactivation (DELETE /sessions/{session_id}).
  4. Conversation storage (user & assistant messages in SQLite).
  5. Conversation history retrieval (GET /sessions/{session_id}/history, chronological order, limit).
  6. Multi-turn context passing (resolving "it" to previous tomato fertilizer discussion).
  7. Different users having isolated sessions (zero cross-session contamination).
  8. Invalid session handling (404 for bad IDs, 400 for expired/inactive, 400 for empty question).
  9. Concurrent session handling (multi-threaded requests without locking errors).
  10. Existing /ask endpoint backward compatibility (text field, no session_id).
  11. Existing RAG pipeline integration (grounded ICAR evidence, sources, confidence).
  12. Isolated temporary test database cleanup.
"""

from __future__ import annotations

import os
import re
import tempfile
import threading
import time
import unittest
from pathlib import Path
from fastapi.testclient import TestClient

from main import app
from session_manager import (
    SessionManager,
    FarmerSession,
    ConversationMessage,
    ConversationTurn,
    SESSION_TTL_SECONDS,
    session_manager as global_session_manager,
)
from rag_pipeline import rag_pipeline


class TestMilestone3Part1(unittest.TestCase):
    """Milestone 3 Part 1 full verification suite."""

    def setUp(self):
        # Create an isolated temporary SQLite database for each test
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_sessions.db"
        self.mgr = SessionManager(db_path=self.db_path)
        self.mgr.clear_all()
        self.client = TestClient(app)

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    # -----------------------------------------------------------------------
    # 1. Session Creation
    # -----------------------------------------------------------------------
    def test_session_creation_api(self):
        """POST /sessions returns 201 Created with valid schema and unique UUID4."""
        resp = self.client.post("/sessions", json={"farmer_id": "farmer_101", "language": "hi"})
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertIn("session_id", data)
        self.assertEqual(data["farmer_id"], "farmer_101")
        self.assertEqual(data["language"], "hi")
        self.assertTrue(data["is_active"])
        self.assertIn("created_at", data)
        self.assertIn("updated_at", data)
        # Verify UUID4 format
        uuid4_pattern = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
        self.assertRegex(data["session_id"], uuid4_pattern)

    def test_session_creation_anonymous(self):
        """POST /sessions allows anonymous session creation with default language."""
        resp = self.client.post("/sessions", json={})
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertIsNone(data["farmer_id"])
        self.assertEqual(data["language"], "en")
        self.assertTrue(data["is_active"])

    # -----------------------------------------------------------------------
    # 2. Session Retrieval
    # -----------------------------------------------------------------------
    def test_session_retrieval_api(self):
        """GET /sessions/{session_id} retrieves the correct session metadata."""
        create_resp = self.client.post("/sessions", json={"farmer_id": "farmer_202", "language": "ta"})
        sid = create_resp.json()["session_id"]

        get_resp = self.client.get(f"/sessions/{sid}")
        self.assertEqual(get_resp.status_code, 200)
        data = get_resp.json()
        self.assertEqual(data["session_id"], sid)
        self.assertEqual(data["farmer_id"], "farmer_202")
        self.assertEqual(data["language"], "ta")
        self.assertTrue(data["is_active"])

    def test_session_retrieval_persisted_in_sqlite(self):
        """Verify session is persisted and queryable from SQLite disk."""
        session = self.mgr.create_session(farmer_id="farmer_db_test", language="en")
        sid = session.session_id

        # Reload through a completely new manager pointing to the same file
        reloaded_mgr = SessionManager(db_path=self.db_path)
        reloaded_sess = reloaded_mgr.get_session(sid)
        self.assertIsNotNone(reloaded_sess)
        self.assertEqual(reloaded_sess.session_id, sid)
        self.assertEqual(reloaded_sess.farmer_id, "farmer_db_test")

    # -----------------------------------------------------------------------
    # 3. Session Deletion / Deactivation
    # -----------------------------------------------------------------------
    def test_session_deletion_api(self):
        """DELETE /sessions/{session_id} deactivates session safely."""
        create_resp = self.client.post("/sessions", json={})
        sid = create_resp.json()["session_id"]

        del_resp = self.client.delete(f"/sessions/{sid}")
        self.assertEqual(del_resp.status_code, 200)
        del_data = del_resp.json()
        self.assertEqual(del_data["status"], "deactivated")

        # Subsequent GET returns 404 (session deactivated)
        get_resp = self.client.get(f"/sessions/{sid}")
        self.assertEqual(get_resp.status_code, 404)

        # Subsequent /ask with deactivated session returns 400
        ask_resp = self.client.post("/ask", json={"session_id": sid, "question": "Watering tomato"})
        self.assertEqual(ask_resp.status_code, 400)
        self.assertIn("expired or inactive", ask_resp.json()["detail"].lower())

    # -----------------------------------------------------------------------
    # 4. Conversation Storage (User Questions & Assistant Responses)
    # -----------------------------------------------------------------------
    def test_conversation_storage_user_and_assistant(self):
        """Each turn records both user question and assistant response in SQLite."""
        session = self.mgr.create_session(language="en")
        sid = session.session_id

        self.mgr.record_turn(
            session_id=sid,
            user_text="What is the best fertilizer for tomato?",
            detected_language="en",
            intent="crop_advisory",
            answer="Apply balanced NPK 10:26:26 or vermicompost every 15 days.",
            entities={"crops": ["tomato"], "fertilizers": ["npk"]},
            sources=["ICAR Research Bulletin (ICAR)"],
            confidence=0.88,
        )

        messages = self.mgr.get_history(sid)
        self.assertEqual(len(messages), 2)
        user_msg = messages[0]
        asst_msg = messages[1]

        self.assertEqual(user_msg.role, "user")
        self.assertEqual(user_msg.content, "What is the best fertilizer for tomato?")
        self.assertEqual(user_msg.intent, "crop_advisory")

        self.assertEqual(asst_msg.role, "assistant")
        self.assertIn("NPK", asst_msg.content)
        self.assertIn("ICAR Research Bulletin (ICAR)", asst_msg.sources)
        self.assertEqual(asst_msg.confidence, 0.88)

    # -----------------------------------------------------------------------
    # 5. Conversation History Retrieval
    # -----------------------------------------------------------------------
    def test_conversation_history_retrieval_api(self):
        """GET /sessions/{session_id}/history returns messages in chronological order."""
        sess_resp = self.client.post("/sessions", json={})
        sid = sess_resp.json()["session_id"]

        # Ask first question
        self.client.post(
            "/ask",
            json={"session_id": sid, "question": "What is the best fertilizer for tomato?"},
        )
        # Ask second question
        self.client.post(
            "/ask",
            json={"session_id": sid, "question": "How often should I apply it?"},
        )

        hist_resp = self.client.get(f"/sessions/{sid}/history")
        self.assertEqual(hist_resp.status_code, 200)
        data = hist_resp.json()
        self.assertEqual(data["session_id"], sid)
        self.assertEqual(data["count"], 4)  # 2 user questions + 2 assistant responses
        messages = data["messages"]
        self.assertEqual(messages[0]["role"], "user")
        self.assertEqual(messages[1]["role"], "assistant")
        self.assertEqual(messages[2]["role"], "user")
        self.assertEqual(messages[3]["role"], "assistant")

        # Test limit query parameter
        limit_resp = self.client.get(f"/sessions/{sid}/history?limit=2")
        self.assertEqual(limit_resp.status_code, 200)
        self.assertEqual(len(limit_resp.json()["messages"]), 2)

    # -----------------------------------------------------------------------
    # 6. Multi-Turn Dialogue Context Passing
    # -----------------------------------------------------------------------
    def test_multi_turn_context_fertilizer_followup(self):
        """Verify follow-up query 'How often should I apply it?' resolves 'it' to tomato fertilizer."""
        sess_resp = self.client.post("/sessions", json={"language": "en"})
        sid = sess_resp.json()["session_id"]

        # Turn 1
        t1_resp = self.client.post(
            "/ask",
            json={"session_id": sid, "question": "What is the best fertilizer for tomato?"},
        )
        self.assertEqual(t1_resp.status_code, 200)
        t1_data = t1_resp.json()
        self.assertIn("tomato", t1_data["entities"]["crops"])

        # Turn 2: Follow-up with pronoun 'it'
        t2_resp = self.client.post(
            "/ask",
            json={"session_id": sid, "question": "How often should I apply it?"},
        )
        self.assertEqual(t2_resp.status_code, 200)
        t2_data = t2_resp.json()

        # The system must resolve 'it' to the active crop 'tomato'
        self.assertIn("tomato", t2_data["entities"]["crops"])
        self.assertTrue(t2_data["entities"].get("_crop_carried_from_context"))

        # The answer must ground the follow-up in the previous context
        self.assertIn("Based on the previous discussion", t2_data["answer"])
        self.assertIn("Tomato", t2_data["answer"])

        # Safety guardrails: Official sources and guidance must be present
        self.assertGreater(len(t2_data["sources"]), 0)
        self.assertFalse(t2_data["is_low_confidence"])

    # -----------------------------------------------------------------------
    # 7. Isolated Sessions for Different Farmers
    # -----------------------------------------------------------------------
    def test_session_isolation_different_farmers(self):
        """Entities and context from Farmer A never leak into Farmer B's session."""
        s1 = self.client.post("/sessions", json={"farmer_id": "farmer_A"}).json()["session_id"]
        s2 = self.client.post("/sessions", json={"farmer_id": "farmer_B"}).json()["session_id"]

        # Farmer A asks about Paddy blast disease
        self.client.post("/ask", json={"session_id": s1, "question": "Paddy blast disease control"})

        # Farmer B asks about Cotton bollworm
        self.client.post("/ask", json={"session_id": s2, "question": "Cotton pink bollworm pest"})

        # Farmer A follow-up
        a2_resp = self.client.post("/ask", json={"session_id": s1, "question": "What fungicide to spray on it?"})
        a2_data = a2_resp.json()
        self.assertIn("paddy", a2_data["entities"]["crops"])
        self.assertNotIn("cotton", a2_data["entities"]["crops"])

        # Farmer B follow-up
        b2_resp = self.client.post("/ask", json={"session_id": s2, "question": "How often to spray?"})
        b2_data = b2_resp.json()
        self.assertIn("cotton", b2_data["entities"]["crops"])
        self.assertNotIn("paddy", b2_data["entities"]["crops"])

    # -----------------------------------------------------------------------
    # 8. Error Handling (Invalid IDs, Expired Sessions, Missing Questions)
    # -----------------------------------------------------------------------
    def test_invalid_session_id_404(self):
        """GET, DELETE, and /ask with invalid session ID return 404."""
        r1 = self.client.get("/sessions/nonexistent-session-12345")
        self.assertEqual(r1.status_code, 404)

        r2 = self.client.get("/sessions/nonexistent-session-12345/history")
        self.assertEqual(r2.status_code, 404)

        r3 = self.client.delete("/sessions/nonexistent-session-12345")
        self.assertEqual(r3.status_code, 404)

        r4 = self.client.post("/ask", json={"session_id": "nonexistent-session-12345", "question": "Watering tomato"})
        self.assertEqual(r4.status_code, 404)

    def test_missing_or_empty_question_400(self):
        """POST /ask rejects empty or whitespace-only questions with 400."""
        r1 = self.client.post("/ask", json={"question": ""})
        self.assertEqual(r1.status_code, 400)
        self.assertIn("farming question", r1.json()["detail"].lower())

        r2 = self.client.post("/ask", json={"question": "   \n\t   "})
        self.assertEqual(r2.status_code, 400)

        r3 = self.client.post("/ask", json={})
        self.assertEqual(r3.status_code, 400)

    def test_session_idle_expiration(self):
        """Session expires when idle time exceeds SESSION_TTL_SECONDS."""
        session = self.mgr.create_session()
        sid = session.session_id

        # Artificially backdate last_active
        session.last_active = time.time() - SESSION_TTL_SECONDS - 10
        self.mgr._store[sid].last_active = session.last_active

        retrieved = self.mgr.get_session(sid)
        self.assertIsNone(retrieved, "Expired session must return None")

    # -----------------------------------------------------------------------
    # 9. Concurrent Session Handling
    # -----------------------------------------------------------------------
    def test_concurrent_session_creation_and_recording(self):
        """Verify thread-safety and SQLite concurrency under high load."""
        created_sids = []
        errors = []

        def worker(idx: int):
            try:
                s = self.mgr.create_session(farmer_id=f"farmer_{idx}")
                created_sids.append(s.session_id)
                self.mgr.record_turn(
                    session_id=s.session_id,
                    user_text=f"Question from worker {idx}",
                    detected_language="en",
                    intent="crop_advisory",
                    answer=f"Answer for worker {idx}",
                    entities={"crops": ["wheat"]},
                )
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Concurrent execution errors: {errors}")
        self.assertEqual(len(set(created_sids)), 20)

    # -----------------------------------------------------------------------
    # 10. Backward Compatibility of /ask Endpoint
    # -----------------------------------------------------------------------
    def test_ask_backward_compatibility(self):
        """Legacy clients sending 'text' without 'session_id' work seamlessly."""
        resp = self.client.post(
            "/ask",
            json={"text": "How often should I water my tomato plants in black soil?"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        # Legacy fields
        self.assertIn("input_text", data)
        self.assertIn("canonical_text", data)
        self.assertEqual(data["language_code"], "en")
        self.assertIn("tomato", data["entities"]["crops"])
        self.assertIn("black", data["entities"]["soil"])
        self.assertIn("retrieved_documents", data)
        self.assertIn("quality_score", data)

        # Milestone 3 Part 1 new fields
        self.assertIn("session_id", data)
        self.assertIn("question", data)
        self.assertIn("answer", data)
        self.assertIn("sources", data)
        self.assertIn("confidence", data)

    # -----------------------------------------------------------------------
    # 11. Existing RAG Pipeline Integration & Agricultural Grounding
    # -----------------------------------------------------------------------
    def test_rag_pipeline_grounding_preserved(self):
        """RAG grounded response and official source citations remain verified."""
        resp = self.client.post(
            "/ask",
            json={"question": "What are the water requirements for wheat crop?", "preferred_language": "en"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("wheat", data["entities"]["crops"])
        self.assertGreater(len(data["sources"]), 0)
        self.assertIn("ICAR", data["sources"][0])
        self.assertGreater(data["confidence"], 0.60)
        self.assertGreaterEqual(data["rag_confidence"], 0.70)


if __name__ == "__main__":
    unittest.main()
