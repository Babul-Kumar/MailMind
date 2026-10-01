import os
import sys
import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.app.main import app
from backend.app.core.session import session_manager, mask_email
from backend.app.core.cache import user_email_cache


class TestMultiUserAuth(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    # 1. Login endpoint constructs valid Google OAuth URL with prompt=select_account
    def test_01_login_endpoint_redirect_and_params(self):
        response = self.client.get("/api/auth/login", follow_redirects=False)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("authorization_url", data)
        auth_url = data["authorization_url"]

        self.assertIn("accounts.google.com", auth_url)
        self.assertIn("prompt=select_account", auth_url)
        self.assertIn("response_type=code", auth_url)
        self.assertIn("access_type=offline", auth_url)
        self.assertIn("state=", auth_url)
        self.assertIn("gmail.readonly", auth_url)

    # 2. Auth status when unauthenticated
    def test_02_auth_status_unauthenticated(self):
        # Fresh client without cookies
        res = self.client.get("/api/auth/status")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertFalse(data.get("authenticated"))
        self.assertIsNone(data.get("user"))

    # 3. Callback rejects invalid or expired OAuth state with 400
    def test_03_callback_invalid_state(self):
        res = self.client.get("/api/auth/callback?code=mock_code&state=non_existent_state_xyz")
        self.assertEqual(res.status_code, 400)
        self.assertIn("Invalid or expired OAuth state", res.json().get("detail", ""))

    # 4. Multi-user session creation & isolation
    def test_04_session_isolation_and_credentials(self):
        alice_session = session_manager.create_session(
            email="alice@company.org",
            user_id="user_alice_123",
            credentials={"access_token": "token_alice", "refresh_token": "refresh_alice"}
        )
        bob_session = session_manager.create_session(
            email="bob@company.org",
            user_id="user_bob_456",
            credentials={"access_token": "token_bob", "refresh_token": "refresh_bob"}
        )

        self.assertNotEqual(alice_session.session_id, bob_session.session_id)

        retrieved_alice = session_manager.get_session(alice_session.session_id)
        retrieved_bob = session_manager.get_session(bob_session.session_id)

        self.assertIsNotNone(retrieved_alice)
        self.assertIsNotNone(retrieved_bob)
        self.assertEqual(retrieved_alice.email, "alice@company.org")
        self.assertEqual(retrieved_bob.email, "bob@company.org")
        self.assertEqual(retrieved_alice.user_id, "user_alice_123")
        self.assertEqual(retrieved_bob.user_id, "user_bob_456")

        # Credentials must not cross
        self.assertEqual(retrieved_alice.credentials["access_token"], "token_alice")
        self.assertEqual(retrieved_bob.credentials["access_token"], "token_bob")

    # 5. Authenticated status endpoint resolves session and NEVER leaks credentials to frontend
    def test_05_authenticated_status_endpoint(self):
        charlie_session = session_manager.create_session(
            email="charlie@enterprise.com",
            user_id="user_charlie_789",
            credentials={"access_token": "secret_access_xyz", "refresh_token": "secret_refresh_abc"}
        )

        res = self.client.get(
            "/api/auth/status",
            cookies={"mailmind_session": charlie_session.session_id}
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data.get("authenticated"))
        user = data.get("user", {})
        self.assertEqual(user.get("email"), "charlie@enterprise.com")
        self.assertEqual(user.get("masked_email"), mask_email("charlie@enterprise.com"))

        # SECURITY CHECK: Access token and refresh token must NEVER be exposed to frontend
        self.assertNotIn("access_token", data)
        self.assertNotIn("refresh_token", data)
        self.assertNotIn("credentials", data)
        self.assertNotIn("access_token", user)
        self.assertNotIn("refresh_token", user)
        self.assertNotIn("credentials", user)

    # 6. Logout endpoint invalidates session and clears cookie
    def test_06_logout_endpoint(self):
        dan_session = session_manager.create_session(
            email="dan@domain.io",
            user_id="user_dan_001",
            credentials={"access_token": "dan_token"}
        )

        # Logout
        res = self.client.post(
            "/api/auth/logout",
            cookies={"mailmind_session": dan_session.session_id}
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data.get("status"), "logged_out")

        # Session should be deleted from session_manager
        self.assertIsNone(session_manager.get_session(dan_session.session_id))

        # Subsequent status check should return unauthenticated
        res_after = self.client.get(
            "/api/auth/status",
            cookies={"mailmind_session": dan_session.session_id}
        )
        self.assertFalse(res_after.json().get("authenticated"))

    # 7. User-scoped cache isolation: User B cannot access User A's cache
    def test_07_user_scoped_cache_isolation(self):
        user_a = "user_alpha_999"
        user_b = "user_beta_888"
        msg_id = "msg_confidential_01"

        email_data = {
            "email_id": msg_id,
            "subject": "Confidential Strategy Q3",
            "predicted_priority": "P1",
            "action_required": True,
            "model_version": "priority-v2"
        }

        # Cache for User A
        user_email_cache.set(user_a, msg_id, email_data)

        # User A gets cache hit
        hit_a = user_email_cache.get(user_a, msg_id)
        self.assertIsNotNone(hit_a)
        self.assertEqual(hit_a["predicted_priority"], "P1")

        # User B gets cache MISS
        hit_b = user_email_cache.get(user_b, msg_id)
        self.assertIsNone(hit_b, "User B must NEVER be able to read User A's cached email!")

        # Batch lookup isolation
        cached_map_b, missing_b = user_email_cache.get_batch(user_b, [msg_id, "msg_other"])
        self.assertNotIn(msg_id, cached_map_b)
        self.assertIn(msg_id, missing_b)

    # 8. Account switching: User A -> User B ensures no state contamination
    def test_08_account_switching_safety(self):
        # 1. User A active
        session_a = session_manager.create_session("usera@mail.com", "user_a_id", {"token": "a"})
        user_email_cache.set("user_a_id", "email_1", {"email_id": "email_1", "subject": "A's email"})

        # 2. Invalidate A's session on switch/logout
        session_manager.delete_session(session_a.session_id)
        self.assertIsNone(session_manager.get_session(session_a.session_id))

        # 3. User B connects
        session_b = session_manager.create_session("userb@mail.com", "user_b_id", {"token": "b"})
        self.assertIsNotNone(session_manager.get_session(session_b.session_id))

        # 4. User B cannot see email_1 in cache
        self.assertIsNone(user_email_cache.get("user_b_id", "email_1"))

    # 9. Regression: Unauthenticated web requests to all Gmail and user-scoped endpoints MUST return 401
    def test_09_unauthenticated_endpoints_return_401(self):
        unauth_client = TestClient(app)

        # /api/emails without session
        res_emails = unauth_client.get("/api/emails")
        self.assertEqual(res_emails.status_code, 401)
        self.assertIn("Authentication required", res_emails.json().get("detail", ""))

        # /api/profile without session
        res_profile = unauth_client.get("/api/profile")
        self.assertEqual(res_profile.status_code, 401)
        self.assertIn("Authentication required", res_profile.json().get("detail", ""))

        # /api/emails/{id} without session
        res_detail = unauth_client.get("/api/emails/mock_msg_001")
        self.assertEqual(res_detail.status_code, 401)
        self.assertIn("Authentication required", res_detail.json().get("detail", ""))

        # /api/feedback without session
        res_feedback = unauth_client.post("/api/feedback", json={
            "message_id": "msg_001",
            "model_version": "priority-v2",
            "predicted_priority": "P4",
            "corrected_priority": "P2",
            "predicted_action_required": False
        })
        self.assertEqual(res_feedback.status_code, 401)
        self.assertIn("Authentication required", res_feedback.json().get("detail", ""))

    # 10. Regression: get_user_gmail_service(session=None) NEVER loads token.json
    def test_10_get_user_gmail_service_never_uses_token_json_when_session_none(self):
        from backend.app.gmail.service import get_user_gmail_service

        # 1. Calling without session must always raise PermissionError
        with self.assertRaises(PermissionError) as ctx:
            get_user_gmail_service(session=None)
        self.assertIn("Valid Google OAuth session required", str(ctx.exception))

        # 2. Even when token.json is mocked to exist with valid data, session=None must NEVER load it
        with patch("os.path.exists", return_value=True), \
             patch("backend.app.gmail.service.Credentials") as mock_creds_cls:
            with self.assertRaises(PermissionError) as ctx2:
                get_user_gmail_service(session=None)
            self.assertIn("Valid Google OAuth session required", str(ctx2.exception))
            # Verify Credentials.from_authorized_user_file was NEVER called
            mock_creds_cls.from_authorized_user_file.assert_not_called()

    # 11. User Credential Isolation: User A vs User B
    def test_11_user_credential_isolation(self):
        from backend.app.gmail.service import get_user_gmail_service

        session_user_a = session_manager.create_session(
            email="usera@test.com",
            user_id="user_a_uid",
            credentials={
                "token": "token_a_val",
                "refresh_token": "refresh_a_val",
                "token_uri": "https://oauth2.googleapis.com/token",
                "client_id": "client_a",
                "client_secret": "secret_a"
            }
        )
        session_user_b = session_manager.create_session(
            email="userb@test.com",
            user_id="user_b_uid",
            credentials={
                "token": "token_b_val",
                "refresh_token": "refresh_b_val",
                "token_uri": "https://oauth2.googleapis.com/token",
                "client_id": "client_b",
                "client_secret": "secret_b"
            }
        )

        creds_a = session_manager.get_credentials(session_user_a)
        creds_b = session_manager.get_credentials(session_user_b)

        self.assertEqual(creds_a.token, "token_a_val")
        self.assertEqual(creds_b.token, "token_b_val")
        self.assertNotEqual(creds_a.token, creds_b.token)


if __name__ == "__main__":
    unittest.main(verbosity=2)
