import unittest
import os
import sys
import hashlib
import importlib
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# Ensure repo root is on sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.app.main import app
from backend.app.ml.registry import model_registry


class TestEnvironmentSeparation(unittest.TestCase):
    """
    Automated test suite verifying the complete environment separation
    between Vercel Frontend and Render Backend.
    """

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    # 1. Frontend Secret Isolation Check
    def test_01_frontend_secret_isolation(self):
        frontend_src = os.path.join(BASE_DIR, "frontend", "src")
        forbidden_keywords = [
            "GOOGLE_CLIENT_SECRET",
            "client_secret",
            "SESSION_SECRET",
            "token.json",
            "credentials.json",
        ]
        for root, _, files in os.walk(frontend_src):
            for file in files:
                if file.endswith((".js", ".jsx", ".ts", ".tsx", ".html")):
                    fpath = os.path.join(root, file)
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                        for kw in forbidden_keywords:
                            self.assertNotIn(
                                kw, content,
                                f"Forbidden backend secret keyword '{kw}' found in frontend file: {file}"
                            )

    # 2. Backend CORS Allows Configured FRONTEND_URL & Preserves Non-Wildcard Credentials
    def test_02_cors_allows_frontend_url(self):
        # A: Existing allowed origin receives explicit access-control-allow-origin with credentials
        res = self.client.options(
            "/api/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET"
            }
        )
        self.assertEqual(res.headers.get("access-control-allow-origin"), "http://localhost:5173")
        self.assertEqual(res.headers.get("access-control-allow-credentials"), "true")

        # B: Disallowed origin does not receive access-control-allow-origin
        res_disallowed = self.client.options(
            "/api/health",
            headers={
                "Origin": "https://malicious-site.evil.com",
                "Access-Control-Request-Method": "GET"
            }
        )
        self.assertNotEqual(res_disallowed.headers.get("access-control-allow-origin"), "*")
        self.assertIsNone(res_disallowed.headers.get("access-control-allow-origin"))

        # C: Verify FRONTEND_URL environment variable is parsed and ingested into ALLOWED_ORIGINS
        test_frontend = "https://mailmind-production.vercel.app"
        with patch.dict(os.environ, {"FRONTEND_URL": test_frontend}):
            import backend.app.core.config as cfg
            importlib.reload(cfg)
            self.assertIn(test_frontend, cfg.ALLOWED_ORIGINS)
            self.assertEqual(cfg.FRONTEND_URL, test_frontend)

    # 3. OAuth Callback Redirects to FRONTEND_URL in Split Deployment
    def test_03_oauth_callback_redirects_to_frontend_url(self):
        test_frontend = "https://mailmind.vercel.app"
        with patch.dict(os.environ, {"FRONTEND_URL": test_frontend}):
            res_err = self.client.get("/api/auth/callback?error=access_denied", follow_redirects=False)
            self.assertEqual(res_err.status_code, 302)
            self.assertTrue(
                res_err.headers.get("location").startswith(f"{test_frontend}/?auth_error="),
                f"Expected error redirect to {test_frontend}, got: {res_err.headers.get('location')}"
            )

    # 4. OAuth Callback Defaults to Root in Monolithic Local Development
    def test_04_oauth_callback_defaults_to_root(self):
        with patch.dict(os.environ, {"FRONTEND_URL": ""}):
            res_err = self.client.get("/api/auth/callback?error=access_denied", follow_redirects=False)
            self.assertEqual(res_err.status_code, 302)
            self.assertTrue(
                res_err.headers.get("location").startswith("/?auth_error="),
                f"Expected default redirect to /?auth_error=, got: {res_err.headers.get('location')}"
            )

    # 5. Production Cookie Flags: SameSite=None; Secure=True for Cross-Origin Vercel
    def test_05_production_cookie_samesite_none_secure(self):
        with patch.dict(os.environ, {"ENVIRONMENT": "production", "ALLOW_TEST_ENDPOINTS": "true"}):
            res = self.client.post("/api/auth/test-session?email=prod_cookie_test@mailmind.dev")
            self.assertEqual(res.status_code, 200)
            cookie_header = res.headers.get("set-cookie", "").lower()
            self.assertIn("mailmind_session=", cookie_header)
            self.assertIn("samesite=none", cookie_header)
            self.assertIn("secure", cookie_header)
            self.assertIn("httponly", cookie_header)

    # 6. Development Cookie Flags: SameSite=Lax; Secure=False for Localhost HTTP
    def test_06_development_cookie_samesite_lax(self):
        with patch.dict(os.environ, {"ENVIRONMENT": "development", "ALLOW_TEST_ENDPOINTS": "true", "COOKIE_SAMESITE": "lax"}):
            res = self.client.post("/api/auth/test-session?email=dev_cookie_test@mailmind.dev")
            self.assertEqual(res.status_code, 200)
            cookie_header = res.headers.get("set-cookie", "").lower()
            self.assertIn("mailmind_session=", cookie_header)
            self.assertIn("samesite=lax", cookie_header)
            self.assertIn("httponly", cookie_header)

    # 7. Production Model v5.1 Cryptographic Integrity
    def test_07_production_model_hash_integrity(self):
        expected_hash = "8524ad73965859ee022f1271caee0040928e7805ab7d32c49b2f26e994f98c06"
        model_path = model_registry.get_active_model_path()
        self.assertTrue(os.path.exists(model_path), f"Active model missing at {model_path}")
        hasher = hashlib.sha256()
        with open(model_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        self.assertEqual(hasher.hexdigest(), expected_hash, "Production model SHA-256 altered!")

    # 8. Rollback Model v4.1 Cryptographic Integrity
    def test_08_rollback_model_hash_integrity(self):
        expected_hash = "09fe269f19ad6afb38e71b56f8c6ee7a386e59605c62c892478400bc09d5cbd0"
        rel_path = model_registry.get_version("priority-v4.1")["artifact_path"]
        model_path = os.path.join(BASE_DIR, "dataset", "models", rel_path)
        self.assertTrue(os.path.exists(model_path), f"Rollback model missing at {model_path}")
        hasher = hashlib.sha256()
        with open(model_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        self.assertEqual(hasher.hexdigest(), expected_hash, "Rollback model SHA-256 altered!")

    # 9. Frozen Test Holdout Cryptographic Integrity
    def test_09_frozen_holdout_hash_integrity(self):
        expected_hash = "6841cd44901fa56242bf3752257e991fd7ff474ed7e0f7a5d2b7065a0827c138"
        holdout_path = os.path.join(BASE_DIR, "dataset", "processed", "test.csv")
        self.assertTrue(os.path.exists(holdout_path), f"Holdout dataset missing at {holdout_path}")
        hasher = hashlib.sha256()
        with open(holdout_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        self.assertEqual(hasher.hexdigest(), expected_hash, "Frozen holdout dataset SHA-256 altered!")

    # 10. Zero External LLM/Gemini APIs in Inference Pipeline
    def test_10_zero_external_llm_imports(self):
        import inspect
        from backend.app.ml import predictor, priority, explanations
        for mod in [predictor, priority, explanations]:
            source = inspect.getsource(mod).lower()
            for disallowed in ["openai", "google.generativeai", "anthropic", "langchain"]:
                self.assertNotIn(f"import {disallowed}", source)
                self.assertNotIn(f"from {disallowed}", source)


if __name__ == "__main__":
    unittest.main()
