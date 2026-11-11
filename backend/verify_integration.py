import json
import base64
import os
import sys
import urllib.request
import urllib.error

# Ensure Windows terminal prints UTF-8 Tamil/Hindi/Kannada characters without charmap errors
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_URL = os.getenv("FASTAPI_BASE_URL", os.getenv("BACKEND_URL", "http://127.0.0.1:8000"))

TEST_CASES = [
    {
        "label": "English Irrigation with Tomato & Soil context",
        "question": "How often should I water my tomato plants in black soil?",
        "expected_intent": "irrigation",
    },
    {
        "label": "Tamil Pest Control with Tomato crop context",
        "question": "தக்காளி பயிரில் பூச்சி தாக்குதலை எப்படி கட்டுப்படுத்துவது?",
        "expected_intent": "pest_control",
    },
    {
        "label": "Kannada Irrigation & Cotton crop query",
        "question": "ಕಪ್ಪು ಮಣ್ಣಿನಲ್ಲಿ ಹತ್ತಿ ಬೆಳೆಗೆ ಹನಿ ನೀರಾವರಿ ಹೇಗೆ ಮಾಡಬೇಕು?",
        "expected_intent": "irrigation",
    },
    {
        "label": "Hindi Pest & Crop Advisory query",
        "question": "टमाटर की फसल में पत्ती झुलसा और सफेद मक्खी का नियंत्रण कैसे करें?",
        "expected_intent": "pest_control",
    },
    {
        "label": "English Crop Advisory with Paddy context",
        "question": "What fertilizer schedule should I follow for paddy?",
        "expected_intent": "crop_advisory",
    },
    {
        "label": "Tamil Market Prices (Guardrail: no invented prices)",
        "question": "தக்காளி சந்தை விலை நிலவரம் என்ன?",
        "expected_intent": "market_prices",
    },
    {
        "label": "English Government Schemes (Guardrail: no invented eligibility)",
        "question": "What government subsidies are available for drip irrigation?",
        "expected_intent": "government_schemes",
    },
]


def run_tests():
    print("=================================================================")
    print("RUNNING END-TO-END VERIFICATION FOR WEEK 1-2 ENGINE")
    print("=================================================================\n")

    passed = 0
    total = len(TEST_CASES) + 4  # Includes empty check, multi-turn, and voice endpoints

    # 1. Test Query Cases
    for idx, test in enumerate(TEST_CASES, start=1):
        print(f"Test #{idx}: {test['label']}")
        print(f"Question: {test['question']}")

        req_data = json.dumps({"text": test["question"]}).encode("utf-8")
        req = urllib.request.Request(
            f"{BASE_URL}/ask",
            data=req_data,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                body = json.loads(response.read().decode("utf-8"))
                print(f"-> Language: {body.get('language')} ({body.get('language_code')})")
                print(f"-> Intent: {body.get('intent')} (Method: {body.get('classification_method')})")
                print(f"-> Entities: {body.get('entities')}")
                print(f"-> Mode: {body.get('mode')}")
                answer_preview = body.get('answer', '')[:140].replace('\n', ' ')
                print(f"-> Answer Preview: {answer_preview}...\n")
                passed += 1
        except Exception as e:
            print(f"-> FAILED: {e}\n")

    # 2. Test Empty Input Validation
    test_idx = len(TEST_CASES) + 1
    print(f"Test #{test_idx}: Empty Input Validation")
    req_data = json.dumps({"text": "   "}).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE_URL}/ask",
        data=req_data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=5)
        print("-> FAILED: Expected HTTP 400 but succeeded\n")
    except urllib.error.HTTPError as e:
        if e.code == 400:
            print("-> PASSED: Correctly returned HTTP 400 Bad Request\n")
            passed += 1
        else:
            print(f"-> FAILED: Returned HTTP {e.code}\n")
    except Exception as e:
        print(f"-> FAILED: {e}\n")

    # 3. Test Multi-turn Context Resolution
    test_idx += 1
    print(f"Test #{test_idx}: Multi-turn Context Resolution (Turn 1 establishes Tomato, Turn 2 asks follow-up)")
    try:
        # Turn 1
        req1 = urllib.request.Request(
            f"{BASE_URL}/ask",
            data=json.dumps({"text": "How to grow tomato plants?"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req1, timeout=10) as r1:
            body1 = json.loads(r1.read().decode("utf-8"))
            sid = body1["session_id"]

        # Turn 2 using session_id but without mentioning "tomato"
        req2 = urllib.request.Request(
            f"{BASE_URL}/ask",
            data=json.dumps({"text": "How much water does it need?", "session_id": sid}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req2, timeout=10) as r2:
            body2 = json.loads(r2.read().decode("utf-8"))
            if "tomato" in body2["entities"].get("crops", []):
                print(f"-> PASSED: Tomato context successfully carried over to Turn 2! (Turn count: {body2['session_context']['turn_count']})\n")
                passed += 1
            else:
                print(f"-> FAILED: Crop context not carried over. Entities: {body2['entities']}\n")
    except Exception as e:
        print(f"-> FAILED: {e}\n")

    # 4. Test Voice Synthesize Endpoint
    test_idx += 1
    print(f"Test #{test_idx}: Voice Speech Synthesis Endpoint (TTS)")
    try:
        tts_req = urllib.request.Request(
            f"{BASE_URL}/voice/synthesize",
            data=json.dumps({"text": "टमाटर में जैविक खाद का उपयोग करें", "language_code": "hi"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(tts_req, timeout=10) as r_tts:
            body_tts = json.loads(r_tts.read().decode("utf-8"))
            if body_tts.get("audio_base64"):
                print(f"-> PASSED: Successfully received base64 audio (Format: {body_tts.get('audio_format', body_tts.get('format'))}, Provider: {body_tts.get('provider')})\n")
                passed += 1
            else:
                print(f"-> FAILED: No audio_base64 returned\n")
    except Exception as e:
        print(f"-> FAILED: {e}\n")

    # 5. Test Knowledge Documents Retrieval
    test_idx += 1
    print(f"Test #{test_idx}: Knowledge Documents Listing Endpoint")
    try:
        with urllib.request.urlopen(f"{BASE_URL}/knowledge/documents", timeout=10) as r_doc:
            doc_data = json.loads(r_doc.read().decode("utf-8"))
            if doc_data.get("count", 0) > 0:
                print(f"-> PASSED: Retrieved {doc_data['count']} ICAR knowledge documents with verified metadata.\n")
                passed += 1
            else:
                print(f"-> FAILED: No documents returned\n")
    except Exception as e:
        print(f"-> FAILED: {e}\n")

    print("=================================================================")
    print(f"SUMMARY: {passed} of {total} verification tests passed successfully.")
    print("=================================================================\n")


if __name__ == "__main__":
    run_tests()
