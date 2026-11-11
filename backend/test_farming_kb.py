"""Automated test suite for local farming knowledge base and FastAPI /ask endpoint."""

import unittest
from fastapi.testclient import TestClient

from main import app
from farming_kb import get_farming_answer, KB_ENTRIES, _detect_crop


class TestFarmingKnowledgeBase(unittest.TestCase):
    def setUp(self):
        self.intents = [
            "irrigation",
            "pest_control",
            "crop_advisory",
            "market_prices",
            "government_schemes",
        ]

    def test_all_five_intents_english(self):
        """Verify all 5 intents produce structured English answers."""
        for intent in self.intents:
            res = get_farming_answer(intent=intent, text="general question", language_code="en")
            self.assertEqual(res["response_language"], "English")
            self.assertIn("【", res["answer"])
            self.assertTrue(len(res["answer"]) > 100)

    def test_all_five_intents_tamil(self):
        """Verify all 5 intents produce structured Tamil answers."""
        for intent in self.intents:
            res = get_farming_answer(intent=intent, text="விவசாய கேள்வி", language_code="ta")
            self.assertEqual(res["response_language"], "Tamil")
            self.assertIn("【", res["answer"])
            # Ensure Tamil script characters are present
            has_tamil_chars = any("\u0B80" <= char <= "\u0BFF" for char in res["answer"])
            self.assertTrue(has_tamil_chars, f"Tamil answer for {intent} must contain Tamil script")

    def test_other_language_fallback_label(self):
        """Verify non-Tamil and non-English requests return English with clear language label."""
        for lang_code in ["hi", "kn", "te", "ml"]:
            res = get_farming_answer(intent="pest_control", text="कीट समस्या", language_code=lang_code)
            self.assertEqual(res["response_language"], "English")
            self.assertIn("[Language Note:", res["answer"])
            self.assertIn("Response provided in English", res["answer"])

    def test_crop_detection_and_tips(self):
        """Verify crop-specific context is appended when crop is mentioned."""
        # English tomato
        res_tomato_en = get_farming_answer(intent="irrigation", text="How to water tomato plants?", language_code="en")
        self.assertIn("Tomato", res_tomato_en["answer"])

        # Tamil tomato
        res_tomato_ta = get_farming_answer(intent="irrigation", text="தக்காளி செடிக்கு தண்ணீர் பாசனம்", language_code="ta")
        self.assertIn("தக்காளி", res_tomato_ta["answer"])

        # English paddy
        res_paddy = get_farming_answer(intent="irrigation", text="Paddy rice field watering", language_code="en")
        self.assertIn("Paddy", res_paddy["answer"])

    def test_guardrails_market_prices(self):
        """Verify market price answers do not invent live rates and reference official portals."""
        res_en = get_farming_answer(intent="market_prices", text="What is tomato price?", language_code="en")
        self.assertIn("agmarknet.gov.in", res_en["answer"])
        self.assertIn("enam.gov.in", res_en["answer"])
        self.assertIn("Important Price Notice", res_en["answer"])

        res_ta = get_farming_answer(intent="market_prices", text="தக்காளி விலை என்ன?", language_code="ta")
        self.assertIn("agmarknet.gov.in", res_ta["answer"])
        self.assertIn("உழவன்", res_ta["answer"])

    def test_guardrails_government_schemes(self):
        """Verify government scheme answers mention major schemes and disclaimer for eligibility."""
        res_en = get_farming_answer(intent="government_schemes", text="government subsidy", language_code="en")
        self.assertIn("PM-KISAN", res_en["answer"])
        self.assertIn("Eligibility Notice", res_en["answer"])

        res_ta = get_farming_answer(intent="government_schemes", text="அரசு மானியம்", language_code="ta")
        self.assertIn("PM-KISAN", res_ta["answer"])
        self.assertIn("மானிய விவர அறிவிப்பு", res_ta["answer"])

    def test_guardrails_chemical_dosages(self):
        """Verify pest control and crop advisory do not give arbitrary chemical dosages and warn user."""
        res_pest = get_farming_answer(intent="pest_control", text="chemical pesticide dose", language_code="en")
        self.assertIn("Dosage Warning", res_pest["answer"])
        self.assertIn("Agricultural Extension Officer", res_pest["answer"])

        res_fert = get_farming_answer(intent="crop_advisory", text="fertilizer dose", language_code="en")
        self.assertIn("Soil Health Card", res_fert["answer"])


class TestFastApiEndpoint(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_empty_question_returns_400(self):
        """Verify empty question yields 400 Bad Request."""
        response = self.client.post("/ask", json={"text": "   "})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Please enter a farming question")

    def test_valid_question_english(self):
        """Verify valid English query returns full response structure with local_knowledge_base mode."""
        response = self.client.post("/ask", json={"text": "How often should I water my tomato plants?"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["language"], "English")
        self.assertEqual(data["language_code"], "en")
        self.assertEqual(data["intent"], "irrigation")
        self.assertEqual(data["mode"], "local_knowledge_base")
        self.assertIn("Irrigation & Water Management Advisory", data["answer"])
        self.assertIn("Tomato", data["answer"])
        # Stage A: entities field must be present
        self.assertIn("entities", data)
        self.assertIn("tomato", data["entities"]["crops"])

    def test_valid_question_tamil(self):
        """Verify valid Tamil query returns full response structure with Tamil answer."""
        response = self.client.post("/ask", json={"text": "தக்காளி செடிக்கு எவ்வளவு தண்ணீர் ஊற்ற வேண்டும்?"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["language"], "Tamil")
        self.assertEqual(data["language_code"], "ta")
        self.assertEqual(data["intent"], "irrigation")
        self.assertEqual(data["mode"], "local_knowledge_base")
        self.assertIn("நீர்ப்பாசனம் மற்றும் நீர் மேலாண்மை வழிகாட்டல்", data["answer"])
        self.assertIn("தக்காளி", data["answer"])
        # Stage A: entities field must be present with Tamil-detected crop
        self.assertIn("entities", data)
        self.assertIn("tomato", data["entities"]["crops"])

    def test_valid_question_hindi_fallback(self):
        """Verify Hindi query returns English answer with language fallback label."""
        response = self.client.post("/ask", json={"text": "मेरी फसल में कीड़े लग गए हैं"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["language"], "Hindi")
        self.assertEqual(data["language_code"], "hi")
        self.assertEqual(data["mode"], "local_knowledge_base")
        self.assertIn("[Language Note:", data["answer"])


if __name__ == "__main__":
    unittest.main()
