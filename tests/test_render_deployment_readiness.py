import unittest
import os
import sys
import json
import hashlib
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# Ensure repo root is on sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.app.main import app
from backend.app.ml.registry import model_registry
from backend.app.api.routes_auth import get_base_url, get_redirect_uri, create_oauth_flow
from backend.app.core.cache import user_email_cache


class TestRenderDeploymentReadiness(unittest.TestCase):
    """
    Comprehensive deployment readiness validation test suite for Render.
    Ensures strict architectural invariants, zero regression, and production compliance.
    """

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    # 1. Application Startup & Route Resolution
    def test_01_app_startup_and_metadata(self):
        self.assertIsNotNone(app)
        self.assertEqual(app.title, "MailMind | AI Email Priority Intelligence")
        route_paths = set()
        for r in app.routes:
            if hasattr(r, "path"):
                route_paths.add(r.path)
            if hasattr(r, "original_router") and hasattr(r.original_router, "routes"):
                for sub_r in r.original_router.routes:
                    if hasattr(sub_r, "path"):
                        route_paths.add(sub_r.path)
        self.assertIn("/health", route_paths)
        self.assertIn("/api/health", route_paths)
        self.assertIn("/api/auth/login", route_paths)
        self.assertIn("/api/auth/callback", route_paths)
        self.assertIn("/api/emails", route_paths)
        self.assertIn("/api/profile", route_paths)

    # 2. Health Check Probes
    def test_02_health_probes(self):
        # Default root health check for container platforms
        res_root = self.client.get("/health")
        self.assertEqual(res_root.status_code, 200)
        data_root = res_root.json()
        self.assertEqual(data_root.get("status"), "healthy")
        self.assertTrue(data_root.get("model_loaded"))

        # Standard API health check
        res_api = self.client.get("/api/health")
        self.assertEqual(res_api.status_code, 200)
        data_api = res_api.json()
        self.assertEqual(data_api.get("status"), "healthy")
        self.assertTrue(data_api.get("model_loaded"))

    # 3. Production ML Model (priority-v5.1) SHA-256 Hash Integrity
    def test_03_production_model_hash(self):
        expected_hash = "8524ad73965859ee022f1271caee0040928e7805ab7d32c49b2f26e994f98c06"
        self.assertEqual(model_registry.get_active_version(), "priority-v5.1")
        model_path = model_registry.get_active_model_path()
        self.assertTrue(os.path.exists(model_path), f"Production model not found at {model_path}")

        hasher = hashlib.sha256()
        with open(model_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        actual_hash = hasher.hexdigest()
        self.assertEqual(actual_hash, expected_hash, "Production model SHA-256 checksum mismatch!")

    # 4. Rollback ML Model (priority-v4.1) SHA-256 Hash Integrity
    def test_04_rollback_model_hash(self):
        expected_hash = "09fe269f19ad6afb38e71b56f8c6ee7a386e59605c62c892478400bc09d5cbd0"
        reg = model_registry.get_registry()
        previous_version = reg.get("previous_model")
        self.assertEqual(previous_version, "priority-v4.1")

        v41_meta = model_registry.get_version("priority-v4.1")
        self.assertIsNotNone(v41_meta)
        rel_path = v41_meta.get("artifact_path", "priority-v4.1/model.joblib")
        model_path = os.path.join(BASE_DIR, "dataset", "models", rel_path)
        self.assertTrue(os.path.exists(model_path), f"Rollback model not found at {model_path}")

        hasher = hashlib.sha256()
        with open(model_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        actual_hash = hasher.hexdigest()
        self.assertEqual(actual_hash, expected_hash, "Rollback model SHA-256 checksum mismatch!")

    # 5. Frozen Test Holdout (dataset/processed/test.csv) SHA-256 Hash Integrity
    def test_05_frozen_test_holdout_hash(self):
        expected_hash = "6841cd44901fa56242bf3752257e991fd7ff474ed7e0f7a5d2b7065a0827c138"
        holdout_path = os.path.join(BASE_DIR, "dataset", "processed", "test.csv")
        self.assertTrue(os.path.exists(holdout_path), f"Frozen holdout not found at {holdout_path}")

        hasher = hashlib.sha256()
        with open(holdout_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        actual_hash = hasher.hexdigest()
        self.assertEqual(actual_hash, expected_hash, "Frozen holdout dataset SHA-256 checksum mismatch!")

    # 6. Protected Endpoints Require Authentication
    def test_06_unauthenticated_requests_return_401(self):
        endpoints = [
            "/api/emails",
            "/api/profile",
            "/api/scan/status",
        ]
        for ep in endpoints:
            res = self.client.get(ep)
            self.assertEqual(res.status_code, 401, f"Expected 401 for unauthenticated {ep}")

    # 7. Test Session Endpoint Strictly Disabled in Production
    def test_07_test_session_endpoint_disabled_in_production(self):
        with patch.dict(os.environ, {"ENVIRONMENT": "production", "ALLOW_TEST_ENDPOINTS": "false"}):
            res = self.client.post("/api/auth/test-session?email=production_probe@test.com")
            self.assertEqual(res.status_code, 403, "test-session must return 403 in production")

    # 8. Zero External LLM/Gemini/OpenAI Dependencies in Classification
    def test_08_zero_external_ai_dependencies(self):
        import inspect
        from backend.app.ml import predictor, priority, explanations
        modules = [predictor, priority, explanations]
        disallowed_keywords = ["openai", "google.generativeai", "anthropic", "langchain"]

        for mod in modules:
            source = inspect.getsource(mod).lower()
            for kw in disallowed_keywords:
                self.assertNotIn(f"import {kw}", source, f"Found external LLM import {kw} in {mod.__name__}")
                self.assertNotIn(f"from {kw}", source, f"Found external LLM import {kw} in {mod.__name__}")

    # 9. Google OAuth Credentials Resolution from Env Vars
    def test_09_oauth_flow_from_env_vars(self):
        with patch.dict(os.environ, {
            "GOOGLE_CLIENT_ID": "test-client-id-123.apps.googleusercontent.com",
            "GOOGLE_CLIENT_SECRET": "test-client-secret-abc",
            "GOOGLE_OAUTH_CLIENT_JSON": "",
        }):
            flow = create_oauth_flow("https://mailmind.onrender.com/api/auth/callback")
            self.assertIsNotNone(flow)
            self.assertEqual(flow.client_config["client_id"], "test-client-id-123.apps.googleusercontent.com")
            self.assertEqual(flow.client_config["client_secret"], "test-client-secret-abc")
            self.assertEqual(flow.redirect_uri, "https://mailmind.onrender.com/api/auth/callback")

    # 10. Google OAuth Credentials Resolution from JSON String Env Var
    def test_10_oauth_flow_from_json_env_var(self):
        raw_json = json.dumps({
            "web": {
                "client_id": "test-web-id.apps.googleusercontent.com",
                "client_secret": "test-web-secret",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token"
            }
        })
        with patch.dict(os.environ, {
            "GOOGLE_OAUTH_CLIENT_JSON": raw_json,
            "GOOGLE_CLIENT_ID": "",
            "GOOGLE_CLIENT_SECRET": "",
        }):
            flow = create_oauth_flow("https://mailmind.onrender.com/api/auth/callback")
            self.assertIsNotNone(flow)
            self.assertEqual(flow.client_config["client_id"], "test-web-id.apps.googleusercontent.com")
            self.assertEqual(flow.client_config["client_secret"], "test-web-secret")

    # 11. Reverse Proxy HTTPS and BASE_URL Resolution
    def test_11_reverse_proxy_base_url_resolution(self):
        # Subtest A: BASE_URL env var configured
        req_mock_a = MagicMock()
        req_mock_a.headers = {}
        with patch.dict(os.environ, {"BASE_URL": "https://mailmind.onrender.com"}):
            base_url = get_base_url(req_mock_a)
            self.assertEqual(base_url, "https://mailmind.onrender.com")
            redirect_uri = get_redirect_uri(req_mock_a)
            self.assertEqual(redirect_uri, "https://mailmind.onrender.com/api/auth/callback")

        # Subtest B: BASE_URL empty, derived from X-Forwarded headers
        req_mock_b = MagicMock()
        req_mock_b.headers = {
            "x-forwarded-proto": "https",
            "x-forwarded-host": "custom-mailmind.onrender.com"
        }
        with patch.dict(os.environ, {"BASE_URL": ""}):
            base_url = get_base_url(req_mock_b)
            self.assertEqual(base_url, "https://custom-mailmind.onrender.com")
            redirect_uri = get_redirect_uri(req_mock_b)
            self.assertEqual(redirect_uri, "https://custom-mailmind.onrender.com/api/auth/callback")

    # 12. Multi-User Cache Isolation
    def test_12_multiuser_cache_isolation(self):
        user_1 = "test_user_alpha@gmail.com"
        user_2 = "test_user_beta@gmail.com"
        msg_id = "render_test_msg_001"
        
        email_data = {
            "id": msg_id,
            "message_id": msg_id,
            "thread_id": "thread_001",
            "subject": "Confidential Render Deployment Memo",
            "sender": "boss@company.com",
            "recipients": user_1,
            "snippet": "Render deployment is ready.",
            "body": "Full body text.",
            "date": "2026-10-04T09:00:00Z",
            "priority": "HIGH",
            "confidence": 0.95,
            "predicted_priority": "P1",
            "model_version": "priority-v5.1",
        }

        # Store for user_1
        user_email_cache.store_batch(user_1, [email_data], model_version="priority-v5.1")

        # Retrieve for user_1 -> Must be found
        cached_1, missing_1 = user_email_cache.get_batch(user_1, [msg_id])
        self.assertIn(msg_id, cached_1)
        self.assertNotIn(msg_id, missing_1)

        # Retrieve for user_2 -> Must NOT be found (zero leakage across users)
        cached_2, missing_2 = user_email_cache.get_batch(user_2, [msg_id])
        self.assertNotIn(msg_id, cached_2)
        self.assertIn(msg_id, missing_2)

    # 13. Direct SPA Fallback Navigation
    def test_13_spa_catch_all_fallback(self):
        # /api routes that don't exist should return 404
        res_nonexistent_api = self.client.get("/api/nonexistent-route-xyz")
        self.assertEqual(res_nonexistent_api.status_code, 404)


if __name__ == "__main__":
    unittest.main()
