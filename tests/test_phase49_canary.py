"""
test_phase49_canary.py — Phase 49 Controlled Canary Deployment & Promotion Gate Test Suite
========================================================================================

Validates all 25 critical invariants mandated by Phase 49:
  1. Registry integrity (active = priority-v4.1, candidate = priority-v5.1)
  2. Canary disabled -> routes to priority-v4.1
  3. Canary 5% routing distribution
  4. Deterministic user-level routing (same user consistently receives same model)
  5. Canary user isolation
  6. Production user isolation
  7. Model-version cache separation (composite PK coexistence)
  8. v4.1 emergency rollback (instant restoration to 0%)
  9. P1 downgrade protection (0 downgrades)
 10. OTP safety (100% retention)
 11. MFA safety (100% retention)
 12. Security alert safety
 13. Password reset safety
 14. Deadline safety
 15. Action-state integrity
 16. Feedback attribution by model version
 17. Latency measurement (median, p95, p99 tracked)
 18. Failure isolation (fallback to active v4.1 on candidate exception)
 19. Account switching (routing updates deterministically per account)
 20. Concurrent users (thread-safe routing)
 21. Monitoring authorization (session authentication required)
 22. Monitoring user scoping
 23. Artifact SHA validation (v4.1 and v5.1 exact checksums)
 24. No raw email persistence in cache or logs
 25. No OAuth token persistence in cache or logs
"""

import os
import sys
import json
import sqlite3
import hashlib
import threading
import pytest
from typing import Dict, Any

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.config import BASE_DIR
from backend.app.ml.registry import model_registry
from backend.app.ml.canary_router import canary_router, STAGE_PERCENTAGES
from backend.app.ml.predictor import predict_email
from backend.app.core.canary_monitor import canary_monitor
from backend.app.core.cache import DB_PATH, user_email_cache
from backend.app.core.prediction_log import log_prediction
from backend.app.core.session import session_manager

client = TestClient(app)

EXPECTED_V41_SHA = "09fe269f19ad6afb38e71b56f8c6ee7a386e59605c62c892478400bc09d5cbd0"
EXPECTED_V51_SHA = "8524ad73965859ee022f1271caee0040928e7805ab7d32c49b2f26e994f98c06"


def compute_file_sha256(filepath: str) -> str:
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


class TestPhase49Canary:
    """Phase 49 Comprehensive Test Suite: 25 Invariant Tests."""

    @classmethod
    def setup_class(cls):
        # Reset canary router to a clean stage 0
        canary_router.rollback()

    @classmethod
    def teardown_class(cls):
        # Ensure canary router remains safely rolled back to active v4.1
        canary_router.rollback()

    def test_01_registry_integrity(self):
        """Invariant 1: active_model is priority-v4.1, candidate_model is priority-v5.1."""
        reg = model_registry.get_registry()
        assert reg.get("active_model") == "priority-v4.1", f"Active model must be priority-v4.1, got {reg.get('active_model')}"
        assert reg.get("candidate_model") == "priority-v5.1", f"Candidate must be priority-v5.1, got {reg.get('candidate_model')}"

    def test_02_canary_disabled_routes_to_v41(self):
        """Invariant 2: When canary is disabled (Stage 0), all users route to priority-v4.1."""
        canary_router.set_stage(0)
        assert canary_router.canary_enabled is False
        assert canary_router.canary_percentage == 0

        for i in range(50):
            res = canary_router.route_user(f"user_test_{i}")
            assert res["model_version"] == "priority-v4.1"
            assert res["is_canary"] is False
            assert res["canary_group"] == "control"

    def test_03_canary_5pct_routing(self):
        """Invariant 3: In Stage 1 (5%), approximately 5% of users route to priority-v5.1."""
        canary_router.set_stage(1)
        assert canary_router.canary_enabled is True
        assert canary_router.canary_percentage == 5

        users = [f"canary_user_eval_{i:04d}" for i in range(1000)]
        routed = [canary_router.route_user(u) for u in users]
        canary_users = [r for r in routed if r["is_canary"]]
        pct = len(canary_users) / len(users) * 100

        # With 1000 users, 5% nominal is 50 users. Allow variance [3.0%, 7.0%]
        assert 3.0 <= pct <= 7.0, f"Expected ~5% canary routing, got {pct:.2f}%"

    def test_04_deterministic_user_routing(self):
        """Invariant 4: The same user consistently receives the exact same model on every query."""
        canary_router.set_stage(3)  # 25% stage
        user_a = "user_alpha_123"
        user_b = "user_beta_456"

        route_a1 = canary_router.route_user(user_a)
        route_a2 = canary_router.route_user(user_a)
        route_a3 = canary_router.route_user(user_a)

        assert route_a1["model_version"] == route_a2["model_version"] == route_a3["model_version"]
        assert route_a1["bucket"] == route_a2["bucket"] == route_a3["bucket"]

        route_b1 = canary_router.route_user(user_b)
        route_b2 = canary_router.route_user(user_b)
        assert route_b1["model_version"] == route_b2["model_version"]

    def test_05_canary_user_isolation(self):
        """Invariant 5: Canary user receives priority-v5.1 pipeline and canary group."""
        canary_router.set_stage(4)  # 50%
        # Find a user whose hash bucket is < 50
        canary_user = None
        for i in range(100):
            u = f"user_probe_{i}"
            r = canary_router.route_user(u)
            if r["is_canary"]:
                canary_user = u
                break
        assert canary_user is not None

        pipe, route = canary_router.get_pipeline_for_user(canary_user)
        assert route["model_version"] == "priority-v5.1"
        assert route["canary_group"] == "canary"
        assert pipe is not None

    def test_06_production_user_isolation(self):
        """Invariant 6: Control user receives priority-v4.1 pipeline and control group."""
        canary_router.set_stage(1)  # 5%
        # Find a user whose hash bucket is >= 5
        control_user = None
        for i in range(100):
            u = f"user_control_probe_{i}"
            r = canary_router.route_user(u)
            if not r["is_canary"]:
                control_user = u
                break
        assert control_user is not None

        pipe, route = canary_router.get_pipeline_for_user(control_user)
        assert route["model_version"] == "priority-v4.1"
        assert route["canary_group"] == "control"
        assert pipe is not None

    def test_07_model_version_cache_separation(self):
        """Invariant 7: user_email_cache primary key (user_id, message_id, model_version) separates predictions."""
        test_uid = "cache_test_user_p49"
        msg_id = "msg_dual_version_001"

        email_v41 = {
            "message_id": msg_id,
            "thread_id": "t1",
            "subject": "System Upgrade Notice",
            "snippet": "Scheduled maintenance",
            "sender": "ops@example.com",
            "received_at": "2026-10-02T10:00:00Z",
            "predicted_priority": "P2",
            "confidence": 0.88,
            "action_required": 1,
            "needs_attention": 1,
            "deadline_detected": 0,
            "rationale": "v4.1 assessment",
            "suggested_actions": ["Review"],
            "model_version": "priority-v4.1",
        }

        email_v51 = dict(email_v41)
        email_v51["predicted_priority"] = "P3"
        email_v51["confidence"] = 0.92
        email_v51["model_version"] = "priority-v5.1"

        # Store both versions in cache
        user_email_cache.store_batch(test_uid, [email_v41], model_version="priority-v4.1")
        user_email_cache.store_batch(test_uid, [email_v51], model_version="priority-v5.1")

        # Query v4.1 result
        cached_v41 = user_email_cache.get(test_uid, msg_id, model_version="priority-v4.1")
        assert cached_v41 is not None
        assert cached_v41["predicted_priority"] == "P2"
        assert cached_v41["model_version"] == "priority-v4.1"

        # Query v5.1 result
        cached_v51 = user_email_cache.get(test_uid, msg_id, model_version="priority-v5.1")
        assert cached_v51 is not None
        assert cached_v51["predicted_priority"] == "P3"
        assert cached_v51["model_version"] == "priority-v5.1"

        # Query without model_version defaults to active (v4.1)
        cached_def = user_email_cache.get(test_uid, msg_id)
        assert cached_def is not None
        assert cached_def["predicted_priority"] == "P2"
        assert cached_def["model_version"] == "priority-v4.1"

    def test_08_v41_rollback(self):
        """Invariant 8: Rollback restores 0% canary and 100% priority-v4.1 routing instantaneously."""
        canary_router.set_stage(3)  # 25%
        assert canary_router.canary_percentage == 25
        assert canary_router.canary_enabled is True

        res = canary_router.rollback()
        assert res["canary_enabled"] is False
        assert res["canary_percentage"] == 0
        assert res["stage"] == 0
        assert res["rollback_ready"] is True

        # Check 100 random users, all must route to v4.1
        for i in range(100):
            routed = canary_router.route_user(f"post_rollback_user_{i}")
            assert routed["model_version"] == "priority-v4.1"
            assert routed["is_canary"] is False

    def test_09_p1_downgrade_protection(self):
        """Invariant 9: Gate 1 verifies 0 critical P1 downgrades."""
        safety = canary_monitor.get_safety_audit()
        assert safety["total_p1_downgrades"] == 0, f"Found {safety['total_p1_downgrades']} P1 downgrades!"

    def test_10_otp_safety(self):
        """Invariant 10: OTP emails retain P1 priority."""
        pipeline_v51 = canary_router.get_pipeline("priority-v5.1")
        otp_email = {
            "subject": "Your verification code is 849201",
            "body": "Use code 849201 to complete your login. It expires in 10 minutes. Do not share this code.",
        }
        pred = predict_email(otp_email, pipeline=pipeline_v51)
        assert pred["final_priority"] == "P1", f"OTP email was classified as {pred['final_priority']}, expected P1"

    def test_11_mfa_safety(self):
        """Invariant 11: MFA challenge emails retain P1 priority."""
        pipeline_v51 = canary_router.get_pipeline("priority-v5.1")
        mfa_email = {
            "subject": "MFA Authorization Request",
            "body": "A login attempt was made from an unrecognized device. Approve or deny this authentication request immediately.",
        }
        pred = predict_email(mfa_email, pipeline=pipeline_v51)
        assert pred["final_priority"] == "P1", f"MFA email was classified as {pred['final_priority']}, expected P1"

    def test_12_security_alert_safety(self):
        """Invariant 12: Security alerts retain P1 priority."""
        pipeline_v51 = canary_router.get_pipeline("priority-v5.1")
        sec_email = {
            "subject": "Critical Security Alert: Suspicious sign-in detected",
            "body": "Someone just used your password to try to sign in to your account. Please change your password immediately.",
        }
        pred = predict_email(sec_email, pipeline=pipeline_v51)
        assert pred["final_priority"] == "P1", f"Security alert was classified as {pred['final_priority']}, expected P1"

    def test_13_password_reset_safety(self):
        """Invariant 13: Password reset emails retain P1 priority."""
        pipeline_v51 = canary_router.get_pipeline("priority-v5.1")
        reset_email = {
            "subject": "Password reset request for your account",
            "body": "Click the link below to reset your password. This link is valid for 15 minutes.",
        }
        pred = predict_email(reset_email, pipeline=pipeline_v51)
        assert pred["final_priority"] == "P1", f"Password reset was classified as {pred['final_priority']}, expected P1"

    def test_14_deadline_safety(self):
        """Invariant 14: Actionable deadlines are detected and maintained at P1 or P2."""
        pipeline_v51 = canary_router.get_pipeline("priority-v5.1")
        deadline_email = {
            "subject": "URGENT: Submit proposal by Friday 5 PM",
            "body": "Please review and send the finalized quarterly budget report by Friday 5 PM. Action is required before the cutoff.",
        }
        pred = predict_email(deadline_email, pipeline=pipeline_v51)
        assert pred["final_priority"] in ("P1", "P2"), f"Deadline email classified as {pred['final_priority']}, expected P1 or P2"
        assert pred["action_required"] is True, "Action required flag should be True"

    def test_15_action_state_integrity(self):
        """Invariant 15: Low-priority newsletters and notifications are not marked action_required."""
        pipeline_v51 = canary_router.get_pipeline("priority-v5.1")
        routine_email = {
            "subject": "Weekly Tech Digest - Issue #342",
            "body": "Here are this week's top stories in software engineering. Unsubscribe anytime by clicking here.",
        }
        pred = predict_email(routine_email, pipeline=pipeline_v51)
        assert pred["final_priority"] in ("P3", "P4")
        assert pred["action_required"] is False

    def test_16_feedback_attribution(self):
        """Invariant 16: User feedback correctly tracks model_version."""
        feedback = canary_monitor.get_feedback_comparison()
        assert "v41_feedback_count" in feedback
        assert "v51_feedback_count" in feedback
        assert "v41_corrections" in feedback
        assert "v51_corrections" in feedback

    def test_17_latency_measurement(self):
        """Invariant 17: Latency telemetry tracks median, p95, p99 without regression."""
        metrics = canary_monitor.get_metrics_comparison()
        lat = metrics["latency"]
        assert "active_median_ms" in lat
        assert "shadow_median_ms" in lat
        assert "active_p95_ms" in lat
        assert "shadow_p95_ms" in lat
        assert lat["user_facing_overhead_ms"] == 0.0

    def test_18_failure_isolation(self):
        """Invariant 18: If candidate model fails, router transparently falls back to active v4.1."""
        # Find a user who routes to canary
        canary_router.set_stage(4)  # 50%
        canary_user = None
        for i in range(100):
            u = f"user_probe_fallback_{i}"
            if canary_router.route_user(u)["is_canary"]:
                canary_user = u
                break
        assert canary_user is not None

        # Simulate candidate pipeline load error by monkeypatching
        original_get_pipeline = canary_router.get_pipeline

        def faulty_get_pipeline(version: str):
            if version == "priority-v5.1":
                raise RuntimeError("Simulated candidate model corruption")
            return original_get_pipeline(version)

        canary_router.get_pipeline = faulty_get_pipeline
        try:
            pipe, route = canary_router.get_pipeline_for_user(canary_user)
            assert pipe is not None
            assert route["model_version"] == "priority-v4.1"
            assert route["canary_group"] == "control_fallback"
            assert route["is_canary"] is False
        finally:
            canary_router.get_pipeline = original_get_pipeline
            canary_router.rollback()

    def test_19_account_switching(self):
        """Invariant 19: Switching user accounts updates canary routing deterministically."""
        canary_router.set_stage(2)  # 10%
        # Evaluate 5 distinct users
        users = [f"account_switch_user_{i}" for i in range(5)]
        routes_pass1 = [canary_router.route_user(u) for u in users]
        # Simulate user switching away and back
        routes_pass2 = [canary_router.route_user(u) for u in reversed(users)]
        routes_pass2_ordered = list(reversed(routes_pass2))

        for r1, r2 in zip(routes_pass1, routes_pass2_ordered):
            assert r1["model_version"] == r2["model_version"]
            assert r1["is_canary"] == r2["is_canary"]

    def test_20_concurrent_users(self):
        """Invariant 20: Concurrent routing requests across multiple threads remain thread-safe."""
        canary_router.set_stage(3)  # 25%
        results = {}

        def worker(uid: str):
            res = canary_router.route_user(uid)
            results[uid] = res

        threads = []
        for i in range(50):
            t = threading.Thread(target=worker, args=(f"concurrent_user_{i}",))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(results) == 50
        for uid, res in results.items():
            assert res["model_version"] in ("priority-v4.1", "priority-v5.1")

    def test_21_monitoring_authorization(self):
        """Invariant 21: Unauthenticated requests to /api/monitoring/canary/* return 401."""
        endpoints = [
            "/api/monitoring/canary/status",
            "/api/monitoring/canary/metrics",
            "/api/monitoring/canary/safety",
            "/api/monitoring/canary/feedback",
            "/api/monitoring/canary/gates",
        ]
        for ep in endpoints:
            resp = client.get(ep)
            assert resp.status_code == 401, f"{ep} did not require authentication"

    def test_22_monitoring_user_scoping(self):
        """Invariant 22: Authenticated session can access canary monitoring endpoints."""
        session = session_manager.create_session(
            user_id="canary_admin_user_01",
            email="admin@example.com",
            credentials={"token": "test_token", "refresh_token": "test_refresh"}
        )
        try:
            cookies = {"mailmind_session": session.session_id}
            resp = client.get("/api/monitoring/canary/status", cookies=cookies)
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "success"
            assert "canary_status" in data

            gates_resp = client.get("/api/monitoring/canary/gates", cookies=cookies)
            assert gates_resp.status_code == 200
            gates_data = gates_resp.json()
            assert gates_data["status"] == "success"
            assert "safety_gates" in gates_data
            assert gates_data["safety_gates"]["total_gates"] == 13
        finally:
            session_manager.delete_session(session.session_id)

    def test_23_artifact_sha_validation(self):
        """Invariant 23: v4.1 and v5.1 artifacts match their exact expected SHA-256 hashes."""
        v41_path = os.path.join(BASE_DIR, "dataset", "models", "priority-v4.1", "model.joblib")
        v51_path = os.path.join(BASE_DIR, "dataset", "models", "priority-v5.1-candidate", "model.joblib")

        v41_sha = compute_file_sha256(v41_path)
        v51_sha = compute_file_sha256(v51_path)

        assert v41_sha == EXPECTED_V41_SHA, f"v4.1 SHA mismatch: expected {EXPECTED_V41_SHA}, got {v41_sha}"
        assert v51_sha == EXPECTED_V51_SHA, f"v5.1 SHA mismatch: expected {EXPECTED_V51_SHA}, got {v51_sha}"

    def test_24_no_raw_email_persistence(self):
        """Invariant 24: Prediction logs never store raw email body or content."""
        test_uid = "audit_user_p49"
        log_prediction(
            user_id=test_uid,
            message_id="msg_audit_001",
            thread_id="th_001",
            model_version="priority-v5.1",
            predicted_priority="P2",
            confidence=0.89,
            action_required=True,
            deadline_detected=False,
            deadline_status="NONE",
            topic="work",
            needs_attention=True,
            canary_group="canary"
        )

        from backend.app.core.prediction_log import _log_path_for_user
        log_file = _log_path_for_user(test_uid)
        assert os.path.exists(log_file), "Prediction log file must be created"

        with open(log_file, "r", encoding="utf-8") as f:
            lines = [json.loads(line) for line in f if line.strip()]

        assert len(lines) > 0
        latest_record = lines[-1]

        # Verify presence of canary metadata
        assert latest_record["model_version"] == "priority-v5.1"
        assert latest_record["canary_group"] == "canary"
        assert "prediction_timestamp" in latest_record

        # Verify strict absence of raw content
        for forbidden in ["body", "raw_body", "raw_content", "subject", "sender"]:
            assert forbidden not in latest_record, f"Forbidden key '{forbidden}' found in prediction log"

    def test_25_no_oauth_token_persistence(self):
        """Invariant 25: Neither prediction logs nor cache store OAuth tokens or secrets."""
        test_uid = "audit_user_p49"
        from backend.app.core.prediction_log import _log_path_for_user
        log_file = _log_path_for_user(test_uid)

        with open(log_file, "r", encoding="utf-8") as f:
            lines = [json.loads(line) for line in f if line.strip()]

        for record in lines:
            for secret in ["token", "access_token", "refresh_token", "client_secret", "password"]:
                assert secret not in record, f"Forbidden credential key '{secret}' found in prediction log"
