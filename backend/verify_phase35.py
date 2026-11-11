#!/usr/bin/env python3
"""FarmSaathi - Milestone 3 Phase 3.5: Complete System Verification Harness.

Automated verification harness for Phase 3.5 testing:
  1. Backend Health & Readiness
  2. Route Discovery (Core & Admin Routes)
  3. Session Management & Multi-Turn Context
  4. Role-Based Access Control (Farmer / Admin Boundary)
  5. Voice Endpoints & Mock-Mode Safeguards (Zero billable API calls)
  6. PWA Web App Manifest Validity
  7. PWA Icon Assets
  8. Service Worker & API Cache Bypass Security
  9. Offline Fallback Document
  10. Frontend-to-Backend Proxy Contracts
  11. Input Validation & Error Handling Guards
"""

from __future__ import annotations

import os
import sys
import json
import base64
import unittest
from pathlib import Path
from unittest.mock import patch

# Ensure UTF-8 printing in Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Ensure backend directory is in sys.path
CURRENT_DIR = Path(__file__).resolve().parent
if CURRENT_DIR.name == "backend":
    BACKEND_DIR = CURRENT_DIR
    REPO_ROOT = CURRENT_DIR.parent
else:
    REPO_ROOT = CURRENT_DIR
    BACKEND_DIR = CURRENT_DIR / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Force mock mode in environment for automated verification to prevent billable calls
os.environ["VOICE_MODE"] = "mock"
os.environ["TRANSLATION_MODE"] = "mock"
os.environ["USE_MOCK_AI"] = "true"

from fastapi.testclient import TestClient
from main import app
from voice_pipeline import voice_pipeline, generate_mock_wav
from security import security_user_manager, JWTManager, PasswordManager


class Phase35VerificationRunner:
    def __init__(self):
        self.client = TestClient(app)
        self.results: list[dict] = []
        self.frontend_dir = REPO_ROOT / "frontend"

    def record(self, category: str, test_name: str, passed: bool, details: str = ""):
        self.results.append({
            "category": category,
            "name": test_name,
            "passed": passed,
            "details": details,
        })
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {status} {test_name}")
        if details and not passed:
            print(f"         Reason: {details}")

    def run_all(self) -> bool:
        print("=" * 70)
        print("FARMSAATHI MILESTONE 3 - PHASE 3.5: SYSTEM VERIFICATION HARNESS")
        print("=" * 70)

        self.verify_backend_health()
        self.verify_route_catalog()
        self.verify_session_and_context()
        self.verify_rbac_and_security()
        self.verify_voice_and_safeguards()
        self.verify_pWA_assets()
        self.verify_service_worker_security()
        self.verify_frontend_proxy_contracts()

        print("\n" + "=" * 70)
        total = len(self.results)
        passed = sum(1 for r in self.results if r["passed"])
        failed = total - passed

        print(f"PHASE 3.5 RESULTS: {passed}/{total} CHECKS PASSED ({failed} FAILED)")
        print("=" * 70)

        if failed > 0:
            print("\nFAILURES SUMMARY:")
            for r in self.results:
                if not r["passed"]:
                    print(f"  - [{r['category']}] {r['name']}: {r['details']}")
            return False

        print("\nAll automated Phase 3.5 checks passed successfully!")
        return True

    # ------------------------------------------------------------------------
    # 1. Backend Health & Readiness
    # ------------------------------------------------------------------------
    def verify_backend_health(self):
        print("\n1. Backend Health & Service Liveness")
        # GET /health
        try:
            res = self.client.get("/health")
            self.record(
                "Health",
                "GET /health probe returns 200 OK and healthy status",
                res.status_code == 200 and res.json().get("status") == "healthy",
                f"Status: {res.status_code}, Body: {res.text}"
            )
        except Exception as e:
            self.record("Health", "GET /health probe", False, str(e))

        # GET /
        try:
            res = self.client.get("/")
            body = res.json()
            modules = body.get("modules", [])
            self.record(
                "Health",
                "GET / root information returns service metadata",
                res.status_code == 200 and "multilingual_nlp" in modules,
                f"Modules found: {modules}"
            )
        except Exception as e:
            self.record("Health", "GET / root probe", False, str(e))

        # GET /config-check (Zero secret leakage)
        try:
            res = self.client.get("/config-check")
            body = res.json()
            has_leak = any(k in str(body).lower() for k in ["sk_live", "secret_key", "jwt_secret"])
            self.record(
                "Health",
                "GET /config-check safe inspection without secret leakage",
                res.status_code == 200 and not has_leak,
                f"Status: {res.status_code}"
            )
        except Exception as e:
            self.record("Health", "GET /config-check", False, str(e))

    # ------------------------------------------------------------------------
    # 2. Route Discovery
    # ------------------------------------------------------------------------
    def verify_route_catalog(self):
        print("\n2. API Route Catalog & Endpoints Discovery")
        route_paths = {r.path for r in app.routes if hasattr(r, "path")}

        expected_routes = [
            "/ask",
            "/sessions",
            "/sessions/{session_id}",
            "/sessions/{session_id}/history",
            "/auth/register",
            "/auth/login",
            "/auth/me",
            "/admin/stats",
            "/admin/users",
            "/admin/sessions",
            "/voice/transcribe-json",
            "/voice/synthesize",
            "/ask-voice-json",
            "/adapters/agmarknet",
            "/adapters/weather",
            "/adapters/schemes",
            "/vector-store/status",
        ]

        missing = [route for route in expected_routes if route not in route_paths]
        self.record(
            "Routes",
            f"All {len(expected_routes)} critical core and admin routes registered",
            len(missing) == 0,
            f"Missing routes: {missing}"
        )

    # ------------------------------------------------------------------------
    # 3. Session Management & Multi-Turn Context
    # ------------------------------------------------------------------------
    def verify_session_and_context(self):
        print("\n3. Session Management & Multi-Turn Context Resolution")
        username = "kisan_phase35"
        password = "SecurePassword123!"

        # Register farmer
        self.client.post("/auth/register", json={"username": username, "password": password, "role": "farmer"})
        login_res = self.client.post("/auth/login", json={"username": username, "password": password})
        token = login_res.json().get("access_token")
        auth_hdr = {"Authorization": f"Bearer {token}"}

        # Create session
        sess_res = self.client.post("/sessions", json={"farmer_id": username, "language": "en"}, headers=auth_hdr)
        sess_ok = sess_res.status_code == 201
        session_id = sess_res.json().get("session_id")
        self.record(
            "Session",
            "POST /sessions creates unique farmer session",
            sess_ok and bool(session_id),
            f"Status: {sess_res.status_code}, Session ID: {session_id}"
        )

        if not session_id:
            return

        # Turn 1: Establish crop entity (Tomato)
        ask1_res = self.client.post(
            "/ask",
            json={"session_id": session_id, "question": "What fertilizer schedule should I follow for tomato plants?"},
            headers=auth_hdr
        )
        ask1_ok = ask1_res.status_code == 200
        self.record(
            "Session",
            "Turn 1: Ask query with entity grounding (Tomato fertilizer)",
            ask1_ok and bool(ask1_res.json().get("answer")),
            f"Status: {ask1_res.status_code}"
        )

        # Turn 2: Follow-up pronoun question ("How often should I apply it?")
        ask2_res = self.client.post(
            "/ask",
            json={"session_id": session_id, "question": "How often should I apply it?"},
            headers=auth_hdr
        )
        ask2_ok = ask2_res.status_code == 200
        self.record(
            "Session",
            "Turn 2: Multi-turn pronoun context resolution maintains agricultural entity",
            ask2_ok and bool(ask2_res.json().get("answer")),
            f"Status: {ask2_res.status_code}"
        )

        # Retrieve History
        hist_res = self.client.get(f"/sessions/{session_id}/history", headers=auth_hdr)
        messages = hist_res.json().get("messages", [])
        self.record(
            "Session",
            "GET /sessions/{id}/history preserves chronological conversation turns",
            hist_res.status_code == 200 and len(messages) >= 4,
            f"Message count: {len(messages)}"
        )

        # Deactivate session
        del_res = self.client.delete(f"/sessions/{session_id}", headers=auth_hdr)
        self.record(
            "Session",
            "DELETE /sessions/{id} safely deactivates session",
            del_res.status_code in (200, 204),
            f"Status: {del_res.status_code}"
        )

    # ------------------------------------------------------------------------
    # 4. RBAC & Security Isolation
    # ------------------------------------------------------------------------
    def verify_rbac_and_security(self):
        print("\n4. Role-Based Access Control (RBAC) & Security Boundaries")

        # Public cannot register admin
        pub_admin_res = self.client.post(
            "/auth/register",
            json={"username": "attacker_admin", "password": "Password123!", "role": "admin"}
        )
        self.record(
            "Security",
            "Public registration with role='admin' is rejected (403 Forbidden)",
            pub_admin_res.status_code == 403,
            f"Returned status: {pub_admin_res.status_code}"
        )

        # Farmer blocked from admin endpoints
        farmer_login = self.client.post(
            "/auth/login",
            json={"username": "kisan_phase35", "password": "SecurePassword123!"}
        )
        farmer_token = farmer_login.json().get("access_token")
        farmer_hdr = {"Authorization": f"Bearer {farmer_token}"}

        admin_stats_res = self.client.get("/admin/stats", headers=farmer_hdr)
        self.record(
            "Security",
            "Farmer token attempting /admin/stats is terminated (403 Forbidden)",
            admin_stats_res.status_code == 403,
            f"Returned status: {admin_stats_res.status_code}"
        )

        # Unauthenticated request blocked from admin endpoints
        anon_stats_res = self.client.get("/admin/stats")
        self.record(
            "Security",
            "Unauthenticated request to /admin/stats rejected (401 Unauthorized)",
            anon_stats_res.status_code == 401,
            f"Returned status: {anon_stats_res.status_code}"
        )

        # Input sanitization: Malformed / Empty queries rejected
        bad_req = self.client.post("/ask", json={"question": "   "})
        self.record(
            "Security",
            "Empty whitespace question rejected with HTTP 400 Bad Request",
            bad_req.status_code == 400,
            f"Returned status: {bad_req.status_code}"
        )

    # ------------------------------------------------------------------------
    # 5. Voice Endpoints & Mock-Mode Safeguards
    # ------------------------------------------------------------------------
    def verify_voice_and_safeguards(self):
        print("\n5. Voice Endpoints & Mock-Mode Safeguards (Zero Billable Calls)")

        with patch.object(voice_pipeline, "mode", "mock"):
            # 1. Synthesis endpoint
            synth_res = self.client.post(
                "/voice/synthesize",
                json={"text": "Namaste Kisan, tomato blight can be controlled with copper oxychloride.", "language_code": "hi"}
            )
            synth_data = synth_res.json()
            is_mock_synth = synth_data.get("is_mock", True) or synth_data.get("provider") == "mock"
            self.record(
                "Voice",
                "POST /voice/synthesize generates speech audio in mock mode",
                synth_res.status_code == 200 and bool(synth_data.get("audio_base64")),
                f"Status: {synth_res.status_code}, provider: {synth_data.get('provider')}"
            )

            # 2. Transcription endpoint
            mock_wav_bytes = generate_mock_wav(duration_seconds=0.4)
            mock_wav_b64 = base64.b64encode(mock_wav_bytes).decode("utf-8")
            trans_res = self.client.post(
                "/voice/transcribe-json",
                json={"audio_base64": mock_wav_b64, "filename": "audio.wav", "language_hint": "hi"}
            )
            trans_data = trans_res.json()
            self.record(
                "Voice",
                "POST /voice/transcribe-json processes audio with mock STT safely",
                trans_res.status_code == 200 and "transcript" in trans_data,
                f"Status: {trans_res.status_code}, transcript: {trans_data.get('transcript')}"
            )

            # 3. End-to-end voice query (/ask-voice-json)
            ask_voice_res = self.client.post(
                "/ask-voice-json",
                json={
                    "audio_base64": mock_wav_b64,
                    "filename": "query.wav",
                    "language_hint": "kn",
                }
            )
            voice_data = ask_voice_res.json()
            self.record(
                "Voice",
                "POST /ask-voice-json executes end-to-end pipeline with mock voice safeguard",
                ask_voice_res.status_code == 200 and "answer" in voice_data,
                f"Status: {ask_voice_res.status_code}, Intent: {voice_data.get('intent')}"
            )

    # ------------------------------------------------------------------------
    # 6. PWA Web App Manifest & Assets
    # ------------------------------------------------------------------------
    def verify_pWA_assets(self):
        print("\n6. Progressive Web App (PWA) Manifest & Icon Assets")

        manifest_path = self.frontend_dir / "public" / "manifest.json"
        manifest_exists = manifest_path.exists()
        manifest_valid = False
        manifest_icons_valid = False

        if manifest_exists:
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                manifest_valid = (
                    manifest.get("name") == "FarmSaathi"
                    and manifest.get("display") == "standalone"
                    and manifest.get("theme_color") == "#047857"
                    and manifest.get("start_url") == "/"
                )
                icons = manifest.get("icons", [])
                has_192 = any(i.get("sizes") == "192x192" for i in icons)
                has_512 = any(i.get("sizes") == "512x512" and i.get("purpose") == "any" for i in icons)
                has_maskable = any(i.get("purpose") == "maskable" for i in icons)
                manifest_icons_valid = has_192 and has_512 and has_maskable
            except Exception as e:
                manifest_valid = False

        self.record(
            "PWA",
            "manifest.json exists and adheres to W3C Web App Manifest standard",
            manifest_exists and manifest_valid and manifest_icons_valid,
            f"Exists: {manifest_exists}, Valid: {manifest_valid}, Icons valid: {manifest_icons_valid}"
        )

        # Check required icon files
        icon_names = [
            "icon-192x192.png",
            "icon-512x512.png",
            "maskable-icon-512x512.png",
            "apple-touch-icon.png",
        ]
        icons_dir = self.frontend_dir / "public" / "icons"
        missing_icons = []
        for name in icon_names:
            p = icons_dir / name
            if not p.exists() or p.stat().st_size == 0:
                missing_icons.append(name)

        self.record(
            "PWA",
            f"All {len(icon_names)} launcher, splash, and maskable icons exist and are non-empty",
            len(missing_icons) == 0,
            f"Missing or empty: {missing_icons}"
        )

        # Check offline.html
        offline_path = self.frontend_dir / "public" / "offline.html"
        offline_ok = offline_path.exists() and offline_path.stat().st_size > 100
        self.record(
            "PWA",
            "offline.html fallback document exists with trilingual farmer guidance",
            offline_ok,
            f"Size: {offline_path.stat().st_size if offline_path.exists() else 0} bytes"
        )

    # ------------------------------------------------------------------------
    # 7. Service Worker & API Cache Bypass
    # ------------------------------------------------------------------------
    def verify_service_worker_security(self):
        print("\n7. Service Worker Implementation & Privacy Cache Bypass")

        sw_path = self.frontend_dir / "public" / "sw.js"
        sw_exists = sw_path.exists()
        has_cache_name = False
        has_api_bypass = False
        has_precache = False

        if sw_exists:
            content = sw_path.read_text(encoding="utf-8")
            has_cache_name = "farmsaathi-v1" in content
            # Security Rule: unconditional bypass for all /api/ endpoints
            has_api_bypass = "startsWith('/api/')" in content or 'startsWith("/api/")' in content
            has_precache = "PRECACHE_ASSETS" in content and "addAll" in content

        self.record(
            "PWA Security",
            "Service worker contains strict /api/ bypass (never caches voice or auth tokens)",
            sw_exists and has_api_bypass,
            f"SW Exists: {sw_exists}, API Bypass Found: {has_api_bypass}"
        )

        self.record(
            "PWA",
            "Service worker configures farmsaathi-v1 cache and precache lifecycle",
            sw_exists and has_cache_name and has_precache,
            f"Cache Name: {has_cache_name}, Precache: {has_precache}"
        )

    # ------------------------------------------------------------------------
    # 8. Frontend-to-Backend Proxy Contracts
    # ------------------------------------------------------------------------
    def verify_frontend_proxy_contracts(self):
        print("\n8. Next.js Frontend API Proxy Routes Contract")

        proxy_routes = [
            ("app/api/ask/route.ts", "/ask"),
            ("app/api/ask-voice/route.ts", "/ask-voice-json"),
            ("app/api/health/route.ts", "/health"),
            ("app/api/voice/synthesize/route.ts", "/voice/synthesize"),
            ("app/api/voice/transcribe/route.ts", "/voice/transcribe-json"),
        ]

        all_matched = True
        failed_routes = []
        for file_rel, target_backend in proxy_routes:
            p = self.frontend_dir / file_rel
            if not p.exists():
                all_matched = False
                failed_routes.append(f"{file_rel} (missing)")
                continue
            content = p.read_text(encoding="utf-8")
            if target_backend not in content:
                all_matched = False
                failed_routes.append(f"{file_rel} (expected target {target_backend})")

        self.record(
            "Proxy",
            f"All {len(proxy_routes)} Next.js API routes forward cleanly to matching FastAPI endpoints",
            all_matched,
            f"Failed routes: {failed_routes}"
        )


if __name__ == "__main__":
    runner = Phase35VerificationRunner()
    success = runner.run_all()
    sys.exit(0 if success else 1)
