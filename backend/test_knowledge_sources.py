"""Tests for Stage B: knowledge_sources.json and its Python helpers.

Run with:  venv\\Scripts\\pytest test_knowledge_sources.py -v
"""

import json
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from farming_kb import load_sources, get_sources_for_intent
from main import app


SOURCES_PATH = Path(__file__).parent / "knowledge_sources.json"
VALID_INTENTS = [
    "irrigation",
    "pest_control",
    "crop_advisory",
    "market_prices",
    "government_schemes",
]


class TestKnowledgeSourcesJSON(unittest.TestCase):
    """Verify the JSON file is well-formed and internally consistent."""

    def setUp(self):
        self.data = json.loads(SOURCES_PATH.read_text(encoding="utf-8"))

    def test_file_is_valid_json(self):
        self.assertIsInstance(self.data, dict)

    def test_required_top_level_keys(self):
        for key in ("sources", "intent_source_mapping", "_schema_version"):
            self.assertIn(key, self.data, f"Missing top-level key: {key}")

    def test_sources_is_list(self):
        self.assertIsInstance(self.data["sources"], list)

    def test_at_least_ten_sources(self):
        self.assertGreaterEqual(
            len(self.data["sources"]), 10,
            "Expected at least 10 source entries"
        )

    def test_every_source_has_required_fields(self):
        required = {"id", "name", "url", "content_types", "organization_type", "access_note"}
        for src in self.data["sources"]:
            missing = required - src.keys()
            self.assertFalse(missing, f"Source '{src.get('id')}' missing fields: {missing}")

    def test_source_ids_are_unique(self):
        ids = [s["id"] for s in self.data["sources"]]
        self.assertEqual(len(ids), len(set(ids)), "Duplicate source IDs found")

    def test_urls_are_non_empty_strings(self):
        for src in self.data["sources"]:
            self.assertIsInstance(src["url"], str)
            self.assertTrue(src["url"].startswith("http"), f"Invalid URL in source '{src['id']}'")

    def test_access_note_present_and_non_empty(self):
        for src in self.data["sources"]:
            self.assertTrue(
                src.get("access_note", "").strip(),
                f"Empty access_note in source '{src['id']}'"
            )

    def test_intent_mapping_covers_all_five_intents(self):
        mapping = self.data["intent_source_mapping"]
        for intent in VALID_INTENTS:
            self.assertIn(intent, mapping, f"Intent '{intent}' missing from intent_source_mapping")
            self.assertGreater(
                len(mapping[intent]), 0,
                f"Intent '{intent}' has no sources in mapping"
            )

    def test_mapping_references_valid_source_ids(self):
        all_ids = {s["id"] for s in self.data["sources"]}
        for intent, src_ids in self.data["intent_source_mapping"].items():
            for sid in src_ids:
                self.assertIn(sid, all_ids, f"Mapping for '{intent}' references unknown id '{sid}'")

    def test_no_live_price_data_claimed(self):
        """Verify no source claims to contain live mandi prices in KB content."""
        sources_text = json.dumps(self.data).lower()
        # The word 'live' may appear in access_note disclaimers but never as a claim
        # that KB holds live data — verify access_note for market_prices sources
        for src in self.data["sources"]:
            if "market_prices" in src.get("content_types", []):
                note = src.get("access_note", "").lower()
                self.assertNotIn(
                    "cached",
                    note,
                    f"Source '{src['id']}' must not claim to serve cached live prices"
                )


class TestLoadSourcesHelper(unittest.TestCase):
    """Test the Python loading helper in farming_kb."""

    def test_load_sources_returns_dict(self):
        data = load_sources()
        self.assertIsInstance(data, dict)
        self.assertNotIn("error", data)

    def test_load_sources_has_sources_list(self):
        data = load_sources()
        self.assertIn("sources", data)
        self.assertIsInstance(data["sources"], list)

    def test_get_sources_for_valid_intent(self):
        for intent in VALID_INTENTS:
            sources = get_sources_for_intent(intent)
            self.assertIsInstance(sources, list)
            self.assertGreater(len(sources), 0, f"No sources returned for intent '{intent}'")

    def test_get_sources_for_unknown_intent_returns_empty(self):
        sources = get_sources_for_intent("unknown_intent_xyz")
        self.assertEqual(sources, [])

    def test_returned_sources_have_name_and_url(self):
        for intent in VALID_INTENTS:
            for src in get_sources_for_intent(intent):
                self.assertIn("name", src)
                self.assertIn("url", src)


class TestSourcesEndpoint(unittest.TestCase):
    """Test the /sources and /sources/{intent} FastAPI endpoints."""

    def setUp(self):
        self.client = TestClient(app)

    def test_get_sources_returns_200(self):
        response = self.client.get("/sources")
        self.assertEqual(response.status_code, 200)

    def test_get_sources_contains_sources_list(self):
        data = self.client.get("/sources").json()
        self.assertIn("sources", data)
        self.assertIsInstance(data["sources"], list)

    def test_get_sources_for_each_valid_intent(self):
        for intent in VALID_INTENTS:
            response = self.client.get(f"/sources/{intent}")
            self.assertEqual(response.status_code, 200, f"Failed for intent: {intent}")
            data = response.json()
            self.assertEqual(data["intent"], intent)
            self.assertIsInstance(data["sources"], list)
            self.assertGreater(len(data["sources"]), 0)

    def test_get_sources_for_invalid_intent_returns_400(self):
        response = self.client.get("/sources/nonexistent_category")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Unknown intent", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
