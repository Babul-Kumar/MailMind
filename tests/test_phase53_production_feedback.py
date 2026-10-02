"""
test_phase53_production_feedback.py — Phase 53 Production Feedback Activation Tests
=====================================================================================
24 comprehensive tests covering Phase 53 requirements:
  01. v5.1 provenance enforced
  02. Server-side model identity immutable (client override ignored)
  03. Server-side user identity enforced (client override ignored)
  04. Feedback submission success & fields
  05. Feedback correction types & valid reasons
  06. NOT_SURE feedback handling
  07. Duplicate submission deduplication
  08. Double-click / retry behavior
  09. Historical and v5.1 model separation
  10. P2/P3 boundary diagnostic metrics
  11. Safety feedback queue & critical escalations
  12. Deadline feedback queue & decoupling
  13. Multi-user isolation
  14. Same message ID across different users
  15. Malformed feedback rejected (422)
  16. Unauthorized access rejected (401)
  17. Session expiration / invalid session rejected (401)
  18. Model artifact immutability (v5.1 SHA unchanged)
  19. Frozen holdout immutability (test.csv SHA unchanged)
  20. No-training invariant
  21. Quality metrics calculation & admonition
  22. Empty state behavior
  23. v5.2 readiness state (EVIDENCE COLLECTING)
  24. Feedback does not block inference / performance
"""
import os
import sys
import json
import time
import uuid
import pytest
import hashlib
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from backend.app.core.config import BASE_DIR
from backend.app.main import app
from backend.app.core.feedback import (
    FeedbackSubmission, feedback_manager,
    VALID_FEEDBACK_TYPES, VALID_REASONS
)
from backend.app.core.adjudication import adjudication_manager


# ---------------------------------------------------------------------------
# Helpers & Fixtures
# ---------------------------------------------------------------------------
def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


@pytest.fixture
def isolated_feedback(tmp_path):
    """Provides temporary feedback and adjudication files for test isolation."""
    import backend.app.core.feedback as fb_mod
    import backend.app.core.adjudication as adj_mod

    orig_fb = fb_mod.FEEDBACK_FILE
    orig_adj = adj_mod.ADJUDICATION_FILE

    tmp_fb_file = str(tmp_path / "feedback.jsonl")
    tmp_adj_file = str(tmp_path / "adjudication.jsonl")

    fb_mod.FEEDBACK_FILE = tmp_fb_file
    adj_mod.ADJUDICATION_FILE = tmp_adj_file
    adj_mod.FEEDBACK_FILE = tmp_fb_file

    yield {
        "feedback_file": tmp_fb_file,
        "adjudication_file": tmp_adj_file,
    }

    fb_mod.FEEDBACK_FILE = orig_fb
    adj_mod.ADJUDICATION_FILE = orig_adj
    adj_mod.FEEDBACK_FILE = orig_fb


def _mock_session(user_id="test_user_p53", email="user@example.com"):
    mock = MagicMock()
    mock.user_id = user_id
    mock.email = email
    return mock


# ---------------------------------------------------------------------------
# 01. v5.1 provenance enforced
# ---------------------------------------------------------------------------
def test_01_v51_provenance_enforced(isolated_feedback):
    mock_s = _mock_session("user_p53_01")
    with patch("backend.app.api.routes_emails.get_session_from_request", return_value=mock_s):
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/feedback", json={
            "message_id": "msg_prov_01",
            "feedback_type": "CORRECT",
            "corrected_priority": "P2",
        })
    assert resp.status_code == 200
    data = resp.json()["record"]
    assert data["provenance"] == "PRODUCTION_FEEDBACK"
    assert data["model_version"] == "priority-v5.1"
    assert data["adjudication_status"] == "PENDING_REVIEW"


# ---------------------------------------------------------------------------
# 02. Server-side model identity immutable (client override ignored)
# ---------------------------------------------------------------------------
def test_02_server_side_model_identity_immutable(isolated_feedback):
    mock_s = _mock_session("user_p53_02")
    with patch("backend.app.api.routes_emails.get_session_from_request", return_value=mock_s):
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/feedback", json={
            "message_id": "msg_model_override",
            "model_version": "priority-v999_fake_model",
            "feedback_type": "CORRECT",
            "corrected_priority": "P1",
        })
    assert resp.status_code == 200
    data = resp.json()["record"]
    assert data["model_version"] == "priority-v5.1", "Client-supplied model_version must be overridden by active model"


# ---------------------------------------------------------------------------
# 03. Server-side user identity enforced (client override ignored)
# ---------------------------------------------------------------------------
def test_03_server_side_user_identity_enforced(isolated_feedback):
    mock_s = _mock_session("legit_user_03")
    with patch("backend.app.api.routes_emails.get_session_from_request", return_value=mock_s):
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/feedback", json={
            "message_id": "msg_user_override",
            "user_id": "impostor_user_99",
            "feedback_type": "CORRECT",
            "corrected_priority": "P2",
        })
    assert resp.status_code == 200
    data = resp.json()["record"]
    assert data["user_id"] == "legit_user_03", "Client user_id must not override authenticated session identity"


# ---------------------------------------------------------------------------
# 04. Feedback submission success & fields
# ---------------------------------------------------------------------------
def test_04_feedback_submission_success(isolated_feedback):
    mock_s = _mock_session("user_p53_04")
    with patch("backend.app.api.routes_emails.get_session_from_request", return_value=mock_s):
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/feedback", json={
            "message_id": "msg_success_04",
            "feedback_type": "CORRECT",
            "predicted_priority": "P3",
            "corrected_priority": "P2",
            "reason": "priority_too_low",
        })
    assert resp.status_code == 200
    rec = resp.json()["record"]
    assert "feedback_id" in rec
    assert len(rec["feedback_id"]) == 36
    assert rec["reason"] == "priority_too_low"
    assert rec["created_at"] is not None


# ---------------------------------------------------------------------------
# 05. Feedback correction types & valid reasons
# ---------------------------------------------------------------------------
def test_05_feedback_correction_types(isolated_feedback):
    reasons = [
        "priority_too_high", "priority_too_low", "action_misunderstood",
        "deadline_misunderstood", "context_missing", "other"
    ]
    mock_s = _mock_session("user_p53_05")
    with patch("backend.app.api.routes_emails.get_session_from_request", return_value=mock_s):
        client = TestClient(app, raise_server_exceptions=False)
        for r in reasons:
            resp = client.post("/api/feedback", json={
                "message_id": f"msg_reason_{r}",
                "feedback_type": "CORRECT",
                "corrected_priority": "P2",
                "reason": r,
            })
            assert resp.status_code == 200
            assert resp.json()["record"]["reason"] == r


# ---------------------------------------------------------------------------
# 06. NOT_SURE feedback handling
# ---------------------------------------------------------------------------
def test_06_not_sure_feedback_handling(isolated_feedback):
    mock_s = _mock_session("user_p53_06")
    with patch("backend.app.api.routes_emails.get_session_from_request", return_value=mock_s):
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/feedback", json={
            "message_id": "msg_not_sure_06",
            "feedback_type": "NOT_SURE",
            "reason": "context_missing",
        })
    assert resp.status_code == 200
    rec = resp.json()["record"]
    assert rec["feedback_type"] == "NOT_SURE"
    assert rec["corrected_priority"] is None


# ---------------------------------------------------------------------------
# 07. Duplicate submission deduplication
# ---------------------------------------------------------------------------
def test_07_duplicate_submission_handling(isolated_feedback):
    mock_s = _mock_session("user_p53_07")
    with patch("backend.app.api.routes_emails.get_session_from_request", return_value=mock_s), \
         patch("backend.app.api.routes_adjudication.get_session_from_request", return_value=mock_s):
        client = TestClient(app, raise_server_exceptions=False)
        for _ in range(4):
            resp = client.post("/api/feedback", json={
                "message_id": "msg_duplicate_07",
                "feedback_type": "CORRECT",
                "corrected_priority": "P2",
            })
            assert resp.status_code == 200

        res = client.get("/api/adjudication/dedup-stats")
        assert res.status_code == 200
        stats = res.json()["dedup_stats"]
        assert stats["raw_feedback_events"] == 4
        assert stats["unique_feedback_cases"] == 1
        assert stats["duplicate_submissions"] == 3


# ---------------------------------------------------------------------------
# 08. Double-click / retry behavior
# ---------------------------------------------------------------------------
def test_08_retry_and_double_click_protection(isolated_feedback):
    mock_s = _mock_session("user_p53_08")
    with patch("backend.app.api.routes_emails.get_session_from_request", return_value=mock_s):
        client = TestClient(app, raise_server_exceptions=False)
        r1 = client.post("/api/feedback", json={"message_id": "msg_double_08", "corrected_priority": "P2"}).json()["record"]
        r2 = client.post("/api/feedback", json={"message_id": "msg_double_08", "corrected_priority": "P2"}).json()["record"]

    assert r1["feedback_id"] != r2["feedback_id"], "Each submission must have distinct audit feedback_id"
    cases = feedback_manager.get_unique_cases("user_p53_08")
    assert len(cases) == 1, "Must collapse to 1 unique logical case"


# ---------------------------------------------------------------------------
# 09. Historical and v5.1 model separation
# ---------------------------------------------------------------------------
def test_09_historical_and_v51_separation(isolated_feedback):
    user_id = "user_p53_09"
    # Submit one v1 record
    feedback_manager.record_feedback(
        FeedbackSubmission(message_id="msg_v1", model_version="priority-v1", predicted_priority="P3", corrected_priority="P2"),
        user_id=user_id,
    )
    # Submit one v4.1 record
    feedback_manager.record_feedback(
        FeedbackSubmission(message_id="msg_v41", model_version="priority-v4.1", predicted_priority="P4", corrected_priority="P2"),
        user_id=user_id,
    )
    # Submit one v5.1 record
    feedback_manager.record_feedback(
        FeedbackSubmission(message_id="msg_v51", model_version="priority-v5.1", predicted_priority="P3", corrected_priority="P1"),
        user_id=user_id,
    )

    sep = feedback_manager.get_metrics_by_model(user_id=user_id)
    assert sep["all_feedback"]["raw_count"] == 3
    assert sep["v51_feedback"]["raw_count"] == 1
    assert sep["v41_feedback"]["raw_count"] == 1
    assert sep["older_feedback"]["raw_count"] == 1


# ---------------------------------------------------------------------------
# 10. P2/P3 boundary diagnostic metrics
# ---------------------------------------------------------------------------
def test_10_p2_p3_boundary_metrics(isolated_feedback):
    user_id = "user_p53_10"
    # P2 -> P3 correction
    feedback_manager.record_feedback(
        FeedbackSubmission(message_id="msg_b_01", model_version="priority-v5.1", predicted_priority="P2", corrected_priority="P3", original_topic="recruitment"),
        user_id=user_id,
    )
    # P3 -> P2 correction
    feedback_manager.record_feedback(
        FeedbackSubmission(message_id="msg_b_02", model_version="priority-v5.1", predicted_priority="P3", corrected_priority="P2", original_topic="academic"),
        user_id=user_id,
    )

    analysis = adjudication_manager.get_p2_p3_analysis(user_id=user_id, model_version="priority-v5.1")
    assert analysis["pending_boundary_cases"] == 2
    assert analysis["p2_to_p3_pending"] == 1
    assert analysis["p3_to_p2_pending"] == 1
    assert "recruitment" in analysis["breakdown_by_topic"]
    assert "academic" in analysis["breakdown_by_topic"]


# ---------------------------------------------------------------------------
# 11. Safety feedback queue & critical escalations
# ---------------------------------------------------------------------------
def test_11_safety_feedback_queue(isolated_feedback):
    user_id = "user_p53_11"
    # OTP classified as P3, user corrects to P1
    feedback_manager.record_feedback(
        FeedbackSubmission(
            message_id="msg_safety_otp",
            model_version="priority-v5.1",
            predicted_priority="P3",
            corrected_priority="P1",
            original_topic="otp",
        ),
        user_id=user_id,
    )

    safety = adjudication_manager.get_safety_analysis(user_id=user_id, model_version="priority-v5.1")
    assert safety["total_safety_feedback"] == 1
    assert safety["critical_p1_escalations"] == 1
    assert "otp" in safety["breakdown_by_safety_topic"]


# ---------------------------------------------------------------------------
# 12. Deadline feedback queue & decoupling
# ---------------------------------------------------------------------------
def test_12_deadline_feedback_queue(isolated_feedback):
    user_id = "user_p53_12"
    feedback_manager.record_feedback(
        FeedbackSubmission(
            message_id="msg_dl_01",
            model_version="priority-v5.1",
            predicted_priority="P3",
            deadline_correction=True,
            deadline_status="ACTIVE",
        ),
        user_id=user_id,
    )

    dl = adjudication_manager.get_deadline_analysis(user_id=user_id, model_version="priority-v5.1")
    assert dl["total_deadline_feedback"] == 1
    assert "ACTIVE" in dl["breakdown_by_status"]


# ---------------------------------------------------------------------------
# 13. Multi-user isolation
# ---------------------------------------------------------------------------
def test_13_multiuser_isolation_feedback(isolated_feedback):
    # User A records feedback
    feedback_manager.record_feedback(
        FeedbackSubmission(message_id="msg_user_a", model_version="priority-v5.1", predicted_priority="P3", corrected_priority="P2"),
        user_id="user_A",
    )
    # User B checks their feedback
    mock_s_b = _mock_session("user_B")
    with patch("backend.app.api.routes_emails.get_session_from_request", return_value=mock_s_b):
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/feedback")
    assert resp.status_code == 200
    records = resp.json()["records"]
    assert len(records) == 0, "User B must not see User A's feedback"


# ---------------------------------------------------------------------------
# 14. Same message ID across different users
# ---------------------------------------------------------------------------
def test_14_same_message_id_across_different_users(isolated_feedback):
    shared_mid = "shared_rfc_message_123"
    feedback_manager.record_feedback(
        FeedbackSubmission(message_id=shared_mid, model_version="priority-v5.1", predicted_priority="P3", corrected_priority="P1"),
        user_id="user_alice",
    )
    feedback_manager.record_feedback(
        FeedbackSubmission(message_id=shared_mid, model_version="priority-v5.1", predicted_priority="P4", corrected_priority="P2"),
        user_id="user_bob",
    )

    alice_cases = feedback_manager.get_unique_cases("user_alice")
    bob_cases = feedback_manager.get_unique_cases("user_bob")

    assert len(alice_cases) == 1
    assert len(bob_cases) == 1
    assert alice_cases[0]["corrected_priority"] == "P1"
    assert bob_cases[0]["corrected_priority"] == "P2"


# ---------------------------------------------------------------------------
# 15. Malformed feedback rejected (422)
# ---------------------------------------------------------------------------
def test_15_malformed_feedback_rejected():
    mock_s = _mock_session("user_p53_15")
    with patch("backend.app.api.routes_emails.get_session_from_request", return_value=mock_s):
        client = TestClient(app, raise_server_exceptions=False)
        # Missing required message_id
        resp = client.post("/api/feedback", json={"feedback_type": "CORRECT"})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 16. Unauthorized access rejected (401)
# ---------------------------------------------------------------------------
def test_16_unauthorized_access_rejected():
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post("/api/feedback", json={"message_id": "test_msg"})
    assert resp.status_code == 401
    resp_adj = client.get("/api/adjudication/v51-metrics")
    assert resp_adj.status_code == 401


# ---------------------------------------------------------------------------
# 17. Session expiration / invalid session rejected (401)
# ---------------------------------------------------------------------------
def test_17_session_expiration_rejected():
    with patch("backend.app.api.routes_emails.get_session_from_request", return_value=None):
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/feedback", json={"message_id": "test_expired"})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 18. Model artifact immutability (v5.1 SHA unchanged)
# ---------------------------------------------------------------------------
def test_18_model_artifact_immutability():
    EXPECTED_SHA = "8524ad73965859ee022f1271caee0040928e7805ab7d32c49b2f26e994f98c06"
    reg_path = os.path.join(BASE_DIR, "dataset", "models", "registry.json")
    with open(reg_path, "r", encoding="utf-8") as f:
        reg = json.load(f)
    v51_sha = reg["versions"]["priority-v5.1"]["artifact_sha256"]
    assert v51_sha == EXPECTED_SHA, f"v5.1 artifact SHA modified! Got: {v51_sha}"
    assert reg["active_model"] == "priority-v5.1"


# ---------------------------------------------------------------------------
# 19. Frozen holdout immutability (test.csv SHA unchanged)
# ---------------------------------------------------------------------------
def test_19_holdout_immutability():
    EXPECTED_TEST_SHA = "6841cd44901fa56242bf3752257e991fd7ff474ed7e0f7a5d2b7065a0827c138"
    test_path = os.path.join(BASE_DIR, "dataset", "processed", "test.csv")
    current_sha = _sha256_file(test_path).lower()
    assert current_sha == EXPECTED_TEST_SHA.lower(), f"Frozen test.csv was mutated! Got: {current_sha}"


# ---------------------------------------------------------------------------
# 20. No-training invariant
# ---------------------------------------------------------------------------
def test_20_no_training_invariant():
    import backend.app.core.feedback as fb_mod
    import backend.app.core.adjudication as adj_mod
    import inspect

    fb_src = inspect.getsource(fb_mod)
    adj_src = inspect.getsource(adj_mod)

    forbidden = ["model.fit(", "GridSearchCV", "Pipeline().fit", "def train_"]
    for pat in forbidden:
        assert pat not in fb_src
        assert pat not in adj_src


# ---------------------------------------------------------------------------
# 21. Quality metrics calculation & admonition
# ---------------------------------------------------------------------------
def test_21_quality_metrics_calculation(isolated_feedback):
    user_id = "user_p53_21"
    qm = feedback_manager.get_quality_metrics(user_id=user_id, total_classified=100)
    assert "feedback_submission_rate_pct" in qm
    assert "duplicate_rate_pct" in qm
    assert qm["admonition"] == "No feedback does not imply no model errors."


# ---------------------------------------------------------------------------
# 22. Empty state behavior
# ---------------------------------------------------------------------------
def test_22_empty_state_behavior(isolated_feedback):
    user_id = "user_empty_22"
    m = feedback_manager.get_v51_production_metrics(user_id=user_id)
    assert m["raw_feedback_events"] == 0
    assert m["unique_feedback_cases"] == 0
    assert "0 genuine v5.1 feedback cases observed." in m["status_statement"]


# ---------------------------------------------------------------------------
# 23. v5.2 readiness state (EVIDENCE COLLECTING)
# ---------------------------------------------------------------------------
def test_23_v52_readiness_evidence_collecting():
    from backend.app.core.dataset_v52 import dataset_v52_builder
    result = dataset_v52_builder.build()
    assert result["readiness"]["state"] == "EVIDENCE COLLECTING"
    assert "Insufficient adjudicated production feedback" in result["readiness"]["reason"]


# ---------------------------------------------------------------------------
# 24. Feedback does not block inference / performance
# ---------------------------------------------------------------------------
def test_24_feedback_does_not_block_inference(isolated_feedback):
    # Benchmark 20 feedback record operations to verify execution latency < 20ms
    latencies = []
    for i in range(20):
        t0 = time.perf_counter()
        feedback_manager.record_feedback(
            FeedbackSubmission(message_id=f"msg_perf_{i}", model_version="priority-v5.1", predicted_priority="P3", corrected_priority="P2"),
            user_id="user_perf",
        )
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000)

    median_ms = sorted(latencies)[len(latencies) // 2]
    assert median_ms < 20.0, f"Feedback logging too slow: {median_ms}ms"
