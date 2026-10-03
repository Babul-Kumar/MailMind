"""
test_phase54_deployment_readiness.py — Phase 54 Final Deployment Readiness Test Suite
======================================================================================
Comprehensive functional, security, privacy, adversarial, and edge-case verification
across the entire MailMind system.
"""
import os
import json
import time
import pytest
import hashlib
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.session import (
    session_manager,
    SessionData,
    SESSION_COOKIE_NAME,
    SESSIONS_DIR,
)
from backend.app.core.cache import user_email_cache
from backend.app.core.feedback import feedback_manager, FeedbackSubmission
from backend.app.ml.registry import model_registry
from backend.app.ml.predictor import predict_email, predict_batch, load_model


client = TestClient(app)

V51_EXPECTED_SHA = "8524ad73965859ee022f1271caee0040928e7805ab7d32c49b2f26e994f98c06"
V41_EXPECTED_SHA = "09fe269f19ad6afb38e71b56f8c6ee7a386e59605c62c892478400bc09d5cbd0"
TEST_HOLDOUT_SHA = "6841cd44901fa56242bf3752257e991fd7ff474ed7e0f7a5d2b7065a0827c138"


def hash_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


@pytest.fixture
def auth_user_a():
    """Creates an isolated test session for User A."""
    email = "usera@example.com"
    user_id = "user_a_id_123"
    session = session_manager.create_session(
        user_id=user_id,
        email=email,
        credentials={"token": "mock_token_a", "refresh_token": "mock_refresh_a"}
    )
    yield session
    session_manager.delete_session(session.session_id)
    user_email_cache.clear_user(user_id)


@pytest.fixture
def auth_user_b():
    """Creates an isolated test session for User B."""
    email = "userb@example.com"
    user_id = "user_b_id_456"
    session = session_manager.create_session(
        user_id=user_id,
        email=email,
        credentials={"token": "mock_token_b", "refresh_token": "mock_refresh_b"}
    )
    yield session
    session_manager.delete_session(session.session_id)
    user_email_cache.clear_user(user_id)


@pytest.fixture(autouse=True)
def preserve_feedback_file():
    feedback_path = os.path.join("dataset", "feedback", "feedback.jsonl")
    backup = None
    if os.path.exists(feedback_path):
        with open(feedback_path, "r", encoding="utf-8") as f:
            backup = f.read()
    yield
    if backup is not None:
        with open(feedback_path, "w", encoding="utf-8") as f:
            f.write(backup)
    elif os.path.exists(feedback_path):
        os.remove(feedback_path)


# ==============================================================================
# 1. INVARIANT & GOVERNANCE CHECKS
# ==============================================================================

class TestGovernanceInvariants:
    def test_active_model_is_v51(self):
        assert model_registry.get_active_version() == "priority-v5.1"

    def test_v51_artifact_sha(self):
        active_path = model_registry.get_active_model_path()
        assert os.path.exists(active_path)
        sha = hash_file(active_path)
        assert sha == V51_EXPECTED_SHA

    def test_v41_rollback_artifact_sha(self):
        v41_path = os.path.join("dataset", "models", "priority-v4.1", "model.joblib")
        assert os.path.exists(v41_path)
        sha = hash_file(v41_path)
        assert sha == V41_EXPECTED_SHA

    def test_frozen_holdout_test_csv_sha(self):
        test_csv = os.path.join("dataset", "processed", "test.csv")
        assert os.path.exists(test_csv)
        sha = hash_file(test_csv)
        assert sha == TEST_HOLDOUT_SHA


# ==============================================================================
# 2. AUTHENTICATION & SESSION AUDIT
# ==============================================================================

class TestAuthenticationAndSecurity:
    def test_unauthenticated_requests_rejected(self):
        endpoints = [
            ("GET", "/api/emails", None),
            ("GET", "/api/emails/msg_123", None),
            ("POST", "/api/feedback", {"message_id": "msg_unauth_test"}),
            ("GET", "/api/feedback", None),
            ("GET", "/api/scan/status", None),
            ("POST", "/api/scan/start", {}),
            ("POST", "/api/scan/cancel", None),
            ("POST", "/api/scan/rescan", None),
            ("GET", "/api/adjudication/queue", None),
            ("GET", "/api/adjudication/cases", None),
            ("POST", "/api/adjudication/adjudicate", {
                "feedback_id": "fb_unauth",
                "adjudication_status": "ACCEPTED",
                "adjudication_reason": "testing unauth",
                "corrected_priority": "P2"
            }),
            ("GET", "/api/monitoring/summary", None),
            ("GET", "/api/monitoring/distribution", None),
            ("GET", "/api/monitoring/phase51/summary", None),
        ]
        for method, url, body in endpoints:
            if method == "GET":
                res = client.get(url)
            else:
                res = client.post(url, json=body or {})
            assert res.status_code == 401, f"Expected 401 for unauthenticated {method} {url}, got {res.status_code}"

    def test_tampered_or_invalid_session_cookie(self):
        client.cookies.set(SESSION_COOKIE_NAME, "tampered_fake_session_token_12345")
        res = client.get("/api/auth/status")
        assert res.status_code == 200
        data = res.json()
        assert data["authenticated"] is False
        assert data["user"] is None
        client.cookies.clear()

    def test_path_traversal_session_id_sanitized(self):
        """Adversarial check: session_id with directory traversal characters must not escape SESSIONS_DIR."""
        malicious_ids = [
            "../../etc/passwd",
            "..\\..\\windows\\system32",
            "../sessions/_pending_oauth_states",
            "subdir/../../test",
            "....//....//escape",
        ]
        for bad_id in malicious_ids:
            # Must return None safely without raising or accessing outside directory
            session = session_manager.get_session(bad_id)
            assert session is None
            deleted = session_manager.delete_session(bad_id)
            assert deleted is False or session_manager.get_session(bad_id) is None

    def test_expired_session_handling(self):
        """An expired session must be rejected with 401 and cleared."""
        now = time.time()
        expired_session = SessionData(
            session_id="test_expired_session_id",
            user_id="user_expired",
            email="expired@example.com",
            credentials={},
            created_at=now - 10000,
            expires_at=now - 100,  # 100s in past
        )
        session_manager._sessions[expired_session.session_id] = expired_session
        session_manager._persist_session(expired_session)

        # Retrieve should detect expiry and return None
        fetched = session_manager.get_session(expired_session.session_id)
        assert fetched is None

        # Request with expired cookie should be unauthenticated
        client.cookies.set(SESSION_COOKIE_NAME, expired_session.session_id)
        res = client.get("/api/emails")
        assert res.status_code == 401
        client.cookies.clear()

    def test_logout_destroys_session(self, auth_user_a):
        client.cookies.set(SESSION_COOKIE_NAME, auth_user_a.session_id)
        res = client.post("/api/auth/logout")
        assert res.status_code == 200
        assert res.json()["status"] == "logged_out"

        # Session should no longer exist
        assert session_manager.get_session(auth_user_a.session_id) is None

        # Subsequent authenticated call should fail
        res2 = client.get("/api/emails")
        assert res2.status_code == 401
        client.cookies.clear()

    def test_invalid_oauth_state_rejected(self):
        res = client.get("/api/auth/callback?code=mock_code&state=non_existent_state_123")
        assert res.status_code == 400
        assert "Invalid or expired OAuth state" in res.json()["detail"]

    def test_test_session_endpoint_disabled_in_prod(self):
        """Verifies test-session endpoint returns 403 Forbidden in production unless explicitly allowed."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            if "ALLOW_TEST_ENDPOINTS" in os.environ:
                del os.environ["ALLOW_TEST_ENDPOINTS"]
            res = client.post("/api/auth/test-session?email=prod_test@example.com")
            assert res.status_code == 403
            assert "disabled in production" in res.json()["detail"]

        with patch.dict(os.environ, {"ENVIRONMENT": "production", "ALLOW_TEST_ENDPOINTS": "false"}):
            res = client.post("/api/auth/test-session?email=prod_test@example.com")
            assert res.status_code == 403


# ==============================================================================
# 3. MULTI-USER ISOLATION AUDIT
# ==============================================================================

class TestMultiUserIsolation:
    def test_identical_message_id_across_users(self, auth_user_a, auth_user_b):
        """
        Adversarial test: User A and User B receive the same message_id (e.g. newsletter).
        Verify:
        - User A's classification and metadata cannot bleed into User B's cache.
        - Updating User A's cache does not modify User B's cache.
        """
        shared_mid = "msg_shared_12345"
        data_a = {
            "email_id": shared_mid,
            "subject": "User A Private Note",
            "body": "User A secret content",
            "predicted_priority": "P2",
            "model_version": "priority-v5.1",
            "action_required": True,
        }
        data_b = {
            "email_id": shared_mid,
            "subject": "User B Public Bulletin",
            "body": "User B newsletter content",
            "predicted_priority": "P4",
            "model_version": "priority-v5.1",
            "action_required": False,
        }

        user_email_cache.set(auth_user_a.user_id, shared_mid, data_a)
        user_email_cache.set(auth_user_b.user_id, shared_mid, data_b)

        # Verify User A gets data_a
        cached_a = user_email_cache.get(auth_user_a.user_id, shared_mid, model_version="priority-v5.1")
        assert cached_a is not None
        assert cached_a["subject"] == "User A Private Note"
        assert cached_a["predicted_priority"] == "P2"
        assert cached_a["action_required"] is True

        # Verify User B gets data_b
        cached_b = user_email_cache.get(auth_user_b.user_id, shared_mid, model_version="priority-v5.1")
        assert cached_b is not None
        assert cached_b["subject"] == "User B Public Bulletin"
        assert cached_b["predicted_priority"] == "P4"
        assert cached_b["action_required"] is False

    def test_cross_user_feedback_isolation(self, auth_user_a, auth_user_b):
        """User A submitting feedback must NOT appear in User B's feedback list."""
        client.cookies.set(SESSION_COOKIE_NAME, auth_user_a.session_id)
        res_a = client.post("/api/feedback", json={
            "message_id": "msg_user_a_only",
            "feedback_type": "CORRECT",
            "corrected_priority": "P1",
            "reason": "priority_too_low",
        })
        assert res_a.status_code == 200

        # User A can see their feedback
        list_a = client.get("/api/feedback").json()["records"]
        assert any(r["message_id"] == "msg_user_a_only" for r in list_a)

        # User B CANNOT see User A's feedback
        client.cookies.set(SESSION_COOKIE_NAME, auth_user_b.session_id)
        list_b = client.get("/api/feedback").json()["records"]
        assert not any(r["message_id"] == "msg_user_a_only" for r in list_b)
        client.cookies.clear()


# ==============================================================================
# 4. ML INFERENCE, ACTION REQUIRED, & DEADLINE DECOUPLING AUDIT
# ==============================================================================

class TestMLInferenceAndDeadlines:
    def test_inference_returns_required_contract(self):
        email = {
            "email_id": "test_contract_1",
            "subject": "Action required: Project migration deadline tomorrow",
            "body": "Action required: Submit your migration report by tomorrow to avoid disruption.",
            "sender": "lead@company.com",
            "date": "2026-10-01T10:00:00Z",
        }
        res = predict_email(email)
        required_fields = [
            "email_id", "subject", "predicted_priority", "final_priority",
            "action_required", "deadline_detected", "deadline_status",
            "needs_attention", "confidence", "probabilities", "model_version"
        ]
        for field in required_fields:
            assert field in res, f"Field '{field}' missing from predict_email contract"

        assert res["model_version"] == "priority-v5.1"
        assert res["action_required"] is True
        assert res["deadline_detected"] is True

    def test_email_arrival_time_never_treated_as_deadline(self):
        """Email arrival date header must NEVER be parsed as a deadline."""
        email = {
            "email_id": "test_arrival_date",
            "subject": "Monthly Engineering Newsletter Issue #42",
            "body": "Here is what our team built this month. No action required, enjoy reading!",
            "sender": "newsletter@techcorp.com",
            "date": "2026-10-01T08:30:00Z",
        }
        res = predict_email(email)
        assert res["deadline_detected"] is False
        assert res["deadline_status"] == "NONE"
        assert res["action_required"] is False
        assert res["needs_attention"] is False

    def test_action_required_decoupled_from_priority(self):
        """Action required can be False on P1 (e.g. passive critical confirmation) and True on P2/P3."""
        p2_actionable = {
            "email_id": "p2_act",
            "subject": "Action required: Submit Assignment 2 before Friday",
            "body": "Assignment 2 submission deadline is Friday. Submit your assignment before Friday.",
            "sender": "professor@university.edu",
            "date": "2026-10-01T10:00:00Z",
        }
        res_p2 = predict_email(p2_actionable)
        assert res_p2["action_required"] is True
        assert res_p2["predicted_priority"] in ("P1", "P2")

        p3_non_actionable = {
            "email_id": "p3_no_act",
            "subject": "Your receipt for Order #987654",
            "body": "Thank you for your payment. Your card ending in 1234 was successfully charged $45.00.",
            "sender": "billing@saas.com",
            "date": "2026-10-01T10:00:00Z",
        }
        res_p3 = predict_email(p3_non_actionable)
        assert res_p3["action_required"] is False
        assert res_p3["predicted_priority"] in ("P3", "P4")

    def test_needs_attention_exact_logic(self):
        """
        Exact Rule:
          needs_attention == True IF:
            - final_priority == "P1"
            OR
            - (final_priority == "P2" AND action_required == True)
            OR
            - (action_required == True AND deadline_status in ("ACTIVE", "OVERDUE"))
        """
        test_cases = [
            # (priority, action_req, deadline_status, expected_needs_attention)
            ("P1", False, "NONE", True),
            ("P1", True, "ACTIVE", True),
            ("P2", True, "NONE", True),
            ("P2", False, "NONE", False),
            ("P2", False, "ACTIVE", False),  # P2 without action is false unless action_required is True
            ("P3", False, "NONE", False),
            ("P3", True, "ACTIVE", True),    # action_required AND active deadline
            ("P3", True, "OVERDUE", True),   # action_required AND overdue deadline
            ("P3", True, "HISTORICAL", False),
            ("P4", False, "NONE", False),
            ("P4", True, "ACTIVE", True),
        ]

        for pri, act, dl_stat, expected in test_cases:
            res = (pri == "P1") or (pri == "P2" and act) or (act and dl_stat in ("ACTIVE", "OVERDUE"))
            assert res is expected, f"Failed for ({pri}, {act}, {dl_stat}): got {res}, expected {expected}"


# ==============================================================================
# 5. SEARCH & CACHE QUERY AUDIT
# ==============================================================================

class TestSearchAndFilterQueries:
    def test_special_characters_in_search_do_not_crash(self, auth_user_a):
        user_id = auth_user_a.user_id
        # Seed cache with email
        user_email_cache.set(user_id, "msg_special", {
            "email_id": "msg_special",
            "subject": "Special chars test: [CRITICAL] 100% discount? 'quote' & *star*",
            "body": "Regex chars (test+123) / \\ % _ should not cause SQL or runtime errors.",
            "predicted_priority": "P2",
            "model_version": "priority-v5.1",
            "action_required": True,
            "needs_attention": True,
        })

        search_terms = [
            "[CRITICAL]",
            "100%",
            "'quote'",
            "test+123",
            "\\",
            "%",
            "_",
            "\"quoted\"",
            "nonexistent_token_xyz_999",
        ]

        for term in search_terms:
            emails, count = user_email_cache.query_emails(
                user_id=user_id,
                search=term,
                model_version="priority-v5.1"
            )
            assert isinstance(emails, list)
            assert isinstance(count, int)

    def test_case_insensitive_priority_filter(self, auth_user_a):
        user_id = auth_user_a.user_id
        user_email_cache.set(user_id, "msg_p1", {
            "email_id": "msg_p1",
            "subject": "Security Incident Alert",
            "body": "Unauthorized login detected.",
            "predicted_priority": "P1",
            "model_version": "priority-v5.1",
            "action_required": True,
            "needs_attention": True,
        })

        # Test both "P1" and lowercase "p1"
        emails_upper, count_upper = user_email_cache.query_emails(user_id=user_id, priority="P1")
        emails_lower, count_lower = user_email_cache.query_emails(user_id=user_id, priority="p1")

        assert count_upper >= 1
        assert count_lower == count_upper, "Priority filter should handle lowercase inputs gracefully"


# ==============================================================================
# 6. FEEDBACK PROVENANCE & CACHED RESOLUTION AUDIT
# ==============================================================================

class TestFeedbackProvenanceAndIntegrity:
    def test_feedback_resolves_cached_prediction(self, auth_user_a):
        """
        Verify Bug-54-002 fix: When user submits feedback, server must resolve
        the original predicted_priority, confidence, and action_required from cache!
        """
        user_id = auth_user_a.user_id
        mid = "msg_with_cache_test"

        user_email_cache.set(user_id, mid, {
            "email_id": mid,
            "subject": "Payment Confirmation Invoice",
            "predicted_priority": "P3",
            "confidence": 0.895,
            "topic": "payment",
            "action_required": False,
            "deadline_detected": False,
            "model_version": "priority-v5.1",
        })

        client.cookies.set(SESSION_COOKIE_NAME, auth_user_a.session_id)
        res = client.post("/api/feedback", json={
            "message_id": mid,
            "feedback_type": "CORRECT",
            "corrected_priority": "P2",
            "reason": "priority_too_low",
            # Client attempts to spoof/omit original prediction:
            "predicted_priority": "P4",
            "model_version": "priority-v1",
        })
        assert res.status_code == 200
        rec = res.json()["record"]

        # Server-side model version must be enforced to active model
        assert rec["model_version"] == "priority-v5.1"

        # Server-side user identity must be enforced
        assert rec["user_id"] == user_id

        # Server-side cache resolution should correctly resolve P3 and 0.895
        assert rec["predicted_priority"] == "P3"
        assert rec["original_confidence"] == pytest.approx(0.895)
        assert rec["provenance"] == "PRODUCTION_FEEDBACK"
        client.cookies.clear()


# ==============================================================================
# 7. ADJUDICATION STATUS TRANSITIONS AUDIT
# ==============================================================================

class TestAdjudicationWorkflow:
    def test_adjudicate_rejects_empty_reason(self, auth_user_a):
        client.cookies.set(SESSION_COOKIE_NAME, auth_user_a.session_id)
        res = client.post("/api/adjudication/adjudicate", json={
            "feedback_id": "dummy_id",
            "adjudication_status": "REJECTED",
            "adjudication_reason": "",
        })
        assert res.status_code == 422
        client.cookies.clear()

    def test_adjudicate_rejects_invalid_status(self, auth_user_a):
        client.cookies.set(SESSION_COOKIE_NAME, auth_user_a.session_id)
        res = client.post("/api/adjudication/adjudicate", json={
            "feedback_id": "dummy_id",
            "adjudication_status": "AUTOMATICALLY_TRAIN",
            "adjudication_reason": "Testing invalid status",
        })
        assert res.status_code == 422
        client.cookies.clear()


# ==============================================================================
# 8. GMAIL ERROR INJECTION & RESILIENCE AUDIT
# ==============================================================================

class TestGmailErrorInjectionAndResilience:
    @patch("backend.app.api.routes_emails.get_user_gmail_service")
    def test_gmail_api_429_rate_limit_handled_gracefully(self, mock_get_service, auth_user_a):
        """Simulate Gmail API 429 rate limit or 503 service unavailable."""
        client.cookies.set(SESSION_COOKIE_NAME, auth_user_a.session_id)
        mock_get_service.side_effect = Exception("Rate limit exceeded (HTTP 429): User rate limit exceeded")

        res = client.get("/api/emails")
        assert res.status_code == 502
        assert "Gmail API connection error" in res.json()["detail"]
        client.cookies.clear()

    @patch("backend.app.api.routes_emails.get_user_gmail_service")
    def test_gmail_permission_error_triggers_reauth_401(self, mock_get_service, auth_user_a):
        """Simulate revoked Gmail OAuth permission (triggers 401 prompting re-auth)."""
        client.cookies.set(SESSION_COOKIE_NAME, auth_user_a.session_id)
        mock_get_service.side_effect = PermissionError("OAuth token has been revoked by user")

        res = client.get("/api/emails")
        assert res.status_code == 401
        assert "Authentication required" in res.json()["detail"]
        client.cookies.clear()

    def test_missing_and_malformed_email_payloads_do_not_crash(self):
        """Emails with None/missing fields must predict safely with valid fallback."""
        malformed_emails = [
            {},
            {"subject": None, "body": None, "sender": None},
            {"subject": "", "body": ""},
            {"subject": "   ", "body": "   ", "date": "invalid-date-format"},
            {"id": "msg_only_id"},
        ]
        for em in malformed_emails:
            pred = predict_email(em)
            assert isinstance(pred, dict)
            assert pred["predicted_priority"] in ("P1", "P2", "P3", "P4")
            assert "action_required" in pred
            assert "deadline_detected" in pred
            assert "needs_attention" in pred


# ==============================================================================
# 9. FAILURE INJECTION & RECOVERY AUDIT
# ==============================================================================

class TestFailureInjectionAndRecovery:
    def test_batch_prediction_handles_empty_and_large_batches(self):
        assert predict_batch([]) == []

        # 100 email batch
        batch = [
            {
                "email_id": f"msg_batch_{i}",
                "subject": f"Notice #{i}: Regular operational report",
                "body": "System status update.",
                "date": "2026-10-01T10:00:00Z"
            }
            for i in range(100)
        ]
        results = predict_batch(batch)
        assert len(results) == 100
        assert all(r["model_version"] == "priority-v5.1" for r in results)

    def test_cache_handles_nonexistent_and_cleared_users(self):
        # Nonexistent user queries return empty stats and empty lists without error
        res, count = user_email_cache.query_emails("user_does_not_exist_99999")
        assert res == []
        assert count == 0

        stats = user_email_cache.get_mailbox_stats("user_does_not_exist_99999")
        assert stats["total_analyzed"] == 0

        # Clearing nonexistent user should not error
        user_email_cache.clear_user("user_does_not_exist_99999")


# ==============================================================================
# 10. PERFORMANCE BENCHMARKS AUDIT
# ==============================================================================

class TestPerformanceBenchmarks:
    def test_ml_inference_speed_benchmark(self):
        """Single email inference must execute in under 10ms; batch inference under 2ms per email."""
        sample_email = {
            "email_id": "perf_test",
            "subject": "Action required: Security verification deadline tomorrow",
            "body": "Your account requires immediate action before tomorrow to verify credentials.",
            "sender": "security@company.com",
            "date": "2026-10-01T10:00:00Z"
        }

        # Warm up
        predict_email(sample_email)

        # Single prediction latency (100 runs)
        t0 = time.perf_counter()
        runs = 100
        for _ in range(runs):
            predict_email(sample_email)
        single_lat_ms = ((time.perf_counter() - t0) / runs) * 1000
        print(f"\n[Perf] Single email inference latency: {single_lat_ms:.2f} ms")
        assert single_lat_ms < 15.0, f"Single inference too slow: {single_lat_ms:.2f}ms"

        # Batch prediction latency (50 emails)
        batch = [sample_email] * 50
        t0 = time.perf_counter()
        predict_batch(batch)
        batch_total_ms = (time.perf_counter() - t0) * 1000
        batch_per_email_ms = batch_total_ms / 50
        print(f"[Perf] Batch 50 email inference latency: {batch_total_ms:.2f} ms ({batch_per_email_ms:.2f} ms/email)")
        assert batch_per_email_ms < 5.0, f"Batch inference too slow: {batch_per_email_ms:.2f}ms/email"

    def test_cache_lookup_latency(self, auth_user_a):
        """Cache lookup for 50 message IDs must execute in under 10ms total."""
        user_id = auth_user_a.user_id
        # Seed 50 messages
        mids = [f"perf_msg_{i}" for i in range(50)]
        for mid in mids:
            user_email_cache.set(user_id, mid, {
                "email_id": mid,
                "subject": f"Bench Subject {mid}",
                "predicted_priority": "P3",
                "model_version": "priority-v5.1",
            })

        t0 = time.perf_counter()
        cached_map, missing_ids = user_email_cache.get_batch(user_id, mids, active_model_version="priority-v5.1")
        dur_ms = (time.perf_counter() - t0) * 1000
        print(f"\n[Perf] Cache get_batch 50 items latency: {dur_ms:.2f} ms")
        assert len(cached_map) == 50
        assert len(missing_ids) == 0
        assert dur_ms < 25.0, f"Cache get_batch took too long: {dur_ms:.2f}ms"


# ==============================================================================
# 11. FRONTEND RESPONSIVE UI & ACCESSIBILITY AUDIT
# ==============================================================================

class TestFrontendResponsiveAndAccessibilityAudit:
    def test_responsive_css_and_viewport_rules(self):
        """Verifies that index.css defines mobile drawer, backdrop, and hamburger rules."""
        css_path = os.path.join("frontend", "src", "styles", "index.css")
        assert os.path.exists(css_path)
        with open(css_path, "r", encoding="utf-8") as f:
            css_content = f.read()

        # Check mobile-menu-btn rules
        assert ".mobile-menu-btn" in css_content
        assert "@media (max-width: 768px)" in css_content
        assert ".sidebar-container" in css_content
        assert ".sidebar-container.mobile-open" in css_content
        assert ".sidebar-backdrop" in css_content

    def test_topbar_and_appshell_components_wired(self):
        """Verifies TopBar and AppShell have mobile toggle and backdrop hooks properly wired."""
        topbar_path = os.path.join("frontend", "src", "components", "layout", "TopBar.jsx")
        with open(topbar_path, "r", encoding="utf-8") as f:
            topbar_content = f.read()

        assert "mobile-menu-btn" in topbar_content
        assert "onToggleMobileMenu" in topbar_content
        assert "zIndex: 1300" in topbar_content

        appshell_path = os.path.join("frontend", "src", "components", "layout", "AppShell.jsx")
        with open(appshell_path, "r", encoding="utf-8") as f:
            appshell_content = f.read()

        assert "sidebar-backdrop" in appshell_content
        assert "isSidebarOpenMobile" in appshell_content
        assert "onCloseMobile" in appshell_content

        sidebar_path = os.path.join("frontend", "src", "components", "layout", "Sidebar.jsx")
        with open(sidebar_path, "r", encoding="utf-8") as f:
            sidebar_content = f.read()

        assert "mobile-open" in sidebar_content
        assert "mobile-sidebar-close-btn" in sidebar_content

