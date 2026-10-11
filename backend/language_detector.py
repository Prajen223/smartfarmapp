
from langdetect import detect, DetectorFactory, LangDetectException

# Make results reproducible
DetectorFactory.seed = 0


def detect_language(text: str) -> dict:
    text = text.strip()

    if not text:
        return {
            "language": "Unknown",
            "language_code": "und",
            "confidence": 0.0,
        }

    # Detect Indian language scripts directly
    # Tamil
    if any("\u0B80" <= char <= "\u0BFF" for char in text):
        return {
            "language": "Tamil",
            "language_code": "ta",
            "confidence": 1.0,
        }

    # Telugu
    if any("\u0C00" <= char <= "\u0C7F" for char in text):
        return {
            "language": "Telugu",
            "language_code": "te",
            "confidence": 1.0,
        }

    # Kannada
    if any("\u0C80" <= char <= "\u0CFF" for char in text):
        return {
            "language": "Kannada",
            "language_code": "kn",
            "confidence": 1.0,
        }

    # Malayalam
    if any("\u0D00" <= char <= "\u0D7F" for char in text):
        return {
            "language": "Malayalam",
            "language_code": "ml",
            "confidence": 1.0,
        }

    # Devanagari: Hindi and other languages using this script
    if any("\u0900" <= char <= "\u097F" for char in text):
        return {
            "language": "Hindi",
            "language_code": "hi",
            "confidence": 1.0,
        }

    # Detect languages in Latin script
    try:
        detected_code = detect(text)

        language_map = {
            "en": ("English", "en"),
            "hi": ("Hindi", "hi"),
            "ta": ("Tamil", "ta"),
            "te": ("Telugu", "te"),
            "kn": ("Kannada", "kn"),
            "ml": ("Malayalam", "ml"),
        }

        language_name, language_code = language_map.get(
            detected_code,
            ("Other", detected_code),
        )

        return {
            "language": language_name,
            "language_code": language_code,
            "confidence": None,
        }

    except LangDetectException:
        return {
            "language": "Unknown",
            "language_code": "und",
            "confidence": 0.0,
        }
