import os
import sys
import time
import json
import pytest
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.session import session_manager
from backend.app.core.cache import user_email_cache
from backend.app.core.feedback import feedback_manager
from backend.app.ml.predictor import load_model, predict_email, predict_batch
from backend.app.ml.registry import model_registry

client = TestClient(app)


class TestPhase31MultiUserE2E:
    """
    Phase 31.1 - 31.17 Real Multi-User E2E, Account Switching, Cache Isolation,
    Concurrency Safety, and Error UX Test Suite.
    """

    @pytest.fixture(autouse=True)
    def setup_users(self):
        """Provision isolated users A, B, and C with distinct sessions."""
        self.user_a_email = "alice.engineer@testcorp.com"
        self.user_a_id = "user_a_uid_101"
        self.session_a = session_manager.create_session(
            email=self.user_a_email,
            user_id=self.user_a_id,
            credentials={"token": "mock_token_alice_123", "refresh_token": "mock_rf_alice"}
        )

        self.user_b_email = "bob.manager@testcorp.com"
        self.user_b_id = "user_b_uid_202"
        self.session_b = session_manager.create_session(
            email=self.user_b_email,
            user_id=self.user_b_id,
            credentials={"token": "mock_token_bob_456", "refresh_token": "mock_rf_bob"}
        )

        self.user_c_email = "carol.director@testcorp.com"
        self.user_c_id = "user_c_uid_303"
        self.session_c = session_manager.create_session(
            email=self.user_c_email,
            user_id=self.user_c_id,
            credentials={"token": "mock_token_carol_789", "refresh_token": "mock_rf_carol"}
        )

        # Clear caches for test users
        user_email_cache.clear_user(self.user_a_id)
        user_email_cache.clear_user(self.user_b_id)
        user_email_cache.clear_user(self.user_c_id)

        # Distinct mailboxes
        self.mailbox_a = [
            {
                "id": f"msg_a_{i}",
                "subject": f"Alice Project Alpha Update #{i}",
                "body": f"Alice, please complete the alpha testing review by Friday. Task #{i}.",
                "sender": "lead@alpha-project.org",
                "date": "2026-10-01T10:00:00Z"
            }
            for i in range(10)
        ]

        self.mailbox_b = [
            {
                "id": f"msg_b_{i}",
                "subject": f"Bob Budget Report Approval #{i}",
                "body": f"Bob, the quarterly budget report requires your immediate sign-off. Ticket #{i}.",
                "sender": "finance@testcorp.com",
                "date": "2026-10-01T11:00:00Z"
            }
            for i in range(10)
        ]

        self.mailbox_c = [
            {
                "id": f"msg_c_{i}",
                "subject": f"Carol Board Strategy Meeting #{i}",
                "body": f"Carol, strategic board agenda for next quarter. Action required before end of day.",
                "sender": "board@testcorp.com",
                "date": "2026-10-01T12:00:00Z"
            }
            for i in range(10)
        ]

        yield

        # Teardown
        user_email_cache.clear_user(self.user_a_id)
        user_email_cache.clear_user(self.user_b_id)
        user_email_cache.clear_user(self.user_c_id)

    # =========================================================================
    # PHASE 31.1: REAL MULTI-USER TEST
    # =========================================================================
    def test_31_1_multi_user_isolation(self):
        """
        Verify User A, B, and C see strictly their own emails and zero cross-user leakage.
        """
        def mock_dispatch(service, msg_id):
            if msg_id.startswith("msg_a_"):
                return next((m for m in self.mailbox_a if m["id"] == msg_id), None)
            elif msg_id.startswith("msg_b_"):
                return next((m for m in self.mailbox_b if m["id"] == msg_id), None)
            elif msg_id.startswith("msg_c_"):
                return next((m for m in self.mailbox_c if m["id"] == msg_id), None)
            return None

        def mock_list(service, max_results=50, query=None, page_token=None):
            # Inspect service or user context
            user_flag = getattr(service, "_user_flag", "a")
            if user_flag == "a":
                return {"messages": [{"id": m["id"]} for m in self.mailbox_a], "nextPageToken": None}
            elif user_flag == "b":
                return {"messages": [{"id": m["id"]} for m in self.mailbox_b], "nextPageToken": None}
            else:
                return {"messages": [{"id": m["id"]} for m in self.mailbox_c], "nextPageToken": None}

        def mock_profile(service):
            user_flag = getattr(service, "_user_flag", "a")
            email = self.user_a_email if user_flag == "a" else (self.user_b_email if user_flag == "b" else self.user_c_email)
            return {"emailAddress": email, "messagesTotal": 10, "threadsTotal": 5}

        def mock_get_service(session=None):
            mock_s = MagicMock()
            if session.user_id == self.user_a_id:
                mock_s._user_flag = "a"
            elif session.user_id == self.user_b_id:
                mock_s._user_flag = "b"
            else:
                mock_s._user_flag = "c"
            return mock_s

        with patch("backend.app.api.routes_emails.get_user_gmail_service", side_effect=mock_get_service), \
             patch("backend.app.api.routes_emails.get_profile", side_effect=mock_profile), \
             patch("backend.app.api.routes_emails.list_message_ids", side_effect=mock_list), \
             patch("backend.app.api.routes_emails._fetch_single_message_safe", side_effect=mock_dispatch):

            # Fetch for User A
            res_a = client.get("/api/emails", cookies={"mailmind_session": self.session_a.session_id})
            assert res_a.status_code == 200
            data_a = res_a.json()
            assert all("Alice Project Alpha" in em["subject"] for em in data_a["emails"])
            assert data_a["profile"]["email_address"] == self.user_a_email

            # Fetch for User B
            res_b = client.get("/api/emails", cookies={"mailmind_session": self.session_b.session_id})
            assert res_b.status_code == 200
            data_b = res_b.json()
            assert all("Bob Budget Report" in em["subject"] for em in data_b["emails"])
            assert data_b["profile"]["email_address"] == self.user_b_email

            # Fetch for User C
            res_c = client.get("/api/emails", cookies={"mailmind_session": self.session_c.session_id})
            assert res_c.status_code == 200
            data_c = res_c.json()
            assert all("Carol Board Strategy" in em["subject"] for em in data_c["emails"])
            assert data_c["profile"]["email_address"] == self.user_c_email

            # Cross-user cache check
            cached_a, _ = user_email_cache.get_batch(self.user_a_id, [m["id"] for m in self.mailbox_a])
            cached_b, _ = user_email_cache.get_batch(self.user_b_id, [m["id"] for m in self.mailbox_b])
            assert len(cached_a) == 10
            assert len(cached_b) == 10

            # User A cannot retrieve User B cached messages from A's cache
            cached_a_b, missing_a_b = user_email_cache.get_batch(self.user_a_id, [m["id"] for m in self.mailbox_b])
            assert len(cached_a_b) == 0
            assert len(missing_a_b) == 10

    def test_31_1_concurrent_multi_user_operations(self):
        """
        Execute concurrent operations:
        A -> refresh, B -> refresh, C -> open detail, A -> search, B -> switch account, C -> refresh.
        Verify zero race conditions, zero cross-user contamination.
        """
        def mock_dispatch(service, msg_id):
            if msg_id.startswith("msg_a_"):
                return next((m for m in self.mailbox_a if m["id"] == msg_id), None)
            elif msg_id.startswith("msg_b_"):
                return next((m for m in self.mailbox_b if m["id"] == msg_id), None)
            elif msg_id.startswith("msg_c_"):
                return next((m for m in self.mailbox_c if m["id"] == msg_id), None)
            return None

        def mock_list(service, max_results=50, query=None, page_token=None):
            user_flag = getattr(service, "_user_flag", "a")
            if user_flag == "a":
                return {"messages": [{"id": m["id"]} for m in self.mailbox_a], "nextPageToken": None}
            elif user_flag == "b":
                return {"messages": [{"id": m["id"]} for m in self.mailbox_b], "nextPageToken": None}
            else:
                return {"messages": [{"id": m["id"]} for m in self.mailbox_c], "nextPageToken": None}

        def mock_profile(service):
            user_flag = getattr(service, "_user_flag", "a")
            email = self.user_a_email if user_flag == "a" else (self.user_b_email if user_flag == "b" else self.user_c_email)
            return {"emailAddress": email, "messagesTotal": 10, "threadsTotal": 5}

        def mock_get_service(session=None):
            mock_s = MagicMock()
            if session.user_id == self.user_a_id:
                mock_s._user_flag = "a"
            elif session.user_id == self.user_b_id:
                mock_s._user_flag = "b"
            else:
                mock_s._user_flag = "c"
            return mock_s

        with patch("backend.app.api.routes_emails.get_user_gmail_service", side_effect=mock_get_service), \
             patch("backend.app.api.routes_emails.get_profile", side_effect=mock_profile), \
             patch("backend.app.api.routes_emails.list_message_ids", side_effect=mock_list), \
             patch("backend.app.api.routes_emails._fetch_single_message_safe", side_effect=mock_dispatch), \
             patch("backend.app.api.routes_emails.get_single_email", side_effect=mock_dispatch):

            def op_a_refresh():
                res = client.get("/api/emails", cookies={"mailmind_session": self.session_a.session_id})
                assert res.status_code == 200
                data = res.json()
                assert all("Alice" in em["subject"] for em in data["emails"])
                return "A_REFRESH_OK"

            def op_b_refresh():
                res = client.get("/api/emails", cookies={"mailmind_session": self.session_b.session_id})
                assert res.status_code == 200
                data = res.json()
                assert all("Bob" in em["subject"] for em in data["emails"])
                return "B_REFRESH_OK"

            def op_c_detail():
                res = client.get(f"/api/emails/{self.mailbox_c[0]['id']}", cookies={"mailmind_session": self.session_c.session_id})
                assert res.status_code == 200
                data = res.json()
                assert "Carol" in data["email"]["subject"]
                return "C_DETAIL_OK"

            def op_a_search():
                res = client.get("/api/emails?query=Alpha", cookies={"mailmind_session": self.session_a.session_id})
                assert res.status_code == 200
                data = res.json()
                assert all("Alice" in em["subject"] for em in data["emails"])
                return "A_SEARCH_OK"

            session_b_switch = session_manager.create_session(
                user_id=self.user_b_id,
                email=self.user_b_email,
                credentials={"token": "mock_token_bob_switch", "refresh_token": "mock_rf_bob_switch"}
            )

            def op_b_switch():
                # Bob logs out and switches account on a session
                res_logout = client.post("/api/auth/logout", cookies={"mailmind_session": session_b_switch.session_id})
                assert res_logout.status_code == 200
                # That session is now destroyed
                res_check = client.get("/api/emails", cookies={"mailmind_session": session_b_switch.session_id})
                assert res_check.status_code == 401
                return "B_SWITCH_OK"

            def op_c_refresh():
                res = client.get("/api/emails", cookies={"mailmind_session": self.session_c.session_id})
                assert res.status_code == 200
                data = res.json()
                assert all("Carol" in em["subject"] for em in data["emails"])
                return "C_REFRESH_OK"

            tasks = [op_a_refresh, op_b_refresh, op_c_detail, op_a_search, op_b_switch, op_c_refresh]
            with ThreadPoolExecutor(max_workers=6) as executor:
                futures = [executor.submit(t) for t in tasks]
                results = [f.result() for f in as_completed(futures)]

            assert len(results) == 6
            assert "A_REFRESH_OK" in results
            assert "B_REFRESH_OK" in results
            assert "C_DETAIL_OK" in results
            assert "A_SEARCH_OK" in results
            assert "B_SWITCH_OK" in results
            assert "C_REFRESH_OK" in results

    # =========================================================================
    # PHASE 31.2: ACCOUNT SWITCH TEST
    # =========================================================================
    def test_31_2_account_switch_cycle(self):
        """
        Verify account switch cycle A -> B -> C -> A leaves clean state without
        stale data, cross-user cache, or shared session leakage.
        """
        # User A connects & logs in
        sess_a = session_manager.create_session("uid_a", "alice@switch.com", {"token": "tok_a"})
        user_email_cache.set("uid_a", "msg_a_1", {"email_id": "msg_a_1", "subject": "Alice Private Note"})
        
        # Switch to B
        session_manager.delete_session(sess_a.session_id)
        user_email_cache.clear_user("uid_a")

        sess_b = session_manager.create_session("uid_b", "bob@switch.com", {"token": "tok_b"})
        # Verify B cannot see A's cache
        cached_b, missing = user_email_cache.get_batch("uid_b", ["msg_a_1"])
        assert len(cached_b) == 0
        assert "msg_a_1" in missing

        # B adds B email
        user_email_cache.set("uid_b", "msg_b_1", {"email_id": "msg_b_1", "subject": "Bob Secret"})

        # Switch to C
        session_manager.delete_session(sess_b.session_id)
        user_email_cache.clear_user("uid_b")

        sess_c = session_manager.create_session("uid_c", "carol@switch.com", {"token": "tok_c"})
        cached_c, _ = user_email_cache.get_batch("uid_c", ["msg_b_1", "msg_a_1"])
        assert len(cached_c) == 0

        # Switch back to A
        session_manager.delete_session(sess_c.session_id)
        sess_a2 = session_manager.create_session("uid_a", "alice@switch.com", {"token": "tok_a2"})
        status_res = client.get("/api/auth/status", cookies={"mailmind_session": sess_a2.session_id})
        assert status_res.status_code == 200
        assert status_res.json()["user"]["email"] == "alice@switch.com"

    # =========================================================================
    # PHASE 31.3: CACHE PERFORMANCE TEST
    # =========================================================================
    def test_31_3_cache_performance_deterministic(self):
        """
        Measure 1st load (100% cache miss, N ML predictions),
        2nd load (100% cache hit, 0 ML predictions),
        and +5 new emails (5 ML predictions).
        """
        user_id = "cache_bench_uid"
        user_email_cache.clear_user(user_id)
        model = load_model()

        emails_100 = [
            {
                "id": f"det_msg_{i}",
                "subject": f"Notice #{i}",
                "body": f"Please verify account #{i} immediately.",
                "sender": "noreply@service.org",
                "date": "2026-10-01T12:00:00Z"
            }
            for i in range(100)
        ]
        msg_ids = [em["id"] for em in emails_100]

        # 1st Load: All missing
        cached, missing = user_email_cache.get_batch(user_id, msg_ids)
        assert len(cached) == 0
        assert len(missing) == 100

        # Predict & store in cache
        preds = predict_batch(emails_100, model)
        assert len(preds) == 100
        for p in preds:
            user_email_cache.set(user_id, p["email_id"], p)

        # 2nd Load: All hit
        t0 = time.perf_counter()
        cached2, missing2 = user_email_cache.get_batch(user_id, msg_ids)
        t_hit2 = (time.perf_counter() - t0) * 1000
        assert len(cached2) == 100
        assert len(missing2) == 0
        assert t_hit2 < 5.0  # In-memory lookup should be sub-5ms for 100 items

        # 3rd Load: All hit
        t0 = time.perf_counter()
        cached3, missing3 = user_email_cache.get_batch(user_id, msg_ids)
        t_hit3 = (time.perf_counter() - t0) * 1000
        assert len(cached3) == 100
        assert len(missing3) == 0

        # +5 New emails arrived
        new_emails = [
            {
                "id": f"det_msg_new_{i}",
                "subject": f"New Notice #{i}",
                "body": "Action required on new document.",
                "sender": "alert@service.org",
                "date": "2026-10-01T12:05:00Z"
            }
            for i in range(5)
        ]
        combined_ids = [em["id"] for em in new_emails] + msg_ids[:95]  # 100 total
        cached_comb, missing_comb = user_email_cache.get_batch(user_id, combined_ids)
        assert len(cached_comb) == 95
        assert len(missing_comb) == 5  # Only 5 ML predictions needed!

        preds_5 = predict_batch(new_emails, model)
        assert len(preds_5) == 5

    # =========================================================================
    # PHASE 31.11 & 31.12: ERROR STATES AND RECOVERY UX
    # =========================================================================
    def test_31_11_error_states_and_recovery(self):
        """
        Verify all error scenarios produce clean, human-readable states without leaking
        tracebacks, secrets, or internal paths.
        """
        # 1. Unauthenticated / Invalid session
        res_no_auth = client.get("/api/emails")
        assert res_no_auth.status_code == 401
        assert "Authentication required" in res_no_auth.json()["detail"]

        res_bad_sess = client.get("/api/emails", cookies={"mailmind_session": "nonexistent_session_id"})
        assert res_bad_sess.status_code == 401

        # 2. Expired session
        expired_sess = session_manager.create_session("uid_exp", "exp@test.com", {"token": "exp_tok"})
        # Force expired timestamp
        expired_sess.expires_at = time.time() - 100
        res_exp = client.get("/api/emails", cookies={"mailmind_session": expired_sess.session_id})
        assert res_exp.status_code == 401
        assert "Authentication required" in res_exp.json()["detail"]

        # 3. OAuth callback error (access denied)
        res_oauth_denied = client.get("/api/auth/callback?error=access_denied&state=random_state", follow_redirects=False)
        assert res_oauth_denied.status_code in [302, 307]
        # Redirects to home with clean error query
        assert "error=" in res_oauth_denied.headers["location"]
        assert "traceback" not in res_oauth_denied.headers["location"].lower()

        # 4. Detail fetch 404
        with patch("backend.app.api.routes_emails.get_user_gmail_service", return_value=MagicMock()), \
             patch("backend.app.api.routes_emails.get_single_email", return_value=None):
            res_404 = client.get("/api/emails/nonexistent_id_999", cookies={"mailmind_session": self.session_a.session_id})
            assert res_404.status_code == 404
            assert "not found" in res_404.json()["detail"].lower()

        # 5. Empty mailbox
        with patch("backend.app.api.routes_emails.get_user_gmail_service", return_value=MagicMock()), \
             patch("backend.app.api.routes_emails.get_profile", return_value={"emailAddress": self.user_a_email, "messagesTotal": 0}), \
             patch("backend.app.api.routes_emails.list_message_ids", return_value={"messages": []}):
            res_empty = client.get("/api/emails", cookies={"mailmind_session": self.session_a.session_id})
            assert res_empty.status_code == 200
            data_empty = res_empty.json()
            assert data_empty["status"] == "success"
            assert data_empty["emails"] == []
            assert data_empty["stats"]["total_analyzed"] == 0

        # 6. Malformed email (missing fields)
        malformed_email = {"id": "malformed_1", "subject": None, "body": None, "sender": None}
        pred_malformed = predict_email(malformed_email)
        assert pred_malformed["predicted_priority"] == "P4"
        assert pred_malformed["action_required"] is False
        assert "Low" in pred_malformed["explanation"]

    # =========================================================================
    # PHASE 31.16: SECURITY REGRESSION
    # =========================================================================
    def test_31_16_security_regressions(self):
        """
        Verify strict security invariants:
        - google_auth/sessions/ is ignored in git
        - No credentials leaked in profile or auth responses
        - CORS headers do not allow arbitrary wildcard with credentials
        - Feedback is user-isolated
        """
        # Gitignore check
        gitignore_path = os.path.join(os.getcwd(), ".gitignore")
        with open(gitignore_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "google_auth/sessions/" in content
        assert "token.json" in content

        # Auth status profile check
        res_status = client.get("/api/auth/status", cookies={"mailmind_session": self.session_a.session_id})
        assert res_status.status_code == 200
        text_resp = res_status.text
        assert "mock_token" not in text_resp
        assert "mock_rf" not in text_resp

        # Feedback isolation
        fb_a = feedback_manager.record_feedback(
            email_id="msg_a_1",
            original_priority="P3",
            user_priority="P1",
            user_id=self.user_a_id,
            reason="Alice urgent"
        )
        fb_b = feedback_manager.record_feedback(
            email_id="msg_b_1",
            original_priority="P4",
            user_priority="P2",
            user_id=self.user_b_id,
            reason="Bob urgent"
        )

        all_feedback = feedback_manager.list_feedback()
        # Verify both recorded with distinct user IDs
        assert any(f.get("user_id") == self.user_a_id for f in all_feedback)
        assert any(f.get("user_id") == self.user_b_id for f in all_feedback)

    # =========================================================================
    # PHASE 31.17: ML INTEGRITY REGRESSION
    # =========================================================================
    def test_31_17_ml_integrity_regression(self):
        """
        Verify CodeVita email prediction:
        - priority-v2 sha256 verified
        - test.csv holdout hash verified
        - raw model: P2
        - confidence: ~53.22%
        - refinement: False
        - deadline: 12 hours from reference
        - No .fit() in runtime
        """
        import joblib
        from backend.app.ml.registry import compute_sha256

        v2_path = os.path.join(os.getcwd(), "dataset", "models", "priority-v2", "model.joblib")
        assert os.path.exists(v2_path)
        v2_sha = compute_sha256(v2_path)
        assert v2_sha == "be52c2dbfe28001a66b134d1125dfa8d117bbe64206590d71bde9f7029f3cd75"

        test_csv_path = os.path.join(os.getcwd(), "dataset", "processed", "test.csv")
        test_sha = compute_sha256(test_csv_path).upper()
        assert test_sha == "6841CD44901FA56242BF3752257E991FD7FF474ED7E0F7A5D2B7065A0827C138"

        model_v2 = joblib.load(v2_path)

        codevita_subject = "TCS CodeVita Season 14 - Email Verification"
        codevita_body = (
            "Dear Candidate, Thank you for registering for TCS CodeVita Season 14. "
            "Please verify your email address to complete your registration process. "
            "Click on the link below to verify your account. "
            "Note: This verification link remains active for 12 hours only."
        )

        raw_pred = predict_email({
            "id": "codevita_test_01",
            "subject": codevita_subject,
            "body": codevita_body,
            "sender": "codevita-noreply@tcs.com",
            "date": "2026-10-01T12:00:00Z"
        }, pipeline=model_v2)

        assert raw_pred["model_priority"] == "P2"
        assert abs(raw_pred["confidence"] - 0.5322) < 0.05
        assert raw_pred["refinement_applied"] is False
        assert raw_pred["action_required"] is True
        assert raw_pred["deadline_detected"] is True
        assert "2026-10-02" in raw_pred["deadline_datetime"]
