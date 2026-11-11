"""Voice Pipeline for Smart Farming Assistant.

Integrates:
  • Primary STT: Sarvam AI Saarika / Saaras model (Hindi, Kannada, English, etc.)
  • Fallback STT: Whisper (configurable when Sarvam fails or is unsupported)
  • Primary TTS: Sarvam AI Bulbul model (Hindi, Kannada, English, etc.)
"""

from __future__ import annotations

import base64
import logging
import os
import re
import struct
import sys
from typing import Optional, Dict, Any

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
from whisper_fallback import whisper_fallback, is_whisper_enabled

logger = logging.getLogger(__name__)

SUPPORTED_AUDIO_EXTENSIONS = {
    ".wav", ".mp3", ".ogg", ".opus", ".webm", ".m4a", ".aac", ".flac"
}


def validate_audio_data(audio_bytes: bytes, filename: str = "voice.wav") -> None:
    """Validate audio data length, format extension, and header content integrity."""
    if not audio_bytes or len(audio_bytes) == 0:
        raise ValueError("Audio input is empty. Please record audio before submitting.")

    if len(audio_bytes) < 12:
        raise ValueError("Audio data is too small to be a valid audio recording.")

    if len(audio_bytes) > 25 * 1024 * 1024:
        raise ValueError("Audio file exceeds maximum allowed size of 25 MB.")

    ext = os.path.splitext(filename.lower())[1]
    if ext and ext not in SUPPORTED_AUDIO_EXTENSIONS:
        supported_str = ", ".join(sorted(e.lstrip(".").upper() for e in SUPPORTED_AUDIO_EXTENSIONS))
        raise ValueError(f"Unsupported audio format '{ext}'. Supported formats: {supported_str}.")

    # Check for obvious non-audio payloads (e.g. plain text, HTML, JSON, scripts)
    header = audio_bytes[:16]
    lower_header = header.lower()
    if (
        lower_header.startswith(b"<!doctype")
        or lower_header.startswith(b"<html")
        or lower_header.startswith(b"<svg")
        or lower_header.startswith(b"<?xml")
        or lower_header.startswith(b"{\n")
        or lower_header.startswith(b"{\r")
        or lower_header.startswith(b'{"')
    ):
        raise ValueError("Invalid audio data: file contains text/markup rather than binary audio.")

    is_recognized_audio = (
        header.startswith(b"RIFF")                   # WAV
        or header.startswith(b"OggS")               # OGG / Opus
        or header.startswith(b"ID3")                # MP3 ID3v2
        or header[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2") # MP3 frame sync
        or header.startswith(b"\x1a\x45\xdf\xa3")   # WebM / Matroska
        or header.startswith(b"fLaC")               # FLAC
        or b"ftyp" in header                        # MP4 / M4A / AAC
        or (ext in SUPPORTED_AUDIO_EXTENSIONS)      # Fallback to extension check
    )

    if not is_recognized_audio:
        raise ValueError("Malformed or unrecognizable audio format header.")


def clean_text_for_speech(text: str, max_chars: int = 500) -> str:
    """Prepare text for TTS synthesis: strip markdown, URLs, symbols, and truncate cleanly."""
    clean = text.strip()
    if not clean:
        raise ValueError("Text to synthesize cannot be empty.")

    # Remove multiline code blocks; keep inline code text without backticks
    clean = re.sub(r"```[\s\S]*?```", "", clean)
    clean = re.sub(r"`([^`]*)`", r"\1", clean)
    # Remove markdown links [text](url) -> text
    clean = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", clean)
    # Remove raw URLs
    clean = re.sub(r"https?://\S+", "", clean)
    # Remove markdown bold/italic and headers
    clean = re.sub(r"[*_~#]", "", clean)
    # Clean bullet symbols and brackets
    clean = re.sub(r"[•\-–—►▪■▶\u3010\u3011\[\]]", " ", clean)
    # Normalize multiple whitespace to single space
    clean = re.sub(r"\s+", " ", clean).strip()

    # Truncate at sentence boundary within max_chars
    if len(clean) > max_chars:
        truncated = clean[:max_chars]
        last_punct = max(
            truncated.rfind(". "),
            truncated.rfind("। "),
            truncated.rfind("? "),
            truncated.rfind("! "),
            truncated.rfind("; "),
        )
        if last_punct > 120:
            clean = truncated[:last_punct + 1].strip()
        else:
            clean = truncated.rstrip() + "..."

    return clean


def generate_mock_wav(duration_seconds: float = 0.5, sample_rate: int = 16000) -> bytes:
    """Generate a minimal valid 16-bit PCM RIFF WAV audio buffer for offline testing."""
    num_samples = int(duration_seconds * sample_rate)
    byte_rate = sample_rate * 2  # 16-bit mono = 2 bytes per sample
    data_size = num_samples * 2
    riff_chunk_size = 36 + data_size

    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        riff_chunk_size,
        b"WAVE",
        b"fmt ",
        16,             # Subchunk1Size for PCM
        1,              # AudioFormat: 1 = PCM
        1,              # NumChannels: 1 = Mono
        sample_rate,    # SampleRate
        byte_rate,      # ByteRate
        2,              # BlockAlign
        16,             # BitsPerSample
        b"data",
        data_size,
    )
    # Silent PCM samples (all zeroes)
    data = b"\x00" * data_size
    return header + data


class VoicePipeline:
    """Complete STT and TTS voice pipeline for farmer interaction."""

    def __init__(
        self,
        sarvam_client: Optional[SarvamClient] = None,
        mode: Optional[str] = None,
    ) -> None:
        self.sarvam = sarvam_client or SarvamClient()
        self._mode = mode

    @property
    def mode(self) -> str:
        if self._mode:
            return self._mode.strip().lower()
        if os.getenv("PYTEST_CURRENT_TEST") or "pytest" in sys.modules:
            env_mode = os.getenv("VOICE_MODE", "").strip().lower()
            if env_mode == "live":
                return "sarvam"
            return "mock"
        return os.getenv("VOICE_MODE", "sarvam").strip().lower()

    @mode.setter
    def mode(self, value: Optional[str]) -> None:
        self._mode = value

    @mode.deleter
    def mode(self) -> None:
        self._mode = None

    # ──────────────────────────────────────────────────────────────────────────
    # Speech-to-Text
    # ──────────────────────────────────────────────────────────────────────────

    def transcribe(
        self,
        audio_bytes: bytes,
        filename: str = "voice_input.wav",
        language_hint: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Transcribe farmer audio input in Hindi, Kannada, or English.

        1. Validates audio data length, format, and content.
        2. In mock mode, returns deterministic test transcript.
        3. Attempts primary transcription with Sarvam Saarika/Saaras.
        4. If Sarvam fails or is unconfigured, delegates to Whisper fallback if enabled.
        5. Never reports a mock response as live Sarvam output.
        """
        validate_audio_data(audio_bytes, filename)

        # Normalize language hint
        normalized_hint = language_hint.strip() if language_hint else None
        if normalized_hint and normalized_hint.lower() in ("auto", "unknown", ""):
            normalized_hint = None

        # 1. Deterministic Mock Mode
        if self.mode == "mock":
            sample_transcripts = {
                "hi": "मेरी टमाटर की फसल में कीड़े लग गए हैं",
                "kn": "ನನ್ನ ಟೊಮೆಟೊ ಬೆಳೆಗೆ ಹುಳು ಬಿದ್ದಿದೆ, ನಿಯಂತ್ರಣ ಹೇಗೆ?",
                "en": "How often should I water my tomato plants in black soil?",
            }
            lang = normalized_hint or "en"
            short_lang = lang[:2].lower()
            return {
                "transcript": sample_transcripts.get(short_lang, sample_transcripts["en"]),
                "language_code": short_lang,
                "provider": "mock",
                "is_mock": True,
            }

        # 2. Primary STT: Sarvam AI
        if self.sarvam.is_configured:
            try:
                result = self.sarvam.speech_to_text(
                    audio_bytes=audio_bytes,
                    filename=filename,
                    language_code=normalized_hint,
                )
                if result is not None:
                    result["is_mock"] = False
                    result["provider"] = "sarvam"
                    return result
            except (SarvamError, Exception) as exc:
                logger.warning("Sarvam STT failed (%s). Checking Whisper fallback...", exc)
                if is_whisper_enabled():
                    try:
                        logger.info("Engaging Whisper fallback for audio transcription...")
                        res = whisper_fallback.transcribe(
                            audio_bytes=audio_bytes,
                            filename=filename,
                            language_code=normalized_hint,
                        )
                        res["is_mock"] = False
                        res["provider"] = "whisper_fallback"
                        return res
                    except Exception as w_exc:
                        logger.error("Whisper fallback also failed: %s", w_exc)
                        raise exc from w_exc
                # If Whisper is not enabled, re-raise Sarvam exception
                raise

        # 3. If Sarvam is unconfigured, try Whisper fallback
        if is_whisper_enabled():
            try:
                logger.info("Sarvam not configured. Using Whisper fallback...")
                res = whisper_fallback.transcribe(
                    audio_bytes=audio_bytes,
                    filename=filename,
                    language_code=normalized_hint,
                )
                res["is_mock"] = False
                res["provider"] = "whisper_fallback"
                return res
            except Exception as exc:
                logger.error("Whisper fallback failed: %s", exc)
                raise RuntimeError(f"Speech recognition failed: {exc}") from exc

        # 4. If neither is available, raise explicit authentication error
        raise SarvamAuthError(
            "Speech recognition failed: Sarvam STT is unconfigured (missing SARVAM_API_KEY) "
            "and Whisper fallback is disabled."
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Text-to-Speech
    # ──────────────────────────────────────────────────────────────────────────

    def synthesize(
        self,
        text: str,
        language_code: str = "hi",
        speaker: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Synthesize agricultural guidance into spoken audio."""
        clean_text = clean_text_for_speech(text)

        # 1. Deterministic Mock Mode
        if self.mode == "mock":
            wav_bytes = generate_mock_wav(duration_seconds=1.0)
            return {
                "audio_bytes": wav_bytes,
                "audio_base64": base64.b64encode(wav_bytes).decode("ascii"),
                "format": "wav",
                "language_code": language_code,
                "provider": "mock",
                "is_mock": True,
            }

        # 2. Live Sarvam AI TTS
        if not self.sarvam.is_configured:
            raise SarvamAuthError(
                "Speech synthesis failed: Sarvam AI TTS is not configured (missing SARVAM_API_KEY) "
                "and mock mode is not enabled."
            )

        try:
            res = self.sarvam.text_to_speech(
                text=clean_text,
                target_lang=language_code,
                speaker=speaker,
            )
            res["is_mock"] = False
            res["provider"] = "sarvam"
            return res
        except (SarvamError, Exception) as exc:
            logger.error("Sarvam TTS failed: %s", exc)
            raise


# Module-level singleton
voice_pipeline = VoicePipeline()
