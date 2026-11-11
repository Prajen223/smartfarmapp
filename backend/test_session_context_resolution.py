"""Unit tests for multi-turn context resolution in session_manager.py."""

import unittest
from session_manager import SessionManager


class TestMultiTurnContextResolution(unittest.TestCase):
    def setUp(self):
        self.mgr = SessionManager()
        self.mgr.clear_all()
        self.session = self.mgr.get_or_create(None)
        self.sid = self.session.session_id

    def test_context_entity_carry_over(self):
        # Turn 1: Farmer asks about tomato blight
        self.mgr.record_turn(
            session_id=self.sid,
            user_text="How to treat early blight on my tomato crop?",
            detected_language="en",
            intent="pest_control",
            answer="Apply copper oxychloride and prune affected lower foliage.",
            entities={
                "crops": ["tomato"],
                "pests": [],
                "diseases": ["blight"],
                "soil": [],
                "schemes": [],
                "locations": [],
                "fertilizers": [],
            },
        )

        session = self.mgr.get_session(self.sid)
        self.assertEqual(session.active_crop, "tomato")
        self.assertEqual(session.active_disease, "blight")

        # Turn 2: Farmer asks follow-up: "How much water does it need in black soil?"
        # Raw turn 2 entities contain NO crop
        turn2_raw_entities = {
            "crops": [],
            "pests": [],
            "diseases": [],
            "soil": ["black"],
            "schemes": [],
            "locations": [],
            "fertilizers": [],
        }

        resolved_entities = session.resolve_context(turn2_raw_entities)
        self.assertIn("tomato", resolved_entities["crops"])
        self.assertIn("black", resolved_entities["soil"])
        self.assertTrue(resolved_entities.get("_crop_carried_from_context"))

    def test_new_crop_overrides_previous_active_crop(self):
        # Turn 1: Paddy
        self.mgr.record_turn(
            session_id=self.sid,
            user_text="Paddy fertilizer",
            detected_language="en",
            intent="crop_advisory",
            answer="Nitrogen in 3 splits",
            entities={"crops": ["paddy"], "soil": [], "pests": [], "diseases": [], "schemes": []},
        )
        self.assertEqual(self.mgr.get_session(self.sid).active_crop, "paddy")

        # Turn 2: Farmer explicitly asks about Wheat
        self.mgr.record_turn(
            session_id=self.sid,
            user_text="What about wheat?",
            detected_language="en",
            intent="crop_advisory",
            answer="Crown root initiation at 20-25 days",
            entities={"crops": ["wheat"], "soil": [], "pests": [], "diseases": [], "schemes": []},
        )
        self.assertEqual(self.mgr.get_session(self.sid).active_crop, "wheat")


if __name__ == "__main__":
    unittest.main()
