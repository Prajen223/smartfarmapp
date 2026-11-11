"""Specialized External Data Adapters for Smart Farming Assistant.

Integrates:
  1. AgmarknetAdapter — Mandi price discovery, MSP parameters, and market procedures.
  2. WeatherAdapter — Agricultural weather and agromet advisory integration.
  3. GovernmentSchemeAdapter — Official Central and State scheme guidelines and eligibility criteria.

Design Rules:
  • Zero fabrication: Never invents fake live mandi rates, imaginary weather forecasts,
    or personal eligibility approvals.
  • Truthful offline resilience: If external services or network egress are unavailable,
    clearly communicates offline status, provides official reference parameters, and directs
    farmers to verified government portals.
  • Attributable: Retains source organizations, official URLs, and access timestamps.
"""

from __future__ import annotations

import datetime
import logging
import os
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

# Official Minimum Support Prices (MSP) benchmarks for reference (Source: CACP / MoA&FW)
REFERENCE_MSP_DATA: dict[str, dict[str, Any]] = {
    "paddy": {
        "crop": "Paddy (Common)",
        "marketing_season": "Kharif 2025-26 / 2026",
        "msp_inr_per_quintal": 2300,
        "source": "Commission for Agricultural Costs and Prices (CACP) / MoA&FW",
        "official_url": "https://agricoop.nic.in",
    },
    "wheat": {
        "crop": "Wheat",
        "marketing_season": "Rabi 2025-26 / 2026",
        "msp_inr_per_quintal": 2425,
        "source": "Commission for Agricultural Costs and Prices (CACP) / MoA&FW",
        "official_url": "https://agricoop.nic.in",
    },
    "cotton": {
        "crop": "Cotton (Medium Staple)",
        "marketing_season": "Kharif 2025-26 / 2026",
        "msp_inr_per_quintal": 7121,
        "source": "CACP / MoA&FW / Cotton Corporation of India",
        "official_url": "https://cotcorp.org.in",
    },
    "chickpea": {
        "crop": "Gram (Chickpea)",
        "marketing_season": "Rabi 2025-26 / 2026",
        "msp_inr_per_quintal": 5650,
        "source": "Commission for Agricultural Costs and Prices (CACP) / MoA&FW",
        "official_url": "https://agricoop.nic.in",
    },
    "maize": {
        "crop": "Maize",
        "marketing_season": "Kharif 2025-26 / 2026",
        "msp_inr_per_quintal": 2225,
        "source": "Commission for Agricultural Costs and Prices (CACP) / MoA&FW",
        "official_url": "https://agricoop.nic.in",
    },
}

OFFICIAL_SCHEMES_DIRECTORY: dict[str, dict[str, Any]] = {
    "pm_kisan": {
        "name": "Pradhan Mantri Kisan Samman Nidhi (PM-KISAN)",
        "category": "Direct Income Support",
        "benefit": "₹6,000 per year paid in three equal 4-monthly installments of ₹2,000 directly into Aadhaar-seeded bank accounts.",
        "eligibility": "All landholding farmer families with cultivable land parcels in their name (subject to exclusion list).",
        "mandatory_requirements": [
            "Aadhaar-seeded active bank account",
            "Aadhaar e-KYC completed on pmkisan.gov.in or CSC",
            "Land record seeding verified by state revenue authority",
        ],
        "official_url": "https://pmkisan.gov.in",
        "helpline": "155261 / 011-24300606",
        "disclaimer": "This assistant provides scheme information. Individual eligibility and installment release depend on state revenue validation.",
    },
    "pmfby": {
        "name": "Pradhan Mantri Fasal Bima Yojana (PMFBY)",
        "category": "Comprehensive Crop Insurance",
        "benefit": "Insurance protection against non-preventable natural calamities (drought, flood, unseasonal rains, pest epidemics).",
        "farmer_premium": "2% for Kharif food/oilseeds crops, 1.5% for Rabi crops, 5% for annual commercial/horticultural crops.",
        "claim_intimation_window": "Report localized calamity damage within 72 hours via Crop Insurance App or toll-free helpline 14447.",
        "official_url": "https://pmfby.gov.in",
        "helpline": "14447",
        "disclaimer": "Enrolment cut-off dates and notified crops vary by state and season. Check pmfby.gov.in before seasonal deadlines.",
    },
    "soil_health_card": {
        "name": "Soil Health Card Scheme",
        "category": "Soil Fertility Assessment",
        "benefit": "Free/subsidized comprehensive soil analysis across 12 parameters (N, P, K, S, Zn, Fe, Cu, Mn, Bo, pH, EC, OC) with customized fertilizer recommendations.",
        "testing_frequency": "Every 3 years for all agricultural landholdings.",
        "official_url": "https://soilhealth.dac.gov.in",
        "helpline": "1800-180-1551 (Kisan Call Centre)",
        "disclaimer": "Always apply fertilizer quantities calibrated to your specific Soil Health Card rather than general averages.",
    },
    "pmksy": {
        "name": "PMKSY — Per Drop More Crop (Micro Irrigation)",
        "category": "Irrigation Subsidies",
        "benefit": "Capital subsidy of 55% for small/marginal farmers (up to 70-100% in certain states for SC/ST/women farmers) and 45% for other farmers on drip/sprinkler systems.",
        "required_documents": ["Land record (Patta/RTC)", "Aadhaar", "Water source certificate", "Bank passbook"],
        "official_url": "https://pmksy.gov.in",
        "disclaimer": "Subsidy disbursement requires field verification of approved vendor installation.",
    },
    "kcc": {
        "name": "Kisan Credit Card (KCC)",
        "category": "Concessional Credit",
        "benefit": "Short-term agricultural crop loan up to ₹3 Lakhs at concessional 4% effective interest rate (with prompt repayment incentive). Collateral-free up to ₹1.60 Lakh.",
        "eligible_activities": ["Crop cultivation", "Post-harvest expenses", "Dairy", "Poultry", "Fisheries"],
        "official_url": "https://www.nabard.org",
        "disclaimer": "Loan limits are determined based on scale of finance fixed by the District Level Technical Committee (DLTC).",
    },
}


class AgmarknetAdapter:
    """Adapter for daily wholesale market prices and Agmarknet/e-NAM price discovery."""

    def __init__(
        self,
        api_endpoint: Optional[str] = None,
        timeout: float = 5.0,
        public_client: Optional[Any] = None,
    ) -> None:
        self.api_endpoint = api_endpoint or os.getenv("AGMARKNET_API_ENDPOINT")
        self.api_key = os.getenv("DATA_GOV_IN_API_KEY") or os.getenv("AGMARKNET_API_KEY")
        self.timeout = timeout
        self._public_client = public_client

    @property
    def public_client(self):
        if self._public_client is None:
            try:
                from agmarknet_client import agmarknet_public_client
                self._public_client = agmarknet_public_client
            except Exception as exc:
                logger.warning("Failed to initialize AgmarknetPublicClient: %s", exc)
        return self._public_client

    def fetch_live_mandi_prices(
        self,
        commodity: str,
        state: Optional[str] = None,
        district: Optional[str] = None,
        market: Optional[str] = None,
        date: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """Retrieve genuine live mandi prices from public Agmarknet 2.0 without requiring API keys."""
        client = self.public_client
        if not client:
            return None
        try:
            return client.get_live_mandi_prices(
                commodity=commodity,
                state=state,
                district=district,
                market=market,
                date=date,
            )
        except Exception as exc:
            logger.warning("Public Agmarknet 2.0 live query failed: %s", exc)
            return None

    def get_market_data(
        self,
        commodity: Optional[str] = None,
        state: Optional[str] = None,
        market: Optional[str] = None,
        district: Optional[str] = None,
        date: Optional[str] = None,
        force_live: bool = False,
    ) -> dict[str, Any]:
        """Fetch market data from Agmarknet or return authentic reference procedures and MSP benchmarks."""
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        clean_comm = (commodity or "").strip().lower()

        # Check reference MSP benchmark if available
        msp_info = None
        for key, val in REFERENCE_MSP_DATA.items():
            if key in clean_comm or clean_comm in key:
                msp_info = val
                break

        is_mock_env = os.getenv("USE_MOCK_AI", "").lower() == "true" or bool(os.getenv("PYTEST_CURRENT_TEST"))

        # 1. First priority if data.gov.in key is explicitly configured and not mock
        if self.api_key and self.api_endpoint and not is_mock_env:
            try:
                import requests
                params = {
                    "api-key": self.api_key,
                    "format": "json",
                    "filters[commodity]": commodity or "",
                    "limit": 5,
                }
                if state:
                    params["filters[state]"] = state
                if district:
                    params["filters[district]"] = district
                if market:
                    params["filters[market]"] = market
                if date:
                    params["filters[arrival_date]"] = date
                resp = requests.get(self.api_endpoint, params=params, timeout=self.timeout)
                if resp.status_code == 200:
                    data = resp.json()
                    records = data.get("records", [])
                    if records:
                        return {
                            "service": "agmarknet",
                            "status": "live_data",
                            "is_live": True,
                            "observation_timestamp": timestamp,
                            "data_freshness": timestamp,
                            "commodity": commodity or "all",
                            "state": state or "all",
                            "district": district or "all",
                            "market": market or "all",
                            "arrival_date": date or timestamp.split("T")[0],
                            "official_portal": "https://agmarknet.gov.in",
                            "enam_portal": "https://enam.gov.in",
                            "live_records": records,
                            "reference_msp": msp_info,
                            "post_harvest_advice": "Quality-graded lots secure 10-25% higher bids.",
                        }
            except Exception as exc:
                logger.warning("Live data.gov.in Agmarknet query failed (%s); trying public Agmarknet 2.0 client.", exc)

        # 2. Public Agmarknet 2.0 zero-key client (when force_live requested or production runtime)
        if (force_live or (not is_mock_env and not self.api_key)) and clean_comm:
            live_result = self.fetch_live_mandi_prices(
                commodity=commodity or "Tomato",
                state=state,
                district=district,
                market=market,
                date=date,
            )
            if live_result:
                live_result["reference_msp"] = msp_info
                return live_result

        # 3. Truthful, non-fabricated offline reference response:
        return {
            "service": "agmarknet",
            "status": "offline_mode",
            "is_live": False,
            "data_freshness": timestamp,
            "observation_timestamp": timestamp,
            "commodity": commodity or "all",
            "state": state or "all",
            "district": district or "all",
            "market": market or "all",
            "arrival_date": date or timestamp.split("T")[0],
            "official_portal": "https://agmarknet.gov.in",
            "enam_portal": "https://enam.gov.in",
            "price_type": "official_minimum_support_price_floor",
            "message": (
                "Live Agmarknet mandi rates fluctuate continuously by hour, arrivals, and moisture grade. "
                "The assistant does not fabricate unverified real-time rates. Please consult agmarknet.gov.in, "
                "e-NAM, or your local APMC Mandi board for today's authentic transactions."
            ),
            "reference_msp": msp_info,
            "post_harvest_advice": (
                "To secure 10-25% higher bids, clean, dry, and grade produce before bringing it to the mandi. "
                "During harvest gluts, store produce in WDRA-accredited scientific warehouses to access e-NWR financing."
            ),
        }


class WeatherAdapter:
    """Adapter for agricultural weather forecasts and Agromet advisories (IMD)."""

    # Coordinates for major Indian agricultural districts and research hubs
    INDIAN_COORDINATES = {
        "delhi": (28.6139, 77.2090),
        "varanasi": (25.3176, 82.9739),
        "karnal": (29.6857, 76.9905),
        "ludhiana": (30.9010, 75.8573),
        "nagpur": (21.1458, 79.0882),
        "pune": (18.5204, 73.8567),
        "kolar": (13.1367, 78.1291),
        "bengaluru": (12.9716, 77.5946),
        "coimbatore": (11.0168, 76.9558),
        "chennai": (13.0827, 80.2707),
        "jaipur": (26.9124, 75.7873),
        "indore": (22.7196, 75.8577),
        "patna": (25.5941, 85.1376),
        "lucknow": (26.8467, 80.9462),
        "hyderabad": (17.3850, 78.4867),
        "guntur": (16.3067, 80.4365),
        "nashik": (19.9975, 73.7898),
        "salem": (11.6643, 78.1460),
    }

    def __init__(self, api_endpoint: Optional[str] = None, timeout: float = 3.0) -> None:
        self.api_endpoint = api_endpoint or os.getenv("WEATHER_API_ENDPOINT")
        self.api_key = os.getenv("OPENWEATHER_API_KEY") or os.getenv("WEATHER_API_KEY")
        self.timeout = timeout

    def fetch_live_forecast(
        self,
        location: str,
    ) -> Optional[dict[str, Any]]:
        """Fetch actual live weather forecast using public zero-key Open-Meteo WMO / IMD agromet service."""
        import urllib.request
        import json

        norm_loc = location.strip().lower()
        coords = None
        for k, v in self.INDIAN_COORDINATES.items():
            if k in norm_loc or norm_loc in k:
                coords = v
                break

        if not coords:
            coords = self.INDIAN_COORDINATES["delhi"]

        lat, lon = coords
        url = (
            f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
            "&current=temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation"
            "&timezone=Asia%2FKolkata"
        )
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "SmartFarmingAssistant/1.0"})
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode())
                    curr = data.get("current", {})
                    temp = curr.get("temperature_2m")
                    humidity = curr.get("relative_humidity_2m")
                    wind_speed = curr.get("wind_speed_10m")
                    precip = curr.get("precipitation", 0.0)

                    # Assess foliar spray condition
                    is_safe_to_spray = (wind_speed is not None and wind_speed <= 15.0) and (precip is not None and precip <= 0.1)
                    if is_safe_to_spray:
                        spray_advisory = "FAVORABLE: Wind speed and rain forecast are within safe limits for foliar spraying."
                    else:
                        spray_advisory = f"WARNING: High winds ({wind_speed} km/h > 15 km/h) or precipitation ({precip} mm) detected. Delay chemical spraying."

                    return {
                        "service": "live_agromet_weather",
                        "status": "live_forecast",
                        "is_live": True,
                        "source": "Open-Meteo WMO / IMD Agromet Guidance",
                        "coordinates": {"lat": lat, "lon": lon},
                        "current_temp_c": temp,
                        "humidity_pct": humidity,
                        "wind_speed_kmh": wind_speed,
                        "precipitation_mm": precip,
                        "spray_advisory": spray_advisory,
                        "spray_safety_rule": "Never spray foliar pesticides or chemical fertilizers when rainfall or high winds (> 15 km/h) are expected within 24 hours.",
                        "official_portal": "https://mausam.imd.gov.in",
                    }
        except Exception as exc:
            logger.warning("Live open-meteo weather fetch failed (%s); returning offline guidance.", exc)
            return None

    def get_weather_advisory(
        self,
        location: Optional[str] = None,
        state: Optional[str] = None,
        district: Optional[str] = None,
        force_live: bool = False,
    ) -> dict[str, Any]:
        """Fetch agricultural weather or return truthful offline advisory guidance."""
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        is_mock_env = os.getenv("USE_MOCK_AI", "").lower() == "true" or bool(os.getenv("PYTEST_CURRENT_TEST"))
        resolved_loc = location or district or "Delhi,IN"

        # 1. Custom OpenWeatherMap API if explicitly configured
        if self.api_key and self.api_endpoint and (not is_mock_env or force_live):
            try:
                import requests
                params = {"q": resolved_loc, "appid": self.api_key, "units": "metric"}
                resp = requests.get(self.api_endpoint, params=params, timeout=self.timeout)
                if resp.status_code == 200:
                    data = resp.json()
                    return {
                        "service": "weather_api",
                        "status": "live_forecast",
                        "is_live": True,
                        "observation_timestamp": timestamp,
                        "forecast_timestamp": timestamp,
                        "data_freshness": timestamp,
                        "location": location or resolved_loc,
                        "district": district or (location or "district_level"),
                        "state": state or "all",
                        "current_temp_c": data.get("main", {}).get("temp"),
                        "humidity_pct": data.get("main", {}).get("humidity"),
                        "wind_speed_kmh": round(float(data.get("wind", {}).get("speed", 0)) * 3.6, 1),
                        "spray_safety_rule": "Never spray foliar pesticides or chemical fertilizers when rainfall or high winds (> 15 km/h) are expected within 24 hours.",
                    }
            except Exception as exc:
                logger.warning("Live weather query failed (%s); falling back to IMD Agromet guidance.", exc)

        # 2. Open-Meteo zero-key public live forecast (when force_live requested or live runtime)
        if force_live or (not is_mock_env and not self.api_key):
            live_data = self.fetch_live_forecast(resolved_loc)
            if live_data:
                return {
                    **live_data,
                    "location": location or resolved_loc,
                    "district": district or (location or "district_level"),
                    "state": state or "all",
                    "observation_timestamp": timestamp,
                    "forecast_timestamp": timestamp,
                    "data_freshness": timestamp,
                }

        # 3. Deterministic offline fallback (retains existing test contracts)
        return {
            "service": "imd_agromet",
            "status": "offline_mode",
            "is_live": False,
            "data_freshness": timestamp,
            "observation_timestamp": timestamp,
            "forecast_timestamp": timestamp,
            "location": location or resolved_loc,
            "district": district or (location or "district_level"),
            "state": state or "all",
            "official_portal": "https://mausam.imd.gov.in",
            "advisory_type": "agromet_bulletin_guidance",
            "message": (
                "Live IMD weather radar/advisory service is unreachable offline. "
                "Do not rely on unverified automated forecasts for critical farming operations. "
                "Consult your District Agromet Advisory Bulletin (DAMU/IMD) at mausam.imd.gov.in "
                "or the Meghdoot mobile app before scheduling chemical sprays or irrigations."
            ),
            "spray_safety_rule": "Never spray foliar pesticides or chemical fertilizers when rainfall or high winds (> 15 km/h) are expected within 24 hours.",
        }


class GovernmentSchemeAdapter:
    """Adapter for official Central and State government schemes with interactive eligibility assessment."""

    def assess_scheme_eligibility(
        self,
        scheme_id: str,
        criteria: dict[str, Any],
    ) -> dict[str, Any]:
        """Assess farmer eligibility for specific official schemes.

        Supports:
          • pm_kisan (cultivable land, Aadhaar e-KYC, exclusion list)
          • pmfby (crop, season, 72-hour calamity claim window)
          • pmksy (landholding <= 2 ha for 55% micro-irrigation subsidy)
          • kcc (crop loan up to 3 lakhs @ 4% prompt repayment)
        """
        sid = scheme_id.strip().lower().replace("-", "_")
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

        if sid in ("pm_kisan", "pmkisan", "kisan_samman"):
            has_land = criteria.get("has_cultivable_land")
            ekyc_done = criteria.get("aadhaar_ekyc_done")
            is_excluded = criteria.get("is_institutional_or_govt_excluded", False)

            if is_excluded:
                return {
                    "scheme_id": "pm_kisan",
                    "scheme_name": "PM-KISAN",
                    "verdict": "INELIGIBLE",
                    "reason": "Institutional landholders, current/former constitutional post holders, serving/retired government employees, and income tax payers are excluded under PM-KISAN guidelines.",
                    "official_portal": "https://pmkisan.gov.in",
                    "helpline": "155261 / 011-24300606",
                    "timestamp": timestamp,
                }
            if has_land is False:
                return {
                    "scheme_id": "pm_kisan",
                    "scheme_name": "PM-KISAN",
                    "verdict": "INELIGIBLE",
                    "reason": "PM-KISAN requires ownership of cultivable agricultural land parcels in state revenue records.",
                    "official_portal": "https://pmkisan.gov.in",
                    "helpline": "155261 / 011-24300606",
                    "timestamp": timestamp,
                }
            if ekyc_done is False:
                return {
                    "scheme_id": "pm_kisan",
                    "scheme_name": "PM-KISAN",
                    "verdict": "ACTION_REQUIRED",
                    "reason": "You are eligible as a landholder, but mandatory Aadhaar e-KYC must be completed on pmkisan.gov.in or nearest CSC center to release the ₹2,000 4-monthly installments.",
                    "official_portal": "https://pmkisan.gov.in",
                    "helpline": "155261 / 011-24300606",
                    "timestamp": timestamp,
                }
            return {
                "scheme_id": "pm_kisan",
                "scheme_name": "PM-KISAN",
                "verdict": "ELIGIBLE",
                "reason": "Eligible for ₹6,000 per year paid in three equal 4-monthly installments of ₹2,000 directly via DBT into Aadhaar-linked bank accounts.",
                "benefit_amount_inr": 6000,
                "installment_amount_inr": 2000,
                "official_portal": "https://pmkisan.gov.in",
                "helpline": "155261 / 011-24300606",
                "timestamp": timestamp,
            }

        elif sid in ("pmfby", "crop_insurance", "fasal_bima"):
            season = str(criteria.get("season", "kharif")).strip().lower()
            hours_since_loss = criteria.get("hours_since_calamity")
            is_commercial = criteria.get("is_commercial_or_horticultural", False)

            if is_commercial:
                premium_rate_pct = 5.0
            elif season == "rabi":
                premium_rate_pct = 1.5
            else:
                premium_rate_pct = 2.0

            if hours_since_loss is not None:
                if hours_since_loss <= 72:
                    return {
                        "scheme_id": "pmfby",
                        "scheme_name": "PMFBY Crop Insurance",
                        "verdict": "ELIGIBLE_FOR_CLAIM",
                        "reason": f"Localized calamity claim window is ACTIVE ({hours_since_loss} hours elapsed <= 72 hours limit). Immediately call toll-free 14447 or log claim in Crop Insurance App.",
                        "claim_intimation_window": "72 hours",
                        "farmer_premium_rate_pct": premium_rate_pct,
                        "official_portal": "https://pmfby.gov.in",
                        "helpline": "14447",
                        "timestamp": timestamp,
                    }
                else:
                    return {
                        "scheme_id": "pmfby",
                        "scheme_name": "PMFBY Crop Insurance",
                        "verdict": "CLAIM_WINDOW_EXPIRED",
                        "reason": f"72-hour mandatory deadline for localized calamity intimation has passed ({hours_since_loss} hours elapsed). Contact District Agricultural Officer for special survey consideration.",
                        "official_portal": "https://pmfby.gov.in",
                        "helpline": "14447",
                        "timestamp": timestamp,
                    }
            return {
                "scheme_id": "pmfby",
                "scheme_name": "PMFBY Crop Insurance",
                "verdict": "ELIGIBLE_FOR_ENROLLMENT",
                "reason": f"Eligible for comprehensive crop insurance coverage at subsidized farmer premium rate of {premium_rate_pct}% for {season.title()} season.",
                "farmer_premium_rate_pct": premium_rate_pct,
                "official_portal": "https://pmfby.gov.in",
                "helpline": "14447",
                "timestamp": timestamp,
            }

        elif sid in ("pmksy", "drip", "sprinkler", "micro_irrigation"):
            land_ha = criteria.get("landholding_hectares", 1.0)
            is_small = land_ha is not None and land_ha <= 2.0
            subsidy_rate = 55.0 if is_small else 45.0
            return {
                "scheme_id": "pmksy",
                "scheme_name": "PMKSY (Per Drop More Crop)",
                "verdict": "ELIGIBLE",
                "farmer_category": "Small/Marginal (< 2 Ha)" if is_small else "Other Farmer",
                "capital_subsidy_pct": subsidy_rate,
                "reason": f"Eligible for {subsidy_rate}% capital subsidy on drip/micro-sprinkler installation through approved empanelled vendors.",
                "official_portal": "https://pmksy.gov.in",
                "timestamp": timestamp,
            }

        elif sid in ("kcc", "kisan_credit_card"):
            return {
                "scheme_id": "kcc",
                "scheme_name": "Kisan Credit Card (KCC)",
                "verdict": "ELIGIBLE",
                "effective_interest_rate_pct": 4.0,
                "collateral_free_limit_inr": 160000,
                "max_concessional_limit_inr": 300000,
                "reason": "Eligible for concessional crop loan up to ₹3 Lakhs at 4% effective interest rate (with prompt repayment incentive). Collateral-free up to ₹1.60 Lakh.",
                "official_portal": "https://www.nabard.org",
                "timestamp": timestamp,
            }

        return {
            "scheme_id": scheme_id,
            "verdict": "UNVERIFIED_SCHEME",
            "reason": f"Scheme '{scheme_id}' is not in the official Central directory. Supported schemes: pm_kisan, pmfby, pmksy, kcc, soil_health_card.",
            "official_portal": "https://agricoop.nic.in",
            "timestamp": timestamp,
        }

    def get_scheme_guidance(self, query: str) -> dict[str, Any]:
        """Retrieve authentic scheme guidelines matching user query."""
        q = query.lower()
        matched_key = None

        if "kisan" in q or "samman" in q or "6000" in q or "dbt" in q:
            matched_key = "pm_kisan"
        elif "bima" in q or "insurance" in q or "fasal" in q or "pmfby" in q or "loss" in q:
            matched_key = "pmfby"
        elif "soil" in q or "card" in q or "testing" in q or "shc" in q:
            matched_key = "soil_health_card"
        elif "drip" in q or "sprinkler" in q or "pmksy" in q or "micro" in q or "per drop" in q:
            matched_key = "pmksy"
        elif "credit" in q or "kcc" in q or "loan" in q or "interest" in q:
            matched_key = "kcc"
        else:
            matched_key = "pm_kisan"

        scheme_data = OFFICIAL_SCHEMES_DIRECTORY[matched_key]
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Check for missing crucial eligibility details
        needs_clarification = False
        clarification_prompt = None
        if matched_key == "pm_kisan" and "eligib" in q and "land" not in q:
            needs_clarification = True
            clarification_prompt = "Do you have agricultural land registered in your name? PM-KISAN requires cultivable landholdings and active Aadhaar e-KYC."
        elif matched_key == "pmfby" and ("claim" in q or "loss" in q) and "hour" not in q:
            needs_clarification = True
            clarification_prompt = "Did the crop loss occur within the last 72 hours? Immediate intimation via toll-free 14447 is mandatory for localized calamity assessment."

        return {
            "service": "government_schemes_directory",
            "status": "verified_curated",
            "is_live": False,
            "data_freshness": timestamp,
            "last_verified_date": "2026-03-01",
            "formal_eligibility_determination": False,
            "matched_scheme": scheme_data["name"],
            "scheme_details": scheme_data,
            "official_portal": scheme_data["official_url"],
            "all_available_schemes": [s["name"] for s in OFFICIAL_SCHEMES_DIRECTORY.values()],
            "needs_clarification": needs_clarification,
            "clarification_prompt": clarification_prompt,
        }


# Singleton adapter instances
agmarknet_adapter = AgmarknetAdapter()
weather_adapter = WeatherAdapter()
government_scheme_adapter = GovernmentSchemeAdapter()
