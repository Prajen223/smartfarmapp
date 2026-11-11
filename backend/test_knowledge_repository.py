"""Unit tests for knowledge_repository.py."""

import unittest
from knowledge_repository import (
    knowledge_repository,
    DOCUMENT_CORPUS,
    INTENT_TO_CATEGORIES,
    get_categories_for_intent,
)


class TestKnowledgeRepository(unittest.TestCase):
    def test_corpus_contains_all_six_categories(self):
        categories = {doc.category for doc in DOCUMENT_CORPUS}
        expected = {"crops", "soil", "pests", "diseases", "farming_practices", "government_schemes"}
        self.assertTrue(expected.issubset(categories), f"Missing categories: {expected - categories}")

    def test_all_documents_have_source_attribution(self):
        for doc in DOCUMENT_CORPUS:
            self.assertTrue(doc.source.name, f"Doc {doc.doc_id} missing source name")
            self.assertTrue(doc.source.official_url.startswith("http"), f"Doc {doc.doc_id} invalid source URL")
            self.assertTrue(doc.guardrail_notice, f"Doc {doc.doc_id} missing guardrail notice")

    def test_search_by_crop_entity(self):
        results = knowledge_repository.search(query="water management", crop="paddy")
        self.assertGreater(len(results), 0)
        self.assertIn("paddy", results[0].crops_applicable)

    def test_search_by_soil_entity(self):
        results = knowledge_repository.search(query="clay and drainage", soil="black")
        self.assertGreater(len(results), 0)
        self.assertIn("black", results[0].soil_types_applicable)

    def test_search_government_schemes(self):
        results = knowledge_repository.search(query="kisan income subsidy", category="government_schemes")
        self.assertGreater(len(results), 0)
        top_ids = [d.doc_id for d in results]
        self.assertIn("doc_scheme_001", top_ids)

    def test_localized_content_retrieval(self):
        doc = knowledge_repository.get_document("doc_crop_001")
        self.assertIsNotNone(doc)
        hi_content = knowledge_repository.get_localized_content(doc, language_code="hi")
        self.assertIn("धान", hi_content)
        kn_content = knowledge_repository.get_localized_content(doc, language_code="kn")
        self.assertIn("ಭತ್ತ", kn_content)

    def test_intent_to_category_mapping_all_five_intents(self):
        """Verify strict intent-to-category mapping required for Stage 1."""
        self.assertEqual(get_categories_for_intent("pest_control"), ["pests", "diseases"])
        self.assertEqual(get_categories_for_intent("irrigation"), ["farming_practices", "soil"])
        self.assertEqual(get_categories_for_intent("crop_advisory"), ["crops", "soil", "farming_practices"])
        self.assertEqual(get_categories_for_intent("government_schemes"), ["government_schemes"])
        self.assertEqual(get_categories_for_intent("market_prices"), ["market_prices"])

    def test_relevant_documents_returned_for_every_intent(self):
        """Ensure search returns relevant documents for each of the 5 intents."""
        intent_queries = {
            "irrigation": "drip irrigation watering frequency in black soil",
            "pest_control": "aphids and whitefly insect control",
            "crop_advisory": "paddy rice fertilizer and cultivation package",
            "government_schemes": "PM-KISAN direct cash transfer subsidy",
            "market_prices": "daily mandi market price on Agmarknet",
        }
        for intent, query in intent_queries.items():
            results = knowledge_repository.search(query=query, intent=intent, top_k=2)
            self.assertGreater(
                len(results), 0,
                f"Expected search results for intent '{intent}' with query '{query}'"
            )
            allowed = INTENT_TO_CATEGORIES[intent]
            for doc in results:
                self.assertIn(
                    doc.category, allowed,
                    f"Doc '{doc.doc_id}' category '{doc.category}' not in allowed {allowed} for intent '{intent}'"
                )

    def test_distinct_queries_within_pest_control(self):
        """Verify distinct pest queries retrieve distinct, accurate evidence documents."""
        # Query 1: Sucking pests / aphids
        r_aphids = knowledge_repository.search(
            query="aphids whiteflies sucking pests sticky traps neem oil",
            category="pest_control",
        )
        self.assertGreater(len(r_aphids), 0)
        self.assertEqual(r_aphids[0].doc_id, "doc_pest_001")

        # Query 2: Blight fungal disease
        r_blight = knowledge_repository.search(
            query="early blight late blight brown rings lesions on leaves",
            category="pest_control",
        )
        self.assertGreater(len(r_blight), 0)
        self.assertEqual(r_blight[0].doc_id, "doc_disease_001")

        # Query 3: Borer / bollworm
        r_borer = knowledge_repository.search(
            query="pink bollworm stem borer pheromone traps trichogramma",
            category="pest_control",
        )
        self.assertGreater(len(r_borer), 0)
        self.assertEqual(r_borer[0].doc_id, "doc_pest_002")

    def test_distinct_queries_within_irrigation(self):
        """Verify distinct irrigation queries retrieve distinct evidence documents."""
        # Query 1: Drip fertigation
        r_drip = knowledge_repository.search(
            query="drip irrigation and soluble fertigation schedule",
            category="irrigation",
        )
        self.assertGreater(len(r_drip), 0)
        self.assertEqual(r_drip[0].doc_id, "doc_practice_001")

        # Query 2: Soil drainage & waterlogging
        r_soil = knowledge_repository.search(
            query="black cotton regur soil waterlogging and drainage management",
            category="irrigation",
        )
        self.assertGreater(len(r_soil), 0)
        self.assertEqual(r_soil[0].doc_id, "doc_soil_001")

    def test_distinct_queries_within_crop_advisory(self):
        """Verify distinct crop advisory queries retrieve distinct crop documents."""
        r_paddy = knowledge_repository.search(
            query="paddy rice SRI transplanting water management",
            category="crop_advisory",
            crop="paddy",
        )
        self.assertGreater(len(r_paddy), 0)
        self.assertEqual(r_paddy[0].doc_id, "doc_crop_001")

        r_wheat = knowledge_repository.search(
            query="wheat CRI stage crown root initiation irrigation",
            category="crop_advisory",
            crop="wheat",
        )
        self.assertGreater(len(r_wheat), 0)
        self.assertEqual(r_wheat[0].doc_id, "doc_crop_002")

        r_tomato = knowledge_repository.search(
            query="tomato staking and fruit rot blossom end rot",
            category="crop_advisory",
            crop="tomato",
        )
        self.assertGreater(len(r_tomato), 0)
        self.assertEqual(r_tomato[0].doc_id, "doc_crop_003")

    def test_market_prices_evidence_retrieval(self):
        """Verify market price queries return official Agmarknet / e-NAM evidence."""
        r_market = knowledge_repository.search(
            query="mandi daily prices modal rates on Agmarknet and e-NAM",
            category="market_prices",
        )
        self.assertGreater(len(r_market), 0)
        self.assertEqual(r_market[0].doc_id, "doc_market_001")
        self.assertIn("agmarknet.gov.in", r_market[0].source.official_url)

    def test_search_intent_parameter_support(self):
        """Verify explicit intent parameter routes accurately to target categories."""
        results = knowledge_repository.search(query="whiteflies", intent="pest_control")
        self.assertGreater(len(results), 0)
        self.assertIn(results[0].category, ["pests", "diseases"])


if __name__ == "__main__":
    unittest.main()
