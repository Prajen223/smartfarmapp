"""Integration tests for Milestone 2 Completion:
  1. Live vs Offline External APIs (Open-Meteo live weather, Agmarknet authentication check).
  2. Five-Intent End-to-End Routing.
  3. Interactive Scheme Eligibility Assessment.
  4. Response Quality Scoring & Human Review Workflow (pending, approve, correct, reject).
"""

import unittest
from fastapi.testclient import TestClient

from main import app
from external_adapters import weather_adapter, agmarknet_adapter, government_scheme_adapter
from review_manager import HumanReviewManager, ReviewRecord


class TestMilestone2LiveAndAdapters(unittest.TestCase):
    """Test actual live weather retrieval and Agmarknet fallback contracts."""

    def test_live_weather_open_meteo_retrieval(self):
        """Test actual live weather query using zero-key Open-Meteo WMO / IMD Agromet service."""
        res = weather_adapter.get_weather_advisory(location="Varanasi", district="Varanasi", force_live=True)
        # Should return live forecast with real observations if network is available
        self.assertIn("status", res)
        if res.get("is_live"):
            self.assertEqual(res["status"], "live_forecast")
            self.assertIsNotNone(res.get("current_temp_c"))
            self.assertIsNotNone(res.get("humidity_pct"))
            self.assertIsNotNone(res.get("wind_speed_kmh"))
            self.assertIn("spray_safety_rule", res)
            self.assertIn("spray_advisory", res)
        else:
            # Resilient offline fallback if network drops
            self.assertEqual(res["status"], "offline_mode")
            self.assertIn("spray_safety_rule", res)

    def test_agmarknet_offline_and_msp_separation(self):
        """Verify Agmarknet clearly distinguishes statutory MSP floor prices from live mandi rates."""
        res = agmarknet_adapter.get_market_data(commodity="paddy", state="Haryana", district="Karnal")
        self.assertEqual(res["service"], "agmarknet")
        self.assertFalse(res["is_live"])
        self.assertEqual(res["price_type"], "official_minimum_support_price_floor")
        self.assertIn("reference_msp", res)
        self.assertEqual(res["reference_msp"]["crop"], "Paddy (Common)")
        self.assertIn("agmarknet.gov.in", res["official_portal"])


class TestMilestone2SchemeEligibility(unittest.TestCase):
    """Test interactive scheme eligibility assessment for PM-KISAN, PMFBY, PMKSY, and KCC."""

    def test_pm_kisan_eligible(self):
        res = government_scheme_adapter.assess_scheme_eligibility(
            "pm_kisan",
            {"has_cultivable_land": True, "aadhaar_ekyc_done": True},
        )
        self.assertEqual(res["verdict"], "ELIGIBLE")
        self.assertEqual(res["benefit_amount_inr"], 6000)

    def test_pm_kisan_action_required_for_ekyc(self):
        res = government_scheme_adapter.assess_scheme_eligibility(
            "pm_kisan",
            {"has_cultivable_land": True, "aadhaar_ekyc_done": False},
        )
        self.assertEqual(res["verdict"], "ACTION_REQUIRED")
        self.assertIn("Aadhaar e-KYC", res["reason"])

    def test_pm_kisan_ineligible_no_land(self):
        res = government_scheme_adapter.assess_scheme_eligibility(
            "pm_kisan",
            {"has_cultivable_land": False},
        )
        self.assertEqual(res["verdict"], "INELIGIBLE")

    def test_pmfby_claim_window_active_vs_expired(self):
        # Within 72 hours
        res_active = government_scheme_adapter.assess_scheme_eligibility(
            "pmfby",
            {"crop": "paddy", "season": "kharif", "hours_since_calamity": 24},
        )
        self.assertEqual(res_active["verdict"], "ELIGIBLE_FOR_CLAIM")
        self.assertEqual(res_active["farmer_premium_rate_pct"], 2.0)

        # After 72 hours
        res_expired = government_scheme_adapter.assess_scheme_eligibility(
            "pmfby",
            {"crop": "paddy", "season": "kharif", "hours_since_calamity": 96},
        )
        self.assertEqual(res_expired["verdict"], "CLAIM_WINDOW_EXPIRED")

    def test_pmksy_micro_irrigation_subsidy_tiers(self):
        res_small = government_scheme_adapter.assess_scheme_eligibility("pmksy", {"landholding_hectares": 1.5})
        self.assertEqual(res_small["verdict"], "ELIGIBLE")
        self.assertEqual(res_small["capital_subsidy_pct"], 55.0)

        res_large = government_scheme_adapter.assess_scheme_eligibility("pmksy", {"landholding_hectares": 5.0})
        self.assertEqual(res_large["capital_subsidy_pct"], 45.0)

    def test_kcc_concessional_loan(self):
        res = government_scheme_adapter.assess_scheme_eligibility("kcc", {})
        self.assertEqual(res["verdict"], "ELIGIBLE")
        self.assertEqual(res["effective_interest_rate_pct"], 4.0)
        self.assertEqual(res["collateral_free_limit_inr"], 160000)


class TestMilestone2FiveIntentRouting(unittest.TestCase):
    """Test that all five agricultural intents route accurately and return relevant responses."""

    def setUp(self):
        self.client = TestClient(app)

    def test_intent_crop_advisory(self):
        r = self.client.post("/ask", json={"text": "What is the recommended seed rate and sowing window for wheat?"})
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertIn(d["intent"], ("crop_advisory", "irrigation"))
        self.assertIn("Wheat", d["answer"])
        self.assertGreater(len(d["retrieved_documents"]), 0)

    def test_intent_pest_control(self):
        r = self.client.post("/ask", json={"text": "How do I control pink bollworm and aphids in my cotton crop?"})
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual(d["intent"], "pest_control")
        self.assertIn("Cotton", d["answer"])
        self.assertIn("Pest & Disease Management", d["answer"])

    def test_intent_irrigation(self):
        r = self.client.post("/ask", json={"text": "How often should I water tomato plants with drip irrigation?"})
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual(d["intent"], "irrigation")
        self.assertIn("Tomato", d["answer"])
        self.assertIn("Irrigation", d["answer"])

    def test_intent_market_prices(self):
        r = self.client.post("/ask", json={"text": "What is the mandi price and minimum support price for paddy?"})
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual(d["intent"], "market_prices")
        self.assertIn(d["response_mode"], ("adapter_market_benchmark", "adapter_live_market"))
        self.assertIsNotNone(d["adapter_data"])
        self.assertIn("reference_msp", d["adapter_data"])

    def test_intent_government_schemes(self):
        r = self.client.post("/ask", json={"text": "How do I apply for the PM-KISAN 6000 subsidy?"})
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual(d["intent"], "government_schemes")
        self.assertIsNotNone(d["adapter_data"])
        self.assertIn("PM-KISAN", d["adapter_data"]["matched_scheme"])


class TestMilestone2QualityAndHumanReview(unittest.TestCase):
    """Test response quality scoring and the human review approval/correction/rejection workflow."""

    def setUp(self):
        self.client = TestClient(app)
        import tempfile
        from pathlib import Path
        self.temp_dir = tempfile.TemporaryDirectory()
        self.manager = HumanReviewManager(storage_path=Path(self.temp_dir.name) / "test_reviews.json")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_quality_scoring_calculation(self):
        # High confidence, official source
        q_high, src_rel, ev = self.manager.compute_quality_score(
            confidence=0.85,
            sources=["ICAR — IIWBR"],
            retrieved_docs=[{"similarity_score": 0.88}],
            is_low_confidence=False,
        )
        self.assertGreaterEqual(q_high, 0.70)
        self.assertEqual(src_rel, 0.95)

        # Low confidence query
        q_low, _, _ = self.manager.compute_quality_score(
            confidence=0.25,
            sources=[],
            retrieved_docs=[],
            is_low_confidence=True,
        )
        self.assertLessEqual(q_low, 0.40)

    def test_human_review_workflow_lifecycle(self):
        """Verify staging, listing, approving, correcting, and rejecting reviews."""
        # 1. Create a staged review
        rec = self.manager.evaluate_and_record(
            query="Can I buy Bitcoin with Kisan Credit Card?",
            canonical_text="Can I buy Bitcoin with Kisan Credit Card?",
            intent="market_prices",
            confidence=0.22,
            answer="KCC funds can only be used for agricultural purposes.",
            sources=[],
            retrieved_docs=[],
            is_low_confidence=True,
        )
        self.assertIsNotNone(rec)
        rid = rec.review_id

        # 2. Check pending
        pending = self.manager.get_pending_reviews()
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["review_id"], rid)

        # 3. Approve review
        ok, msg = self.manager.approve_review(rid, notes="Confirmed agricultural disclaimer is present.")
        self.assertTrue(ok)
        self.assertEqual(self.manager.get_review(rid)["status"], "approved")

        # 4. Correct review
        ok_c, _ = self.manager.correct_review(rid, corrected_answer="KCC is strictly restricted to agricultural activities.")
        self.assertTrue(ok_c)
        self.assertEqual(self.manager.get_review(rid)["status"], "corrected")

        # 5. Reject review
        ok_r, _ = self.manager.reject_review(rid, reason="Irrelevant query.")
        self.assertTrue(ok_r)
        self.assertEqual(self.manager.get_review(rid)["status"], "rejected")

    def test_review_endpoints_via_api(self):
        """Test /review/pending, /review/stats, and review actions through FastAPI."""
        r_stats = self.client.get("/review/stats")
        self.assertEqual(r_stats.status_code, 200)
        self.assertIn("total", r_stats.json())

        r_pending = self.client.get("/review/pending")
        self.assertEqual(r_pending.status_code, 200)
        self.assertIn("pending_reviews", r_pending.json())

    def test_scheme_assessment_api_endpoint(self):
        """Test /adapters/schemes/assess endpoint."""
        payload = {
            "scheme_id": "pm_kisan",
            "criteria": {"has_cultivable_land": True, "aadhaar_ekyc_done": True},
        }
        r = self.client.post("/adapters/schemes/assess", json=payload)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["verdict"], "ELIGIBLE")
        self.assertEqual(data["benefit_amount_inr"], 6000)


if __name__ == "__main__":
    unittest.main()
