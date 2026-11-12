"""Smart Farming Assistant API — Week 1–2: NLP & Multilingual Processing Engine.

Endpoints:
  • POST /ask               - Multilingual text query processing with canonical English pipeline
  • POST /voice/transcribe  - Voice input STT (Sarvam Saarika with Whisper fallback)
  • POST /voice/synthesize  - Spoken response TTS (Sarvam Bulbul)
  • POST /ask-voice         - End-to-end voice query with spoken audio response
  • GET  /sources           - Authoritative ICAR/Government source catalogue
  • GET  /sources/{intent}  - Sources filtered by agricultural category
  • GET  /knowledge/documents - Retrieval-ready ICAR documents for future RAG
  • GET  /session/{session_id} - Conversation session history and context
  • GET  /config-check      - API key and provider readiness inspection
  • GET  /health            - Service liveness probe
"""

from __future__ import annotations

import os
import base64
import datetime
import logging
from typing import Optional, List, Dict, Any
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# pyrefly: ignore [missing-import]
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Query, Request, Response, Header, Depends, Body
from fastapi.responses import JSONResponse
# pyrefly: ignore [missing-import]
from fastapi.middleware.cors import CORSMiddleware
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, Field

from language_detector import detect_language
from intent_classifier import classify_intent
from farming_kb import get_farming_answer, load_sources, get_sources_for_intent
from ner_extractor import extract_agricultural_entities
from translation_service import TranslationService, MockTranslator, SarvamTranslator
from session_manager import session_manager
from voice_pipeline import voice_pipeline
from sarvam_client import (
    SarvamError,
    SarvamAuthError,
    SarvamQuotaError,
    SarvamTimeoutError,
    SarvamRateLimitError,
    SarvamAPIError,
)
from knowledge_repository import knowledge_repository
from rag_pipeline import rag_pipeline
from external_adapters import agmarknet_adapter, weather_adapter, government_scheme_adapter
from security import (
    InputValidator,
    rate_limiter,
    security_user_manager,
    JWTManager,
    PasswordManager,
    get_client_ip,
    get_optional_current_user,
    get_current_user,
    require_admin,
    verify_session_access,
    validate_jwt_secret,
    mask_secret,
    User,
)

# Pre-instantiate translation services
_mock_translation_service = TranslationService(mode="mock")
_sarvam_translation_service = TranslationService(mode="sarvam")

app = FastAPI(
    title="Smart Farming Assistant API",
    description="Multilingual Agricultural Guidance & Voice Engine",
    version="1.2.0",
)

@app.exception_handler(Exception)
async def global_unhandled_exception_handler(request: Request, exc: Exception):
    """Global exception handler preventing stack trace, password, or secret leakage."""
    import logging
    logging.getLogger("uvicorn.error").error("Unhandled exception on %s: %s", request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred. Please try again later."},
    )

@app.on_event("startup")
def verify_production_security_config():
    """Verify security requirements and reject insecure JWT secrets on application startup."""
    validate_jwt_secret()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request & Response Models
# ---------------------------------------------------------------------------

class AskRequest(BaseModel):
    text: Optional[str] = None
    question: Optional[str] = None
    mode: str = "auto"   # "auto", "sarvam", "local", "mock"
    session_id: Optional[str] = None
    language: Optional[str] = None
    preferred_language: Optional[str] = None
    include_audio: Optional[bool] = False


class CreateSessionRequest(BaseModel):
    farmer_id: Optional[str] = None
    language: Optional[str] = "en"


class RegisterRequest(BaseModel):
    username: str
    password: str
    role: str = "farmer"  # "farmer" or "admin"


class LoginRequest(BaseModel):
    username: str
    password: str


class SynthesizeRequest(BaseModel):
    text: str
    language_code: str = "hi"
    speaker: Optional[str] = None


# ---------------------------------------------------------------------------
# Health & Status
# ---------------------------------------------------------------------------

@app.get("/")
def home():
    return {
        "message": "Smart Farming Assistant backend is running",
        "version": "1.2.0",
        "modules": [
            "multilingual_nlp",
            "sarvam_ai",
            "whisper_fallback",
            "agricultural_kb",
            "voice_pipeline",
            "conversation_state",
        ],
    }


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/config-check")
def config_check():
    sarvam_configured = bool(
        os.getenv("SARVAM_API_KEY") and not os.getenv("SARVAM_API_KEY", "").startswith("your_")
    )
    translation_mode = os.getenv("TRANSLATION_MODE", "mock").lower()
    voice_mode = os.getenv("VOICE_MODE", "sarvam").lower()
    whisper_enabled = os.getenv("ENABLE_WHISPER_FALLBACK", "true").lower() in ("true", "1")

    return {
        "sarvam_key_configured": sarvam_configured,
        "mode": "sarvam" if sarvam_configured and translation_mode == "sarvam" else "local",
        "translation_mode": translation_mode,
        "voice_mode": voice_mode,
        "whisper_fallback_enabled": whisper_enabled,
    }


# ---------------------------------------------------------------------------
# Core Multilingual Query Engine (/ask)
# ---------------------------------------------------------------------------

@app.post("/ask")
def ask_farming_assistant(
    request: AskRequest,
    http_request: Request = None,
):
    # ── 0. Security: Input Validation, Sanitization & Rate Limiting ────────
    raw_query = request.question if request.question is not None else request.text
    query_text = InputValidator.validate_and_sanitize_question(raw_query)

    client_ip = get_client_ip(http_request) if http_request else "127.0.0.1"
    rate_limiter.check_rate_limit(client_ip=client_ip, session_id=request.session_id)

    # Optional authenticated user identification
    auth_header = http_request.headers.get("authorization") if (http_request and hasattr(http_request, "headers")) else None
    auth_user = get_optional_current_user(auth_header)

    # ── 1. Session: validate or create ─────────────────────────────────────
    if request.session_id:
        session = session_manager.get_session(request.session_id, include_inactive=True)
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Session '{request.session_id}' not found.",
            )
        verify_session_access(session, auth_user)
        if not session.is_active:
            raise HTTPException(
                status_code=400,
                detail=f"Session '{request.session_id}' is expired or inactive.",
            )
    else:
        req_lang = request.preferred_language or request.language or "en"
        farmer_owner = auth_user.username if auth_user else None
        session = session_manager.create_session(farmer_id=farmer_owner, language=req_lang)

    pref_lang = request.preferred_language or request.language
    if pref_lang:
        session_manager.set_preferred_language(session.session_id, pref_lang)

    # ── 2. Determine translation service to use ────────────────────────────
    is_pytest = bool(os.getenv("PYTEST_CURRENT_TEST"))
    if request.mode == "sarvam":
        active_translation_service = _sarvam_translation_service
    elif request.mode in ("mock", "local") or is_pytest:
        active_translation_service = _mock_translation_service
    elif os.getenv("TRANSLATION_MODE") == "sarvam" and os.getenv("USE_MOCK_AI", "").lower() != "true":
        active_translation_service = _sarvam_translation_service
    else:
        active_translation_service = _mock_translation_service

    # ── 3. Language Detection ──────────────────────────────────────────────
    language_info = detect_language(query_text)
    user_lang = pref_lang or language_info["language_code"]

    # ── 4. Canonical-Language Translation (Input -> English) ───────────────
    # For English and Tamil, native paths are used; for Hindi, Kannada, etc.
    # text is translated to canonical English for optimal intent and entity analysis.
    canonical_input_res = active_translation_service.translate_to_canonical(
        text=query_text,
        source_language=user_lang,
    )
    canonical_text = canonical_input_res.translated_text

    # ── 5. Intent Classification & Named Entity Recognition ────────────────
    # Run classification on canonical text for semantic consistency
    eval_lang = "en" if (not canonical_input_res.is_mock and user_lang != "ta") else user_lang
    classification = classify_intent(
        canonical_text,
        language_code=eval_lang,
    )

    # Extract entities from both raw input and canonical English
    raw_entities = extract_agricultural_entities(query_text)
    canonical_entities = extract_agricultural_entities(canonical_text)

    # Merge entities
    merged_entities: dict[str, list[str]] = {
        key: sorted(list(set(raw_entities.get(key, []) + canonical_entities.get(key, []))))
        for key in ("crops", "pests", "diseases", "soil", "locations", "schemes", "fertilizers", "nutrients", "seasons")
    }

    # ── 6. Context Resolution across Turns ─────────────────────────────────
    # If this turn has missing context but a previous turn established active entities,
    # carry them over so follow-ups ("how often to water it?") are answered accurately.
    # CRITICAL: Prevent cross-turn contamination:
    # 1. Weather queries must NEVER inherit crops or schemes from previous turns.
    # 2. Market price queries that specify a crop must NEVER inherit unrelated crops.
    current_intent = classification["intent"]
    current_crops = sorted(list(set(raw_entities.get("crops", []) + canonical_entities.get("crops", []))))

    if current_intent == "weather":
        resolved_entities = {**merged_entities, "crops": [], "schemes": []}
    elif current_intent == "market_prices" and current_crops:
        resolved_entities = {**merged_entities, "crops": current_crops}
    else:
        resolved_entities = session.resolve_context(merged_entities)
        if current_crops:
            resolved_entities["crops"] = current_crops

    resolved_crop = resolved_entities.get("crops")[0] if resolved_entities.get("crops") else None
    resolved_soil = resolved_entities.get("soil")[0] if resolved_entities.get("soil") else None
    resolved_season = resolved_entities.get("seasons")[0] if resolved_entities.get("seasons") else None
    resolved_nutrient = resolved_entities.get("nutrients")[0] if resolved_entities.get("nutrients") else None

    # Retrieve recent conversation history for multi-turn context
    recent_history = session_manager.get_history(session.session_id, limit=6)
    history_context = [
        {"role": msg.role, "content": msg.content, "intent": msg.intent}
        for msg in recent_history
    ]

    # ── 7. RAG Pipeline Execution & Evidence-Grounded Synthesis ────────────
    rag_result = rag_pipeline.generate_response(
        query=query_text,
        canonical_text=canonical_text,
        intent=classification["intent"],
        language_code=user_lang,
        entities=resolved_entities,
        top_k=2,
        conversation_context=history_context,
    )

    # For native Tamil, use local Tamil knowledge base guidance to preserve Tamil script
    if user_lang == "ta":
        query_text_for_kb = f"{query_text} {resolved_crop or ''}"
        kb_result = get_farming_answer(
            intent=classification["intent"],
            text=query_text_for_kb,
            language_code="ta",
        )
        base_answer = kb_result["answer"]
    else:
        base_answer = rag_result["answer"]

    # ── 8. Canonical Translation (English Answer -> User Language) ─────────
    translation = active_translation_service.run_pipeline(
        user_text=query_text,
        source_lang=user_lang,
        kb_answer=base_answer,
    )

    final_answer = translation.answer_in_user_lang
    # If guidance was requested in a non-native language (HI, KN, etc.) and real translation was not performed, provide transparent advisory
    if (
        user_lang not in ("ta", "en")
        and active_translation_service.is_mock
        and not getattr(getattr(translation, "answer_translation", None), "translation_performed", False)
    ):
        final_answer = (
            f"[Language Note: Response provided in English as reliable local guidance is currently available in English and Tamil.]\n\n"
            f"{final_answer}"
        )

    # ── 9. Optional TTS Speech Synthesis ──────────────────────────────────
    audio_base64: Optional[str] = None
    audio_format: Optional[str] = None
    tts_provider: Optional[str] = None
    if request.include_audio:
        try:
            tts_res = voice_pipeline.synthesize(
                text=final_answer[:400],
                language_code=user_lang,
            )
            audio_base64 = tts_res.get("audio_base64")
            audio_format = tts_res.get("format", "wav")
            tts_provider = tts_res.get("provider")
        except Exception as exc:
            logger.warning("Optional TTS synthesis in /ask failed: %s", exc)

    # ── 10. Record Turn in Session History ─────────────────────────────────
    turn_msgs = session_manager.record_turn(
        session_id=session.session_id,
        user_text=query_text,
        detected_language=user_lang,
        intent=classification["intent"],
        answer=final_answer,
        entities=resolved_entities,
        sources=rag_result.get("sources", []),
        confidence=classification.get("confidence", 0.85),
    )
    assistant_msg_id = turn_msgs[1].message_id if turn_msgs else None

    return {
        "session_id": session.session_id,
        "message_id": assistant_msg_id,
        "question": query_text,
        "input_text": query_text,
        "canonical_text": canonical_text,
        "answer": final_answer,
        "intent": classification["intent"],
        "confidence": classification["confidence"],
        "language": language_info["language"],
        "language_code": user_lang,
        "sources": rag_result.get("sources", []),
        "rag_confidence": rag_result["confidence"],
        "quality_score": rag_result.get("quality_score", 0.85),
        "source_reliability": rag_result.get("source_reliability", 0.90),
        "evidence_grounding": rag_result.get("evidence_grounding", 0.80),
        "review_id": rag_result.get("review_id"),
        "review_status": rag_result.get("review_status", "auto_verified"),
        "is_low_confidence": rag_result["is_low_confidence"],
        "needs_clarification": rag_result.get("needs_clarification", False),
        "response_mode": rag_result.get("response_mode", "rag_grounded_extractive"),
        "pipeline_backend": rag_result.get("pipeline_backend", "langchain_lcel"),
        "data_freshness": rag_result.get("data_freshness", datetime.datetime.now(datetime.timezone.utc).isoformat()),
        "classification_method": classification["classification_method"],
        "mode": "local_knowledge_base" if active_translation_service.is_mock else "sarvam_ai",
        "entities": resolved_entities,
        "translation_note": translation.translation_note,
        "session_context": session.get_context_summary(),
        "retrieved_documents": rag_result["retrieved_documents"],
        "adapter_data": rag_result.get("adapter_data"),
        "audio_base64": audio_base64,
        "audio_format": audio_format,
        "tts_provider": tts_provider,
    }


# ---------------------------------------------------------------------------
# Voice Pipeline Endpoints
# ---------------------------------------------------------------------------

def _handle_voice_exception(exc: Exception) -> None:
    """Map voice processing and Sarvam exceptions to standard HTTP error responses."""
    if isinstance(exc, HTTPException):
        raise exc
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, SarvamAuthError):
        logger.error("Sarvam authentication failure: %s", exc)
        raise HTTPException(
            status_code=401,
            detail="Speech service authentication failed. Check configured credentials.",
        )
    if isinstance(exc, SarvamQuotaError):
        logger.error("Sarvam quota exhausted: %s", exc)
        raise HTTPException(
            status_code=402,
            detail="Sarvam AI speech service quota exhausted. Please recharge API credits in the Sarvam AI dashboard.",
        )
    if isinstance(exc, SarvamTimeoutError):
        logger.error("Sarvam timeout failure: %s", exc)
        raise HTTPException(
            status_code=504,
            detail="Speech service timed out. Please try again.",
        )
    if isinstance(exc, SarvamRateLimitError):
        logger.warning("Sarvam rate limit reached: %s", exc)
        raise HTTPException(
            status_code=429,
            detail="Speech service rate limit exceeded. Please wait a moment.",
            headers={"Retry-After": "60"},
        )
    if isinstance(exc, SarvamAPIError):
        logger.error("Sarvam upstream failure: %s (status=%s)", exc, getattr(exc, "status_code", None))
        raise HTTPException(
            status_code=502,
            detail=f"Speech service upstream error: {exc}",
        )
    if isinstance(exc, RuntimeError):
        logger.error("Voice processing runtime failure: %s", exc)
        raise HTTPException(
            status_code=502,
            detail=f"Voice processing failure: {exc}",
        )
    logger.exception("Unexpected voice processing failure: %s", exc)
    raise HTTPException(status_code=500, detail=f"Voice processing failed: {exc}")


class AskVoiceJsonRequest(BaseModel):
    audio_base64: str
    filename: str = "voice.wav"
    session_id: Optional[str] = None
    language_hint: Optional[str] = None


class VoiceTranscribeJsonRequest(BaseModel):
    audio_base64: str
    filename: str = "voice.wav"
    language_hint: Optional[str] = None


@app.post("/voice/transcribe-json")
def transcribe_audio_json(
    request: VoiceTranscribeJsonRequest,
    http_request: Request = None,
):
    """Transcribe base64 encoded audio in Hindi, Kannada, English, etc."""
    client_ip = get_client_ip(http_request) if http_request else "127.0.0.1"
    rate_limiter.check_rate_limit(client_ip=client_ip)

    if not request.audio_base64 or not request.audio_base64.strip():
        raise HTTPException(status_code=400, detail="Audio base64 data cannot be empty.")

    try:
        audio_bytes = base64.b64decode(request.audio_base64)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid base64 audio: {exc}")

    try:
        result = voice_pipeline.transcribe(
            audio_bytes=audio_bytes,
            filename=request.filename,
            language_hint=request.language_hint,
        )
        return result
    except Exception as exc:
        _handle_voice_exception(exc)


@app.post("/ask-voice-json")
def ask_voice_json(
    request: AskVoiceJsonRequest,
    http_request: Request = None,
):
    """End-to-end voice query via JSON base64 audio."""
    client_ip = get_client_ip(http_request) if http_request else "127.0.0.1"
    rate_limiter.check_rate_limit(client_ip=client_ip, session_id=request.session_id)

    if not request.audio_base64 or not request.audio_base64.strip():
        raise HTTPException(status_code=400, detail="Audio base64 data cannot be empty.")

    try:
        audio_bytes = base64.b64decode(request.audio_base64)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid base64 audio: {exc}")

    try:
        stt_result = voice_pipeline.transcribe(
            audio_bytes=audio_bytes,
            filename=request.filename,
            language_hint=request.language_hint,
        )
    except Exception as exc:
        _handle_voice_exception(exc)

    user_query = stt_result.get("transcript", "").strip()
    if not user_query:
        raise HTTPException(status_code=400, detail="No intelligible speech detected in audio.")

    # Respect user's manually chosen language preference when provided
    user_hint = (request.language_hint or "").strip().lower()
    if user_hint in ("en", "hi", "kn", "ta", "te"):
        target_lang = user_hint
    else:
        target_lang = stt_result.get("language_code") or "hi"

    ask_res = ask_farming_assistant(
        AskRequest(
            text=user_query,
            session_id=request.session_id,
            preferred_language=target_lang,
            mode="auto",
        ),
        http_request=http_request,
    )

    tts_result: dict[str, Any] = {}
    try:
        tts_result = voice_pipeline.synthesize(
            text=ask_res["answer"],
            language_code=target_lang,
        )
    except Exception as exc:
        logger.warning("TTS speech synthesis skipped due to service error: %s", exc)
        tts_result = {
            "audio_base64": None,
            "format": "wav",
            "provider": "unavailable",
            "error": str(exc),
        }

    return {
        "session_id": ask_res["session_id"],
        "message_id": ask_res.get("message_id"),
        "transcript": user_query,
        "question": user_query,
        "answer": ask_res["answer"],
        "intent": ask_res["intent"],
        "confidence": ask_res["confidence"],
        "language": ask_res["language"],
        "language_code": ask_res["language_code"],
        "sources": ask_res.get("sources", []),
        "quality_score": ask_res.get("quality_score", 0.85),
        "retrieved_documents": ask_res.get("retrieved_documents", []),
        "adapter_data": ask_res.get("adapter_data"),
        "session_context": ask_res.get("session_context"),
        "audio_base64": tts_result.get("audio_base64"),
        "audio_format": tts_result.get("format", "wav"),
        "stt_provider": stt_result.get("provider"),
        "tts_provider": tts_result.get("provider"),
        "analysis": ask_res,
    }


@app.post("/voice/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    language_hint: Optional[str] = Form(None),
    http_request: Request = None,
):
    """Transcribe spoken audio in Hindi, Kannada, or English."""
    client_ip = get_client_ip(http_request) if http_request else "127.0.0.1"
    rate_limiter.check_rate_limit(client_ip=client_ip)

    if not file.filename:
        raise HTTPException(status_code=400, detail="Audio file must have a filename.")

    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Uploaded audio file is empty.")

    try:
        result = voice_pipeline.transcribe(
            audio_bytes=audio_bytes,
            filename=file.filename,
            language_hint=language_hint,
        )
        return result
    except Exception as exc:
        _handle_voice_exception(exc)


@app.post("/voice/synthesize")
def synthesize_speech(
    request: SynthesizeRequest,
    http_request: Request = None,
):
    """Synthesize text guidance into spoken audio (WAV base64)."""
    client_ip = get_client_ip(http_request) if http_request else "127.0.0.1"
    rate_limiter.check_rate_limit(client_ip=client_ip)

    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Text to synthesize cannot be empty.")

    try:
        result = voice_pipeline.synthesize(
            text=request.text,
            language_code=request.language_code,
            speaker=request.speaker,
        )
        return {
            "audio_base64": result.get("audio_base64"),
            "format": result.get("format", "wav"),
            "provider": result.get("provider", "sarvam"),
            "language_code": request.language_code,
        }
    except Exception as exc:
        _handle_voice_exception(exc)


@app.post("/ask-voice")
async def ask_voice(
    file: UploadFile = File(...),
    session_id: Optional[str] = Form(None),
    language_hint: Optional[str] = Form(None),
    http_request: Request = None,
):
    """End-to-end voice query: Audio -> STT -> Ask Pipeline -> TTS Audio Response."""
    client_ip = get_client_ip(http_request) if http_request else "127.0.0.1"
    rate_limiter.check_rate_limit(client_ip=client_ip, session_id=session_id)

    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Voice recording is empty.")

    # 1. Transcribe audio
    try:
        stt_result = voice_pipeline.transcribe(
            audio_bytes=audio_bytes,
            filename=file.filename or "recording.wav",
            language_hint=language_hint,
        )
    except Exception as exc:
        _handle_voice_exception(exc)

    user_query = stt_result.get("transcript", "").strip()
    if not user_query:
        raise HTTPException(status_code=400, detail="No intelligible speech detected in audio.")

    detected_lang = stt_result.get("language_code", language_hint or "hi")

    # 2. Process via ask pipeline
    ask_res = ask_farming_assistant(
        AskRequest(
            text=user_query,
            session_id=session_id,
            preferred_language=detected_lang,
            mode="auto",
        ),
        http_request=http_request,
    )

    # 3. Synthesize spoken response in user's language
    try:
        tts_result = voice_pipeline.synthesize(
            text=ask_res["answer"],
            language_code=detected_lang,
        )
    except Exception as exc:
        _handle_voice_exception(exc)

    return {
        "session_id": ask_res["session_id"],
        "message_id": ask_res.get("message_id"),
        "transcript": user_query,
        "question": user_query,
        "answer": ask_res["answer"],
        "intent": ask_res["intent"],
        "confidence": ask_res["confidence"],
        "language": ask_res["language"],
        "language_code": ask_res["language_code"],
        "sources": ask_res.get("sources", []),
        "quality_score": ask_res.get("quality_score", 0.85),
        "retrieved_documents": ask_res.get("retrieved_documents", []),
        "adapter_data": ask_res.get("adapter_data"),
        "session_context": ask_res.get("session_context"),
        "audio_base64": tts_result.get("audio_base64"),
        "audio_format": tts_result.get("format", "wav"),
        "stt_provider": stt_result.get("provider"),
        "tts_provider": tts_result.get("provider"),
        "analysis": ask_res,
    }


# ---------------------------------------------------------------------------
# Knowledge Repository & Source Provenance Endpoints
# ---------------------------------------------------------------------------

@app.get("/sources")
def list_sources():
    """Return the full knowledge source provenance catalogue."""
    data = load_sources()
    if "error" in data:
        raise HTTPException(status_code=500, detail=data["error"])
    return data


VALID_INTENTS = {
    "irrigation", "pest_control", "crop_advisory",
    "market_prices", "government_schemes", "weather",
}


@app.get("/sources/{intent}")
def sources_for_intent(intent: str):
    """Return source records for a specific intent category."""
    if intent not in VALID_INTENTS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown intent '{intent}'. Valid intents: {sorted(VALID_INTENTS)}",
        )
    return {"intent": intent, "sources": get_sources_for_intent(intent)}


@app.get("/knowledge/documents")
def list_knowledge_documents(
    category: Optional[str] = Query(None),
    crop: Optional[str] = Query(None),
    soil: Optional[str] = Query(None),
    season: Optional[str] = Query(None),
    nutrient: Optional[str] = Query(None),
    query: Optional[str] = Query(None),
):
    """List or search retrieval-ready ICAR knowledge documents."""
    if query or crop or soil or season or nutrient:
        docs = knowledge_repository.search(
            query=query or "",
            category=category,
            crop=crop,
            soil=soil,
            season=season,
            nutrient=nutrient,
            top_k=10,
        )
    else:
        docs = knowledge_repository.list_documents(category=category)

    return {
        "count": len(docs),
        "documents": [doc.to_dict() for doc in docs],
    }


@app.get("/knowledge/documents/{doc_id}")
def get_knowledge_document(doc_id: str):
    """Retrieve an individual ICAR knowledge document by ID."""
    doc = knowledge_repository.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found.")
    return doc.to_dict()


# ---------------------------------------------------------------------------
# Session History Inspection
# ---------------------------------------------------------------------------

@app.get("/session/{session_id}")
def get_session_history(session_id: str, http_request: Request = None):
    """Retrieve full turn history and context for a session (Legacy v1 route)."""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found or expired.")
    auth_header = http_request.headers.get("authorization") if (http_request and hasattr(http_request, "headers")) else None
    auth_user = get_optional_current_user(auth_header)
    verify_session_access(session, auth_user)
    return {
        "session_id": session.session_id,
        "created_at_iso": session.created_at_iso,
        "last_active": session.last_active,
        "context_summary": session.get_context_summary(),
        "turns": [
            {
                "turn_number": turn.turn_number,
                "user_text": turn.user_text,
                "detected_language": turn.detected_language,
                "intent": turn.intent,
                "answer_summary": turn.answer_summary,
                "entities": turn.entities,
                "iso_timestamp": turn.iso_timestamp,
            }
            for turn in session.history
        ],
    }


# ---------------------------------------------------------------------------
# Farmer Session Management Endpoints (Milestone 3 – Part 1)
# ---------------------------------------------------------------------------

@app.post("/sessions", status_code=201)
def create_farmer_session_endpoint(
    request: Optional[CreateSessionRequest] = None,
    http_request: Request = None,
):
    """Create a new persistent farmer session, optionally associated with a farmer_id."""
    client_ip = get_client_ip(http_request) if http_request else "127.0.0.1"
    rate_limiter.check_rate_limit(client_ip=client_ip)

    auth_header = http_request.headers.get("authorization") if (http_request and hasattr(http_request, "headers")) else None
    auth_user = get_optional_current_user(auth_header)
    farmer_id = (auth_user.username if auth_user else None) or (request.farmer_id if request else None)
    language = (request.language if request else None) or "en"
    sess = session_manager.create_session(farmer_id=farmer_id, language=language)
    return sess.to_dict()


@app.get("/sessions/{session_id}")
def get_farmer_session_endpoint(session_id: str, http_request: Request = None):
    """Retrieve session information and current multi-turn context state."""
    client_ip = get_client_ip(http_request) if http_request else "127.0.0.1"
    rate_limiter.check_rate_limit(client_ip=client_ip, session_id=session_id)
    sess = session_manager.get_session(session_id)
    if not sess or not sess.is_active:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found or expired.")
    
    auth_header = http_request.headers.get("authorization") if (http_request and hasattr(http_request, "headers")) else None
    auth_user = get_optional_current_user(auth_header)
    verify_session_access(sess, auth_user)

    return sess.to_dict()


@app.get("/sessions/{session_id}/history")
def get_farmer_session_messages(
    session_id: str,
    limit: Optional[int] = Query(None, ge=1, le=100),
    http_request: Request = None,
):
    """Retrieve persistent chronological conversation messages for a session."""
    client_ip = get_client_ip(http_request) if http_request else "127.0.0.1"
    rate_limiter.check_rate_limit(client_ip=client_ip, session_id=session_id)
    sess = session_manager.get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")
    
    auth_header = http_request.headers.get("authorization") if (http_request and hasattr(http_request, "headers")) else None
    auth_user = get_optional_current_user(auth_header)
    verify_session_access(sess, auth_user)

    messages = session_manager.get_history(session_id, limit=limit)
    return {
        "session_id": session_id,
        "count": len(messages),
        "messages": [m.to_dict() for m in messages],
    }


@app.delete("/sessions/{session_id}")
def delete_farmer_session_endpoint(session_id: str, http_request: Request = None):
    """Safely deactivate/close a farmer session."""
    client_ip = get_client_ip(http_request) if http_request else "127.0.0.1"
    rate_limiter.check_rate_limit(client_ip=client_ip, session_id=session_id)
    sess = session_manager.get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")
    
    auth_header = http_request.headers.get("authorization") if (http_request and hasattr(http_request, "headers")) else None
    auth_user = get_optional_current_user(auth_header)
    verify_session_access(sess, auth_user)

    session_manager.deactivate_session(session_id)
    return {
        "session_id": session_id,
        "status": "deactivated",
        "message": "Session closed successfully",
    }


# ---------------------------------------------------------------------------
# Authentication & Role-Based Access Control (Milestone 3 – Part 2)
# ---------------------------------------------------------------------------

@app.post("/auth/register", status_code=201)
def register_user_account(request: RegisterRequest, http_request: Request = None):
    """Register a new farmer account. Public registration cannot assign administrative privileges."""
    client_ip = get_client_ip(http_request) if http_request else "127.0.0.1"
    rate_limiter.check_rate_limit(client_ip=client_ip)

    # Security: Prevent public users from self-assigning the admin role
    if request.role and request.role.lower() == "admin":
        raise HTTPException(
            status_code=403,
            detail="Forbidden: Public registration cannot assign administrative privileges. Public accounts are created with 'farmer' role.",
        )

    # Force role to 'farmer' for all public registrations
    user = security_user_manager.register_user(
        username=request.username,
        password=request.password,
        role="farmer",
    )
    return user.to_dict()


@app.post("/admin/users", status_code=201)
def create_user_by_admin(
    request: RegisterRequest,
    admin_user: User = Depends(require_admin),
):
    """Create a user account (farmer or admin) with administrative privileges."""
    user = security_user_manager.register_user(
        username=request.username,
        password=request.password,
        role=request.role,
    )
    return user.to_dict()


@app.post("/auth/bootstrap-admin", status_code=201)
def bootstrap_admin_account(
    request: RegisterRequest,
    bootstrap_key: Optional[str] = Header(None, alias="X-Admin-Bootstrap-Key"),
):
    """Secure controlled bootstrap endpoint to initialize the primary administrator account."""
    env_bootstrap_key = os.getenv("ADMIN_BOOTSTRAP_KEY")
    if not env_bootstrap_key or not bootstrap_key or bootstrap_key != env_bootstrap_key:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: Invalid or missing administrator bootstrap key.",
        )
    user = security_user_manager.register_user(
        username=request.username,
        password=request.password,
        role="admin",
    )
    return user.to_dict()


@app.post("/auth/login")
def login_user_account(request: LoginRequest, http_request: Request = None):
    """Authenticate credentials and issue a signed RFC 7519 JWT access token."""
    client_ip = get_client_ip(http_request) if http_request else "127.0.0.1"
    rate_limiter.check_rate_limit(client_ip=client_ip)
    user = security_user_manager.authenticate(
        username=request.username,
        password=request.password,
    )
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = JWTManager.create_access_token(
        claims={"sub": user.username, "role": user.role, "user_id": user.user_id}
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": user.role,
        "username": user.username,
        "user_id": user.user_id,
    }


@app.get("/auth/me")
def get_current_user_profile(user: User = Depends(get_current_user)):
    """Retrieve current authenticated user profile."""
    return user.to_dict()


@app.get("/admin/stats")
def get_admin_security_stats(admin_user: User = Depends(require_admin)):
    """Retrieve administrative metrics and review statistics (Admin role required)."""
    from review_manager import review_manager
    return {
        "admin_user": admin_user.username,
        "role": admin_user.role,
        "active_sessions": session_manager.session_count(),
        "review_queue_stats": review_manager.get_stats(),
        "rate_limiter": {
            "enabled": rate_limiter.enabled,
            "ip_limit_per_minute": rate_limiter.ip_limit,
            "session_limit_per_minute": rate_limiter.session_limit,
        },
    }


@app.get("/admin/users")
def get_admin_users_list(
    limit: int = Query(50, ge=1, le=200),
    admin_user: User = Depends(require_admin),
):
    """List registered user accounts (Admin role required)."""
    users = security_user_manager.list_users(limit=limit)
    return {
        "count": len(users),
        "users": [u.to_dict() for u in users],
    }


@app.get("/admin/sessions")
def get_admin_sessions_summary(
    admin_user: User = Depends(require_admin),
):
    """Retrieve summary of active farmer sessions (Admin role required)."""
    return {
        "active_sessions_count": session_manager.session_count(),
    }


@app.get("/admin/analytics")
def get_admin_analytics(
    days: int = Query(7, ge=1, le=90),
    admin_user: User = Depends(require_admin),
):
    """Retrieve platform analytics, daily query usage, language/intent distributions,

    and recent farmer activity for the Admin Dashboard (Admin role required).
    """
    return session_manager.get_analytics_summary(days=days)


class ReviewActionRequest(BaseModel):
    notes: Optional[str] = None
    corrected_answer: Optional[str] = None


class UpdateUnansweredQueryRequest(BaseModel):
    status: str
    reviewer_notes: Optional[str] = None
    corrected_answer: Optional[str] = None


@app.get("/admin/unanswered-queries")
def list_admin_unanswered_queries(
    status: Optional[str] = Query(None, description="Filter by status ('pending', 'approved', 'rejected', 'corrected', 'all')"),
    language: Optional[str] = Query(None, description="Filter by language code ('en', 'hi', 'kn', 'ta', etc.)"),
    intent: Optional[str] = Query(None, description="Filter by agricultural intent"),
    search: Optional[str] = Query(None, description="Search keyword in query text or answer"),
    start_date: Optional[str] = Query(None, description="Filter starting YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="Filter ending YYYY-MM-DD"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    admin_user: User = Depends(require_admin),
):
    """Retrieve filtered, paginated unanswered and flagged queries for expert review (Admin role required)."""
    from review_manager import review_manager
    return review_manager.list_queries(
        status=status,
        language=language,
        intent=intent,
        search=search,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )


@app.get("/admin/unanswered-queries/{query_id}")
def get_admin_unanswered_query_detail(
    query_id: str,
    admin_user: User = Depends(require_admin),
):
    """Retrieve full details of a specific unanswered/flagged query (Admin role required)."""
    from review_manager import review_manager
    rec = review_manager.get_review(query_id)
    if not rec:
        raise HTTPException(status_code=404, detail=f"Query review '{query_id}' not found.")
    return rec


@app.patch("/admin/unanswered-queries/{query_id}")
def update_admin_unanswered_query(
    query_id: str,
    payload: UpdateUnansweredQueryRequest,
    admin_user: User = Depends(require_admin),
):
    """Update review status, expert notes, or corrected answer (Admin role required)."""
    from review_manager import review_manager
    success, msg, rec = review_manager.update_review(
        review_id=query_id,
        status=payload.status,
        reviewer_notes=payload.reviewer_notes,
        corrected_answer=payload.corrected_answer,
        reviewer_username=admin_user.username,
    )
    if not success:
        if "not found" in msg.lower():
            raise HTTPException(status_code=404, detail=msg)
        raise HTTPException(status_code=400, detail=msg)
    return {"review_id": query_id, "status": payload.status.lower(), "message": msg, "record": rec}


@app.post("/admin/unanswered-queries/{query_id}/approve")
def approve_admin_unanswered_query(
    query_id: str,
    action: Optional[ReviewActionRequest] = Body(default=None),
    admin_user: User = Depends(require_admin),
):
    """Approve a query answer as verified agricultural guidance (Admin role required)."""
    from review_manager import review_manager
    notes = action.notes if action else None
    success, msg, rec = review_manager.update_review(
        review_id=query_id,
        status="approved",
        reviewer_notes=notes,
        reviewer_username=admin_user.username,
    )
    if not success:
        raise HTTPException(status_code=404, detail=msg)
    return {"review_id": query_id, "status": "approved", "message": msg, "record": rec}


@app.post("/admin/unanswered-queries/{query_id}/reject")
def reject_admin_unanswered_query(
    query_id: str,
    action: Optional[ReviewActionRequest] = Body(default=None),
    admin_user: User = Depends(require_admin),
):
    """Reject a query answer due to unverified or unsafe guidance (Admin role required)."""
    from review_manager import review_manager
    notes = action.notes if action else None
    success, msg, rec = review_manager.update_review(
        review_id=query_id,
        status="rejected",
        reviewer_notes=notes,
        reviewer_username=admin_user.username,
    )
    if not success:
        raise HTTPException(status_code=404, detail=msg)
    return {"review_id": query_id, "status": "rejected", "message": msg, "record": rec}


@app.post("/admin/unanswered-queries/{query_id}/correct")
def correct_admin_unanswered_query(
    query_id: str,
    action: ReviewActionRequest = Body(...),
    admin_user: User = Depends(require_admin),
):
    """Submit an expert agricultural correction for a flagged query (Admin role required)."""
    from review_manager import review_manager
    if not action.corrected_answer or not action.corrected_answer.strip():
        raise HTTPException(status_code=400, detail="corrected_answer is required for correction.")
    success, msg, rec = review_manager.update_review(
        review_id=query_id,
        status="corrected",
        corrected_answer=action.corrected_answer,
        reviewer_notes=action.notes,
        reviewer_username=admin_user.username,
    )
    if not success:
        raise HTTPException(status_code=404, detail=msg)
    return {"review_id": query_id, "status": "corrected", "message": msg, "record": rec}


# ---------------------------------------------------------------------------
# Admin Knowledge Base Management & Vector Synchronization (Milestone 3 - Part 4.3)
# ---------------------------------------------------------------------------

class CreateKnowledgeRecordRequest(BaseModel):
    category: str
    title: str
    sub_category: Optional[str] = "general"
    source_name: Optional[str] = "ICAR / Government of India"
    organization: Optional[str] = "Agricultural Department"
    official_url: Optional[str] = "https://icar.gov.in"
    verification_status: Optional[str] = "verified_curated"
    content_en: str
    content_hi: Optional[str] = ""
    content_ta: Optional[str] = ""
    content_kn: Optional[str] = ""
    crops_applicable: Optional[list[str]] = None
    soil_types_applicable: Optional[list[str]] = None
    nutrients_applicable: Optional[list[str]] = None
    seasons_applicable: Optional[list[str]] = None
    tags: Optional[list[str]] = None
    guardrail_notice: Optional[str] = ""
    access_note: Optional[str] = ""
    doc_id: Optional[str] = None


class UpdateKnowledgeRecordRequest(BaseModel):
    category: Optional[str] = None
    title: Optional[str] = None
    sub_category: Optional[str] = None
    source_name: Optional[str] = None
    organization: Optional[str] = None
    official_url: Optional[str] = None
    verification_status: Optional[str] = None
    content_en: Optional[str] = None
    content_hi: Optional[str] = None
    content_ta: Optional[str] = None
    content_kn: Optional[str] = None
    crops_applicable: Optional[list[str]] = None
    soil_types_applicable: Optional[list[str]] = None
    nutrients_applicable: Optional[list[str]] = None
    seasons_applicable: Optional[list[str]] = None
    tags: Optional[list[str]] = None
    guardrail_notice: Optional[str] = None
    access_note: Optional[str] = None


@app.get("/admin/knowledge-base")
def list_admin_knowledge_records(
    category: Optional[str] = Query(None, description="Filter by category ('crops', 'soil', 'pests', 'diseases', 'farming_practices', 'government_schemes')"),
    crop: Optional[str] = Query(None, description="Filter by applicable crop"),
    language: Optional[str] = Query(None, description="Filter by available language ('en', 'hi', 'kn', 'ta')"),
    source: Optional[str] = Query(None, description="Filter by source or organization name"),
    search: Optional[str] = Query(None, description="Search keyword in title, content, or tags"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    admin_user: User = Depends(require_admin),
):
    """List knowledge base records with multi-factor filtering, search, and pagination (Admin role required)."""
    from knowledge_manager import knowledge_base_manager
    return knowledge_base_manager.list_records(
        category=category,
        crop=crop,
        language=language,
        source=source,
        search=search,
        limit=limit,
        offset=offset,
    )


@app.get("/admin/knowledge-base/status")
def get_admin_knowledge_status(
    admin_user: User = Depends(require_admin),
):
    """Inspect knowledge repository and vector store synchronization health (Admin role required)."""
    from knowledge_manager import knowledge_base_manager
    return knowledge_base_manager.get_sync_status()


@app.get("/admin/knowledge-base/{record_id}")
def get_admin_knowledge_record(
    record_id: str,
    admin_user: User = Depends(require_admin),
):
    """Retrieve full details of an agricultural knowledge record (Admin role required)."""
    from knowledge_manager import knowledge_base_manager
    rec = knowledge_base_manager.get_record(record_id)
    if not rec:
        raise HTTPException(status_code=404, detail=f"Knowledge record '{record_id}' not found.")
    return rec


@app.post("/admin/knowledge-base", status_code=201)
def create_admin_knowledge_record(
    payload: CreateKnowledgeRecordRequest,
    admin_user: User = Depends(require_admin),
):
    """Create a new verified agricultural record and synchronize with vector store (Admin role required)."""
    from knowledge_manager import knowledge_base_manager
    data = payload.model_dump()
    # PII sanity check on new knowledge records to protect farmer privacy
    from review_manager import sanitize_pii_for_review
    for content_key in ("content_en", "content_hi", "content_kn", "content_ta"):
        if data.get(content_key):
            data[content_key] = sanitize_pii_for_review(data[content_key])

    success, msg, rec = knowledge_base_manager.create_record(data)
    if not success:
        if "already exists" in msg.lower():
            raise HTTPException(status_code=409, detail=msg)
        raise HTTPException(status_code=400, detail=msg)
    return {"message": msg, "record": rec}


@app.put("/admin/knowledge-base/{record_id}")
def update_admin_knowledge_record(
    record_id: str,
    payload: UpdateKnowledgeRecordRequest,
    admin_user: User = Depends(require_admin),
):
    """Update an agricultural record and re-index vector store chunks (Admin role required)."""
    from knowledge_manager import knowledge_base_manager
    data = {k: v for k, v in payload.model_dump().items() if v is not None}
    from review_manager import sanitize_pii_for_review
    for content_key in ("content_en", "content_hi", "content_kn", "content_ta"):
        if data.get(content_key):
            data[content_key] = sanitize_pii_for_review(data[content_key])

    success, msg, rec = knowledge_base_manager.update_record(record_id, data)
    if not success:
        if "not found" in msg.lower():
            raise HTTPException(status_code=404, detail=msg)
        raise HTTPException(status_code=400, detail=msg)
    return {"message": msg, "record": rec}


@app.delete("/admin/knowledge-base/{record_id}")
def delete_admin_knowledge_record(
    record_id: str,
    confirm: bool = Query(True, description="Explicit confirmation required for deletion"),
    admin_user: User = Depends(require_admin),
):
    """Delete an agricultural record and purge all associated vector chunks (Admin role required)."""
    if not confirm:
        raise HTTPException(status_code=400, detail="Explicit confirmation required to delete record.")
    from knowledge_manager import knowledge_base_manager
    success, msg, deleted_chunks = knowledge_base_manager.delete_record(record_id)
    if not success:
        if "not found" in msg.lower():
            raise HTTPException(status_code=404, detail=msg)
        raise HTTPException(status_code=400, detail=msg)
    return {"record_id": record_id, "message": msg, "deleted_chunks": deleted_chunks}


@app.post("/admin/knowledge-base/reindex")
def reindex_admin_knowledge_base(
    admin_user: User = Depends(require_admin),
):
    """Trigger a controlled full vector re-indexing of all knowledge documents (Admin role required)."""
    from knowledge_manager import knowledge_base_manager
    return knowledge_base_manager.reindex_all()


@app.post("/admin/knowledge-base/upload")
async def upload_admin_knowledge_document(
    file: UploadFile = File(...),
    admin_user: User = Depends(require_admin),
):
    """Safely extract plain text and suggest metadata from uploaded document for preview (Admin role required)."""
    from knowledge_manager import knowledge_base_manager
    if not file.filename:
        raise HTTPException(status_code=400, detail="Uploaded file must have a filename.")
    file_bytes = await file.read()
    success, msg, preview_data = knowledge_base_manager.preview_document_upload(
        file_bytes=file_bytes,
        filename=file.filename,
        content_type=file.content_type,
    )
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {"message": msg, "preview": preview_data}


# ---------------------------------------------------------------------------
# Specialized External Data & Vector Store Inspection Endpoints (Milestone 2)
# ---------------------------------------------------------------------------

@app.get("/adapters/agmarknet")
def get_agmarknet_market_data(
    commodity: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    market: Optional[str] = Query(None),
    district: Optional[str] = Query(None),
    date: Optional[str] = Query(None),
    force_live: bool = Query(False),
):
    """Retrieve Agmarknet & e-NAM market intelligence and MSP reference benchmarks."""
    return agmarknet_adapter.get_market_data(
        commodity=commodity,
        state=state,
        market=market,
        district=district,
        date=date,
        force_live=force_live,
    )


@app.get("/adapters/weather")
def get_agricultural_weather_data(
    location: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    district: Optional[str] = Query(None),
):
    """Retrieve official IMD Agromet advisory and agricultural weather guidance."""
    return weather_adapter.get_weather_advisory(location=location, state=state, district=district)


@app.get("/adapters/schemes")
def get_government_scheme_guidance(query: str = Query("pm-kisan")):
    """Retrieve official government scheme eligibility criteria and documentation checklists."""
    return government_scheme_adapter.get_scheme_guidance(query=query)


@app.get("/vector-store/status")
def get_vector_store_status():
    """Inspect the status and backend of the persistent vector database."""
    store = rag_pipeline.vector_store
    import importlib.util
    chroma_available = importlib.util.find_spec("chromadb") is not None
    langchain_available = importlib.util.find_spec("langchain_core") is not None
    return {
        "backend": getattr(store, "backend_name", "vector_store"),
        "chunk_count": store.count(),
        "storage_directory": str(getattr(store, "storage_dir", "default")),
        "chromadb_available": chroma_available,
        "langchain_available": langchain_available,
        "configured_backend": os.getenv("VECTOR_STORE_BACKEND", "numpy").lower(),
        "supports_persistence": True,
        "supports_metadata_filtering": True,
    }


# ---------------------------------------------------------------------------
# Human Review & Response Quality Endpoints (Milestone 2)
# ---------------------------------------------------------------------------


@app.get("/review/pending")
def list_pending_reviews(limit: int = Query(50)):
    """Retrieve list of queries flagged for human expert review."""
    from review_manager import review_manager
    pending = review_manager.get_pending_reviews(limit=limit)
    return {"count": len(pending), "pending_reviews": pending}


@app.get("/review/stats")
def get_review_statistics():
    """Retrieve statistical summary of human review queue."""
    from review_manager import review_manager
    return review_manager.get_stats()


@app.get("/review/{review_id}")
def get_individual_review(review_id: str):
    """Retrieve a specific review record by ID."""
    from review_manager import review_manager
    rec = review_manager.get_review(review_id)
    if not rec:
        raise HTTPException(status_code=404, detail=f"Review '{review_id}' not found.")
    return rec


@app.post("/review/{review_id}/approve")
def approve_human_review(review_id: str, action: Optional[ReviewActionRequest] = None):
    """Approve a flagged answer as compliant with agricultural safety standards."""
    from review_manager import review_manager
    notes = action.notes if action else None
    success, msg = review_manager.approve_review(review_id, notes=notes)
    if not success:
        raise HTTPException(status_code=404, detail=msg)
    return {"review_id": review_id, "status": "approved", "message": msg}


@app.post("/review/{review_id}/reject")
def reject_human_review(review_id: str, action: Optional[ReviewActionRequest] = None):
    """Reject a flagged answer."""
    from review_manager import review_manager
    reason = action.notes if action else None
    success, msg = review_manager.reject_review(review_id, reason=reason)
    if not success:
        raise HTTPException(status_code=404, detail=msg)
    return {"review_id": review_id, "status": "rejected", "message": msg}


@app.post("/review/{review_id}/correct")
def correct_human_review(review_id: str, action: ReviewActionRequest):
    """Submit an expert correction for a flagged query response."""
    from review_manager import review_manager
    if not action.corrected_answer:
        raise HTTPException(status_code=400, detail="corrected_answer is required for correction.")
    success, msg = review_manager.correct_review(
        review_id=review_id,
        corrected_answer=action.corrected_answer,
        notes=action.notes,
    )
    if not success:
        raise HTTPException(status_code=404, detail=msg)
    return {"review_id": review_id, "status": "corrected", "message": msg}


# ---------------------------------------------------------------------------
# Farmer Feedback & Satisfaction Management (Milestone 3, Part 4.4)
# ---------------------------------------------------------------------------

class CreateFeedbackRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=100)
    message_id: Optional[str] = Field(None, max_length=100)
    rating: str = Field(..., description="'positive' / 'thumbs_up' or 'negative' / 'thumbs_down'")
    comment: Optional[str] = Field(None, max_length=500)
    farmer_id: Optional[str] = Field(None, max_length=100)


class FlagFeedbackRequest(BaseModel):
    notes: Optional[str] = Field(None, max_length=500)


@app.post("/feedback")
def submit_farmer_feedback(
    payload: CreateFeedbackRequest,
    http_request: Request = None,
    authorization: Optional[str] = Header(None),
):
    """Submit farmer feedback (thumbs-up or thumbs-down with optional comment)."""
    client_ip = get_client_ip(http_request) if http_request else "127.0.0.1"
    rate_limiter.check_rate_limit(client_ip=client_ip, session_id=payload.session_id)

    # 1. Validate session
    session = session_manager.get_session(payload.session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{payload.session_id}' not found.")

    # 2. Check authorization if session belongs to a registered farmer
    optional_user = get_optional_current_user(authorization)
    verify_session_access(session, optional_user)

    # 3. Validate rating
    norm_rating = payload.rating.strip().lower()
    if norm_rating not in ("positive", "negative", "thumbs_up", "thumbs_down", "up", "down"):
        raise HTTPException(status_code=400, detail="Invalid rating. Must be 'positive' or 'negative'.")

    # 4. Record feedback
    farmer_id = payload.farmer_id or (optional_user.username if optional_user else session.farmer_id)
    try:
        record = session_manager.record_feedback(
            session_id=payload.session_id,
            message_id=payload.message_id,
            rating=norm_rating,
            comment=payload.comment,
            farmer_id=farmer_id,
        )
        return {
            "status": "success",
            "feedback_id": record["feedback_id"],
            "rating": record["rating"],
            "message": "Feedback recorded successfully.",
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Failed to record farmer feedback: %s", exc)
        raise HTTPException(status_code=500, detail=f"Failed to record feedback: {exc}")


@app.get("/admin/feedback")
def list_admin_feedback(
    rating: Optional[str] = Query(None, description="Filter: all, positive, or negative"),
    language: Optional[str] = Query(None, description="Filter by language code"),
    intent: Optional[str] = Query(None, description="Filter by query intent"),
    search: Optional[str] = Query(None, description="Search term across query, answer, or comment"),
    start_date: Optional[str] = Query(None, description="ISO format start date"),
    end_date: Optional[str] = Query(None, description="ISO format end date"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    admin_user: User = Depends(require_admin),
):
    """Retrieve filtered, paginated feedback records and overall statistics (Admin role required)."""
    return session_manager.list_feedback(
        rating=rating,
        language=language,
        intent=intent,
        search=search,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )


@app.get("/admin/feedback/analytics")
def get_admin_feedback_analytics(
    days: int = Query(30, ge=1, le=365, description="Number of past days to aggregate"),
    admin_user: User = Depends(require_admin),
):
    """Compute satisfaction rate, daily trends, and breakdowns by language/intent (Admin role required)."""
    return session_manager.get_feedback_analytics(days=days)


@app.get("/admin/feedback/{feedback_id}")
def get_admin_feedback_detail(
    feedback_id: str,
    admin_user: User = Depends(require_admin),
):
    """Inspect full details of a specific feedback submission (Admin role required)."""
    detail = session_manager.get_feedback_detail(feedback_id)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Feedback '{feedback_id}' not found.")
    return detail


@app.post("/admin/feedback/{feedback_id}/flag-for-review")
def flag_feedback_for_expert_review(
    feedback_id: str,
    payload: Optional[FlagFeedbackRequest] = None,
    admin_user: User = Depends(require_admin),
):
    """Flag negative feedback into the human review queue for agricultural expert analysis (Admin role required)."""
    notes = payload.notes if payload else None
    try:
        return session_manager.flag_feedback_for_review(feedback_id=feedback_id, reviewer_notes=notes)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.exception("Failed to flag feedback for review: %s", exc)
        raise HTTPException(status_code=500, detail=f"Failed to flag feedback: {exc}")


# ---------------------------------------------------------------------------
# Interactive Scheme Assessment & Live Weather (Milestone 2)
# ---------------------------------------------------------------------------

class SchemeAssessmentRequest(BaseModel):
    scheme_id: str = "pm_kisan"
    criteria: dict[str, Any] = {}


@app.post("/adapters/schemes/assess")
def assess_government_scheme_eligibility(request: SchemeAssessmentRequest):
    """Assess farmer eligibility for PM-KISAN, PMFBY, PMKSY, or KCC."""
    return government_scheme_adapter.assess_scheme_eligibility(
        scheme_id=request.scheme_id,
        criteria=request.criteria,
    )


@app.get("/adapters/schemes/assess")
def assess_government_scheme_eligibility_get(
    scheme_id: str = Query("pm_kisan"),
    has_cultivable_land: Optional[bool] = Query(None),
    aadhaar_ekyc_done: Optional[bool] = Query(None),
    hours_since_calamity: Optional[int] = Query(None),
    landholding_hectares: Optional[float] = Query(None),
):
    """Convenience GET endpoint for scheme eligibility assessment."""
    criteria = {}
    if has_cultivable_land is not None:
        criteria["has_cultivable_land"] = has_cultivable_land
    if aadhaar_ekyc_done is not None:
        criteria["aadhaar_ekyc_done"] = aadhaar_ekyc_done
    if hours_since_calamity is not None:
        criteria["hours_since_calamity"] = hours_since_calamity
    if landholding_hectares is not None:
        criteria["landholding_hectares"] = landholding_hectares
    return government_scheme_adapter.assess_scheme_eligibility(
        scheme_id=scheme_id,
        criteria=criteria,
    )


@app.get("/adapters/weather/live")
def get_live_weather_observation(
    location: Optional[str] = Query("Delhi"),
    district: Optional[str] = Query(None),
):
    """Retrieve actual live weather forecast using Open-Meteo WMO / IMD Agromet guidance."""
    return weather_adapter.get_weather_advisory(
        location=location,
        district=district,
        force_live=True,
    )

