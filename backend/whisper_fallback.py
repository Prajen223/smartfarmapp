"""Whisper STT fallback module for Smart Farming Assistant.

Used ONLY as a configurable fallback when Sarvam AI STT does not support
the language, experiences an API failure, or times out.
"""

from __future__ import annotations

import io
import logging
import os
import tempfile
import wave
from typing import Optional, Dict, Any
import numpy as np

logger = logging.getLogger(__name__)

# Module-level lazy pipeline
_whisper_pipeline: Optional[Any] = None


def is_whisper_enabled() -> bool:
    """Check if Whisper fallback is enabled in environment."""
    return os.getenv("ENABLE_WHISPER_FALLBACK", "true").strip().lower() in ("true", "1", "yes")


def get_whisper_pipeline():
    """Lazily load Hugging Face Whisper ASR pipeline."""
    global _whisper_pipeline
    if _whisper_pipeline is None:
        model_name = os.getenv("WHISPER_MODEL_NAME", "openai/whisper-tiny")
        try:
            from transformers import pipeline
            logger.info("Initializing Whisper fallback pipeline: %s", model_name)
            _whisper_pipeline = pipeline(
                "automatic-speech-recognition",
                model=model_name,
            )
        except Exception as exc:
            logger.warning("Could not initialize Whisper pipeline (%s).", exc)
            _whisper_pipeline = False
    return _whisper_pipeline if _whisper_pipeline is not False else None


class WhisperFallbackEngine:
    """Provides speech-to-text transcription as a secondary fallback."""

    def __init__(self, model_name: Optional[str] = None) -> None:
        self.model_name = model_name or os.getenv("WHISPER_MODEL_NAME", "openai/whisper-tiny")

    def transcribe(
        self,
        audio_bytes: bytes,
        filename: str = "audio.wav",
        language_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Transcribe audio using Whisper model.

        Decodes WAV audio in-memory to avoid requiring ffmpeg.exe on Windows.
        """
        if not audio_bytes:
            raise ValueError("Audio data cannot be empty")

        if not is_whisper_enabled():
            raise RuntimeError("Whisper fallback is disabled via ENABLE_WHISPER_FALLBACK=false")

        asr = get_whisper_pipeline()
        if asr is not None:
            try:
                # Direct in-memory WAV decoding via standard library wave module (no ffmpeg needed)
                with io.BytesIO(audio_bytes) as bio:
                    with wave.open(bio, "rb") as wf:
                        framerate = wf.getframerate()
                        num_frames = wf.getnframes()
                        channels = wf.getnchannels()
                        sampwidth = wf.getsampwidth()
                        raw_data = wf.readframes(num_frames)

                        if sampwidth == 2:
                            arr = np.frombuffer(raw_data, dtype=np.int16).astype(np.float32) / 32768.0
                        else:
                            arr = np.frombuffer(raw_data, dtype=np.int8).astype(np.float32) / 128.0

                        # If stereo, average channels to mono
                        if channels > 1:
                            arr = arr.reshape(-1, channels).mean(axis=1)

                        generate_kwargs = {}
                        if language_code:
                            generate_kwargs["language"] = language_code

                        # Feed raw numpy array to pipeline (bypasses ffmpeg requirement)
                        result = asr({"raw": arr, "sampling_rate": framerate}, generate_kwargs=generate_kwargs)
                        transcript = result.get("text", "").strip()
                        return {
                            "transcript": transcript,
                            "language_code": language_code or "en",
                            "provider": "whisper_fallback",
                            "is_mock": False,
                        }
            except Exception as exc:
                logger.warning("Whisper STT inference error: %s", exc)
                if os.getenv("VOICE_MODE", "sarvam").strip().lower() == "mock":
                    return {
                        "transcript": "Mock Whisper transcription: farmer question received.",
                        "language_code": language_code or "en",
                        "provider": "mock",
                        "is_mock": True,
                    }
                raise RuntimeError(f"Whisper STT processing failed: {exc}") from exc

        # If pipeline could not be loaded:
        if os.getenv("VOICE_MODE", "sarvam").strip().lower() == "mock":
            return {
                "transcript": "Mock Whisper transcription: farmer question received.",
                "language_code": language_code or "en",
                "provider": "mock",
                "is_mock": True,
            }
        raise RuntimeError("Whisper ASR pipeline could not be loaded and mock mode is not enabled.")


# Singleton fallback engine
whisper_fallback = WhisperFallbackEngine()
