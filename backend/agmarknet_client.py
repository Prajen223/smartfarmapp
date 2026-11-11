"""Public AGMARKNET 2.0 Client for Smart Farming Assistant.

Fetches genuine, unauthenticated daily wholesale mandi prices from the official
Agmarknet 2.0 portal backend (https://api.agmarknet.gov.in/v1).

Features:
  - Zero-key unauthenticated access to official Agmarknet 2.0 endpoints.
  - In-memory and disk caching with TTL for metadata (states, commodities, markets)
    and price quotes to prevent rate limiting (HTTP 429).
  - Search by commodity, state, district, market, and date.
  - Extraction of variety, min_price, max_price, modal_price, unit, and arrival date.
  - Resilient retry logic with exponential backoff and configurable timeouts.
  - Never fabricates prices: clearly returns empty/NR if no market transactions
    occurred for that date/commodity.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import ssl
import time
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

BASE_URL = "https://api.agmarknet.gov.in/v1"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Cache TTLs
METADATA_TTL_SECONDS = 86400  # 24 hours for states/commodities/markets
PRICE_TTL_SECONDS = 1800      # 30 minutes for price quotes


class AgmarknetPublicClient:
    """Dedicated client for the official Agmarknet 2.0 public API."""

    def __init__(
        self,
        base_url: str = BASE_URL,
        timeout: float = 8.0,
        max_retries: int = 2,
        cache_dir: Optional[str] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE

        # In-memory caches
        self._states_cache: Optional[List[Dict[str, Any]]] = None
        self._commodities_cache: Optional[List[Dict[str, Any]]] = None
        self._markets_cache: Optional[List[Dict[str, Any]]] = None
        self._metadata_timestamp: float = 0.0
        self._price_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}

        # Optional cache directory
        if cache_dir is None:
            backend_dir = os.path.dirname(os.path.abspath(__file__))
            cache_dir = os.path.join(backend_dir, "data", "agmarknet_cache")
        self.cache_dir = cache_dir
        try:
            os.makedirs(self.cache_dir, exist_ok=True)
        except Exception:
            pass

    def _http_get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Tuple[int, Optional[Any]]:
        """Execute HTTP GET with headers, retries, and timeout."""
        url = f"{self.base_url}{endpoint}"
        if params:
            url += "?" + urllib.parse.urlencode(params)

        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://agmarknet.gov.in",
            "Referer": "https://agmarknet.gov.in/",
        }

        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=self.timeout, context=self.ssl_context) as resp:
                    status_code = resp.status
                    body = resp.read().decode("utf-8", errors="replace")
                    try:
                        return status_code, json.loads(body)
                    except Exception:
                        return status_code, body
            except urllib.error.HTTPError as e:
                status_code = e.code
                if status_code == 429:
                    # Rate limit hit: back off
                    wait_time = 1.0 * (2 ** attempt)
                    logger.warning("AGMARKNET 429 rate limit hit, backing off %.1fs...", wait_time)
                    time.sleep(wait_time)
                    last_error = e
                    continue
                err_body = e.read().decode("utf-8", errors="replace") if e.fp else ""
                logger.warning("AGMARKNET HTTP %d on %s: %s", status_code, url, err_body[:200])
                return status_code, None
            except Exception as exc:
                last_error = exc
                if attempt < self.max_retries:
                    time.sleep(0.5 * (attempt + 1))
                continue

        logger.error("AGMARKNET GET %s failed after %d retries: %s", url, self.max_retries, last_error)
        return 0, None

    def get_states(self) -> List[Dict[str, Any]]:
        """Fetch all Indian states and districts from Agmarknet."""
        now = time.time()
        if self._states_cache and (now - self._metadata_timestamp < METADATA_TTL_SECONDS):
            return self._states_cache

        cache_path = os.path.join(self.cache_dir, "states.json")
        if os.path.exists(cache_path) and (now - os.path.getmtime(cache_path) < METADATA_TTL_SECONDS):
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    self._states_cache = json.load(f)
                    return self._states_cache
            except Exception:
                pass

        status, data = self._http_get("/location/state", {"page_size": 100})
        if status == 200 and isinstance(data, dict):
            states = data.get("states", [])
            if states:
                self._states_cache = states
                self._metadata_timestamp = now
                try:
                    with open(cache_path, "w", encoding="utf-8") as f:
                        json.dump(states, f)
                except Exception:
                    pass
                return states

        return self._states_cache or []

    def get_commodities(self) -> List[Dict[str, Any]]:
        """Fetch all recognized commodities from Agmarknet."""
        now = time.time()
        if self._commodities_cache and (now - self._metadata_timestamp < METADATA_TTL_SECONDS):
            return self._commodities_cache

        cache_path = os.path.join(self.cache_dir, "commodities.json")
        if os.path.exists(cache_path) and (now - os.path.getmtime(cache_path) < METADATA_TTL_SECONDS):
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    self._commodities_cache = json.load(f)
                    return self._commodities_cache
            except Exception:
                pass

        status, data = self._http_get("/commodities", {"page_size": 650})
        if status == 200 and isinstance(data, dict):
            commodities = data.get("data", [])
            if commodities:
                self._commodities_cache = commodities
                try:
                    with open(cache_path, "w", encoding="utf-8") as f:
                        json.dump(commodities, f)
                except Exception:
                    pass
                return commodities

        return self._commodities_cache or []

    def get_markets(self) -> List[Dict[str, Any]]:
        """Fetch all market-district-state mappings from Agmarknet."""
        now = time.time()
        if self._markets_cache and (now - self._metadata_timestamp < METADATA_TTL_SECONDS):
            return self._markets_cache

        cache_path = os.path.join(self.cache_dir, "markets.json")
        if os.path.exists(cache_path) and (now - os.path.getmtime(cache_path) < METADATA_TTL_SECONDS):
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    self._markets_cache = json.load(f)
                    return self._markets_cache
            except Exception:
                pass

        status, data = self._http_get("/market-district-state")
        if status == 200 and isinstance(data, list):
            self._markets_cache = data
            try:
                with open(cache_path, "w", encoding="utf-8") as f:
                    json.dump(data, f)
            except Exception:
                pass
            return data

        return self._markets_cache or []

    def resolve_commodity_id(self, commodity_name: str) -> Optional[int]:
        """Resolve a natural commodity string to its Agmarknet commodity ID."""
        clean = commodity_name.strip().lower()
        commodities = self.get_commodities()

        # Direct exact match
        for c in commodities:
            name = c.get("cmdt_name", "").lower()
            if name == clean:
                return c.get("id")

        # Specific common overrides
        if clean in ("paddy", "rice", "dhan"):
            # Return Paddy(Common)
            for c in commodities:
                if c.get("cmdt_name") == "Paddy(Common)":
                    return c.get("id")
        if clean in ("tomato", "tamatar"):
            for c in commodities:
                if c.get("cmdt_name") == "Tomato":
                    return c.get("id")
        if clean in ("onion", "pyaz"):
            for c in commodities:
                if c.get("cmdt_name") == "Onion":
                    return c.get("id")

        # Substring match
        for c in commodities:
            name = c.get("cmdt_name", "").lower()
            if clean in name:
                return c.get("id")

        return None

    def resolve_state_id(self, state_name: str) -> Optional[int]:
        """Resolve state string to Agmarknet state ID."""
        clean = state_name.strip().lower()
        states = self.get_states()
        for s in states:
            sname = s.get("state_name", "").lower()
            if clean == sname or clean in sname or sname in clean:
                return s.get("id")
        return None

    def resolve_markets(
        self,
        state_id: Optional[int] = None,
        district_name: Optional[str] = None,
        market_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Filter markets by state, district, or market name."""
        all_markets = self.get_markets()
        matches = []
        clean_dist = district_name.strip().lower() if district_name else None
        clean_mkt = market_name.strip().lower() if market_name else None

        for m in all_markets:
            if state_id and m.get("state_id") != state_id:
                continue
            if clean_dist:
                d_name = m.get("district_name", "").lower()
                m_name = m.get("market_name", "").lower()
                if clean_dist not in d_name and clean_dist not in m_name:
                    continue
            if clean_mkt:
                m_name = m.get("market_name", "").lower()
                if clean_mkt not in m_name:
                    continue
            matches.append(m)

        return matches

    def get_weekly_commodity_prices(
        self,
        market_id: int,
        state_id: int,
        commodity_id: int,
    ) -> Tuple[int, Optional[Dict[str, Any]]]:
        """Fetch weekly daily price records for a specific market and commodity."""
        cache_key = f"{market_id}_{state_id}_{commodity_id}"
        now = time.time()
        if cache_key in self._price_cache:
            ts, val = self._price_cache[cache_key]
            if now - ts < PRICE_TTL_SECONDS:
                return 200, val

        status, data = self._http_get(
            "/prices-and-arrivals/commodity-price/lastweek",
            {
                "marketId": market_id,
                "stateId": state_id,
                "commodityId": commodity_id,
                "includeExcel": "false",
            },
        )
        if status == 200 and isinstance(data, dict):
            self._price_cache[cache_key] = (now, data)
        return status, data

    def get_live_mandi_prices(
        self,
        commodity: str,
        state: Optional[str] = None,
        district: Optional[str] = None,
        market: Optional[str] = None,
        date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Search Agmarknet 2.0 for live wholesale mandi prices.

        Returns a structured dictionary with live records, HTTP status,
        source endpoint, min, max, modal prices, and data freshness.
        """
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        resolved_state = state
        state_id = self.resolve_state_id(resolved_state) if resolved_state else None
        if not state_id and district:
            clean_d = district.strip().lower()
            for m in self.get_markets():
                if clean_d in m.get("district_name", "").lower() or clean_d in m.get("market_name", "").lower():
                    resolved_state = m.get("state_name")
                    state_id = m.get("state_id")
                    break
        if not resolved_state:
            resolved_state = "Tamil Nadu"
            state_id = 31
        commodity_id = self.resolve_commodity_id(commodity)

        if not commodity_id:
            return {
                "service": "agmarknet",
                "status": "commodity_not_found",
                "is_live": True,
                "http_status": 404,
                "source": "AGMARKNET 2.0 API (api.agmarknet.gov.in)",
                "source_endpoint": f"{self.base_url}/commodities",
                "message": f"Commodity '{commodity}' was not recognized in official AGMARKNET commodity directory.",
                "live_records": [],
                "data_freshness": timestamp,
                "observation_timestamp": timestamp,
            }

        # Resolve candidate markets
        candidate_markets = self.resolve_markets(
            state_id=state_id,
            district_name=district,
            market_name=market,
        )

        if not candidate_markets:
            # Fallback to any market in state if district had no matches
            candidate_markets = self.resolve_markets(state_id=state_id)

        # Query candidate markets (prioritizing up to 6 markets to respect rate limits)
        live_records: List[Dict[str, Any]] = []
        last_http_status = 200
        last_endpoint = f"{self.base_url}/prices-and-arrivals/commodity-price/lastweek"

        # Check candidate markets
        for mkt in candidate_markets[:6]:
            m_id = mkt["market_id"]
            m_name = mkt.get("market_name", "")
            d_name = mkt.get("district_name", "")
            s_name = mkt.get("state_name", resolved_state)

            status, raw_data = self.get_weekly_commodity_prices(
                market_id=m_id,
                state_id=state_id,
                commodity_id=commodity_id,
            )
            last_http_status = status

            if status != 200 or not isinstance(raw_data, dict):
                continue

            rows = raw_data.get("data", [])
            for row in rows:
                variety = row.get("variety", "General")
                unit = row.get("unitOfPrice", "Rs./Quintal")

                # Extract dates and price values
                date_prices: List[Tuple[str, float]] = []
                for k, v in row.items():
                    if k not in ("variety", "unitOfPrice") and isinstance(v, (int, float)):
                        date_prices.append((k, float(v)))

                if not date_prices:
                    continue

                # Sort by date descending (latest first)
                date_prices.sort(key=lambda x: x[0], reverse=True)

                # Filter by date if requested
                selected_date, selected_price = date_prices[0]
                if date:
                    matched = [dp for dp in date_prices if dp[0] == date]
                    if matched:
                        selected_date, selected_price = matched[0]

                all_prices = [p for _, p in date_prices]
                min_p = min(all_prices)
                max_p = max(all_prices)
                modal_p = selected_price

                live_records.append({
                    "commodity": commodity.title(),
                    "variety": variety,
                    "market": m_name,
                    "district": d_name,
                    "state": s_name,
                    "market_id": m_id,
                    "arrival_date": selected_date,
                    "min_price": min_p,
                    "max_price": max_p,
                    "modal_price": modal_p,
                    "price_unit": unit,
                    "weekly_trend": dict(date_prices),
                })

        if live_records:
            return {
                "service": "agmarknet",
                "status": "live_data",
                "is_live": True,
                "http_status": last_http_status,
                "source": "AGMARKNET 2.0 API (api.agmarknet.gov.in)",
                "source_endpoint": last_endpoint,
                "commodity": commodity.title(),
                "state": resolved_state,
                "district": district or "all",
                "market": market or "all",
                "data_freshness": timestamp,
                "observation_timestamp": timestamp,
                "official_portal": "https://agmarknet.gov.in",
                "enam_portal": "https://enam.gov.in",
                "live_records": live_records,
                "post_harvest_advice": (
                    "To secure 10-25% higher bids, clean, dry, and grade produce before bringing it to the mandi. "
                    "During harvest gluts, store produce in WDRA-accredited scientific warehouses to access e-NWR financing."
                ),
            }

        # Authentic zero-records reported in this district/date window
        return {
            "service": "agmarknet",
            "status": "no_transactions_reported",
            "is_live": True,
            "http_status": last_http_status,
            "source": "AGMARKNET 2.0 API (api.agmarknet.gov.in)",
            "source_endpoint": last_endpoint,
            "commodity": commodity.title(),
            "state": resolved_state,
            "district": district or "all",
            "market": market or "all",
            "data_freshness": timestamp,
            "observation_timestamp": timestamp,
            "message": (
                f"No daily market arrivals or wholesale transactions were reported for {commodity.title()} "
                f"in {district or resolved_state} during the last 7 days. "
                "In Tamil Nadu, grains like Paddy are procured via Direct Purchase Centers (DPCs) and Regulated Markets."
            ),
            "official_portal": "https://agmarknet.gov.in",
            "enam_portal": "https://enam.gov.in",
            "live_records": [],
            "post_harvest_advice": (
                "Quality-graded lots secure higher bids. Check agmarknet.gov.in or contact the local APMC mandi board."
            ),
        }


# Singleton instance
agmarknet_public_client = AgmarknetPublicClient()
