"""Unit tests for external_adapters.py — AGMARKNET, Weather, and Government Schemes."""

import unittest
from external_adapters import (
    AgmarknetAdapter,
    WeatherAdapter,
    GovernmentSchemeAdapter,
    agmarknet_adapter,
    weather_adapter,
    government_scheme_adapter,
)


class TestExternalAdapters(unittest.TestCase):
    def test_agmarknet_adapter_offline_resilience(self):
        res = agmarknet_adapter.get_market_data(commodity="tomato")
        self.assertEqual(res["service"], "agmarknet")
        self.assertFalse(res["is_live"])
        self.assertEqual(res["status"], "offline_mode")
        self.assertIn("agmarknet.gov.in", res["official_portal"])
        self.assertIn("fluctuate continuously", res["message"])
        self.assertIn("observation_timestamp", res)

    def test_agmarknet_adapter_notified_crop_msp_reference(self):
        res_paddy = agmarknet_adapter.get_market_data(commodity="paddy")
        self.assertIsNotNone(res_paddy["reference_msp"])
        self.assertEqual(res_paddy["reference_msp"]["crop"], "Paddy (Common)")
        self.assertGreater(res_paddy["reference_msp"]["msp_inr_per_quintal"], 2000)

        res_wheat = agmarknet_adapter.get_market_data(commodity="wheat")
        self.assertIsNotNone(res_wheat["reference_msp"])
        self.assertEqual(res_wheat["reference_msp"]["crop"], "Wheat")

    def test_weather_adapter_offline_resilience(self):
        res = weather_adapter.get_weather_advisory(location="Varanasi")
        self.assertEqual(res["service"], "imd_agromet")
        self.assertFalse(res["is_live"])
        self.assertEqual(res["status"], "offline_mode")
        self.assertIn("mausam.imd.gov.in", res["official_portal"])
        self.assertIn("spray_safety_rule", res)

    def test_government_scheme_adapter_pm_kisan(self):
        res = government_scheme_adapter.get_scheme_guidance("How to apply for PM-KISAN ₹6000?")
        self.assertEqual(res["service"], "government_schemes_directory")
        self.assertIn("PM-KISAN", res["matched_scheme"])
        self.assertIn("pmkisan.gov.in", res["official_portal"])
        self.assertIn("e-KYC", res["scheme_details"]["mandatory_requirements"][1])

    def test_government_scheme_adapter_pmfby_crop_insurance(self):
        res = government_scheme_adapter.get_scheme_guidance("Crop loss flood insurance claim")
        self.assertIn("PMFBY", res["matched_scheme"])
        self.assertIn("72 hours", res["scheme_details"]["claim_intimation_window"])
        self.assertIn("pmfby.gov.in", res["official_portal"])

    def test_government_scheme_adapter_disclaimer(self):
        res = government_scheme_adapter.get_scheme_guidance("Kisan Credit Card loan")
        self.assertIn("disclaimer", res["scheme_details"])
        self.assertFalse(res["is_live"])

    def test_agmarknet_live_api_mocked_success(self):
        """Milestone 2: Verify AgmarknetAdapter handles live API responses when credentials and endpoint are present."""
        from unittest.mock import patch, MagicMock
        adapter = AgmarknetAdapter(api_endpoint="https://api.data.gov.in/resource/mock", timeout=2.0)
        adapter.api_key = "mock_key_123"

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "records": [{"commodity": "Tomato", "market": "Kolar", "modal_price": "2500", "unit": "Quintal"}]
        }

        with patch("requests.get", return_value=mock_resp), patch.dict("os.environ", {"USE_MOCK_AI": "false", "PYTEST_CURRENT_TEST": ""}):
            res = adapter.get_market_data(commodity="tomato")
            self.assertTrue(res["is_live"])
            self.assertEqual(res["status"], "live_data")
            self.assertEqual(len(res["live_records"]), 1)

    def test_weather_live_api_mocked_success(self):
        """Milestone 2: Verify WeatherAdapter handles live weather observations when configured."""
        from unittest.mock import patch, MagicMock
        adapter = WeatherAdapter(api_endpoint="https://api.openweathermap.org/data/2.5/weather", timeout=2.0)
        adapter.api_key = "mock_weather_key"

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "main": {"temp": 28.5, "humidity": 65},
            "wind": {"speed": 4.1},
        }

        with patch("requests.get", return_value=mock_resp), patch.dict("os.environ", {"USE_MOCK_AI": "false", "PYTEST_CURRENT_TEST": ""}):
            res = adapter.get_weather_advisory(location="Nagpur")
            self.assertTrue(res["is_live"])
            self.assertEqual(res["status"], "live_forecast")
            self.assertEqual(res["current_temp_c"], 28.5)
            self.assertEqual(res["humidity_pct"], 65)

    def test_government_scheme_needs_clarification_flag(self):
        """Milestone 2: Verify scheme adapter flags queries lacking essential eligibility criteria."""
        res = government_scheme_adapter.get_scheme_guidance("Tell me about PM-KISAN eligibility")
        self.assertTrue(res["needs_clarification"])
        self.assertIsNotNone(res["clarification_prompt"])
        self.assertFalse(res["formal_eligibility_determination"])
        self.assertEqual(res["last_verified_date"], "2026-03-01")

    def test_agmarknet_adapter_district_and_date_parameters(self):
        """Milestone 2: Verify AgmarknetAdapter correctly incorporates district, market, and arrival date."""
        res = agmarknet_adapter.get_market_data(
            commodity="tomato",
            state="Karnataka",
            district="Kolar",
            market="Kolar Mandi",
            date="2026-03-30",
        )
        self.assertEqual(res["district"], "Kolar")
        self.assertEqual(res["state"], "Karnataka")
        self.assertEqual(res["market"], "Kolar Mandi")
        self.assertEqual(res["arrival_date"], "2026-03-30")
        self.assertEqual(res["status"], "offline_mode")
        self.assertFalse(res["is_live"])

    def test_weather_adapter_district_and_forecast_timestamp(self):
        """Milestone 2: Verify WeatherAdapter accepts district and returns forecast timestamp and safety rule."""
        res = weather_adapter.get_weather_advisory(location="Nagpur", district="Nagpur Rural", state="Maharashtra")
        self.assertEqual(res["district"], "Nagpur Rural")
        self.assertEqual(res["state"], "Maharashtra")
        self.assertIn("forecast_timestamp", res)
        self.assertIn("spray_safety_rule", res)
        self.assertEqual(res["status"], "offline_mode")


if __name__ == "__main__":
    unittest.main()
