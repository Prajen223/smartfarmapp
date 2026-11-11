"""Tests for Stage D: session_manager.py and /ask session integration.

Run with:  venv\\Scripts\\pytest test_session_manager.py -v
"""

import threading
import time
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from session_manager import (
    SessionManager,
    Session,
    ConversationTurn,
    MAX_HISTORY_TURNS,
    SESSION_TTL_SECONDS,
)
from main import app


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_manager() -> SessionManager:
    """Return a fresh, empty SessionManager for each test."""
    m = SessionManager()
    m.clear_all()
    return m


def _sample_turn(n: int = 1) -> dict:
    return dict(
        user_text=f"Question number {n}",
        detected_language="en",
        intent="irrigation",
        answer="Sample irrigation answer " * 5,
        entities={"crops": ["tomato"], "pests": [], "diseases": [], "fertilizers": [], "locations": []},
    )


# ---------------------------------------------------------------------------
# SessionManager unit tests
# ---------------------------------------------------------------------------

class TestSessionCreation(unittest.TestCase):

    def setUp(self):
        self.manager = _make_manager()

    def test_get_or_create_returns_session(self):
        s = self.manager.get_or_create(None)
        self.assertIsInstance(s, Session)

    def test_new_session_has_unique_id(self):
        ids = {self.manager.get_or_create(None).session_id for _ in range(10)}
        self.assertEqual(len(ids), 10, "Every new session must have a unique UUID")

    def test_session_id_is_uuid4_format(self):
        import re
        s = self.manager.get_or_create(None)
        uuid4_re = re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
        )
        self.assertRegex(s.session_id, uuid4_re)

    def test_passing_none_creates_new_session(self):
        s1 = self.manager.get_or_create(None)
        s2 = self.manager.get_or_create(None)
        self.assertNotEqual(s1.session_id, s2.session_id)

    def test_passing_existing_id_returns_same_session(self):
        s1 = self.manager.get_or_create(None)
        s2 = self.manager.get_or_create(s1.session_id)
        self.assertEqual(s1.session_id, s2.session_id)

    def test_empty_string_creates_new_session(self):
        s = self.manager.get_or_create("")
        self.assertIsInstance(s, Session)

    def test_session_count_increments(self):
        self.assertEqual(self.manager.session_count(), 0)
        self.manager.get_or_create(None)
        self.assertEqual(self.manager.session_count(), 1)
        self.manager.get_or_create(None)
        self.assertEqual(self.manager.session_count(), 2)


class TestConversationHistory(unittest.TestCase):

    def setUp(self):
        self.manager = _make_manager()
        self.session = self.manager.get_or_create(None)
        self.sid = self.session.session_id

    def test_new_session_has_empty_history(self):
        self.assertEqual(self.session.history, [])

    def test_record_turn_adds_to_history(self):
        self.manager.record_turn(self.sid, **_sample_turn(1))
        session = self.manager.get_session(self.sid)
        self.assertEqual(len(session.history), 1)

    def test_history_stores_correct_intent(self):
        self.manager.record_turn(self.sid, **_sample_turn(1))
        turn = self.manager.get_session(self.sid).history[0]
        self.assertEqual(turn.intent, "irrigation")

    def test_answer_is_capped_at_200_chars(self):
        long_answer = "x" * 500
        self.manager.record_turn(
            self.sid,
            user_text="question",
            detected_language="en",
            intent="pest_control",
            answer=long_answer,
            entities={},
        )
        turn = self.manager.get_session(self.sid).history[0]
        self.assertLessEqual(len(turn.answer_summary), 200)

    def test_history_capped_at_max_turns(self):
        for i in range(MAX_HISTORY_TURNS + 5):
            self.manager.record_turn(self.sid, **_sample_turn(i))
        session = self.manager.get_session(self.sid)
        self.assertEqual(len(session.history), MAX_HISTORY_TURNS)

    def test_oldest_turns_evicted_first(self):
        for i in range(MAX_HISTORY_TURNS + 3):
            self.manager.record_turn(
                self.sid,
                user_text=f"Question {i}",
                detected_language="en",
                intent="irrigation",
                answer="answer",
                entities={},
            )
        session = self.manager.get_session(self.sid)
        # The first remaining turn should be question 3 (index 3)
        first_remaining = session.history[0].user_text
        self.assertIn("3", first_remaining)

    def test_turn_number_increments(self):
        for i in range(3):
            self.manager.record_turn(self.sid, **_sample_turn(i))
        session = self.manager.get_session(self.sid)
        for idx, turn in enumerate(session.history):
            self.assertEqual(turn.turn_number, idx + 1)

    def test_record_turn_for_missing_session_does_not_raise(self):
        """Recording against a non-existent session must silently do nothing."""
        try:
            self.manager.record_turn("nonexistent-id", **_sample_turn())
        except Exception as exc:
            self.fail(f"record_turn raised unexpectedly: {exc}")


class TestLanguagePreferences(unittest.TestCase):

    def setUp(self):
        self.manager = _make_manager()
        self.session = self.manager.get_or_create(None)
        self.sid = self.session.session_id

    def test_initial_language_is_und(self):
        self.assertEqual(self.session.detected_language_code, "und")

    def test_record_turn_updates_detected_language(self):
        self.manager.record_turn(
            self.sid,
            user_text="question",
            detected_language="ta",
            intent="irrigation",
            answer="answer",
            entities={},
        )
        session = self.manager.get_session(self.sid)
        self.assertEqual(session.detected_language_code, "ta")

    def test_set_preferred_language_returns_true(self):
        result = self.manager.set_preferred_language(self.sid, "hi")
        self.assertTrue(result)

    def test_set_preferred_language_persisted(self):
        self.manager.set_preferred_language(self.sid, "kn")
        session = self.manager.get_session(self.sid)
        self.assertEqual(session.preferred_language, "kn")

    def test_set_preferred_language_unknown_session_returns_false(self):
        result = self.manager.set_preferred_language("bad-id", "hi")
        self.assertFalse(result)


class TestSessionExpiry(unittest.TestCase):

    def setUp(self):
        self.manager = _make_manager()

    def test_active_session_not_expired(self):
        s = self.manager.get_or_create(None)
        retrieved = self.manager.get_session(s.session_id)
        self.assertIsNotNone(retrieved)

    def test_stale_session_expires(self):
        s = self.manager.get_or_create(None)
        sid = s.session_id
        # Manually backdate last_active beyond TTL
        with self.manager._lock:
            self.manager._store[sid].last_active = time.time() - SESSION_TTL_SECONDS - 1
        # Next access should trigger passive expiry
        retrieved = self.manager.get_session(sid)
        self.assertIsNone(retrieved)

    def test_session_count_after_expiry(self):
        s = self.manager.get_or_create(None)
        with self.manager._lock:
            self.manager._store[s.session_id].last_active = time.time() - SESSION_TTL_SECONDS - 1
        self.assertEqual(self.manager.session_count(), 0)


class TestContextSummary(unittest.TestCase):

    def setUp(self):
        self.manager = _make_manager()
        self.session = self.manager.get_or_create(None)
        self.sid = self.session.session_id

    def test_context_summary_has_required_keys(self):
        summary = self.session.get_context_summary()
        for key in ("session_id", "turn_count", "detected_language_code",
                    "preferred_language", "last_intent"):
            self.assertIn(key, summary, f"Missing key '{key}' in context summary")

    def test_context_summary_last_intent_none_on_new_session(self):
        summary = self.session.get_context_summary()
        self.assertIsNone(summary["last_intent"])

    def test_context_summary_last_intent_after_turn(self):
        self.manager.record_turn(
            self.sid,
            user_text="pest question",
            detected_language="en",
            intent="pest_control",
            answer="answer",
            entities={},
        )
        session = self.manager.get_session(self.sid)
        summary = session.get_context_summary()
        self.assertEqual(summary["last_intent"], "pest_control")

    def test_context_summary_turn_count(self):
        for i in range(3):
            self.manager.record_turn(self.sid, **_sample_turn(i))
        session = self.manager.get_session(self.sid)
        self.assertEqual(session.get_context_summary()["turn_count"], 3)


class TestThreadSafety(unittest.TestCase):
    """Verify no data races under concurrent access."""

    def test_concurrent_session_creation(self):
        manager = _make_manager()
        results = []
        errors = []

        def create():
            try:
                s = manager.get_or_create(None)
                results.append(s.session_id)
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=create) for _ in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Thread errors: {errors}")
        self.assertEqual(len(set(results)), 50, "All 50 sessions should have unique IDs")

    def test_concurrent_record_turns(self):
        manager = _make_manager()
        session = manager.get_or_create(None)
        sid = session.session_id
        errors = []

        def record(n: int):
            try:
                manager.record_turn(sid, **_sample_turn(n))
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=record, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Thread errors: {errors}")
        # History should be capped at MAX_HISTORY_TURNS
        final = manager.get_session(sid)
        self.assertLessEqual(len(final.history), MAX_HISTORY_TURNS)


class TestSessionAPIIntegration(unittest.TestCase):
    """Verify /ask endpoint returns and reuses session IDs correctly."""

    def setUp(self):
        self.client = TestClient(app)

    def test_ask_returns_session_id(self):
        response = self.client.post(
            "/ask", json={"text": "How often should I water my tomato plants?"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("session_id", data)
        self.assertIsInstance(data["session_id"], str)
        self.assertTrue(len(data["session_id"]) > 0)

    def test_ask_returns_session_context(self):
        response = self.client.post(
            "/ask", json={"text": "How often should I water my tomato plants?"}
        )
        data = response.json()
        self.assertIn("session_context", data)
        ctx = data["session_context"]
        self.assertIn("turn_count", ctx)
        self.assertEqual(ctx["turn_count"], 1)

    def test_ask_with_existing_session_id_increments_turn_count(self):
        # First turn — no session_id supplied
        r1 = self.client.post(
            "/ask", json={"text": "How often should I water my tomato plants?"}
        )
        sid = r1.json()["session_id"]

        # Second turn — supply the returned session_id
        r2 = self.client.post(
            "/ask", json={"text": "What fertilizer for paddy?", "session_id": sid}
        )
        self.assertEqual(r2.status_code, 200)
        ctx2 = r2.json()["session_context"]
        self.assertEqual(ctx2["turn_count"], 2)
        self.assertEqual(ctx2["session_id"], sid)

    def test_ask_without_session_id_always_starts_new_session(self):
        r1 = self.client.post("/ask", json={"text": "irrigation for tomato"})
        r2 = self.client.post("/ask", json={"text": "irrigation for tomato"})
        self.assertNotEqual(r1.json()["session_id"], r2.json()["session_id"])

    def test_session_language_updated_from_tamil_input(self):
        r = self.client.post(
            "/ask", json={"text": "தக்காளி செடிக்கு தண்ணீர் எவ்வளவு?"}
        )
        ctx = r.json()["session_context"]
        self.assertEqual(ctx["detected_language_code"], "ta")


if __name__ == "__main__":
    unittest.main()
