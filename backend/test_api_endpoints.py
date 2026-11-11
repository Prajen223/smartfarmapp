"""End-to-end FastAPI endpoint integration tests for Week 1–2."""

import io
import unittest
from fastapi.testclient import TestClient

from main import app
from voice_pipeline import generate_mock_wav


class TestAPIEndpoints(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_home_and_health(self):
        r1 = self.client.get("/")
        self.assertEqual(r1.status_code, 200)
        self.assertIn("Smart Farming Assistant", r1.json()["message"])

        r2 = self.client.get("/health")
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.json()["status"], "healthy")

    def test_config_check(self):
        r = self.client.get("/config-check")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("sarvam_key_configured", data)
        self.assertIn("whisper_fallback_enabled", data)

    def test_ask_text_endpoint_english(self):
        r = self.client.post("/ask", json={"text": "How often should I water my tomato plants in black soil?"})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["language_code"], "en")
        self.assertIn("tomato", data["entities"]["crops"])
        self.assertIn("black", data["entities"]["soil"])
        self.assertIn("session_id", data)
        self.assertIn("retrieved_documents", data)

    def test_ask_text_endpoint_tamil(self):
        r = self.client.post("/ask", json={"text": "தக்காளி செடிக்கு எவ்வளவு தண்ணீர் ஊற்ற வேண்டும்?"})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["language_code"], "ta")
        self.assertEqual(data["language"], "Tamil")

    def test_voice_transcribe_empty_file_rejected(self):
        files = {"file": ("empty.wav", b"", "audio/wav")}
        r = self.client.post("/voice/transcribe", files=files)
        self.assertEqual(r.status_code, 400)
        self.assertIn("empty", r.json()["detail"].lower())

    def test_voice_transcribe_valid_mock(self):
        wav_bytes = generate_mock_wav(duration_seconds=0.5)
        files = {"file": ("sample.wav", io.BytesIO(wav_bytes), "audio/wav")}
        r = self.client.post("/voice/transcribe", files=files, data={"language_hint": "hi"})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("transcript", data)
        self.assertIn("language_code", data)

    def test_voice_synthesize_valid(self):
        payload = {
            "text": "टमाटर की फसल में जैविक खाद का उपयोग करें",
            "language_code": "hi",
        }
        r = self.client.post("/voice/synthesize", json=payload)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("audio_base64", data)
        self.assertEqual(data["format"], "wav")

    def test_voice_synthesize_empty_rejected(self):
        r = self.client.post("/voice/synthesize", json={"text": "   ", "language_code": "hi"})
        self.assertEqual(r.status_code, 400)

    def test_ask_voice_endpoint(self):
        wav_bytes = generate_mock_wav(duration_seconds=0.5)
        files = {"file": ("voice_q.wav", io.BytesIO(wav_bytes), "audio/wav")}
        r = self.client.post("/ask-voice", files=files, data={"language_hint": "en"})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("transcript", data)
        self.assertIn("analysis", data)
        self.assertIn("audio_base64", data)
        self.assertIn("session_id", data["analysis"])

    def test_knowledge_documents_listing_and_detail(self):
        r = self.client.get("/knowledge/documents")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertGreater(data["count"], 0)
        first_doc_id = data["documents"][0]["doc_id"]

        r_detail = self.client.get(f"/knowledge/documents/{first_doc_id}")
        self.assertEqual(r_detail.status_code, 200)
        self.assertEqual(r_detail.json()["doc_id"], first_doc_id)

    def test_session_history_endpoint(self):
        # Create a turn first
        r_ask = self.client.post("/ask", json={"text": "Water requirements for wheat"})
        sid = r_ask.json()["session_id"]

        r_sess = self.client.get(f"/session/{sid}")
        self.assertEqual(r_sess.status_code, 200)
        sess_data = r_sess.json()
        self.assertEqual(sess_data["session_id"], sid)
        self.assertEqual(len(sess_data["turns"]), 1)
        self.assertIn("iso_timestamp", sess_data["turns"][0])

    def test_adapters_agmarknet_endpoint(self):
        """Milestone 2: Verify /adapters/agmarknet endpoint returns structured offline benchmark."""
        r = self.client.get("/adapters/agmarknet?commodity=paddy&district=Karnal&state=Haryana&date=2026-03-30")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["service"], "agmarknet")
        self.assertFalse(data["is_live"])
        self.assertEqual(data["district"], "Karnal")
        self.assertEqual(data["arrival_date"], "2026-03-30")
        self.assertIn("reference_msp", data)
        self.assertIn("post_harvest_advice", data)

    def test_adapters_weather_endpoint(self):
        """Milestone 2: Verify /adapters/weather endpoint returns offline resilient guidance with district."""
        r = self.client.get("/adapters/weather?location=Pune&district=Pune_Rural&state=Maharashtra")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["service"], "imd_agromet")
        self.assertFalse(data["is_live"])
        self.assertEqual(data["district"], "Pune_Rural")
        self.assertIn("forecast_timestamp", data)
        self.assertIn("message", data)
        self.assertIn("spray_safety_rule", data)

    def test_adapters_schemes_endpoint(self):
        """Milestone 2: Verify /adapters/schemes endpoint returns official eligibility criteria."""
        r = self.client.get("/adapters/schemes?query=pm-kisan")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("scheme_details", data)
        self.assertIn("PM-KISAN", data["scheme_details"]["name"])
        self.assertIn("mandatory_requirements", data["scheme_details"])

    def test_vector_store_status_endpoint(self):
        """Milestone 2: Verify /vector-store/status endpoint reports persistent store status."""
        r = self.client.get("/vector-store/status")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("backend", data)
        self.assertIn("chunk_count", data)
        self.assertGreater(data["chunk_count"], 0)

    def test_ask_endpoint_rag_response_schema(self):
        """Milestone 2: Verify /ask returns rag_confidence, is_low_confidence, and adapter_data."""
        r = self.client.post("/ask", json={"text": "What is the market rate of cotton?"})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("rag_confidence", data)
        self.assertIn("is_low_confidence", data)
        self.assertIn("retrieved_documents", data)
        self.assertIn("adapter_data", data)
        self.assertIsNotNone(data["adapter_data"])
        self.assertEqual(data["adapter_data"]["service"], "agmarknet")

    def test_ask_endpoint_uses_langchain_lcel_retrieval_and_sources(self):
        """Milestone 2: Verify /ask executes LCEL chain and returns attributed official sources."""
        r = self.client.post("/ask", json={"text": "What is the irrigation schedule for wheat at crown root initiation?"})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["pipeline_backend"], "langchain_lcel")
        self.assertIn("sources", data)
        self.assertGreater(len(data["sources"]), 0)
        self.assertGreater(len(data["retrieved_documents"]), 0)
        self.assertTrue(data["retrieved_documents"][0]["url"].startswith("http"))


if __name__ == "__main__":
    unittest.main()
