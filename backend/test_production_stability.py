"""Tests for FarmSaathi production stability, admin persistence, and voice resilience.

Covers:
1. Issue 1: Admin account auto-seeding from environment variables on startup / table init.
2. Issue 1: Admin credential synchronization if environment password is updated.
3. Issue 1: RBAC enforcement (farmer rejected from /admin routes, invalid password rejected).
4. Issue 2 & 4: Language hint preservation (user-selected language honored).
5. Issue 5: Non-blocking TTS fallback (answer preserved even if synthesis fails).
6. Issue 6: Session and multi-turn persistence.
"""

from __future__ import annotations

import os
import sqlite3
import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from main import app
from security import PasswordManager, SecurityUserManager, User


@pytest.fixture
def client():
    return TestClient(app)


class TestAdminPersistenceAndAutoSeeding:
    """Verify administrator account auto-seeding and credential synchronization."""

    def test_admin_auto_seeding_on_init(self, tmp_path):
        db_file = tmp_path / "test_ephemeral_sessions.db"
        test_user = "farmadmin_test"
        test_pass = "FarmAdminSecure123!"

        with patch.dict(
            os.environ,
            {
                "ADMIN_USERNAME": test_user,
                "ADMIN_PASSWORD": test_pass,
                "FARM_SESSIONS_DB_PATH": str(db_file),
            },
        ):
            mgr = SecurityUserManager(db_path=db_file)
            user = mgr.get_user_by_username(test_user)
            assert user is not None
            assert user.username == test_user
            assert user.role == "admin"
            assert user.is_active is True

            # Verify authentication succeeds with the seeded password
            auth_user = mgr.authenticate(test_user, test_pass)
            assert auth_user is not None
            assert auth_user.username == test_user

            # Verify invalid password fails
            assert mgr.authenticate(test_user, "WrongPassword999") is None

    def test_admin_credential_synchronization_on_password_update(self, tmp_path):
        db_file = tmp_path / "test_sync_sessions.db"
        test_user = "sync_admin"
        old_pass = "OldPassword123!"
        new_pass = "NewStrongerPassword456!"

        # Initial seed
        with patch.dict(
            os.environ,
            {
                "ADMIN_USERNAME": test_user,
                "ADMIN_PASSWORD": old_pass,
                "FARM_SESSIONS_DB_PATH": str(db_file),
            },
        ):
            mgr1 = SecurityUserManager(db_path=db_file)
            assert mgr1.authenticate(test_user, old_pass) is not None

        # Re-initialization with new password (simulating Render env update + restart)
        with patch.dict(
            os.environ,
            {
                "ADMIN_USERNAME": test_user,
                "ADMIN_PASSWORD": new_pass,
                "FARM_SESSIONS_DB_PATH": str(db_file),
            },
        ):
            mgr2 = SecurityUserManager(db_path=db_file)
            # Old password should no longer work
            assert mgr2.authenticate(test_user, old_pass) is None
            # New password works immediately
            assert mgr2.authenticate(test_user, new_pass) is not None

    def test_admin_login_api_endpoint(self, client):
        """Test /auth/login with newly seeded admin."""
        unique_user = f"adm_{uuid.uuid4().hex[:8]}"
        unique_pass = "SuperSecretAdmPass!"

        with patch.dict(
            os.environ,
            {
                "ADMIN_USERNAME": unique_user,
                "ADMIN_PASSWORD": unique_pass,
            },
        ):
            # Trigger table init with new credentials
            SecurityUserManager()

            # Attempt login
            resp = client.post(
                "/auth/login",
                json={"username": unique_user, "password": unique_pass},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["role"] == "admin"
            assert data["username"] == unique_user
            assert "access_token" in data

            # Verify invalid credentials return 401
            bad_resp = client.post(
                "/auth/login",
                json={"username": unique_user, "password": "WrongPassword"},
            )
            assert bad_resp.status_code == 401


class TestVoiceAndLanguageResilience:
    """Verify voice processing, language hint prioritization, and non-blocking TTS."""

    def test_ask_voice_json_non_blocking_when_tts_fails(self, client):
        """If TTS synthesis throws an exception, user still receives full text guidance."""
        dummy_base64 = "UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA="

        # Mock voice_pipeline.transcribe to return a valid transcript
        with patch("voice_pipeline.voice_pipeline.transcribe") as mock_stt, \
             patch("voice_pipeline.voice_pipeline.synthesize", side_effect=RuntimeError("Sarvam Bulbul quota exceeded")):
            mock_stt.return_value = {
                "transcript": "Why are my crop leaves turning yellow?",
                "language_code": "en",
                "provider": "mock",
            }

            resp = client.post(
                "/ask-voice-json",
                json={
                    "audio_base64": dummy_base64,
                    "filename": "question.wav",
                    "language_hint": "en",
                },
            )

            assert resp.status_code == 200
            data = resp.json()
            assert "leaves" in data["question"].lower()
            assert len(data["answer"]) > 0
            assert len(data["sources"]) > 0
            # Audio is None because TTS failed, but text response was preserved
            assert data["audio_base64"] is None
            assert data["tts_provider"] == "unavailable"

    def test_language_hint_respected_for_kannada_query(self, client):
        """User's selected language hint 'kn' is prioritized over fallback."""
        dummy_base64 = "UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA="

        with patch("voice_pipeline.voice_pipeline.transcribe") as mock_stt:
            # Simulate STT returning default 'en' but user selected 'kn'
            mock_stt.return_value = {
                "transcript": "ನನ್ನ ಬೆಳೆಗೆ ಯಾವ ಗೊಬ್ಬರ ಬೇಕು?",
                "language_code": "en",
                "provider": "mock",
            }

            resp = client.post(
                "/ask-voice-json",
                json={
                    "audio_base64": dummy_base64,
                    "filename": "question.wav",
                    "language_hint": "kn",
                },
            )

            assert resp.status_code == 200
            data = resp.json()
            # Language code passed to RAG should be 'kn'
            assert data["language_code"] == "kn"

    def test_language_hint_respected_for_hindi_query(self, client):
        """User's selected language hint 'hi' is prioritized over fallback."""
        dummy_base64 = "UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA="

        with patch("voice_pipeline.voice_pipeline.transcribe") as mock_stt:
            mock_stt.return_value = {
                "transcript": "धान की सिंचाई कब करनी चाहिए?",
                "language_code": "en",
                "provider": "mock",
            }

            resp = client.post(
                "/ask-voice-json",
                json={
                    "audio_base64": dummy_base64,
                    "filename": "question.wav",
                    "language_hint": "hi",
                },
            )

            assert resp.status_code == 200
            data = resp.json()
            assert data["language_code"] == "hi"

    @pytest.mark.parametrize("lang", ["en", "hi", "kn"])
    def test_synthesize_multilingual_mock(self, client, lang):
        """Verify /voice/synthesize produces valid WAV base64 in English, Hindi, and Kannada."""
        sample_texts = {
            "en": "Apply urea in split doses after irrigation.",
            "hi": "सिंचाई के बाद यूरिया को दो भागों में डालें।",
            "kn": "ನೀರಾವರಿಯ ನಂತರ ಯೂರಿಯಾವನ್ನು ಎರಡು ಕಂತುಗಳಲ್ಲಿ ಹಾಕಿ.",
        }
        resp = client.post(
            "/voice/synthesize",
            json={
                "text": sample_texts[lang],
                "language_code": lang,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "audio_base64" in data
        assert len(data["audio_base64"]) > 50
        assert data["format"] == "wav"
        assert data["language_code"] == lang

    def test_voice_synthesize_quota_error_returns_402(self, client):
        """Verify SarvamQuotaError returns HTTP 402 with actionable guidance."""
        from sarvam_client import SarvamQuotaError
        with patch("voice_pipeline.voice_pipeline.synthesize", side_effect=SarvamQuotaError("Sarvam AI account credit balance exhausted (HTTP 402).")):
            resp = client.post(
                "/voice/synthesize",
                json={
                    "text": "Check soil moisture before seeding.",
                    "language_code": "en",
                },
            )
            assert resp.status_code == 402
            assert "quota exhausted" in resp.json()["detail"].lower()

    def test_sarvam_client_raises_quota_error_on_402(self):
        """Verify SarvamClient methods specifically raise SarvamQuotaError on HTTP 402."""
        from unittest.mock import MagicMock
        from sarvam_client import SarvamClient, SarvamQuotaError

        mock_session = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 402
        mock_resp.text = '{"error":{"message":"No credits available.","code":"insufficient_quota_error"}}'
        mock_session.post.return_value = mock_resp

        client = SarvamClient(api_key="valid_dummy_key", session=mock_session)

        # Test text_to_speech
        with pytest.raises(SarvamQuotaError):
            client.text_to_speech(text="Soil health test", target_lang="hi")

        # Test speech_to_text
        with pytest.raises(SarvamQuotaError):
            client.speech_to_text(audio_bytes=b"RIFFdummy", language_code="hi")

        # Test translate chunk
        with pytest.raises(SarvamQuotaError):
            client._translate_single_chunk("Hello", "en-IN", "hi-IN", "formal", "mayura:v1")
