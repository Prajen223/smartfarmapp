
import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from language_detector import detect_language
from intent_classifier import classify_intent

load_dotenv()

app = FastAPI(title="Smart Farming Assistant API")

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


class AskRequest(BaseModel):
    text: str
    mode: str = "local"


@app.get("/")
def home():
    return {
        "message": "Smart Farming Assistant backend is running"
    }


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/config-check")
def config_check():
    return {
        "sarvam_key_configured": bool(
            os.getenv("SARVAM_API_KEY")
        ),
        "mode": "local",
    }


@app.post("/ask")
def ask_farming_assistant(request: AskRequest):
    if not request.text.strip():
        raise HTTPException(
            status_code=400,
            detail="Please enter a farming question",
        )

    # Local processing only: no Sarvam API calls
    language_info = detect_language(request.text)

    classification = classify_intent(
        request.text,
        language_code=language_info["language_code"],
    )

    return {
        "input_text": request.text,
        "language": language_info["language"],
        "language_code": language_info["language_code"],
        "intent": classification["intent"],
        "confidence": classification["confidence"],
        "classification_method": classification[
            "classification_method"
        ],
        "answer": (
            "Language detection and intent classification "
            "successful. Local testing mode is enabled. "
            "A full agricultural answer is not enabled yet."
        ),
        "mode": "local",
    }

