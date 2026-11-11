"""Translation service for Smart Farming Assistant.

Architecture
------------
The canonical processing pipeline is:

    user_text (any language)
        │
        ▼
    translate_to_canonical(text, src_lang) ─► canonical_text (English)
        │
        ▼
    [intent classification + KB lookup in English]
        │
        ▼
    translate_from_canonical(answer, tgt_lang) ──► answer_in_user_language
        │
        ▼
    returned to farmer with translation_note

Special fast-paths (no translation called):
  • src_lang == "en"  → canonical_text == user_text         (native EN)
  • src_lang == "ta"  → KB answers natively in Tamil, no translation needed

Modes:
  • "sarvam": Live Sarvam AI translation using Mayura model for Hindi, Kannada, etc.
  • "mock": Deterministic local passthrough with transparent disclaimer notes.
  • "stub": SarvamTranslatorStub raising NotImplementedError (for explicit stub testing).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Optional

from sarvam_client import SarvamClient, SarvamError, SarvamAuthError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Supported language codes and their display names
# ---------------------------------------------------------------------------

SUPPORTED_LANGUAGES: dict[str, str] = {
    "en": "English",
    "hi": "Hindi",
    "kn": "Kannada",
    "ta": "Tamil",
    "te": "Telugu",
    "ml": "Malayalam",
    "pa": "Punjabi",
    "bn": "Bengali",
    "mr": "Marathi",
    "gu": "Gujarati",
    "or": "Odia",
}

# Languages that have native KB answer paths (no translation step needed)
NATIVE_KB_LANGUAGES: frozenset[str] = frozenset({"en", "ta"})

CANONICAL_LANGUAGE = "en"  # All non-native queries are normalized to English first


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class TranslationResult:
    """Result of a single translate() call."""
    original_text: str
    translated_text: str
    source_language: str
    target_language: str
    is_mock: bool
    error: Optional[str] = None
    # When True, translated_text != original_text or real translation was performed successfully
    translation_performed: bool = field(init=False)

    def __post_init__(self) -> None:
        self.translation_performed = (not self.is_mock) and (self.error is None)


@dataclass
class PipelineResult:
    """Full round-trip pipeline result for /ask."""
    canonical_text: str       # text used for intent classification & KB lookup
    answer_in_user_lang: str  # final answer sent to farmer
    source_language: str      # detected language code of the input
    translation_note: str     # human-readable status, always present
    is_mock: bool             # True = no real translation happened
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Mock translator
# ---------------------------------------------------------------------------

class MockTranslator:
    """Passes text through unchanged and marks every result as is_mock=True."""

    IS_MOCK = True

    def translate(
        self,
        text: str,
        source_language: str,
        target_language: str,
    ) -> TranslationResult:
        """Return text unchanged without making external calls."""
        return TranslationResult(
            original_text=text,
            translated_text=text,
            source_language=source_language,
            target_language=target_language,
            is_mock=True,
        )


# ---------------------------------------------------------------------------
# Sarvam translator stub (preserves backwards-compatibility for existing tests)
# ---------------------------------------------------------------------------

class SarvamTranslatorStub:
    """Placeholder stub retained for explicit unit testing."""

    IS_MOCK = False

    def translate(
        self,
        text: str,
        source_language: str,
        target_language: str,
    ) -> TranslationResult:
        raise NotImplementedError(
            "SarvamTranslatorStub: real translation integration has not been "
            "enabled yet. Set TRANSLATION_MODE=mock or implement Sarvam client "
            "and obtain explicit approval before activating live API calls."
        )


# ---------------------------------------------------------------------------
# Real Sarvam AI Translator
# ---------------------------------------------------------------------------

class SarvamTranslator:
    """Production translator integrating Sarvam AI's Mayura model."""

    IS_MOCK = False

    def __init__(self, client: Optional[SarvamClient] = None) -> None:
        self.client = client or SarvamClient()

    def translate(
        self,
        text: str,
        source_language: str,
        target_language: str,
    ) -> TranslationResult:
        """Translate text using Sarvam AI API with safe fallback on failure."""
        if not text.strip():
            return TranslationResult(
                original_text=text,
                translated_text=text,
                source_language=source_language,
                target_language=target_language,
                is_mock=False,
            )

        try:
            translated = self.client.translate(
                text=text,
                source_lang=source_language,
                target_lang=target_language,
            )
            return TranslationResult(
                original_text=text,
                translated_text=translated or text,
                source_language=source_language,
                target_language=target_language,
                is_mock=False,
            )
        except SarvamError as exc:
            logger.warning(
                "Sarvam translation failed for %s -> %s: %s. Falling back to original text.",
                source_language, target_language, exc,
            )
            # Record explicit error without pretending this was an intended mock run
            return TranslationResult(
                original_text=text,
                translated_text=text,
                source_language=source_language,
                target_language=target_language,
                is_mock=False,
                error=str(exc),
            )


# ---------------------------------------------------------------------------
# Factory: choose translator based on environment or argument
# ---------------------------------------------------------------------------

def _build_translator(mode: Optional[str] = None) -> MockTranslator | SarvamTranslatorStub | SarvamTranslator:
    """Select translator from mode argument or environment."""
    if mode is not None:
        selected_mode = mode.strip().lower()
    elif os.getenv("USE_MOCK_AI", "").lower() == "true":
        selected_mode = "mock"
    else:
        selected_mode = os.getenv("TRANSLATION_MODE", "mock").strip().lower()

    if selected_mode == "sarvam":
        api_key = os.getenv("SARVAM_API_KEY", "").strip()
        if api_key and not api_key.startswith("your_"):
            return SarvamTranslator()
        return MockTranslator()

    if selected_mode == "stub":
        return SarvamTranslatorStub()

    return MockTranslator()


# ---------------------------------------------------------------------------
# Public translation service
# ---------------------------------------------------------------------------

class TranslationService:
    """Canonical-language translation pipeline for the Smart Farming Assistant."""

    def __init__(self, mode: Optional[str] = None) -> None:
        self._mode = mode
        self._translator = _build_translator(mode)

    @property
    def is_mock(self) -> bool:
        return getattr(self._translator, "IS_MOCK", True)

    def translate_to_canonical(
        self,
        text: str,
        source_language: str,
    ) -> TranslationResult:
        """Translate user input to the canonical language (English)."""
        if source_language == CANONICAL_LANGUAGE:
            return TranslationResult(
                original_text=text,
                translated_text=text,
                source_language=source_language,
                target_language=CANONICAL_LANGUAGE,
                is_mock=False,
            )
        return self._translator.translate(
            text=text,
            source_language=source_language,
            target_language=CANONICAL_LANGUAGE,
        )

    def translate_from_canonical(
        self,
        text: str,
        target_language: str,
    ) -> TranslationResult:
        """Translate an English KB answer into the farmer's language."""
        if target_language == CANONICAL_LANGUAGE:
            return TranslationResult(
                original_text=text,
                translated_text=text,
                source_language=CANONICAL_LANGUAGE,
                target_language=target_language,
                is_mock=False,
            )
        return self._translator.translate(
            text=text,
            source_language=CANONICAL_LANGUAGE,
            target_language=target_language,
        )

    def run_pipeline(
        self,
        user_text: str,
        source_lang: str,
        kb_answer: str,
    ) -> PipelineResult:
        """Run the full canonical-language round-trip for non-native languages.

        For native paths (EN, TA) this is a no-op: kb_answer is returned as-is
        and translation_note says "native_path".

        For Hindi, Kannada, and other non-native languages:
        Translates input -> English for analysis, and translates English answer -> user language.
        """
        # ── Fast path: native language, no translation needed ────────────────
        if source_lang in NATIVE_KB_LANGUAGES:
            return PipelineResult(
                canonical_text=user_text,
                answer_in_user_lang=kb_answer,
                source_language=source_lang,
                translation_note="native_path",
                is_mock=False,
            )

        # ── Non-native: translate input → canonical ──────────────────────────
        input_result = self.translate_to_canonical(user_text, source_lang)

        # ── Translate canonical answer → user language ───────────────────────
        answer_result = self.translate_from_canonical(kb_answer, source_lang)

        # ── Build translation_note ──────────────────────────────────────────
        lang_name = SUPPORTED_LANGUAGES.get(source_lang, source_lang)
        error_msg = input_result.error or answer_result.error

        if error_msg:
            translation_note = (
                f"translation_failed: Sarvam AI API error ({error_msg}). "
                f"Response provided in English as safe fallback."
            )
            return PipelineResult(
                canonical_text=input_result.translated_text,
                answer_in_user_lang=kb_answer,
                source_language=source_lang,
                translation_note=translation_note,
                is_mock=False,
                error=error_msg,
            )

        is_mock_run = self.is_mock or input_result.is_mock or answer_result.is_mock

        if is_mock_run:
            translation_note = (
                f"mock_translation_not_active: input was {lang_name}, "
                f"answer is in English (translation to {lang_name} not yet enabled). "
                f"Real translation will be activated when Sarvam AI integration is approved."
            )
        else:
            translation_note = f"translated: {source_lang} → en → {source_lang} via Sarvam AI"

        return PipelineResult(
            canonical_text=input_result.translated_text,
            answer_in_user_lang=answer_result.translated_text,
            source_language=source_lang,
            translation_note=translation_note,
            is_mock=is_mock_run,
        )
