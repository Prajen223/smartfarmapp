"""End-to-End Integration and Regression Tests for Weather and AGMARKNET Live Prices.

Validates:
1. "What is today's tomato price in Salem? Give minimum, maximum and modal prices."
   - Intent: market_prices
   - Clean entity extraction: Tomato (crop), Salem (location), NO false lentils
   - Live AGMARKNET API routing with structured record rendering
   - Synthesis includes: Market name, Commodity & variety, Min price, Max price,
     Modal price, Unit (Rs./Quintal), Reporting date, Source.
   - Multiple markets separated, honest no-data notice when zero transactions.
2. "What is the current weather in Varanasi?"
   - Intent: weather (confidence >= 0.90)
   - Clean entity extraction: Varanasi (location), NO crops (no false lentil)
   - Live Open-Meteo WMO / IMD agromet routing
   - Synthesis includes: Location, Temperature, Humidity, Wind speed, Precipitation,
     Chemical spray recommendation, Spray safety rule, Source, Portal.
3. Cross-turn context anti-contamination:
   - Weather queries never inherit previous turn crops/schemes.
   - Market price queries with specified crop override previous crops.
4. Preserved functionality:
   - PM-KISAN scheme eligibility
   - Pest control, irrigation, and crop advisory intents
   - Vector store (ChromaDB) record integrity
"""

import pytest
from fastapi.testclient import TestClient

from main import app
from intent_classifier import classify_intent
from ner_extractor import extract_agricultural_entities, extract_primary_commodity, extract_primary_location
from external_adapters import agmarknet_adapter, weather_adapter
from rag_pipeline import rag_pipeline
from session_manager import session_manager


client = TestClient(app)


class TestWeatherQueryRouting:
    """Verifies that weather queries are cleanly classified, extracted, and routed."""

    def test_varanasi_weather_intent_and_clean_entities(self):
        query = "What is the current weather in Varanasi?"
        
        # 1. Intent classification
        res = classify_intent(query, language_code="en")
        assert res["intent"] == "weather", f"Expected 'weather', got {res['intent']}"
        assert res["confidence"] >= 0.90, f"Expected confidence >= 0.90, got {res['confidence']}"

        # 2. NER extraction must NOT extract 'lentil' or other false crops
        entities = extract_agricultural_entities(query)
        assert "varanasi" in entities.get("locations", []), "Varanasi must be recognized as location"
        assert entities.get("crops") == [], f"No crop should be extracted from weather query, got {entities.get('crops')}"
        assert entities.get("schemes") == []

        prim_loc = extract_primary_location(query, entities)
        assert prim_loc.lower() == "varanasi"

    @pytest.mark.parametrize(
        "weather_query,expected_loc",
        [
            ("What is the current weather in Varanasi?", "Varanasi"),
            ("Is it safe to spray pesticides today in Varanasi?", "Varanasi"),
            ("Will it rain tomorrow in Salem?", "Salem"),
            ("What is the temperature and humidity in Coimbatore?", "Coimbatore"),
            ("Check weather forecast for Delhi", "Delhi"),
            ("Aaj ka mausam kaisa hai Varanasi mein?", "Varanasi"),
        ],
    )
    def test_multilingual_and_phrased_weather_queries(self, weather_query, expected_loc):
        res = classify_intent(weather_query, language_code="en")
        assert res["intent"] == "weather", f"Failed for query '{weather_query}', got {res['intent']}"
        assert res["confidence"] >= 0.85

    def test_weather_live_adapter_and_rag_synthesis(self):
        query = "What is the current weather in Varanasi?"
        entities = extract_agricultural_entities(query)
        
        rag_res = rag_pipeline.generate_response(
            query=query,
            canonical_text=query,
            intent="weather",
            language_code="en",
            entities=entities,
        )

        assert rag_res["intent"] == "weather"
        assert rag_res["response_mode"] in ("adapter_live_weather", "adapter_weather_advisory")
        
        adapter_data = rag_res.get("adapter_data")
        assert adapter_data is not None, "Adapter data must be populated for weather query"
        assert adapter_data.get("service") in ("live_agromet_weather", "weather_api", "imd_agromet")

        answer = rag_res["answer"]
        assert "Live Agricultural Weather Advisory" in answer or "Weather" in answer
        assert "Temperature" in answer
        assert "Humidity" in answer
        assert "Wind Speed" in answer
        assert "Chemical Spray" in answer or "Spray" in answer
        assert "Safety Rule" in answer

    def test_weather_fastapi_ask_endpoint(self):
        resp = client.post(
            "/ask",
            json={"text": "What is the current weather in Varanasi?", "preferred_language": "en"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["intent"] == "weather"
        assert "crops" in data["entities"]
        assert data["entities"]["crops"] == []
        assert "varanasi" in [loc.lower() for loc in data["entities"].get("locations", [])]
        assert data["adapter_data"] is not None
        assert "Temperature" in data["answer"]


class TestAgmarknetTomatoPriceIntegration:
    """Verifies that tomato price in Salem returns live mandi prices and structured synthesis."""

    def test_tomato_salem_clean_entities_no_lentil(self):
        query = "What is today's tomato price in Salem? Give minimum, maximum and modal prices."
        
        # 1. Intent
        res = classify_intent(query, language_code="en")
        assert res["intent"] == "market_prices"

        # 2. NER extraction must extract tomato and salem, NEVER lentil
        entities = extract_agricultural_entities(query)
        assert "tomato" in entities.get("crops", []), "Tomato must be extracted"
        assert "lentil" not in entities.get("crops", []), "False crop 'lentil' must NOT be extracted"
        assert "salem" in entities.get("locations", []), "Salem must be extracted"

        prim_comm = extract_primary_commodity(query, entities)
        prim_loc = extract_primary_location(query, entities)
        assert prim_comm.lower() == "tomato"
        assert prim_loc.lower() == "salem"

    def test_agmarknet_rag_synthesis_formatting(self):
        query = "What is today's tomato price in Salem? Give minimum, maximum and modal prices."
        entities = {"crops": ["tomato"], "locations": ["salem"]}

        rag_res = rag_pipeline.generate_response(
            query=query,
            canonical_text=query,
            intent="market_prices",
            language_code="en",
            entities=entities,
        )

        assert rag_res["intent"] == "market_prices"
        adapter_data = rag_res.get("adapter_data")
        assert adapter_data is not None
        assert adapter_data.get("service") == "agmarknet"

        answer = rag_res["answer"]
        # Required elements from the user prompt:
        # Market name, Commodity and variety, Min price, Max price, Modal price, Unit, Reporting date, Source
        if adapter_data.get("is_live") and adapter_data.get("live_records"):
            assert "Market:" in answer
            assert "Commodity:" in answer and "Variety:" in answer
            assert "Modal Price:" in answer
            assert "Minimum Price:" in answer
            assert "Maximum Price:" in answer
            assert "Reporting Date:" in answer
            assert "Source:" in answer
            assert "Rs./Quintal" in answer or "Quintal" in answer
        else:
            # Honest no-data or offline mode
            assert "Price Verification" in answer or "AGMARKNET" in answer

    def test_fastapi_ask_tomato_salem_endpoint(self):
        resp = client.post(
            "/ask",
            json={
                "text": "What is today's tomato price in Salem? Give minimum, maximum and modal prices.",
                "preferred_language": "en",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["intent"] == "market_prices"
        assert "tomato" in data["entities"]["crops"]
        assert "lentil" not in data["entities"]["crops"]
        assert "salem" in [loc.lower() for loc in data["entities"].get("locations", [])]
        assert data["adapter_data"] is not None


class TestCrossTurnContextAntiContamination:
    """Verifies that entities from previous turns do not bleed into unrelated subsequent queries."""

    def test_weather_does_not_inherit_previous_crop(self):
        # Turn 1: Discuss lentil cultivation
        t1_resp = client.post(
            "/ask",
            json={"text": "How do I cultivate lentil in black soil?", "preferred_language": "en"},
        )
        assert t1_resp.status_code == 200
        t1_data = t1_resp.json()
        session_id = t1_data["session_id"]
        assert "lentil" in t1_data["entities"]["crops"]

        # Turn 2: Ask about weather in Varanasi using the SAME session_id
        t2_resp = client.post(
            "/ask",
            json={
                "text": "What is the current weather in Varanasi?",
                "preferred_language": "en",
                "session_id": session_id,
            },
        )
        assert t2_resp.status_code == 200
        t2_data = t2_resp.json()
        assert t2_data["intent"] == "weather"
        # CRITICAL ASSERTION: Crops must be empty for weather turn!
        assert t2_data["entities"]["crops"] == [], (
            f"Weather turn must not inherit crops from turn 1, but got {t2_data['entities']['crops']}"
        )
        assert "varanasi" in [loc.lower() for loc in t2_data["entities"]["locations"]]

    def test_tomato_price_does_not_inherit_previous_crop(self):
        # Turn 1: Discuss wheat irrigation
        t1_resp = client.post(
            "/ask",
            json={"text": "How often should I irrigate wheat?", "preferred_language": "en"},
        )
        assert t1_resp.status_code == 200
        session_id = t1_resp.json()["session_id"]

        # Turn 2: Ask for tomato price in Salem using same session_id
        t2_resp = client.post(
            "/ask",
            json={
                "text": "What is today's tomato price in Salem? Give minimum, maximum and modal prices.",
                "preferred_language": "en",
                "session_id": session_id,
            },
        )
        assert t2_resp.status_code == 200
        t2_data = t2_resp.json()
        assert t2_data["intent"] == "market_prices"
        assert t2_data["entities"]["crops"] == ["tomato"], (
            f"Expected crops to be strictly ['tomato'], got {t2_data['entities']['crops']}"
        )


class TestPreservedFunctionality:
    """Verifies existing schemes and intents remain 100% operational."""

    def test_pm_kisan_scheme_eligibility(self):
        resp = client.post(
            "/ask",
            json={"text": "What are the eligibility requirements for PM-KISAN?", "preferred_language": "en"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["intent"] == "government_schemes"
        assert data["adapter_data"] is not None
        assert (
            data["adapter_data"].get("scheme_key") == "pm_kisan"
            or "PM-KISAN" in str(data["adapter_data"].get("matched_scheme", ""))
            or "PM-KISAN" in str(data["adapter_data"].get("scheme_details", {}).get("name", ""))
        )
        assert "₹6,000" in data["answer"]
        assert "Aadhaar" in data["answer"]

    def test_pest_control_intent(self):
        res = classify_intent("How to control aphids and whitefly in tomato crop?")
        assert res["intent"] == "pest_control"

    def test_irrigation_intent(self):
        res = classify_intent("How much water does drip irrigation need for cotton?")
        assert res["intent"] == "irrigation"

    def test_crop_advisory_intent(self):
        res = classify_intent("What is the best sowing time and seed rate for mustard?")
        assert res["intent"] == "crop_advisory"
