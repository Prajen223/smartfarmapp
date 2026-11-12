"""Agricultural intent classification for Smart Farming Assistant.

Combines:
  1. Multilingual keyword baseline for instant local routing across Indian languages.
  2. Hugging Face zero-shot classification pipeline (valhalla/distilbart-mnli-12-1)
     for robust semantic generalization.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Optional, Any

logger = logging.getLogger(__name__)

INTENTS = [
    "pest_control",
    "irrigation",
    "market_prices",
    "government_schemes",
    "crop_advisory",
    "weather",
]

# Multilingual keywords covering English, Hindi, Kannada, Tamil, and Telugu
FARMING_KEYWORDS: dict[str, list[str]] = {
    "pest_control": [
        "pest", "pests", "insect", "insects", "worm", "worms", "disease", "diseases",
        "caterpillar", "caterpillars", "bug", "bugs", "fungus", "fungal", "blight", "infestation",
        "pesticide", "pesticides", "fungicide", "fungicides", "insecticide", "insecticides",
        "spray", "spraying", "control pests", "pest control",
        "aphid", "aphids", "whitefly", "whiteflies", "bollworm", "borer", "borers",
        "thrips", "mite", "mites", "rust", "mildew", "rot", "canker", "wilt",
        "weevil", "beetle", "leafminer", "leaf miner", "stem borer", "fruit borer",
        "कीट", "कीड़ों", "कीड़े", "बीमारी", "रोग", "इल्ली", "फंगस", "दवा", "कीटनाशक", "माहू", "सफेद मक्खी",
        "ಕೀಟ", "ಹುಳು", "ರೋಗ", "ಶಿಲೀಂಧ್ರ", "ಔಷಧಿ", "ಕೀಟನಾಶಕ",
        "பூச்சி", "புழு", "நோய்", "பூஞ்சை", "மருந்து", "பூச்சிக்கொல்லி",
        "పురుగు", "కీటకం", "తెగులు", "శిలీంధ్రం", "పురుగుమందు",
    ],
    "irrigation": [
        "irrigation", "irrigate", "irrigating", "watering", "water", "drip", "sprinkler",
        "moisture", "borewell", "pump", "canal", "water requirement", "how much water",
        "पानी", "सिंचाई", "ड्रिप", "फुहारा", "नमी", "नलकूप", "नहर",
        "ನೀರು", "ನೀರಾವರಿ", "ಹನಿ ನೀರಾವರಿ", "ತೇವಾಂಶ",
        "தண்ணீர்", "நீர்ப்பாசனம்", "சொட்டு நீர்", "ஈரப்பதம்",
        "నీరు", "సాగునీరు", "బిందు సేద్యం", "తేమ",
    ],
    "market_prices": [
        "price", "prices", "market", "cost", "mandi", "market rate", "market rates",
        "mandi rate", "mandi rates", "msp", "minimum support price", "wholesale", "apmc",
        "मूल्य", "कीमत", "मंडी", "बाजार", "भाव", "मंडी भाव", "बाजार भाव", "मंडी दर",
        "ಬೆಲೆ", "ಮಾರುಕಟ್ಟೆ", "ಮಂಡಿ", "ಮಾರುಕಟ್ಟೆ ದರ", "ಮಂಡಿ ಬೆಲೆ",
        "விலை", "சந்தை", "மண்டி", "விற்பனை",
        "ధర", "మార్కెట్", "మండి", "మార్కెట్ ధర",
    ],
    "government_schemes": [
        "subsidy", "subsidies", "scheme", "schemes", "government", "pm-kisan", "pmkisan", "pmfby", "pmksy",
        "insurance", "loan", "kcc", "portal", "yojana", "yojna", "financial assistance", "grant",
        "योजना", "सब्सिडी", "सरकार", "बीमा", "ऋण", "अनुदान", "सरकारी",
        "ಯೋಜನೆ", "ಸರ್ಕಾರ", "ಸಬ್ಸಿಡಿ", "ವಿಮೆ", "ಸಾಲ",
        "திட்டம்", "மானியம்", "அரசு", "காப்பீடு", "கடன்",
        "పథకం", "రాయితీ", "ప్రభుత్వం", "భీమా", "రుణం",
    ],
    "crop_advisory": [
        "crop", "crops", "fertilizer", "fertiliser", "soil", "harvest", "seed", "seeds",
        "seed rate", "seedrate", "sowing", "sow", "variety", "yield", "urea", "dap",
        "yellowing", "yellow", "leaf", "leaves", "chlorosis", "stunted", "growth",
        "wilting", "deficiency", "npk", "compost", "nutrient", "nutrients", "manure",
        "germination", "transplanting", "spacing",
        "फसल", "उर्वरक", "खाद", "मिट्टी", "बीज", "बीज दर", "बुवाई", "उपज", "पीली", "पीला", "पत्तियां", "पत्ते",
        "ಬೆಳೆ", "ಗೊಬ್ಬರ", "ಮಣ್ಣು", "ಬೀಜ", "ಬಿತ್ತನೆ", "ಇಳುವರಿ", "ಹಳದಿ", "ಎಲೆ", "ಎಲೆಗಳು",
        "பயிர்", "உரம்", "மண்", "விதை", "மகசூல்", "மஞ்சள்", "இலை",
        "పంట", "ఎరువు", "మట్టి", "విత్తనం", "దిగుబడి", "పసుపు", "ఆకులు",
    ],
    "weather": [
        "weather", "rain", "raining", "temperature", "humidity", "wind", "forecast", "climate", "precipitation",
        "safe to spray", "spray safe", "spray today",
        "मौसम", "बारिश", "तापमान", "हवा", "आर्द्रता", "वर्षा", "बादल",
        "ಹವಾಮಾನ", "ಮಳೆ", "ತಾಪಮಾನ", "ಗಾಳಿ", "ತೇವಾಂಶ",
        "வானிலை", "மழை", "வெப்பநிலை", "காற்று", "ஈரப்பதம்",
        "వాతావరణం", "వర్షம்", "ఉష్ణోగ్రత", "గాలి",
    ],
}

# Module-level singleton pipeline (lazy-loaded to avoid blocking module import)
_hf_classifier: Optional[Any] = None


def is_hf_intent_enabled() -> bool:
    """Check if Hugging Face zero-shot intent classifier is enabled."""
    model_name = os.getenv("HF_INTENT_MODEL", "valhalla/distilbart-mnli-12-1").strip()
    if model_name.lower() in ("disabled", "false", "none", "off", "0", ""):
        return False
    return True


def get_hf_classifier():
    """Lazily load Hugging Face zero-shot classification pipeline.

    If HF_INTENT_MODEL is disabled, never imports transformers or downloads models.
    """
    global _hf_classifier
    if _hf_classifier is None:
        if not is_hf_intent_enabled():
            logger.info("Hugging Face intent classifier disabled via HF_INTENT_MODEL. Using keyword engine.")
            _hf_classifier = False
            return None
        model_name = os.getenv("HF_INTENT_MODEL", "valhalla/distilbart-mnli-12-1").strip()
        try:
            # pyrefly: ignore [missing-import]
            from transformers import pipeline
            logger.info("Loading Hugging Face zero-shot intent classifier: %s", model_name)
            _hf_classifier = pipeline(
                "zero-shot-classification",
                model=model_name,
            )
        except Exception as exc:
            logger.warning("Could not load Hugging Face pipeline (%s). Falling back to keyword engine.", exc)
            _hf_classifier = False
    return _hf_classifier if _hf_classifier is not False else None


# Backwards compatibility alias for code that expects 'classifier' object
class _LazyClassifierProxy:
    def __call__(self, *args, **kwargs):
        clf = get_hf_classifier()
        if clf:
            return clf(*args, **kwargs)
        # Fallback dictionary if model unavailable
        return {"labels": [INTENTS[0]], "scores": [0.5]}


classifier = _LazyClassifierProxy()


def classify_intent(text: str, language_code: str = "en") -> dict:
    """Classify the agricultural intent of a user question.

    Args:
        text: Query text (native language or canonical English).
        language_code: Detected language code ('en', 'hi', 'kn', 'ta', etc.).

    Returns:
        Dict with 'intent', 'confidence', 'classification_method'.
    """
    normalized = text.casefold()

    # 1. High-precision agricultural weather query recognition
    weather_pattern = (
        r"\b(?:weather|temperature|humidity|wind\s*speed|windspeed|rainfall?|precipitation|climate|forecast|mausam|barish|barsat|tapman)\b"
        r"|\b(?:safe\s+to\s+spray|spray\s+safety|spray\s+today|can\s+i\s+spray|spray\s+pesticides?\s+today)\b"
        r"|\b(?:will\s+it\s+rain|chance\s+of\s+rain|is\s+it\s+raining)\b"
        r"|(?:मौसम|बारिश|तापमान|हवा\s*की\s*गति|हवामान|வானிலை|மழை|வெப்பநிலை|বাতಾವరణం)"
    )
    if re.search(weather_pattern, text, re.IGNORECASE):
        return {
            "intent": "weather",
            "confidence": 0.96,
            "classification_method": "weather_rules_engine",
        }

    # Calculate keyword match scores across intents
    keyword_scores = {
        intent: sum(
            1 for keyword in keywords
            if keyword.casefold() in normalized
        )
        for intent, keywords in FARMING_KEYWORDS.items()
    }

    best_intent = max(keyword_scores, key=keyword_scores.get)
    best_score = keyword_scores[best_intent]

    hf_enabled = is_hf_intent_enabled()

    # Fast-path keyword routing:
    # 1. Non-English scripts with clear keyword presence (native Indic keywords are unambiguous)
    # 2. English queries when HF model is disabled via environment
    # 3. High-confidence keyword matches (best_score >= 1)
    if best_score > 0:
        if language_code != "en" or not hf_enabled or best_score >= 1:
            return {
                "intent": best_intent,
                "confidence": min(0.95, round(0.70 + (best_score * 0.1), 2)),
                "classification_method": "keyword_baseline",
            }

    # Attempt Hugging Face Zero-Shot classification only when enabled and no distinct keyword matched
    if hf_enabled:
        hf_clf = get_hf_classifier()
        if hf_clf is not None:
            try:
                result = hf_clf(
                    text,
                    candidate_labels=INTENTS,
                    hypothesis_template="This question is about {}.",
                )
                return {
                    "intent": result["labels"][0],
                    "confidence": round(float(result["scores"][0]), 4),
                    "classification_method": "huggingface_zero_shot",
                }
            except Exception as exc:
                logger.warning("Zero-shot inference failed: %s. Using keyword fallback.", exc)

    # Keyword fallback if HF classifier is not available or errored
    final_intent = best_intent if best_score > 0 else "crop_advisory"
    return {
        "intent": final_intent,
        "confidence": min(0.95, round(0.70 + (best_score * 0.1), 2)) if best_score > 0 else 0.40,
        "classification_method": "keyword_baseline",
    }
