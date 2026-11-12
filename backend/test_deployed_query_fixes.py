"""Tests for FarmSaathi deployed farmer query fixes and Render Free optimizations.

Verifies:
1. Five core target queries classify accurately via keyword baseline:
   - "Why are my crop leaves turning yellow?" -> crop_advisory
   - "How often should I irrigate paddy?" -> irrigation
   - "How can I control pests in tomato crops?" -> pest_control
   - "What government schemes are available for farmers?" -> government_schemes
   - "What is the current mandi price?" -> market_prices
2. Unknown/ambiguous queries provide safe fallback without errors.
3. Hugging Face intent model disabled prevents model loading and unnecessary memory allocation.
4. Whisper fallback disabled prevents model initialization.
5. End-to-end /ask requests execute through RAG with official source citations.
6. Session creation and conversation history persistence remain operational.
"""

from __future__ import annotations

import os
import sys
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from intent_classifier import classify_intent, is_hf_intent_enabled, get_hf_classifier, FARMING_KEYWORDS
from ner_extractor import is_hf_ner_enabled, get_hf_ner
from whisper_fallback import is_whisper_enabled, get_whisper_pipeline
from main import app


@pytest.fixture
def client():
    return TestClient(app)


class TestTargetQueryClassification:
    """Verify that all 5 target farmer queries classify to their expected intents."""

    def test_yellow_crop_leaves_classifies_to_crop_advisory(self):
        query = "Why are my crop leaves turning yellow?"
        result = classify_intent(query, language_code="en")
        assert result["intent"] == "crop_advisory"
        assert result["confidence"] >= 0.70
        assert result["classification_method"] in ("keyword_baseline", "huggingface_zero_shot")

    def test_irrigating_paddy_classifies_to_irrigation(self):
        query = "How often should I irrigate paddy?"
        result = classify_intent(query, language_code="en")
        assert result["intent"] == "irrigation"
        assert result["confidence"] >= 0.70

    def test_tomato_pests_classifies_to_pest_control(self):
        query = "How can I control pests in tomato crops?"
        result = classify_intent(query, language_code="en")
        assert result["intent"] == "pest_control"
        assert result["confidence"] >= 0.70

    def test_government_schemes_classifies_to_government_schemes(self):
        query = "What government schemes are available for farmers?"
        result = classify_intent(query, language_code="en")
        assert result["intent"] == "government_schemes"
        assert result["confidence"] >= 0.70

    def test_mandi_prices_classifies_to_market_prices(self):
        query = "What is the current mandi price?"
        result = classify_intent(query, language_code="en")
        assert result["intent"] == "market_prices"
        assert result["confidence"] >= 0.70

    def test_unknown_question_safe_fallback(self):
        query = "What is quantum entanglement and string theory?"
        result = classify_intent(query, language_code="en")
        # Should gracefully fall back to a valid agricultural intent without raising exceptions
        assert result["intent"] in ("crop_advisory", "weather", "pest_control", "irrigation", "market_prices", "government_schemes")
        assert result["classification_method"] in ("keyword_baseline", "huggingface_zero_shot")

    def test_unknown_question_keyword_fallback_when_hf_disabled(self):
        query = "What is quantum entanglement and string theory?"
        with patch.dict(os.environ, {"HF_INTENT_MODEL": "disabled"}), \
             patch("intent_classifier._hf_classifier", None):
            result = classify_intent(query, language_code="en")
            assert result["intent"] == "crop_advisory"
            assert result["classification_method"] == "keyword_baseline"
            assert result["confidence"] <= 0.65


class TestModelDisableOptimizations:
    """Verify memory optimization guards when models are disabled."""

    def test_hf_intent_model_disabled_flag(self):
        with patch.dict(os.environ, {"HF_INTENT_MODEL": "disabled"}):
            assert is_hf_intent_enabled() is False

        with patch.dict(os.environ, {"HF_INTENT_MODEL": "false"}):
            assert is_hf_intent_enabled() is False

        with patch.dict(os.environ, {"HF_INTENT_MODEL": "none"}):
            assert is_hf_intent_enabled() is False

        with patch.dict(os.environ, {"HF_INTENT_MODEL": "valhalla/distilbart-mnli-12-1"}):
            assert is_hf_intent_enabled() is True

    def test_hf_intent_classifier_returns_none_when_disabled(self):
        with patch.dict(os.environ, {"HF_INTENT_MODEL": "disabled"}), \
             patch("intent_classifier._hf_classifier", None):
            clf = get_hf_classifier()
            assert clf is None

    def test_hf_ner_model_disabled_flag(self):
        with patch.dict(os.environ, {"HF_NER_MODEL": "disabled"}):
            assert is_hf_ner_enabled() is False

        with patch.dict(os.environ, {"HF_NER_MODEL": "disabled"}), \
             patch("ner_extractor._hf_ner_pipeline", None):
            ner = get_hf_ner()
            assert ner is None

    def test_whisper_fallback_disabled_flag(self):
        with patch.dict(os.environ, {"ENABLE_WHISPER_FALLBACK": "false"}):
            assert is_whisper_enabled() is False

        with patch.dict(os.environ, {"ENABLE_WHISPER_FALLBACK": "false"}), \
             patch("whisper_fallback._whisper_pipeline", None):
            whisper = get_whisper_pipeline()
            assert whisper is None

    def test_classification_works_completely_without_hf_model(self):
        with patch.dict(os.environ, {"HF_INTENT_MODEL": "disabled"}), \
             patch("intent_classifier._hf_classifier", None):
            res1 = classify_intent("Why are my crop leaves turning yellow?", language_code="en")
            assert res1["intent"] == "crop_advisory"
            assert res1["classification_method"] == "keyword_baseline"

            res2 = classify_intent("How often should I irrigate paddy?", language_code="en")
            assert res2["intent"] == "irrigation"
            assert res2["classification_method"] == "keyword_baseline"

            res3 = classify_intent("How can I control pests in tomato crops?", language_code="en")
            assert res3["intent"] == "pest_control"
            assert res3["classification_method"] == "keyword_baseline"


class TestEndToEndRAGAndSessionExecution:
    """Verify that keyword-classified queries execute through full RAG with citations and sessions."""

    def test_ask_endpoint_with_crop_advisory_query(self, client):
        resp = client.post("/ask", json={"question": "Why are my crop leaves turning yellow?", "mode": "mock"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["intent"] == "crop_advisory"
        assert len(data["answer"]) > 0
        assert len(data["sources"]) > 0
        assert data["session_id"] is not None
        assert data["pipeline_backend"] in ("langchain_lcel", "rag_deterministic_fallback")

    def test_ask_endpoint_with_irrigation_query(self, client):
        resp = client.post("/ask", json={"question": "How often should I irrigate paddy?", "mode": "mock"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["intent"] == "irrigation"
        assert len(data["answer"]) > 0
        assert len(data["sources"]) > 0

    def test_ask_endpoint_with_pest_control_query(self, client):
        resp = client.post("/ask", json={"question": "How can I control pests in tomato crops?", "mode": "mock"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["intent"] == "pest_control"
        assert len(data["answer"]) > 0

    def test_ask_endpoint_preserves_session_context_across_turns(self, client):
        # Turn 1: Establish session and crop
        resp1 = client.post("/ask", json={"question": "How often should I irrigate paddy?", "mode": "mock"})
        assert resp1.status_code == 200
        session_id = resp1.json()["session_id"]

        # Turn 2: Follow up in the same session
        resp2 = client.post("/ask", json={"question": "What fertilizer should I apply to it?", "session_id": session_id, "mode": "mock"})
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["session_id"] == session_id
        assert data2["session_context"]["turn_count"] >= 2
