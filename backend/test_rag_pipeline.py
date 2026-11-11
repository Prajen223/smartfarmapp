"""Unit tests for rag_pipeline.py — RAG Pipeline, Evidence Grounding, and Quality Assessment."""

import tempfile
import unittest
from pathlib import Path

from rag_pipeline import RAGPipeline, LOW_CONFIDENCE_LOG_PATH
from vector_store import DeterministicFixtureEmbeddings, PersistentLocalVectorStore


class TestRAGPipeline(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.storage_dir = Path(self.temp_dir.name)
        embeddings = DeterministicFixtureEmbeddings(dimension=64)
        store = PersistentLocalVectorStore(storage_dir=self.storage_dir, embeddings=embeddings)
        self.pipeline = RAGPipeline(vector_store=store, use_fixture_embeddings=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_distinct_questions_generate_distinct_evidence(self):
        """Verify that distinct questions produce distinct evidence and answers."""
        res_tomato = self.pipeline.generate_response(
            query="How often should I water my tomato plants in black soil?",
            canonical_text="How often should I water my tomato plants in black soil?",
            intent="irrigation",
            entities={"crops": ["tomato"], "soil": ["black"]},
        )
        res_wheat = self.pipeline.generate_response(
            query="When is the critical crown root initiation irrigation stage for wheat?",
            canonical_text="When is the critical crown root initiation irrigation stage for wheat?",
            intent="crop_advisory",
            entities={"crops": ["wheat"]},
        )

        self.assertNotEqual(res_tomato["answer"], res_wheat["answer"])
        self.assertIn("Tomato", res_tomato["answer"])
        self.assertIn("Wheat", res_wheat["answer"])
        self.assertGreater(res_tomato["confidence"], 0.40)
        self.assertGreater(res_wheat["confidence"], 0.40)

    def test_distinct_pest_questions(self):
        """Verify distinct pest queries generate distinct evidence."""
        res_bollworm = self.pipeline.generate_response(
            query="How to manage pink bollworm in cotton?",
            canonical_text="How to manage pink bollworm in cotton?",
            intent="pest_control",
            entities={"crops": ["cotton"], "pests": ["pink_bollworm"]},
        )
        res_aphids = self.pipeline.generate_response(
            query="Aphids and whiteflies sucking pests control",
            canonical_text="Aphids and whiteflies sucking pests control",
            intent="pest_control",
            entities={"pests": ["aphids", "whiteflies"]},
        )

        self.assertNotEqual(res_bollworm["answer"], res_aphids["answer"])
        self.assertIn("Bollworm", res_bollworm["answer"])
        self.assertIn("Sucking Pests", res_aphids["answer"])

    def test_market_prices_adapter_integration(self):
        """Verify market price queries integrate Agmarknet adapter cleanly."""
        res = self.pipeline.generate_response(
            query="What is the mandi price for paddy?",
            canonical_text="What is the mandi price for paddy?",
            intent="market_prices",
            entities={"crops": ["paddy"]},
        )
        self.assertIn("agmarknet.gov.in", res["answer"])
        self.assertTrue("Paddy" in res["answer"])
        self.assertIsNotNone(res["adapter_data"])
        self.assertEqual(res["adapter_data"]["service"], "agmarknet")
        self.assertIsInstance(res["adapter_data"]["is_live"], bool)

    def test_government_schemes_adapter_integration(self):
        """Verify government scheme queries integrate GovernmentSchemeAdapter."""
        res = self.pipeline.generate_response(
            query="How to apply for PM-KISAN ₹6000 installment?",
            canonical_text="How to apply for PM-KISAN ₹6000 installment?",
            intent="government_schemes",
            entities={"schemes": ["pm_kisan"]},
        )
        self.assertIn("PM-KISAN", res["answer"])
        self.assertIn("pmkisan.gov.in", res["answer"])
        self.assertIn("e-KYC", res["answer"])

    def test_low_confidence_fallback_and_logging(self):
        """Verify out-of-scope question triggers low-confidence fallback and logs query."""
        res = self.pipeline.generate_response(
            query="xyz irrelevant crypto query quantum computing spaceship",
            canonical_text="xyz irrelevant crypto query quantum computing spaceship",
            intent="crop_advisory",
            entities={},
        )
        # Should flag low confidence
        self.assertTrue(res["is_low_confidence"])
        self.assertIn("1800-180-1551", res["answer"])
        self.assertIn("Agricultural Extension Notice", res["answer"])

        # Check log file exists
        self.assertTrue(LOW_CONFIDENCE_LOG_PATH.exists())
        log_content = LOW_CONFIDENCE_LOG_PATH.read_text(encoding="utf-8")
        self.assertIn("crypto", log_content)

    def test_attribution_completeness(self):
        """Verify all retrieved documents carry full provenance and timestamps."""
        res = self.pipeline.generate_response(
            query="water management alternate wetting drying in paddy",
            canonical_text="water management alternate wetting drying in paddy",
            intent="crop_advisory",
            entities={"crops": ["paddy"]},
        )
        self.assertGreater(len(res["retrieved_documents"]), 0)
        doc = res["retrieved_documents"][0]
        self.assertTrue(doc["title"])
        self.assertTrue(doc["source"])
        self.assertTrue(doc["url"].startswith("http"))
        self.assertTrue(doc["organization"])
        self.assertTrue(doc["retrieval_timestamp"])

    def test_langchain_retriever_interface(self):
        """Milestone 2: Verify LangChain retriever integration returns Document objects with metadata."""
        from langchain_core.documents import Document as LCDocument
        retriever = self.pipeline.as_langchain_retriever(top_k=2)
        docs = retriever.invoke("tomato blossom rot irrigation")
        self.assertGreater(len(docs), 0)
        self.assertIsInstance(docs[0], LCDocument)
        self.assertTrue(len(docs[0].page_content) > 10)
        self.assertIn("similarity_score", docs[0].metadata)
        self.assertIn("doc_id", docs[0].metadata)

    def test_pii_sanitization_in_low_confidence_log(self):
        """Milestone 2: Verify PII (phone, email) is scrubbed before writing to low_confidence_queries.jsonl."""
        test_query = "alien spaceship query call me at 9876543210 or email farmer123@example.com"
        self.pipeline.log_low_confidence_query(
            query=test_query,
            intent="crop_advisory",
            confidence=0.15,
            reason="Low confidence test with PII",
        )
        self.assertTrue(LOW_CONFIDENCE_LOG_PATH.exists())
        log_content = LOW_CONFIDENCE_LOG_PATH.read_text(encoding="utf-8")
        self.assertNotIn("9876543210", log_content)
        self.assertNotIn("farmer123@example.com", log_content)
        self.assertIn("[REDACTED_PHONE]", log_content)
        self.assertIn("[REDACTED_EMAIL]", log_content)

    def test_structured_response_fields(self):
        """Milestone 2: Verify all required structured response contract fields are populated."""
        res = self.pipeline.generate_response(
            query="Watering tomato plants",
            canonical_text="Watering tomato plants",
            intent="irrigation",
            entities={"crops": ["tomato"]},
        )
        self.assertIn("sources", res)
        self.assertIsInstance(res["sources"], list)
        self.assertIn("needs_clarification", res)
        self.assertIn("data_freshness", res)
        self.assertIn("response_mode", res)
        self.assertEqual(res["response_mode"], "rag_grounded_extractive")
        self.assertIn("rag_confidence", res)

    def test_custom_low_confidence_threshold(self):
        """Milestone 2: Verify configurable low_confidence_threshold triggers safety fallback."""
        strict_pipeline = RAGPipeline(
            vector_store=self.pipeline.vector_store,
            use_fixture_embeddings=True,
            low_confidence_threshold=0.99,  # Very high threshold
        )
        res = strict_pipeline.generate_response(
            query="How to water tomato?",
            canonical_text="How to water tomato?",
            intent="irrigation",
            entities={"crops": ["tomato"]},
        )
        self.assertTrue(res["is_low_confidence"])
        self.assertEqual(res["response_mode"], "kcc_referral_safety")

    def test_lcel_chain_execution_and_sources_retrieval(self):
        """Milestone 2: Verify that RAG execution utilizes LangChain LCEL chain and returns attributed sources."""
        self.assertIsNotNone(self.pipeline.lcel_chain)
        res = self.pipeline.generate_response(
            query="Water management and AWD practice in paddy rice field",
            canonical_text="Water management and AWD practice in paddy rice field",
            intent="crop_advisory",
            entities={"crops": ["paddy"]},
        )
        self.assertEqual(res["pipeline_backend"], "langchain_lcel")
        self.assertGreater(len(res["sources"]), 0)
        self.assertGreater(len(res["retrieved_documents"]), 0)
        first_doc = res["retrieved_documents"][0]
        self.assertTrue(first_doc["url"].startswith("http"))
        self.assertIn("similarity_score", first_doc)


if __name__ == "__main__":
    unittest.main()
