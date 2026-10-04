import unittest
import os
import sys
import time
from unittest.mock import patch
from fastapi.testclient import TestClient

# Ensure repo root is on sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.app.main import app
from backend.app.core.session import session_manager, SESSION_COOKIE_NAME


class TestOAuthHandoffArchitecture(unittest.TestCase):
    """
    Automated test suite verifying the one-time OAuth handoff code architecture,
    single-use anti-replay guarantees, session isolation, and /api/auth/exchange endpoint.
    """

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def setUp(self):
        # Create a test session
        self.session = session_manager.create_session(
            user_id="user_handoff_test",
            email="handoff_tester@mailmind.dev",
            credentials={"token": "mock_token", "refresh_token": "mock_refresh"}
        )

    def tearDown(self):
        if hasattr(self, "session") and self.session:
            session_manager.delete_session(self.session.session_id)

    # 1. Handoff Code Creation & Pattern
    def test_01_create_handoff_generates_safe_token(self):
        code = session_manager.create_handoff(self.session.session_id)
        self.assertIsInstance(code, str)
        self.assertGreaterEqual(len(code), 20)
        self.assertTrue(session_manager._is_safe_session_id(code))

    # 2. Handoff Consumption Returns Correct Session ID
    def test_02_consume_handoff_success(self):
        code = session_manager.create_handoff(self.session.session_id)
        consumed_session_id = session_manager.consume_handoff(code)
        self.assertEqual(consumed_session_id, self.session.session_id)

    # 3. Anti-Replay: Handoff Code Is Strictly Single-Use
    def test_03_handoff_code_single_use_anti_replay(self):
        code = session_manager.create_handoff(self.session.session_id)
        # First consumption must succeed
        first = session_manager.consume_handoff(code)
        self.assertEqual(first, self.session.session_id)

        # Second consumption MUST fail (None)
        second = session_manager.consume_handoff(code)
        self.assertIsNone(second, "Handoff code was replayed! Must be single-use only.")

    # 4. Expiration: Handoff Code Expires After TTL (120s)
    def test_04_handoff_code_expires_after_ttl(self):
        code = session_manager.create_handoff(self.session.session_id)
        # Simulate time jump past 120s TTL
        with patch("time.time", return_value=time.time() + 125):
            consumed = session_manager.consume_handoff(code)
            self.assertIsNone(consumed, "Expired handoff code was accepted!")

    # 5. Path Traversal & Malicious Token Rejection
    def test_05_malicious_handoff_code_rejected(self):
        bad_codes = [
            "../../../etc/passwd",
            "../sessions/something",
            "",
            "   ",
            "short",
            "code with spaces",
            "code;with$special#chars!",
        ]
        for bad in bad_codes:
            self.assertIsNone(session_manager.consume_handoff(bad))

    # 6. /api/auth/exchange Endpoint Sets Session Cookie
    def test_06_exchange_endpoint_sets_session_cookie(self):
        code = session_manager.create_handoff(self.session.session_id)
        res = self.client.post("/api/auth/exchange", json={"handoff": code})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data.get("authenticated"))
        self.assertEqual(data.get("user", {}).get("email"), "handoff_tester@mailmind.dev")

        # Verify session cookie was set
        cookie_header = res.headers.get("set-cookie", "")
        self.assertIn(SESSION_COOKIE_NAME, cookie_header)
        self.assertIn(self.session.session_id, cookie_header)
        self.assertIn("httponly", cookie_header.lower())

    # 7. /api/auth/exchange Rejects Missing Handoff Code
    def test_07_exchange_endpoint_missing_code_returns_400(self):
        res = self.client.post("/api/auth/exchange", json={})
        self.assertEqual(res.status_code, 400)

    # 8. /api/auth/exchange Rejects Replayed Handoff Code
    def test_08_exchange_endpoint_replayed_code_returns_400(self):
        code = session_manager.create_handoff(self.session.session_id)
        # First exchange succeeds
        res1 = self.client.post("/api/auth/exchange", json={"handoff": code})
        self.assertEqual(res1.status_code, 200)

        # Second exchange with the same code must return 400
        res2 = self.client.post("/api/auth/exchange", json={"handoff": code})
        self.assertEqual(res2.status_code, 400)

    # 9. Multi-User Handoff Isolation
    def test_09_multiuser_handoff_isolation(self):
        session_b = session_manager.create_session(
            user_id="user_b",
            email="user_b@mailmind.dev",
            credentials={"token": "token_b"}
        )
        try:
            code_a = session_manager.create_handoff(self.session.session_id)
            code_b = session_manager.create_handoff(session_b.session_id)

            self.assertNotEqual(code_a, code_b)

            # Consume B
            res_b = self.client.post("/api/auth/exchange", json={"handoff": code_b})
            self.assertEqual(res_b.status_code, 200)
            self.assertEqual(res_b.json().get("user", {}).get("email"), "user_b@mailmind.dev")

            # Consume A
            res_a = self.client.post("/api/auth/exchange", json={"handoff": code_a})
            self.assertEqual(res_a.status_code, 200)
            self.assertEqual(res_a.json().get("user", {}).get("email"), "handoff_tester@mailmind.dev")
        finally:
            session_manager.delete_session(session_b.session_id)

    # 10. Query Parameter Fallback on Exchange Endpoint
    def test_10_exchange_endpoint_query_param_fallback(self):
        code = session_manager.create_handoff(self.session.session_id)
        res = self.client.get(f"/api/auth/exchange?handoff={code}")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json().get("authenticated"))


if __name__ == "__main__":
    unittest.main()
