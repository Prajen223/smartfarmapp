"""Tests for Stage C: translation_service.py

Run with:  venv\\Scripts\\pytest test_translation_service.py -v
"""

import unittest

from translation_service import (
    MockTranslator,
    SarvamTranslatorStub,
    TranslationService,
    TranslationResult,
    PipelineResult,
    NATIVE_KB_LANGUAGES,
    CANONICAL_LANGUAGE,
    SUPPORTED_LANGUAGES,
)


class TestMockTranslator(unittest.TestCase):
    """MockTranslator must be honest about what it does (and doesn't do)."""

    def setUp(self):
        self.tr = MockTranslator()

    def test_is_mock_flag_is_true(self):
        self.assertTrue(self.tr.IS_MOCK)

    def test_returns_translation_result(self):
        result = self.tr.translate("hello", "en", "hi")
        self.assertIsInstance(result, TranslationResult)

    def test_text_is_returned_unchanged(self):
        original = "मेरी फसल में कीड़े लग गए हैं"
        result = self.tr.translate(original, "hi", "en")
        self.assertEqual(result.translated_text, original)

    def test_is_mock_true_in_result(self):
        result = self.tr.translate("test", "ta", "en")
        self.assertTrue(result.is_mock)

    def test_translation_performed_false_in_mock(self):
        result = self.tr.translate("test", "te", "en")
        self.assertFalse(result.translation_performed)

    def test_source_and_target_recorded(self):
        result = self.tr.translate("some text", "kn", "en")
        self.assertEqual(result.source_language, "kn")
        self.assertEqual(result.target_language, "en")

    def test_no_exception_on_any_supported_language(self):
        for lang in SUPPORTED_LANGUAGES:
            try:
                self.tr.translate("sample text", lang, "en")
            except Exception as exc:
                self.fail(f"MockTranslator raised {exc} for lang '{lang}'")


class TestSarvamStub(unittest.TestCase):
    """SarvamTranslatorStub must not make any live calls — it raises NotImplementedError."""

    def setUp(self):
        self.stub = SarvamTranslatorStub()

    def test_is_mock_false(self):
        self.assertFalse(self.stub.IS_MOCK)

    def test_raises_not_implemented_error(self):
        with self.assertRaises(NotImplementedError):
            self.stub.translate("any text", "hi", "en")

    def test_error_message_is_informative(self):
        try:
            self.stub.translate("text", "hi", "en")
        except NotImplementedError as exc:
            self.assertIn("Sarvam", str(exc))
            self.assertIn("not been", str(exc))


class TestTranslationServiceNativePaths(unittest.TestCase):
    """EN and Tamil must bypass translator entirely (native path)."""

    def setUp(self):
        self.service = TranslationService()

    def test_canonical_language_is_english(self):
        self.assertEqual(CANONICAL_LANGUAGE, "en")

    def test_native_languages_include_en_and_ta(self):
        self.assertIn("en", NATIVE_KB_LANGUAGES)
        self.assertIn("ta", NATIVE_KB_LANGUAGES)

    def test_translate_to_canonical_en_no_mock(self):
        result = self.service.translate_to_canonical("How to water tomato?", "en")
        self.assertFalse(result.is_mock)
        self.assertEqual(result.translated_text, "How to water tomato?")

    def test_translate_to_canonical_en_returns_same_text(self):
        text = "soil test for paddy"
        result = self.service.translate_to_canonical(text, "en")
        self.assertEqual(result.translated_text, text)

    def test_translate_from_canonical_en_no_mock(self):
        result = self.service.translate_from_canonical("Advisory text", "en")
        self.assertFalse(result.is_mock)

    def test_run_pipeline_en_is_native_path(self):
        result = self.service.run_pipeline(
            user_text="How often should I water tomato?",
            source_lang="en",
            kb_answer="Water twice a week at root level.",
        )
        self.assertIsInstance(result, PipelineResult)
        self.assertEqual(result.translation_note, "native_path")
        self.assertFalse(result.is_mock)
        self.assertEqual(result.answer_in_user_lang, "Water twice a week at root level.")

    def test_run_pipeline_ta_is_native_path(self):
        result = self.service.run_pipeline(
            user_text="தக்காளி செடிக்கு தண்ணீர் எவ்வளவு?",
            source_lang="ta",
            kb_answer="வாரம் இரு முறை பாசனம் செய்யவும்.",
        )
        self.assertEqual(result.translation_note, "native_path")
        self.assertFalse(result.is_mock)
        self.assertEqual(result.answer_in_user_lang, "வாரம் இரு முறை பாசனம் செய்யவும்.")


class TestTranslationServiceMockPaths(unittest.TestCase):
    """Non-native languages must go through mock pipeline with honest labels."""

    def setUp(self):
        self.service = TranslationService(mode="mock")

    def test_service_is_mock_by_default(self):
        self.assertTrue(self.service.is_mock)

    def test_hindi_pipeline_returns_pipeline_result(self):
        result = self.service.run_pipeline(
            user_text="मेरी फसल में कीड़े लग गए हैं",
            source_lang="hi",
            kb_answer="IPM advisory in English.",
        )
        self.assertIsInstance(result, PipelineResult)

    def test_hindi_pipeline_is_mock(self):
        result = self.service.run_pipeline(
            user_text="मेरी फसल में कीड़े लग गए हैं",
            source_lang="hi",
            kb_answer="IPM advisory.",
        )
        self.assertTrue(result.is_mock)

    def test_non_native_translation_note_contains_mock(self):
        result = self.service.run_pipeline(
            user_text="मेरी फसल में कीड़े लग गए हैं",
            source_lang="hi",
            kb_answer="Answer text.",
        )
        self.assertIn("mock_translation_not_active", result.translation_note)

    def test_translation_note_names_detected_language(self):
        result = self.service.run_pipeline(
            user_text="some telugu text",
            source_lang="te",
            kb_answer="KB answer.",
        )
        self.assertIn("Telugu", result.translation_note)

    def test_canonical_text_unchanged_in_mock(self):
        original = "कीट समस्या"
        result = self.service.run_pipeline(
            user_text=original,
            source_lang="hi",
            kb_answer="Advisory text.",
        )
        # In mock mode canonical_text == original (no real translation done)
        self.assertEqual(result.canonical_text, original)

    def test_answer_unchanged_in_mock(self):
        """In mock mode the answer text is returned unchanged — never claimed as translated."""
        answer = "IPM advisory for pest control."
        result = self.service.run_pipeline(
            user_text="pest problem",
            source_lang="kn",
            kb_answer=answer,
        )
        self.assertEqual(result.answer_in_user_lang, answer)

    def test_mock_note_does_not_claim_success(self):
        """The note must never say translation 'succeeded' or 'completed' when mock."""
        result = self.service.run_pipeline(
            user_text="text",
            source_lang="ml",
            kb_answer="answer",
        )
        note_lower = result.translation_note.lower()
        self.assertNotIn("success", note_lower)
        self.assertNotIn("succeeded", note_lower)
        self.assertNotIn("completed successfully", note_lower)

    def test_all_non_native_languages_get_mock_note(self):
        non_native = [lang for lang in SUPPORTED_LANGUAGES if lang not in NATIVE_KB_LANGUAGES]
        for lang in non_native:
            result = self.service.run_pipeline("text", lang, "KB answer")
            self.assertIn("mock_translation_not_active", result.translation_note,
                          f"Expected mock note for language '{lang}'")


class TestTranslationServiceAPIEndpoints(unittest.TestCase):
    """Verify /ask response always contains translation_note field."""

    def setUp(self):
        from fastapi.testclient import TestClient
        from main import app
        self.client = TestClient(app)

    def test_english_ask_has_translation_note_native(self):
        response = self.client.post("/ask", json={"text": "How often should I water my tomato?"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("translation_note", data)
        self.assertEqual(data["translation_note"], "native_path")

    def test_tamil_ask_has_translation_note_native(self):
        response = self.client.post("/ask", json={"text": "தக்காளி செடிக்கு தண்ணீர் எவ்வளவு?"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("translation_note", data)
        self.assertEqual(data["translation_note"], "native_path")

    def test_hindi_ask_has_mock_translation_note(self):
        response = self.client.post("/ask", json={"text": "मेरी फसल में कीड़े लग गए हैं"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("translation_note", data)
        self.assertIn("mock_translation_not_active", data["translation_note"])
        # Must also explicitly say English is the answer language
        self.assertIn("English", data["translation_note"])


if __name__ == "__main__":
    unittest.main()
