
from transformers import pipeline

classifier = pipeline(
    "zero-shot-classification",
    model="valhalla/distilbart-mnli-12-1",
)

INTENTS = [
    "pest_control",
    "irrigation",
    "market_prices",
    "government_schemes",
    "crop_advisory",
]

# Simple multilingual keyword baseline.
# This is not a complete translation system.
FARMING_KEYWORDS = {
    "pest_control": [
        "pest", "insect", "worm", "disease", "कीट", "कीड़ों",
        "ಕೀಟ", "ಹುಳು", "பூச்சி", "புழு",
    ],
    "irrigation": [
        "water", "irrigation", "watering", "पानी", "सिंचाई",
        "ನೀರು", "ನೀರಾವರಿ", "தண்ணீர்", "நீர்ப்பாசனம்",
    ],
    "market_prices": [
        "price", "market", "cost", "मूल्य", "कीमत",
        "ಬೆಲೆ", "ಮಾರುಕಟ್ಟೆ", "விலை", "சந்தை",
    ],
    "government_schemes": [
        "subsidy", "scheme", "government", "योजना", "सब्सिडी",
        "ಯೋಜನೆ", "ಸರ್ಕಾರ", "திட்டம்", "மானியம்",
    ],
    "crop_advisory": [
        "crop", "fertilizer", "fertiliser", "soil", "फसल",
        "उर्वरक", "ಬೆಳೆ", "ಗೊಬ್ಬರ", "பயிர்", "உரம்",
    ],
}


def classify_intent(text: str, language_code: str = "en") -> dict:
    normalized = text.casefold()

    # Use known keywords for a basic local multilingual baseline.
    keyword_scores = {
        intent: sum(
            1 for keyword in keywords
            if keyword.casefold() in normalized
        )
        for intent, keywords in FARMING_KEYWORDS.items()
    }

    best_intent = max(keyword_scores, key=keyword_scores.get)
    best_score = keyword_scores[best_intent]

    if best_score > 0 and language_code != "en":
        return {
            "intent": best_intent,
            "confidence": None,
            "classification_method": "keyword_baseline",
        }

    result = classifier(
        text,
        candidate_labels=INTENTS,
        hypothesis_template="This question is about {}.",
    )

    return {
        "intent": result["labels"][0],
        "confidence": round(float(result["scores"][0]), 4),
        "classification_method": "huggingface_zero_shot",
    }
