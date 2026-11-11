"""Comprehensive tests for Sarvam AI Voice Pipeline (STT, TTS, Fallbacks, Validation, and FastAPI Endpoints).

Covers Milestone 3 Part 3 - Phase 3.1:
  • Audio validation (formats, headers, sizes, empty payloads, corrupt files).
  • Language normalization and mapping (hi, kn, en, and others).
  • SarvamClient STT and TTS mocked HTTP interactions (200, 401, 429, 500, timeout).
  • VoicePipeline modes (mock, sarvam, whisper fallback).
  • FastAPI endpoints (/voice/transcribe-json, /voice/transcribe, /voice/synthesize, /ask-voice-json, /ask-voice).
  • Multi-turn session context preservation across voice interactions.
  • Security auditing: zero leakage of API keys or credentials in responses or logs.
"""

from __future__ import annotations

import base64
import os
import unittest
from unittest.mock import patch, MagicMock
import requests
from fastapi.testclient import TestClient

from main import app
from sarvam_client import (
    SarvamClient,
    SarvamError,
    SarvamAuthError,
    SarvamTimeoutError,
    SarvamRateLimitError,
    SarvamAPIError,
    to_sarvam_lang,
    from_sarvam_lang,
)
from voice_pipeline import (
    VoicePipeline,
    generate_mock_wav,
    clean_text_for_speech,
    validate_audio_data,
    voice_pipeline,
)
from session_manager import session_manager


class TestSarvamClientHelpers(unittest.TestCase):
    """Test language mappings, mock WAV generation, and TTS text preprocessing."""

    def test_language_tag_mapping(self):
        """Verify bidirectional mapping between ISO-639-1 and Sarvam BCP-47 codes."""
        self.assertEqual(to_sarvam_lang("hi"), "hi-IN")
        self.assertEqual(to_sarvam_lang("kn"), "kn-IN")
        self.assertEqual(to_sarvam_lang("en"), "en-IN")
        self.assertEqual(to_sarvam_lang("ta"), "ta-IN")
        self.assertEqual(to_sarvam_lang("hi-IN"), "hi-IN")
        self.assertEqual(to_sarvam_lang("unknown"), "en-IN")

        self.assertEqual(from_sarvam_lang("hi-IN"), "hi")
        self.assertEqual(from_sarvam_lang("kn-IN"), "kn")
        self.assertEqual(from_sarvam_lang("en-IN"), "en")
        self.assertEqual(from_sarvam_lang("ta-IN"), "ta")

    def test_mock_wav_generator(self):
        """Verify mock WAV buffer is a valid RIFF PCM WAV file."""
        wav_bytes = generate_mock_wav(duration_seconds=0.5, sample_rate=16000)
        self.assertGreater(len(wav_bytes), 44)
        self.assertTrue(wav_bytes.startswith(b"RIFF"))
        self.assertEqual(wav_bytes[8:12], b"WAVE")
        self.assertEqual(wav_bytes[12:16], b"fmt ")

    def test_clean_text_for_speech_markdown_and_links(self):
        """Verify TTS text cleaner strips markdown, URLs, and code blocks cleanly."""
        raw_text = (
            "**Tomato Early Blight Advisory**:\n"
            "- Apply `Mancozeb 75% WP` at 2g/liter of water.\n"
            "Visit [ICAR Guide](https://icar.org.in/blight) for details #farming"
        )
        cleaned = clean_text_for_speech(raw_text)
        self.assertNotIn("**", cleaned)
        self.assertNotIn("`", cleaned)
        self.assertNotIn("https://", cleaned)
        self.assertNotIn("[ICAR Guide]", cleaned)
        self.assertIn("ICAR Guide", cleaned)
        self.assertIn("Mancozeb 75% WP", cleaned)

    def test_clean_text_for_speech_sentence_boundary_truncation(self):
        """Verify TTS cleaner truncates cleanly at sentence boundaries rather than mid-word."""
        long_advisory = (
            "First sentence with important information about soil moisture. "
            "Second sentence detailing the specific NPK fertilizer ratio required. "
            "Third sentence warning against over-irrigation during flowering stage. "
            "Fourth sentence explaining post-harvest storage conditions in detail."
        )
        cleaned = clean_text_for_speech(long_advisory, max_chars=140)
        self.assertLessEqual(len(cleaned), 140)
        self.assertTrue(cleaned.endswith(".") or cleaned.endswith("..."))

    def test_clean_text_for_speech_empty_rejected(self):
        """Verify empty text raises ValueError."""
        with self.assertRaises(ValueError) as ctx:
            clean_text_for_speech("   \n\t  ")
        self.assertIn("empty", str(ctx.exception).lower())


class TestVoiceAudioValidation(unittest.TestCase):
    """Test audio data validation rules (sizes, formats, content integrity)."""

    def test_empty_audio_raises_value_error(self):
        with self.assertRaises(ValueError) as ctx:
            validate_audio_data(b"", "recording.wav")
        self.assertIn("empty", str(ctx.exception).lower())

    def test_too_small_audio_raises_value_error(self):
        with self.assertRaises(ValueError) as ctx:
            validate_audio_data(b"RIFFshort", "recording.wav")
        self.assertIn("too small", str(ctx.exception).lower())

    def test_oversized_audio_raises_value_error(self):
        huge_bytes = b"0" * (26 * 1024 * 1024)
        with self.assertRaises(ValueError) as ctx:
            validate_audio_data(huge_bytes, "huge.wav")
        self.assertIn("exceeds", str(ctx.exception).lower())

    def test_unsupported_audio_extension_rejected(self):
        valid_wav = generate_mock_wav(0.2)
        with self.assertRaises(ValueError) as ctx:
            validate_audio_data(valid_wav, "document.pdf")
        self.assertIn("unsupported", str(ctx.exception).lower())

    def test_markup_or_text_payload_rejected(self):
        html_payload = b"<!DOCTYPE html><html><body>Malformed audio</body></html>"
        with self.assertRaises(ValueError) as ctx:
            validate_audio_data(html_payload, "voice.wav")
        self.assertIn("text/markup", str(ctx.exception).lower())

        json_payload = b'{"error": "not an audio stream", "status": 400}'
        with self.assertRaises(ValueError) as ctx:
            validate_audio_data(json_payload, "voice.wav")
        self.assertIn("text/markup", str(ctx.exception).lower())

    def test_valid_audio_payloads_accepted(self):
        wav_data = generate_mock_wav(0.2)
        # Should not raise any exception
        validate_audio_data(wav_data, "sample.wav")
        validate_audio_data(b"ID3" + b"\x00" * 20, "audio.mp3")
        validate_audio_data(b"OggS" + b"\x00" * 20, "audio.ogg")


class TestSarvamClientMockedAPI(unittest.TestCase):
    """Test SarvamClient HTTP interactions using mocked requests.Session."""

    def setUp(self):
        self.session_mock = MagicMock(spec=requests.Session)
        self.client = SarvamClient(
            api_key="test_sarvam_api_key_12345",
            session=self.session_mock,
        )

    def test_speech_to_text_success_hindi(self):
        """Verify Hindi STT request payload and response parsing."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "transcript": "टमाटर के लिए सबसे अच्छी खाद कौन सी है?",
            "language_code": "hi-IN",
        }
        self.session_mock.post.return_value = mock_resp

        wav_bytes = generate_mock_wav(0.5)
        res = self.client.speech_to_text(
            audio_bytes=wav_bytes,
            filename="query.wav",
            language_code="hi",
        )

        self.assertEqual(res["transcript"], "टमाटर के लिए सबसे अच्छी खाद कौन सी है?")
        self.assertEqual(res["language_code"], "hi")
        self.assertEqual(res["provider"], "sarvam")

        # Verify POST request parameters
        call_kwargs = self.session_mock.post.call_args[1]
        self.assertEqual(call_kwargs["headers"]["api-subscription-key"], "test_sarvam_api_key_12345")
        self.assertEqual(call_kwargs["data"]["language_code"], "hi-IN")

    def test_speech_to_text_success_kannada(self):
        """Verify Kannada STT request and response parsing."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "transcript": "ಟೊಮೆಟೊ ಬೆಳೆಗೆ ಸೂಕ್ತ ಗೊಬ್ಬರ ಯಾವುದು?",
            "language_code": "kn-IN",
        }
        self.session_mock.post.return_value = mock_resp

        wav_bytes = generate_mock_wav(0.5)
        res = self.client.speech_to_text(
            audio_bytes=wav_bytes,
            filename="query_kn.wav",
            language_code="kn",
        )
        self.assertEqual(res["transcript"], "ಟೊಮೆಟೊ ಬೆಳೆಗೆ ಸೂಕ್ತ ಗೊಬ್ಬರ ಯಾವುದು?")
        self.assertEqual(res["language_code"], "kn")

    def test_speech_to_text_success_english(self):
        """Verify English STT request and response parsing."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "transcript": "What is the best pesticide for cotton bollworm?",
            "language_code": "en-IN",
        }
        self.session_mock.post.return_value = mock_resp

        wav_bytes = generate_mock_wav(0.5)
        res = self.client.speech_to_text(
            audio_bytes=wav_bytes,
            filename="query_en.wav",
            language_code="en",
        )
        self.assertEqual(res["transcript"], "What is the best pesticide for cotton bollworm?")
        self.assertEqual(res["language_code"], "en")

    def test_speech_to_text_auth_error(self):
        """Verify HTTP 401/403 maps to SarvamAuthError."""
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = "Unauthorized: Invalid Subscription Key"
        self.session_mock.post.return_value = mock_resp

        with self.assertRaises(SarvamAuthError):
            self.client.speech_to_text(generate_mock_wav(0.2), "sample.wav")

    def test_speech_to_text_rate_limit(self):
        """Verify HTTP 429 maps to SarvamRateLimitError."""
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.text = "Rate limit exceeded"
        self.session_mock.post.return_value = mock_resp

        with self.assertRaises(SarvamRateLimitError):
            self.client.speech_to_text(generate_mock_wav(0.2), "sample.wav")

    def test_speech_to_text_timeout(self):
        """Verify requests timeout maps to SarvamTimeoutError."""
        self.session_mock.post.side_effect = requests.exceptions.Timeout("Request timed out")

        with self.assertRaises(SarvamTimeoutError):
            self.client.speech_to_text(generate_mock_wav(0.2), "sample.wav")

    def test_speech_to_text_api_error(self):
        """Verify HTTP 500 maps to SarvamAPIError."""
        mock_resp = MagicMock()
        mock_resp.status_code = 502
        mock_resp.text = "Bad Gateway"
        self.session_mock.post.return_value = mock_resp

        with self.assertRaises(SarvamAPIError):
            self.client.speech_to_text(generate_mock_wav(0.2), "sample.wav")

    def test_text_to_speech_success_all_languages(self):
        """Verify TTS generation for Hindi, Kannada, and English."""
        mock_audio = generate_mock_wav(0.3)
        b64_audio = base64.b64encode(mock_audio).decode("ascii")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"audios": [b64_audio]}
        self.session_mock.post.return_value = mock_resp

        # Test Hindi TTS
        res_hi = self.client.text_to_speech("टमाटर की खेती में सिंचाई करें", target_lang="hi")
        self.assertEqual(res_hi["audio_base64"], b64_audio)
        self.assertEqual(res_hi["language_code"], "hi")
        self.assertEqual(res_hi["format"], "wav")

        # Test Kannada TTS
        res_kn = self.client.text_to_speech("ಟೊಮೆಟೊ ಬೆಳೆಗೆ ನೀರುಣಿಸಿ", target_lang="kn")
        self.assertEqual(res_kn["language_code"], "kn")

        # Test English TTS
        res_en = self.client.text_to_speech("Water tomato crops regularly.", target_lang="en")
        self.assertEqual(res_en["language_code"], "en")

    def test_unconfigured_client_raises_auth_error(self):
        """Verify that an unconfigured client immediately raises SarvamAuthError."""
        unconfigured_client = SarvamClient(api_key="")
        self.assertFalse(unconfigured_client.is_configured)
        with self.assertRaises(SarvamAuthError):
            unconfigured_client.speech_to_text(generate_mock_wav(0.2), "test.wav")
        with self.assertRaises(SarvamAuthError):
            unconfigured_client.text_to_speech("Test advisory", "en")


class TestVoicePipelineModesAndFallbacks(unittest.TestCase):
    """Test VoicePipeline mode handling, Whisper fallbacks, and truthful reporting."""

    def test_mock_transcribe_mode(self):
        """Verify deterministic mock transcription for hi, kn, and en."""
        vp = VoicePipeline(mode="mock")
        wav = generate_mock_wav(0.2)

        res_hi = vp.transcribe(wav, "test.wav", language_hint="hi")
        self.assertEqual(res_hi["provider"], "mock")
        self.assertTrue(res_hi["is_mock"])
        self.assertEqual(res_hi["language_code"], "hi")

        res_kn = vp.transcribe(wav, "test.wav", language_hint="kn")
        self.assertEqual(res_kn["language_code"], "kn")
        self.assertTrue(res_kn["is_mock"])

        res_en = vp.transcribe(wav, "test.wav", language_hint="en")
        self.assertEqual(res_en["language_code"], "en")
        self.assertTrue(res_en["is_mock"])

    def test_mock_synthesize_mode(self):
        """Verify mock TTS produces valid base64 WAV marked as mock."""
        vp = VoicePipeline(mode="mock")
        res = vp.synthesize("टमाटर की फसल में खाद डालें", language_code="hi")
        self.assertEqual(res["provider"], "mock")
        self.assertTrue(res["is_mock"])
        self.assertEqual(res["format"], "wav")
        self.assertTrue(len(res["audio_base64"]) > 50)

    def test_sarvam_mode_truthful_reporting(self):
        """Verify live Sarvam transcription marks provider as sarvam and is_mock as False."""
        mock_sarvam = MagicMock(spec=SarvamClient)
        mock_sarvam.is_configured = True
        mock_sarvam.speech_to_text.return_value = {
            "transcript": "Live farmer audio query",
            "language_code": "en",
        }
        mock_sarvam.text_to_speech.return_value = {
            "audio_base64": base64.b64encode(generate_mock_wav(0.2)).decode("ascii"),
            "format": "wav",
            "language_code": "en",
        }

        vp = VoicePipeline(sarvam_client=mock_sarvam, mode="sarvam")
        wav = generate_mock_wav(0.2)

        stt_res = vp.transcribe(wav, "test.wav", language_hint="en")
        self.assertEqual(stt_res["provider"], "sarvam")
        self.assertFalse(stt_res["is_mock"])
        self.assertEqual(stt_res["transcript"], "Live farmer audio query")

        tts_res = vp.synthesize("Grounded farmer guidance", language_code="en")
        self.assertEqual(tts_res["provider"], "sarvam")
        self.assertFalse(tts_res["is_mock"])

    def test_whisper_fallback_on_sarvam_failure(self):
        """Verify Whisper fallback is engaged when Sarvam STT fails and Whisper is enabled."""
        mock_sarvam = MagicMock(spec=SarvamClient)
        mock_sarvam.is_configured = True
        mock_sarvam.speech_to_text.side_effect = SarvamAPIError("Sarvam service down", status_code=502)

        vp = VoicePipeline(sarvam_client=mock_sarvam, mode="sarvam")
        with patch("voice_pipeline.is_whisper_enabled", return_value=True):
            with patch("voice_pipeline.whisper_fallback.transcribe", return_value={
                "transcript": "Fallback transcribed text",
                "language_code": "en",
                "provider": "whisper_fallback",
            }):
                res = vp.transcribe(generate_mock_wav(0.2), "input.wav", language_hint="en")
                self.assertEqual(res["provider"], "whisper_fallback")
                self.assertFalse(res["is_mock"])
                self.assertEqual(res["transcript"], "Fallback transcribed text")

    def test_whisper_disabled_re_raises_sarvam_error(self):
        """Verify that when Whisper fallback is disabled, Sarvam error is propagated."""
        mock_sarvam = MagicMock(spec=SarvamClient)
        mock_sarvam.is_configured = True
        mock_sarvam.speech_to_text.side_effect = SarvamTimeoutError("Sarvam timed out")

        vp = VoicePipeline(sarvam_client=mock_sarvam, mode="sarvam")
        with patch("voice_pipeline.is_whisper_enabled", return_value=False):
            with self.assertRaises(SarvamTimeoutError):
                vp.transcribe(generate_mock_wav(0.2), "input.wav")


class TestFastAPIVoiceEndpoints(unittest.TestCase):
    """Integration tests for FastAPI /voice/* and /ask-voice endpoints."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.sample_wav = generate_mock_wav(0.3)
        cls.sample_b64 = base64.b64encode(cls.sample_wav).decode("ascii")

    def test_voice_transcribe_json_valid_and_invalid(self):
        """Test POST /voice/transcribe-json input validation and execution."""
        # Empty audio_base64
        r_empty = self.client.post("/voice/transcribe-json", json={"audio_base64": ""})
        self.assertEqual(r_empty.status_code, 400)

        # Invalid base64
        r_bad_b64 = self.client.post("/voice/transcribe-json", json={"audio_base64": "!!!not_base64!!!"})
        self.assertEqual(r_bad_b64.status_code, 400)

        # Valid mock audio
        with patch.object(voice_pipeline, "mode", "mock"):
            r_valid = self.client.post(
                "/voice/transcribe-json",
                json={
                    "audio_base64": self.sample_b64,
                    "filename": "query.wav",
                    "language_hint": "hi",
                },
            )
            self.assertEqual(r_valid.status_code, 200)
            data = r_valid.json()
            self.assertIn("transcript", data)
            self.assertEqual(data["language_code"], "hi")
            self.assertEqual(data["provider"], "mock")

    def test_voice_transcribe_multipart(self):
        """Test POST /voice/transcribe multipart file upload."""
        # Empty file
        r_empty = self.client.post(
            "/voice/transcribe",
            files={"file": ("empty.wav", b"", "audio/wav")},
        )
        self.assertEqual(r_empty.status_code, 400)

        # Non-audio file
        r_text = self.client.post(
            "/voice/transcribe",
            files={"file": ("notes.txt", b"plain text notes", "text/plain")},
        )
        self.assertEqual(r_text.status_code, 400)

        # Valid WAV
        with patch.object(voice_pipeline, "mode", "mock"):
            r_valid = self.client.post(
                "/voice/transcribe",
                files={"file": ("farmer.wav", self.sample_wav, "audio/wav")},
                data={"language_hint": "en"},
            )
            self.assertEqual(r_valid.status_code, 200)
            data = r_valid.json()
            self.assertIn("transcript", data)
            self.assertEqual(data["provider"], "mock")

    def test_voice_synthesize_endpoint(self):
        """Test POST /voice/synthesize with empty text and valid text."""
        # Empty text
        r_empty = self.client.post("/voice/synthesize", json={"text": "   "})
        self.assertEqual(r_empty.status_code, 400)

        # Valid text
        with patch.object(voice_pipeline, "mode", "mock"):
            r_valid = self.client.post(
                "/voice/synthesize",
                json={"text": "टमाटर के लिए जल प्रबंधन", "language_code": "hi"},
            )
            self.assertEqual(r_valid.status_code, 200)
            data = r_valid.json()
            self.assertIn("audio_base64", data)
            self.assertEqual(data["format"], "wav")
            self.assertEqual(data["language_code"], "hi")

    def test_ask_voice_json_end_to_end_multilingual(self):
        """Test POST /ask-voice-json: STT -> RAG -> TTS for Hindi, Kannada, and English."""
        with patch.object(voice_pipeline, "mode", "mock"):
            for lang in ("hi", "kn", "en"):
                r = self.client.post(
                    "/ask-voice-json",
                    json={
                        "audio_base64": self.sample_b64,
                        "filename": f"query_{lang}.wav",
                        "language_hint": lang,
                    },
                )
                self.assertEqual(r.status_code, 200, f"Failed for language {lang}: {r.text}")
                data = r.json()

                # Verify required top-level fields
                self.assertIn("session_id", data)
                self.assertIn("transcript", data)
                self.assertIn("question", data)
                self.assertIn("answer", data)
                self.assertIn("intent", data)
                self.assertIn("audio_base64", data)
                self.assertIn("audio_format", data)
                self.assertEqual(data["audio_format"], "wav")
                self.assertIn("stt_provider", data)
                self.assertIn("tts_provider", data)
                self.assertIn("analysis", data)

    def test_ask_voice_multipart_end_to_end(self):
        """Test POST /ask-voice multipart audio query."""
        with patch.object(voice_pipeline, "mode", "mock"):
            r = self.client.post(
                "/ask-voice",
                files={"file": ("recording.wav", self.sample_wav, "audio/wav")},
                data={"language_hint": "en"},
            )
            self.assertEqual(r.status_code, 200)
            data = r.json()
            self.assertIn("transcript", data)
            self.assertIn("answer", data)
            self.assertIn("audio_base64", data)
            self.assertEqual(data["audio_format"], "wav")

    def test_ask_voice_session_context_preservation(self):
        """Test that consecutive voice queries in the same session maintain context and turn count."""
        with patch.object(voice_pipeline, "mode", "mock"):
            # Turn 1
            r1 = self.client.post(
                "/ask-voice-json",
                json={
                    "audio_base64": self.sample_b64,
                    "filename": "turn1.wav",
                    "language_hint": "en",
                },
            )
            self.assertEqual(r1.status_code, 200)
            session_id = r1.json()["session_id"]
            self.assertTrue(session_id)

            # Turn 2 using the same session_id
            r2 = self.client.post(
                "/ask-voice-json",
                json={
                    "audio_base64": self.sample_b64,
                    "filename": "turn2.wav",
                    "session_id": session_id,
                    "language_hint": "en",
                },
            )
            self.assertEqual(r2.status_code, 200)
            data2 = r2.json()
            self.assertEqual(data2["session_id"], session_id)

            sess = session_manager.get_session(session_id)
            self.assertIsNotNone(sess)
            self.assertGreaterEqual(sess.turn_count, 2)

    def test_voice_error_mapping_and_security(self):
        """Verify mapped HTTP error status codes and ensure API keys are never exposed."""
        secret_key_mock = "sk_secret_value_that_must_never_leak_xyz"

        # 1. SarvamAuthError -> 401
        with patch.object(voice_pipeline, "mode", "sarvam"):
            with patch.object(
                voice_pipeline.sarvam,
                "speech_to_text",
                side_effect=SarvamAuthError(f"Invalid key: {secret_key_mock}"),
            ):
                with patch("voice_pipeline.is_whisper_enabled", return_value=False):
                    r_auth = self.client.post(
                        "/voice/transcribe-json",
                        json={"audio_base64": self.sample_b64},
                    )
                    self.assertEqual(r_auth.status_code, 401)
                    self.assertNotIn(secret_key_mock, r_auth.text)

        # 2. SarvamTimeoutError -> 504
        with patch.object(voice_pipeline, "mode", "sarvam"):
            with patch.object(
                voice_pipeline.sarvam,
                "speech_to_text",
                side_effect=SarvamTimeoutError("Gateway timeout after 15s"),
            ):
                with patch("voice_pipeline.is_whisper_enabled", return_value=False):
                    r_timeout = self.client.post(
                        "/voice/transcribe-json",
                        json={"audio_base64": self.sample_b64},
                    )
                    self.assertEqual(r_timeout.status_code, 504)

        # 3. SarvamRateLimitError -> 429 with Retry-After header
        with patch.object(voice_pipeline, "mode", "sarvam"):
            with patch.object(
                voice_pipeline.sarvam,
                "speech_to_text",
                side_effect=SarvamRateLimitError("Rate limit reached"),
            ):
                with patch("voice_pipeline.is_whisper_enabled", return_value=False):
                    r_rate = self.client.post(
                        "/voice/transcribe-json",
                        json={"audio_base64": self.sample_b64},
                    )
                    self.assertEqual(r_rate.status_code, 429)
                    self.assertEqual(r_rate.headers.get("retry-after"), "60")

        # 4. SarvamAPIError -> 502
        with patch.object(voice_pipeline, "mode", "sarvam"):
            with patch.object(
                voice_pipeline.sarvam,
                "speech_to_text",
                side_effect=SarvamAPIError("Upstream 502 Bad Gateway", status_code=502),
            ):
                with patch("voice_pipeline.is_whisper_enabled", return_value=False):
                    r_api = self.client.post(
                        "/voice/transcribe-json",
                        json={"audio_base64": self.sample_b64},
                    )
                    self.assertEqual(r_api.status_code, 502)


class TestPhase33EndToEndVoiceIntegration(unittest.TestCase):
    """End-to-end integration tests for FarmSaathi Milestone 3 Phase 3.3.

    Covers:
      1. English, Hindi, and Kannada voice questions via POST /ask-voice-json
      2. Multi-turn conversation sessions interleaving voice and text
      3. On-demand TTS synthesis fallback (/voice/synthesize)
      4. Invalid and empty audio handling (validation, error formats)
      5. Session reset and isolation
      6. Expired / not-found session handling
      7. Browser audio container formats (WebM, Ogg, WAV)
    """

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.wav_bytes = generate_mock_wav(0.4)
        cls.wav_b64 = base64.b64encode(cls.wav_bytes).decode("ascii")
        cls.webm_bytes = b"\x1a\x45\xdf\xa3" + b"\x00" * 60
        cls.webm_b64 = base64.b64encode(cls.webm_bytes).decode("ascii")
        cls.ogg_bytes = b"OggS" + b"\x00" * 60
        cls.ogg_b64 = base64.b64encode(cls.ogg_bytes).decode("ascii")

    def test_multilingual_voice_questions_en_hi_kn(self):
        """Test voice questions across English, Hindi, and Kannada."""
        with patch.object(voice_pipeline, "mode", "mock"):
            for lang in ("en", "hi", "kn"):
                res = self.client.post(
                    "/ask-voice-json",
                    json={
                        "audio_base64": self.webm_b64,
                        "filename": f"recording_{lang}.webm",
                        "language_hint": lang,
                    },
                )
                self.assertEqual(res.status_code, 200, f"Failed for {lang}: {res.text}")
                data = res.json()
                self.assertTrue(data.get("session_id"))
                self.assertTrue(data.get("transcript"))
                self.assertTrue(data.get("answer"))
                self.assertTrue(data.get("intent"))
                self.assertEqual(data.get("audio_format"), "wav")
                self.assertTrue(data.get("audio_base64"))

    def test_multi_turn_voice_and_text_same_session(self):
        """Test multi-turn interaction in the same session mixing voice and text."""
        with patch.object(voice_pipeline, "mode", "mock"):
            # Turn 1: Voice question
            r1 = self.client.post(
                "/ask-voice-json",
                json={
                    "audio_base64": self.webm_b64,
                    "filename": "turn1.webm",
                    "language_hint": "hi",
                },
            )
            self.assertEqual(r1.status_code, 200)
            session_id = r1.json()["session_id"]
            self.assertTrue(session_id)

            # Turn 2: Follow-up text question in the same session
            r2 = self.client.post(
                "/ask",
                json={
                    "text": "What fertilizer should I apply?",
                    "session_id": session_id,
                    "preferred_language": "hi",
                },
            )
            self.assertEqual(r2.status_code, 200)
            self.assertEqual(r2.json()["session_id"], session_id)

            # Turn 3: Follow-up voice question in the same session
            r3 = self.client.post(
                "/ask-voice-json",
                json={
                    "audio_base64": self.webm_b64,
                    "filename": "turn3.webm",
                    "session_id": session_id,
                    "language_hint": "hi",
                },
            )
            self.assertEqual(r3.status_code, 200)
            self.assertEqual(r3.json()["session_id"], session_id)

            sess = session_manager.get_session(session_id)
            self.assertIsNotNone(sess)
            self.assertGreaterEqual(sess.turn_count, 3)

    def test_tts_playback_synthesis_multilingual(self):
        """Test on-demand TTS synthesis fallback across supported languages."""
        with patch.object(voice_pipeline, "mode", "mock"):
            for lang, text in [
                ("en", "Apply nitrogen fertilizer during vegetative growth."),
                ("hi", "फसल में नाइट्रोजन खाद का समय पर उपयोग करें।"),
                ("kn", "ಬೆಳೆಗೆ ಸಾರಜನಕ ಗೊಬ್ಬರವನ್ನು ಸರಿಯಾದ ಸಮಯದಲ್ಲಿ ಹಾಕಿ."),
            ]:
                res = self.client.post(
                    "/voice/synthesize",
                    json={"text": text, "language_code": lang},
                )
                self.assertEqual(res.status_code, 200, f"Synthesis failed for {lang}")
                data = res.json()
                self.assertTrue(data.get("audio_base64"))
                self.assertEqual(data.get("format"), "wav")

    def test_invalid_and_empty_voice_recordings(self):
        """Verify validation rejects empty, too-small, and corrupted audio."""
        # Empty base64
        r_empty = self.client.post("/ask-voice-json", json={"audio_base64": ""})
        self.assertEqual(r_empty.status_code, 400)

        # Truncated / too small (< 12 bytes)
        too_small_b64 = base64.b64encode(b"short").decode("ascii")
        r_small = self.client.post("/ask-voice-json", json={"audio_base64": too_small_b64})
        self.assertEqual(r_small.status_code, 400)

        # Corrupted / HTML payload
        html_b64 = base64.b64encode(b"<!DOCTYPE html><html><body>Error</body></html>").decode("ascii")
        r_html = self.client.post(
            "/ask-voice-json",
            json={"audio_base64": html_b64, "filename": "test.wav"},
        )
        self.assertEqual(r_html.status_code, 400)

    def test_expired_or_invalid_session_handling(self):
        """Verify handling of invalid or non-existent session IDs."""
        with patch.object(voice_pipeline, "mode", "mock"):
            res = self.client.post(
                "/ask-voice-json",
                json={
                    "audio_base64": self.wav_b64,
                    "filename": "query.wav",
                    "session_id": "nonexistent-session-id-12345",
                    "language_hint": "en",
                },
            )
            self.assertEqual(res.status_code, 404)

    def test_new_chat_session_reset_isolation(self):
        """Verify that starting a new session without session_id creates an isolated session."""
        with patch.object(voice_pipeline, "mode", "mock"):
            r1 = self.client.post(
                "/ask-voice-json",
                json={"audio_base64": self.wav_b64, "filename": "turn1.wav", "language_hint": "en"},
            )
            s1_id = r1.json()["session_id"]

            r2 = self.client.post(
                "/ask-voice-json",
                json={"audio_base64": self.wav_b64, "filename": "turn2.wav", "language_hint": "en"},
            )
            s2_id = r2.json()["session_id"]

            self.assertNotEqual(s1_id, s2_id)
            s1 = session_manager.get_session(s1_id)
            s2 = session_manager.get_session(s2_id)
            self.assertIsNotNone(s1)
            self.assertIsNotNone(s2)
            self.assertEqual(s1.turn_count, 1)
            self.assertEqual(s2.turn_count, 1)

    def test_browser_audio_formats_webm_and_ogg(self):
        """Verify backend accepts WebM and Ogg containers produced by modern browsers."""
        with patch.object(voice_pipeline, "mode", "mock"):
            # WebM
            r_webm = self.client.post(
                "/ask-voice-json",
                json={"audio_base64": self.webm_b64, "filename": "recording.webm", "language_hint": "en"},
            )
            self.assertEqual(r_webm.status_code, 200)

            # Ogg
            r_ogg = self.client.post(
                "/ask-voice-json",
                json={"audio_base64": self.ogg_b64, "filename": "recording.ogg", "language_hint": "en"},
            )
            self.assertEqual(r_ogg.status_code, 200)


if __name__ == "__main__":
    unittest.main()
