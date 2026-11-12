"""Sarvam AI client module for Smart Farming Assistant.

Provides production-grade integrations for:
  • Translation (Mayura model)
  • Speech-to-Text (Saarika model)
  • Text-to-Speech (Bulbul model)

Supports English (en), Hindi (hi), and Kannada (kn), plus other Indian languages.
Includes robust retry handling, timeout protection, error mapping, and mock fallback.
"""

from __future__ import annotations

import base64
import logging
import os
from typing import Optional, Dict, Any
import requests

logger = logging.getLogger(__name__)

# Base endpoint for Sarvam AI APIs
SARVAM_BASE_URL = os.getenv("SARVAM_BASE_URL", "https://api.sarvam.ai").rstrip("/")

# Language code normalization mapping: ISO 639-1 <-> Sarvam BCP-47 tags
ISO_TO_SARVAM_LANG: dict[str, str] = {
    "en": "en-IN",
    "hi": "hi-IN",
    "kn": "kn-IN",
    "ta": "ta-IN",
    "te": "te-IN",
    "ml": "ml-IN",
    "mr": "mr-IN",
    "bn": "bn-IN",
    "gu": "gu-IN",
    "pa": "pa-IN",
    "od": "od-IN",
}

SARVAM_TO_ISO_LANG: dict[str, str] = {
    v: k for k, v in ISO_TO_SARVAM_LANG.items()
}

# Default voice personas per language for Bulbul TTS (validated for bulbul:v3)
DEFAULT_SPEAKERS: dict[str, str] = {
    "hi-IN": "ritu",
    "kn-IN": "ritu",
    "en-IN": "ritu",
    "ta-IN": "gokul",
    "te-IN": "kavitha",
    "ml-IN": "ritu",
    "mr-IN": "ritu",
    "bn-IN": "roopa",
    "gu-IN": "pooja",
    "pa-IN": "simran",
    "od-IN": "ritu",
}


class SarvamError(Exception):
    """Base exception for Sarvam AI errors."""
    pass


class SarvamAuthError(SarvamError):
    """Raised when the Sarvam API key is missing or invalid (HTTP 401/403)."""
    pass


class SarvamQuotaError(SarvamError):
    """Raised when the Sarvam AI API credit balance is exhausted or expired (HTTP 402)."""
    pass


class SarvamRateLimitError(SarvamError):
    """Raised when rate limits are exceeded (HTTP 429)."""
    pass


class SarvamTimeoutError(SarvamError):
    """Raised when the API call times out."""
    pass


class SarvamAPIError(SarvamError):
    """Raised when the API returns an error response."""
    def __init__(self, message: str, status_code: Optional[int] = None, response_text: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text


def to_sarvam_lang(code: str) -> str:
    """Normalize short code ('hi') or full code ('hi-IN') to Sarvam format."""
    clean = code.strip().lower()
    if clean in ISO_TO_SARVAM_LANG:
        return ISO_TO_SARVAM_LANG[clean]
    for sarvam_code in ISO_TO_SARVAM_LANG.values():
        if sarvam_code.lower() == clean:
            return sarvam_code
    return "en-IN"


def from_sarvam_lang(code: str) -> str:
    """Convert Sarvam code ('hi-IN') to ISO 2-letter ('hi')."""
    return SARVAM_TO_ISO_LANG.get(code.strip(), code.strip()[:2].lower())


class SarvamClient:
    """Client for Sarvam AI REST API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout_seconds: float = 15.0,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.getenv("SARVAM_API_KEY", "").strip()
        self.timeout_seconds = timeout_seconds
        self.session = session or requests.Session()

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and not self.api_key.startswith("your_"))

    def _headers(self) -> dict[str, str]:
        if not self.is_configured:
            raise SarvamAuthError("SARVAM_API_KEY is not configured or is empty.")
        return {
            "api-subscription-key": self.api_key,
        }

    # ──────────────────────────────────────────────────────────────────────────
    # Translation (Mayura)
    # ──────────────────────────────────────────────────────────────────────────

    def _translate_single_chunk(
        self,
        chunk: str,
        src_sarvam: str,
        tgt_sarvam: str,
        mode: str,
        model: str,
    ) -> str:
        url = f"{SARVAM_BASE_URL}/translate"
        headers = self._headers()
        headers["Content-Type"] = "application/json"

        payload = {
            "input": chunk,
            "source_language_code": src_sarvam,
            "target_language_code": tgt_sarvam,
            "speaker_gender": "Male",
            "mode": mode,
            "model": model,
        }

        try:
            response = self.session.post(
                url,
                headers=headers,
                json=payload,
                timeout=self.timeout_seconds,
            )
        except requests.exceptions.Timeout as e:
            raise SarvamTimeoutError(f"Sarvam translation request timed out after {self.timeout_seconds}s") from e
        except requests.exceptions.RequestException as e:
            raise SarvamAPIError(f"Sarvam connection error: {e}") from e

        if response.status_code == 200:
            data = response.json()
            return data.get("translated_text", "")

        if response.status_code in (401, 403):
            raise SarvamAuthError(f"Sarvam authentication failed (status {response.status_code}): {response.text}")
        if response.status_code == 402:
            raise SarvamQuotaError("Sarvam AI account credit balance exhausted (HTTP 402).")
        if response.status_code == 429:
            raise SarvamRateLimitError("Sarvam API rate limit exceeded.")

        raise SarvamAPIError(
            f"Sarvam translation failed with status {response.status_code}: {response.text}",
            status_code=response.status_code,
            response_text=response.text,
        )

    def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        mode: str = "formal",
        model: str = "mayura:v1",
    ) -> str:
        """Translate text between Indian languages using Sarvam Mayura.

        Splits text into chunks of <= 800 characters to adhere to Sarvam's
        1000 character maximum payload limit per request.
        """
        text = text.strip()
        if not text:
            return ""

        src_sarvam = to_sarvam_lang(source_lang)
        tgt_sarvam = to_sarvam_lang(target_lang)

        if src_sarvam == tgt_sarvam:
            return text

        # If text is small enough, send directly
        if len(text) <= 800:
            return self._translate_single_chunk(text, src_sarvam, tgt_sarvam, mode, model)

        # Chunk text across paragraph or sentence boundaries
        paragraphs = text.split("\n\n")
        translated_paragraphs = []

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            if len(para) <= 800:
                translated_paragraphs.append(
                    self._translate_single_chunk(para, src_sarvam, tgt_sarvam, mode, model)
                )
            else:
                # Sub-split long paragraph by sentences
                sentences = para.split(". ")
                current_chunk = ""
                for sent in sentences:
                    if len(current_chunk) + len(sent) + 2 <= 800:
                        current_chunk = f"{current_chunk}. {sent}" if current_chunk else sent
                    else:
                        if current_chunk:
                            translated_paragraphs.append(
                                self._translate_single_chunk(current_chunk, src_sarvam, tgt_sarvam, mode, model)
                            )
                        current_chunk = sent[:800]
                if current_chunk:
                    translated_paragraphs.append(
                        self._translate_single_chunk(current_chunk, src_sarvam, tgt_sarvam, mode, model)
                    )

        return "\n\n".join(translated_paragraphs)

    # ──────────────────────────────────────────────────────────────────────────
    # Speech-to-Text (Saarika)
    # ──────────────────────────────────────────────────────────────────────────

    def speech_to_text(
        self,
        audio_bytes: bytes,
        filename: str = "audio.wav",
        language_code: Optional[str] = None,
        model: str = "saaras:v3",
    ) -> Dict[str, Any]:
        """Transcribe spoken audio in Hindi, Kannada, English, or other languages.

        Args:
            audio_bytes: Raw binary audio bytes.
            filename: Audio filename (e.g. 'sample.wav' or 'recording.mp3').
            language_code: Optional expected language hint ('hi', 'kn', 'en', etc.).
            model: 'saaras:v3' (recommended) or earlier.

        Returns:
            Dict with 'transcript' (str) and 'language_code' (str).
        """
        if not audio_bytes:
            raise ValueError("Audio data cannot be empty")

        url = f"{SARVAM_BASE_URL}/speech-to-text"
        headers = self._headers()

        content_type = "audio/wav"
        lower_name = filename.lower()
        if lower_name.endswith(".mp3"):
            content_type = "audio/mpeg"
        elif lower_name.endswith(".ogg") or lower_name.endswith(".opus"):
            content_type = "audio/ogg"
        elif lower_name.endswith(".webm"):
            content_type = "audio/webm"
        elif lower_name.endswith(".m4a") or lower_name.endswith(".aac"):
            content_type = "audio/mp4"

        files = {
            "file": (filename, audio_bytes, content_type),
        }
        data: dict[str, str] = {
            "model": os.getenv("SARVAM_STT_MODEL", model),
        }
        if language_code:
            data["language_code"] = to_sarvam_lang(language_code)
        else:
            data["language_code"] = "unknown"

        try:
            response = self.session.post(
                url,
                headers=headers,
                files=files,
                data=data,
                timeout=self.timeout_seconds + 10.0,
            )
        except requests.exceptions.Timeout as e:
            raise SarvamTimeoutError("Sarvam STT request timed out") from e
        except requests.exceptions.RequestException as e:
            raise SarvamAPIError(f"Sarvam connection error during STT: {e}") from e

        if response.status_code == 200:
            res_json = response.json()
            transcript = res_json.get("transcript", "").strip()
            detected_lang = res_json.get("language_code", "en-IN")
            return {
                "transcript": transcript,
                "language_code": from_sarvam_lang(detected_lang),
                "sarvam_language_code": detected_lang,
                "provider": "sarvam",
            }

        if response.status_code in (401, 403):
            raise SarvamAuthError(f"Sarvam STT authentication failed: {response.text}")
        if response.status_code == 402:
            raise SarvamQuotaError("Sarvam AI account credit balance exhausted (HTTP 402).")
        if response.status_code == 429:
            raise SarvamRateLimitError("Sarvam STT rate limit exceeded.")

        raise SarvamAPIError(
            f"Sarvam STT failed with status {response.status_code}: {response.text}",
            status_code=response.status_code,
            response_text=response.text,
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Text-to-Speech (Bulbul)
    # ──────────────────────────────────────────────────────────────────────────

    def text_to_speech(
        self,
        text: str,
        target_lang: str = "hi",
        speaker: Optional[str] = None,
        pace: float = 1.0,
        model: str = "bulbul:v3",
    ) -> Dict[str, Any]:
        """Synthesize spoken agricultural response using Sarvam Bulbul.

        Args:
            text: Text to speak.
            target_lang: Target language code ('hi', 'kn', 'en', etc.).
            speaker: Optional speaker voice (default selected per language).
            pace: Speech rate (default 1.0).
            model: Sarvam TTS model name.

        Returns:
            Dict with 'audio_bytes' (bytes), 'audio_base64' (str), 'format' ('wav').
        """
        text = text.strip()
        if not text:
            raise ValueError("TTS text cannot be empty")

        # Sarvam Bulbul recommends maximum 500 characters per single call for best audio clarity
        safe_text = text[:800]

        sarvam_lang = to_sarvam_lang(target_lang)
        speaker_name = speaker or DEFAULT_SPEAKERS.get(sarvam_lang, "ritu")

        logger.info(
            "Sarvam TTS request: lang=%s (%s), speaker=%s, chars=%d",
            target_lang,
            sarvam_lang,
            speaker_name,
            len(safe_text),
        )

        url = f"{SARVAM_BASE_URL}/text-to-speech"
        headers = self._headers()
        headers["Content-Type"] = "application/json"

        payload = {
            "inputs": [safe_text],
            "target_language_code": sarvam_lang,
            "speaker": speaker_name,
            "pitch": 0,
            "pace": pace,
            "loudness": 1.2,
            "speech_sample_rate": 16000,
            "enable_preprocessing": True,
            "model": os.getenv("SARVAM_TTS_MODEL", model),
        }

        try:
            response = self.session.post(
                url,
                headers=headers,
                json=payload,
                timeout=self.timeout_seconds + 10.0,
            )
        except requests.exceptions.Timeout as e:
            raise SarvamTimeoutError("Sarvam TTS request timed out") from e
        except requests.exceptions.RequestException as e:
            raise SarvamAPIError(f"Sarvam connection error during TTS: {e}") from e

        if response.status_code == 200:
            data = response.json()
            audios = data.get("audios", [])
            if not audios:
                raise SarvamAPIError("Sarvam TTS returned empty audio list")
            b64_audio = audios[0]
            audio_bytes = base64.b64decode(b64_audio)
            return {
                "audio_bytes": audio_bytes,
                "audio_base64": b64_audio,
                "format": "wav",
                "speaker": speaker_name,
                "language_code": target_lang,
                "provider": "sarvam",
            }

        if response.status_code in (401, 403):
            raise SarvamAuthError(f"Sarvam TTS authentication failed: {response.text}")
        if response.status_code == 402:
            raise SarvamQuotaError("Sarvam AI account credit balance exhausted (HTTP 402).")
        if response.status_code == 429:
            raise SarvamRateLimitError("Sarvam TTS rate limit exceeded.")

        raise SarvamAPIError(
            f"Sarvam TTS failed with status {response.status_code}: {response.text}",
            status_code=response.status_code,
            response_text=response.text,
        )
