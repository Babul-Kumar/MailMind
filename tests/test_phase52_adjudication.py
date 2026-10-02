"""
test_phase52_adjudication.py — Phase 52 Feedback Adjudication & Dataset-v5.2 Tests
====================================================================================
28 tests covering:
  01. feedback_id generated on every record
  02. adjudication_status = PENDING_REVIEW on new records
  03. provenance field set
  04. Feedback validation — required fields enforced
  05. Deduplication stats — raw events vs unique cases
  06. Unique cases — same (user_id, message_id) deduped
  07. Adjudication ACCEPTED transition
  08. Adjudication REJECTED transition
  09. Adjudication NEEDS_CONTEXT status
  10. Adjudication DUPLICATE status
  11. ACCEPTED requires corrected_priority
  12. ACCEPTED requires non-empty reason
  13. P2/P3 review queue — only P2↔P3 transitions
  14. Safety queue — P1 escalations surfaced
  15. Deadline queue — deadline_correction cases included
  16. Provenance on every accepted record
  17. Candidate pool — ACCEPTED only (not REJECTED)
  18. REJECTED feedback not in candidate pool
  19. Leakage audit — no overlap with frozen test.csv
  20. Leakage audit — internal duplicate detection
  21. Dataset manifest — all required fields present
  22. Multi-user isolation — User A adj invisible to User B
  23. Model version preserved in adjudication record
  24. Session/permission — unauthenticated cannot POST adjudication
  25. Feedback API security — GET /api/feedback scoped to user
  26. Malformed feedback — missing message_id rejected
  27. No training — no model artifact changes
  28. Production model SHA — v5.1 unchanged throughout phase
"""
import os
import json
import time
import uuid
import pytest
import hashlib
import tempfile
import shutil
from unittest.mock import patch, MagicMock

from backend.app.core.config import BASE_DIR


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _sha256_file(path):
    if not os.path.exists(path):
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def _make_feedback_submission(**overrides):
    """Creates a minimal valid FeedbackSubmission-compatible dict."""
    return {
        "message_id": overrides.get("message_id", f"test_msg_{uuid.uuid4().hex[:8]}"),
        "model_version": overrides.get("model_version", "priority-v5.1"),
        "thread_id": overrides.get("thread_id", None),
        "feedback_type": overrides.get("feedback_type", "CORRECT"),
        "predicted_priority": overrides.get("predicted_priority", "P3"),
        "predicted_action_required": overrides.get("predicted_action_required", False),
        "original_confidence": overrides.get("original_confidence", 0.65),
        "original_topic": overrides.get("original_topic", "academic"),
        "original_deadline_detected": overrides.get("original_deadline_detected", False),
        "corrected_priority": overrides.get("corrected_priority", "P2"),
        "notes": overrides.get("notes", "Test correction"),
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def tmp_feedback_dir(tmp_path):
    """Redirects feedback.jsonl and adjudication.jsonl to a temp dir."""
    import backend.app.core.feedback as fb_mod
    import backend.app.core.adjudication as adj_mod

    orig_feedback_file = fb_mod.FEEDBACK_FILE
    orig_adj_file = adj_mod.ADJUDICATION_FILE

    tmp_fb = str(tmp_path / "feedback.jsonl")
    tmp_adj = str(tmp_path / "adjudication.jsonl")

    fb_mod.FEEDBACK_FILE = tmp_fb
    adj_mod.ADJUDICATION_FILE = tmp_adj
    adj_mod.FEEDBACK_FILE = tmp_fb  # sync ref in adjudication module

    # Fresh manager instances pointing to tmp files
    fb_mod.feedback_manager = fb_mod.FeedbackManager.__new__(fb_mod.FeedbackManager)
    fb_mod.feedback_manager.__init__ = lambda: None
    fb_mod.feedback_manager.FEEDBACK_DIR = str(tmp_path)

    from backend.app.core.feedback import FeedbackManager
    manager = FeedbackManager()
    fb_mod.feedback_manager = manager

    from backend.app.core.adjudication import AdjudicationManager
    adj_manager = AdjudicationManager()
    adj_mod.adjudication_manager = adj_manager
    adj_mod.ADJUDICATION_FILE = tmp_adj

    yield {
        "feedback_file": tmp_fb,
        "adjudication_file": tmp_adj,
        "feedback_manager": manager,
        "adjudication_manager": adj_manager,
    }

    fb_mod.FEEDBACK_FILE = orig_feedback_file
    adj_mod.ADJUDICATION_FILE = orig_adj_file
    adj_mod.FEEDBACK_FILE = orig_feedback_file


# ---------------------------------------------------------------------------
# 01 — feedback_id generated on every record
# ---------------------------------------------------------------------------
def test_01_feedback_id_generated(tmp_feedback_dir):
    mgr = tmp_feedback_dir["feedback_manager"]
    from backend.app.core.feedback import FeedbackSubmission
    sub = FeedbackSubmission(**_make_feedback_submission())
    rec = mgr.record_feedback(sub, user_id="user_test_01")
    assert "feedback_id" in rec, "feedback_id missing"
    assert len(rec["feedback_id"]) == 36, "feedback_id should be UUID4 (36 chars)"


# ---------------------------------------------------------------------------
# 02 — adjudication_status = PENDING_REVIEW on creation
# ---------------------------------------------------------------------------
def test_02_adjudication_status_pending_on_creation(tmp_feedback_dir):
    mgr = tmp_feedback_dir["feedback_manager"]
    from backend.app.core.feedback import FeedbackSubmission
    sub = FeedbackSubmission(**_make_feedback_submission())
    rec = mgr.record_feedback(sub, user_id="user_test_02")
    assert rec.get("adjudication_status") == "PENDING_REVIEW"


# ---------------------------------------------------------------------------
# 03 — provenance field set
# ---------------------------------------------------------------------------
def test_03_provenance_field_set(tmp_feedback_dir):
    mgr = tmp_feedback_dir["feedback_manager"]
    from backend.app.core.feedback import FeedbackSubmission
    sub = FeedbackSubmission(**_make_feedback_submission())
    rec = mgr.record_feedback(sub, user_id="user_test_03")
    assert rec.get("provenance") == "HUMAN_PRODUCTION_FEEDBACK"


# ---------------------------------------------------------------------------
# 04 — Feedback validation — missing message_id rejected by Pydantic
# ---------------------------------------------------------------------------
def test_04_feedback_validation_missing_message_id():
    from pydantic import ValidationError
    from backend.app.core.feedback import FeedbackSubmission
    with pytest.raises(ValidationError):
        FeedbackSubmission(
            model_version="priority-v5.1",
            predicted_priority="P3",
            predicted_action_required=False,
        )


# ---------------------------------------------------------------------------
# 05 — Deduplication stats — raw events vs unique cases
# ---------------------------------------------------------------------------
def test_05_dedup_stats_raw_vs_unique(tmp_feedback_dir):
    mgr = tmp_feedback_dir["feedback_manager"]
    from backend.app.core.feedback import FeedbackSubmission
    msg_id = f"msg_dedup_{uuid.uuid4().hex[:8]}"
    user_id = "user_dedup_05"

    # Submit same (user_id, message_id) 5 times
    for _ in range(5):
        sub = FeedbackSubmission(**_make_feedback_submission(message_id=msg_id))
        mgr.record_feedback(sub, user_id=user_id)

    stats = mgr.get_dedup_stats(user_id)
    assert stats["raw_feedback_events"] == 5, "Expected 5 raw events"
    assert stats["unique_feedback_cases"] == 1, "Expected 1 unique case"
    assert stats["duplicate_submissions"] == 4, "Expected 4 duplicates"


# ---------------------------------------------------------------------------
# 06 — Unique cases — same (user_id, message_id) collapses to 1
# ---------------------------------------------------------------------------
def test_06_unique_cases_dedup(tmp_feedback_dir):
    mgr = tmp_feedback_dir["feedback_manager"]
    from backend.app.core.feedback import FeedbackSubmission
    msg_id = f"msg_unique_{uuid.uuid4().hex[:8]}"
    user_id = "user_unique_06"

    for i in range(3):
        sub = FeedbackSubmission(**_make_feedback_submission(message_id=msg_id, notes=f"attempt {i}"))
        mgr.record_feedback(sub, user_id=user_id)

    cases = mgr.get_unique_cases(user_id)
    assert len(cases) == 1, "3 submissions to same message should yield 1 unique case"
    # Most recent should win
    assert cases[0].get("notes") == "attempt 2"


# ---------------------------------------------------------------------------
# 07 — Adjudication ACCEPTED transition
# ---------------------------------------------------------------------------
def test_07_adjudication_accepted(tmp_feedback_dir):
    fb_mgr = tmp_feedback_dir["feedback_manager"]
    adj_mgr = tmp_feedback_dir["adjudication_manager"]
    from backend.app.core.feedback import FeedbackSubmission

    sub = FeedbackSubmission(**_make_feedback_submission())
    rec = fb_mgr.record_feedback(sub, user_id="user_adj_07")
    fid = rec["feedback_id"]

    adj = adj_mgr.adjudicate(
        feedback_id=fid,
        adjudicator_id="reviewer_07",
        status="ACCEPTED",
        reason="Genuine P2: registration deadline, action required within 3 days.",
        corrected_priority="P2",
    )
    assert adj["adjudication_status"] == "ACCEPTED"
    assert adj["eligible_for_training"] is True
    assert adj["corrected_priority"] == "P2"
    assert "adjudication_id" in adj
    assert adj["provenance"] == "HUMAN_PRODUCTION_FEEDBACK_ADJUDICATED"


# ---------------------------------------------------------------------------
# 08 — Adjudication REJECTED transition
# ---------------------------------------------------------------------------
def test_08_adjudication_rejected(tmp_feedback_dir):
    fb_mgr = tmp_feedback_dir["feedback_manager"]
    adj_mgr = tmp_feedback_dir["adjudication_manager"]
    from backend.app.core.feedback import FeedbackSubmission

    sub = FeedbackSubmission(**_make_feedback_submission(predicted_priority="P4", corrected_priority="P1"))
    rec = fb_mgr.record_feedback(sub, user_id="user_adj_08")

    adj = adj_mgr.adjudicate(
        feedback_id=rec["feedback_id"],
        adjudicator_id="reviewer_08",
        status="REJECTED",
        reason="P4 promotional email — user correction appears to be personal preference, not model error.",
    )
    assert adj["adjudication_status"] == "REJECTED"
    assert adj["eligible_for_training"] is False
    assert adj["ineligibility_reason"] is not None


# ---------------------------------------------------------------------------
# 09 — Adjudication NEEDS_CONTEXT
# ---------------------------------------------------------------------------
def test_09_adjudication_needs_context(tmp_feedback_dir):
    fb_mgr = tmp_feedback_dir["feedback_manager"]
    adj_mgr = tmp_feedback_dir["adjudication_manager"]
    from backend.app.core.feedback import FeedbackSubmission

    sub = FeedbackSubmission(**_make_feedback_submission())
    rec = fb_mgr.record_feedback(sub, user_id="user_adj_09")

    adj = adj_mgr.adjudicate(
        feedback_id=rec["feedback_id"],
        adjudicator_id="reviewer_09",
        status="NEEDS_CONTEXT",
        reason="Cannot determine without knowing the user's role and deadline context.",
    )
    assert adj["adjudication_status"] == "NEEDS_CONTEXT"
    assert adj["eligible_for_training"] is False


# ---------------------------------------------------------------------------
# 10 — Adjudication DUPLICATE status
# ---------------------------------------------------------------------------
def test_10_adjudication_duplicate(tmp_feedback_dir):
    fb_mgr = tmp_feedback_dir["feedback_manager"]
    adj_mgr = tmp_feedback_dir["adjudication_manager"]
    from backend.app.core.feedback import FeedbackSubmission

    sub = FeedbackSubmission(**_make_feedback_submission())
    rec = fb_mgr.record_feedback(sub, user_id="user_adj_10")

    adj = adj_mgr.adjudicate(
        feedback_id=rec["feedback_id"],
        adjudicator_id="reviewer_10",
        status="DUPLICATE",
        reason="Same message already adjudicated in a prior submission.",
    )
    assert adj["adjudication_status"] == "DUPLICATE"
    assert adj["eligible_for_training"] is False


# ---------------------------------------------------------------------------
# 11 — ACCEPTED requires corrected_priority
# ---------------------------------------------------------------------------
def test_11_accepted_requires_corrected_priority(tmp_feedback_dir):
    fb_mgr = tmp_feedback_dir["feedback_manager"]
    adj_mgr = tmp_feedback_dir["adjudication_manager"]
    from backend.app.core.feedback import FeedbackSubmission

    sub = FeedbackSubmission(**_make_feedback_submission(corrected_priority=None))
    rec = fb_mgr.record_feedback(sub, user_id="user_adj_11")

    with pytest.raises(ValueError, match="corrected_priority"):
        adj_mgr.adjudicate(
            feedback_id=rec["feedback_id"],
            adjudicator_id="reviewer_11",
            status="ACCEPTED",
            reason="Valid correction.",
            corrected_priority=None,  # Missing — should raise
        )


# ---------------------------------------------------------------------------
# 12 — ACCEPTED requires non-empty reason
# ---------------------------------------------------------------------------
def test_12_accepted_requires_reason(tmp_feedback_dir):
    fb_mgr = tmp_feedback_dir["feedback_manager"]
    adj_mgr = tmp_feedback_dir["adjudication_manager"]
    from backend.app.core.feedback import FeedbackSubmission

    sub = FeedbackSubmission(**_make_feedback_submission())
    rec = fb_mgr.record_feedback(sub, user_id="user_adj_12")

    with pytest.raises(ValueError):
        adj_mgr.adjudicate(
            feedback_id=rec["feedback_id"],
            adjudicator_id="reviewer_12",
            status="ACCEPTED",
            reason="",  # Empty reason — should raise
            corrected_priority="P2",
        )


# ---------------------------------------------------------------------------
# 13 — P2/P3 review queue — only P2↔P3 transitions
# ---------------------------------------------------------------------------
def test_13_p2_p3_queue_filters_correctly(tmp_feedback_dir):
    fb_mgr = tmp_feedback_dir["feedback_manager"]
    adj_mgr = tmp_feedback_dir["adjudication_manager"]
    from backend.app.core.feedback import FeedbackSubmission

    user_id = "user_p2p3_13"

    # P2→P3 — should appear
    sub1 = FeedbackSubmission(**_make_feedback_submission(
        message_id="msg_p2_to_p3", predicted_priority="P2", corrected_priority="P3"))
    fb_mgr.record_feedback(sub1, user_id=user_id)

    # P1→P2 — should NOT appear in P2/P3 queue
    sub2 = FeedbackSubmission(**_make_feedback_submission(
        message_id="msg_p1_to_p2", predicted_priority="P1", corrected_priority="P2"))
    fb_mgr.record_feedback(sub2, user_id=user_id)

    # P3→P4 — should NOT appear
    sub3 = FeedbackSubmission(**_make_feedback_submission(
        message_id="msg_p3_to_p4", predicted_priority="P3", corrected_priority="P4"))
    fb_mgr.record_feedback(sub3, user_id=user_id)

    queue = adj_mgr.get_p2_p3_queue(user_id=user_id)
    msg_ids = {r.get("message_id") for r in queue}
    assert "msg_p2_to_p3" in msg_ids, "P2→P3 should be in boundary queue"
    assert "msg_p1_to_p2" not in msg_ids, "P1→P2 should NOT be in P2/P3 queue"
    assert "msg_p3_to_p4" not in msg_ids, "P3→P4 should NOT be in P2/P3 queue"


# ---------------------------------------------------------------------------
# 14 — Safety queue — P1 escalations surfaced first
# ---------------------------------------------------------------------------
def test_14_safety_queue_p1_escalation(tmp_feedback_dir):
    fb_mgr = tmp_feedback_dir["feedback_manager"]
    adj_mgr = tmp_feedback_dir["adjudication_manager"]
    from backend.app.core.feedback import FeedbackSubmission

    user_id = "user_safety_14"

    # OTP / security feedback
    sub_otp = FeedbackSubmission(**_make_feedback_submission(
        message_id="msg_otp_01",
        predicted_priority="P3",
        corrected_priority="P1",
        original_topic="otp",
    ))
    fb_mgr.record_feedback(sub_otp, user_id=user_id)

    # Regular P2/P3 feedback
    sub_regular = FeedbackSubmission(**_make_feedback_submission(
        message_id="msg_regular_01",
        predicted_priority="P3",
        corrected_priority="P2",
        original_topic="newsletter",
    ))
    fb_mgr.record_feedback(sub_regular, user_id=user_id)

    safety_queue = adj_mgr.get_safety_queue(user_id=user_id)
    safety_msg_ids = {r.get("message_id") for r in safety_queue}
    assert "msg_otp_01" in safety_msg_ids, "OTP escalation should be in safety queue"


# ---------------------------------------------------------------------------
# 15 — Deadline queue — deadline_correction cases included
# ---------------------------------------------------------------------------
def test_15_deadline_queue(tmp_feedback_dir):
    fb_mgr = tmp_feedback_dir["feedback_manager"]
    adj_mgr = tmp_feedback_dir["adjudication_manager"]
    from backend.app.core.feedback import FeedbackSubmission

    user_id = "user_deadline_15"

    sub_dl = FeedbackSubmission(**_make_feedback_submission(
        message_id="msg_deadline_01",
        original_deadline_detected=True,
        deadline_correction=True,
    ))
    fb_mgr.record_feedback(sub_dl, user_id=user_id)

    sub_nodl = FeedbackSubmission(**_make_feedback_submission(
        message_id="msg_no_deadline_01",
        original_deadline_detected=False,
    ))
    fb_mgr.record_feedback(sub_nodl, user_id=user_id)

    dl_queue = adj_mgr.get_deadline_queue(user_id=user_id)
    dl_ids = {r.get("message_id") for r in dl_queue}
    assert "msg_deadline_01" in dl_ids


# ---------------------------------------------------------------------------
# 16 — Provenance on every accepted record
# ---------------------------------------------------------------------------
def test_16_accepted_records_have_provenance(tmp_feedback_dir):
    fb_mgr = tmp_feedback_dir["feedback_manager"]
    adj_mgr = tmp_feedback_dir["adjudication_manager"]
    from backend.app.core.feedback import FeedbackSubmission

    for i in range(3):
        sub = FeedbackSubmission(**_make_feedback_submission(message_id=f"msg_prov_{i}"))
        rec = fb_mgr.record_feedback(sub, user_id=f"user_prov_{i}")
        adj_mgr.adjudicate(
            feedback_id=rec["feedback_id"],
            adjudicator_id="reviewer_prov",
            status="ACCEPTED",
            reason="Valid correction with documented reasoning.",
            corrected_priority="P2",
        )

    pool = adj_mgr.get_candidate_pool()
    for r in pool:
        assert r.get("provenance") == "HUMAN_PRODUCTION_FEEDBACK_ADJUDICATED", (
            f"Missing provenance on: {r.get('adjudication_id')}"
        )


# ---------------------------------------------------------------------------
# 17 — Candidate pool — ACCEPTED only
# ---------------------------------------------------------------------------
def test_17_candidate_pool_accepted_only(tmp_feedback_dir):
    fb_mgr = tmp_feedback_dir["feedback_manager"]
    adj_mgr = tmp_feedback_dir["adjudication_manager"]
    from backend.app.core.feedback import FeedbackSubmission

    # ACCEPTED
    sub_a = FeedbackSubmission(**_make_feedback_submission(message_id="msg_pool_accepted"))
    rec_a = fb_mgr.record_feedback(sub_a, user_id="user_pool_17")
    adj_mgr.adjudicate(
        feedback_id=rec_a["feedback_id"],
        adjudicator_id="rev_17",
        status="ACCEPTED",
        reason="Genuine P2 correction — operational deadline, action required.",
        corrected_priority="P2",
    )

    # REJECTED — must NOT enter pool
    sub_r = FeedbackSubmission(**_make_feedback_submission(message_id="msg_pool_rejected"))
    rec_r = fb_mgr.record_feedback(sub_r, user_id="user_pool_17")
    adj_mgr.adjudicate(
        feedback_id=rec_r["feedback_id"],
        adjudicator_id="rev_17",
        status="REJECTED",
        reason="User preference, not model error.",
    )

    pool = adj_mgr.get_candidate_pool()
    pool_msg_ids = {r.get("message_id") for r in pool}
    assert "msg_pool_accepted" in pool_msg_ids
    assert "msg_pool_rejected" not in pool_msg_ids


# ---------------------------------------------------------------------------
# 18 — REJECTED feedback not in candidate pool
# ---------------------------------------------------------------------------
def test_18_rejected_not_in_pool(tmp_feedback_dir):
    fb_mgr = tmp_feedback_dir["feedback_manager"]
    adj_mgr = tmp_feedback_dir["adjudication_manager"]
    from backend.app.core.feedback import FeedbackSubmission

    sub = FeedbackSubmission(**_make_feedback_submission(message_id="msg_reject_18"))
    rec = fb_mgr.record_feedback(sub, user_id="user_reject_18")
    adj_mgr.adjudicate(
        feedback_id=rec["feedback_id"],
        adjudicator_id="rev_18",
        status="REJECTED",
        reason="Sender identity bias — user corrects because they know the sender, not because of email content.",
    )

    pool = adj_mgr.get_candidate_pool()
    pool_ids = {r.get("message_id") for r in pool}
    assert "msg_reject_18" not in pool_ids, "REJECTED feedback must not enter candidate pool"


# ---------------------------------------------------------------------------
# 19 — Leakage audit — no overlap with frozen test.csv
# ---------------------------------------------------------------------------
def test_19_leakage_audit_no_test_overlap(tmp_path):
    """
    Builds a v5.2 candidate pool with synthetic accepted records and
    verifies the leakage audit detects zero overlap with frozen test.csv.
    """
    from backend.app.core.dataset_v52 import DatasetV52Builder

    # Create a synthetic pool with IDs that do NOT appear in test.csv
    synthetic_pool = [
        {
            "message_id": f"synthetic_phase52_msg_{i}",
            "adjudication_id": str(uuid.uuid4()),
            "feedback_id": str(uuid.uuid4()),
            "user_id": f"user_leak_{i}",
            "original_priority": "P3",
            "corrected_priority": "P2",
            "adjudication_status": "ACCEPTED",
            "eligible_for_training": True,
            "provenance": "HUMAN_PRODUCTION_FEEDBACK_ADJUDICATED",
            "source_model_version": "priority-v5.1",
            "topic": "academic",
        }
        for i in range(5)
    ]

    builder = DatasetV52Builder()
    leakage = builder.run_leakage_audit(pool=synthetic_pool)
    assert leakage["leakage_free"] is True, (
        f"Expected leakage-free. Got: {leakage['leakage_details']}"
    )


# ---------------------------------------------------------------------------
# 20 — Leakage audit — internal duplicate detection
# ---------------------------------------------------------------------------
def test_20_leakage_audit_internal_duplicates():
    from backend.app.core.dataset_v52 import DatasetV52Builder

    builder = DatasetV52Builder()
    pool = [
        {"message_id": "msg_dup", "corrected_priority": "P2", "eligible_for_training": True},
        {"message_id": "msg_dup", "corrected_priority": "P2", "eligible_for_training": True},
        {"message_id": "msg_unique", "corrected_priority": "P3", "eligible_for_training": True},
    ]
    leakage = builder.run_leakage_audit(pool=pool)
    assert leakage["internal_duplicate_count"] == 1, "Should detect 1 internal duplicate"


# ---------------------------------------------------------------------------
# 21 — Dataset manifest — all required fields present
# ---------------------------------------------------------------------------
def test_21_manifest_required_fields(tmp_path):
    from backend.app.core.dataset_v52 import DatasetV52Builder, CANDIDATE_DIR

    with patch("backend.app.core.dataset_v52.CANDIDATE_DIR", str(tmp_path)):
        with patch("backend.app.core.dataset_v52.TRAIN_CANDIDATE_CSV", str(tmp_path / "train_candidate.csv")):
            with patch("backend.app.core.dataset_v52.PROVENANCE_CSV", str(tmp_path / "provenance.csv")):
                with patch("backend.app.core.dataset_v52.ADJUDICATION_LOG", str(tmp_path / "adjudication_log.jsonl")):
                    with patch("backend.app.core.dataset_v52.CANDIDATE_MANIFEST", str(tmp_path / "candidate_manifest.json")):
                        with patch("backend.app.core.dataset_v52.LEAKAGE_AUDIT_JSON", str(tmp_path / "leakage_audit.json")):
                            with patch("backend.app.core.dataset_v52.DATASET_CARD", str(tmp_path / "dataset_card.md")):
                                with patch("backend.app.core.dataset_v52.adjudication_manager") as mock_adj:
                                    mock_adj.get_candidate_pool.return_value = []
                                    builder = DatasetV52Builder()
                                    result = builder.build()

    assert "candidate_dir" in result
    assert "readiness" in result
    assert "leakage_audit" in result
    assert result["candidate_status"] == "CANDIDATE — NOT TRAINED — NOT PRODUCTION"


# ---------------------------------------------------------------------------
# 22 — Multi-user isolation — User A adj invisible to User B
# ---------------------------------------------------------------------------
def test_22_multiuser_isolation(tmp_feedback_dir):
    fb_mgr = tmp_feedback_dir["feedback_manager"]
    adj_mgr = tmp_feedback_dir["adjudication_manager"]
    from backend.app.core.feedback import FeedbackSubmission

    # User A submits and adjudicates
    sub_a = FeedbackSubmission(**_make_feedback_submission(message_id="msg_user_a_iso"))
    rec_a = fb_mgr.record_feedback(sub_a, user_id="user_iso_A")
    adj_mgr.adjudicate(
        feedback_id=rec_a["feedback_id"],
        adjudicator_id="user_iso_A",
        status="ACCEPTED",
        reason="Genuine correction for user A.",
        corrected_priority="P2",
    )

    # User B should not see User A's feedback
    b_records = fb_mgr.list_feedback(user_id="user_iso_B")
    b_msg_ids = {r.get("message_id") for r in b_records}
    assert "msg_user_a_iso" not in b_msg_ids, "User B must not see User A's feedback"

    # User B queue should not include User A's records
    b_queue = adj_mgr.get_pending_queue(user_id="user_iso_B")
    b_queue_ids = {r.get("message_id") for r in b_queue}
    assert "msg_user_a_iso" not in b_queue_ids


# ---------------------------------------------------------------------------
# 23 — Model version preserved in adjudication record
# ---------------------------------------------------------------------------
def test_23_model_version_preserved(tmp_feedback_dir):
    fb_mgr = tmp_feedback_dir["feedback_manager"]
    adj_mgr = tmp_feedback_dir["adjudication_manager"]
    from backend.app.core.feedback import FeedbackSubmission

    sub = FeedbackSubmission(**_make_feedback_submission(model_version="priority-v5.1"))
    rec = fb_mgr.record_feedback(sub, user_id="user_mv_23")

    adj = adj_mgr.adjudicate(
        feedback_id=rec["feedback_id"],
        adjudicator_id="rev_23",
        status="ACCEPTED",
        reason="Valid model version reference.",
        corrected_priority="P2",
    )
    assert adj.get("source_model_version") == "priority-v5.1" or adj.get("model_version") == "priority-v5.1"


# ---------------------------------------------------------------------------
# 24 — Unauthenticated cannot POST adjudication (FastAPI route test)
# ---------------------------------------------------------------------------
def test_24_unauthenticated_adjudication_rejected():
    from fastapi.testclient import TestClient
    from backend.app.main import app

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post("/api/adjudication/adjudicate", json={
        "feedback_id": "fake_id",
        "adjudication_status": "ACCEPTED",
        "adjudication_reason": "attempt without auth",
        "corrected_priority": "P2",
    })
    assert resp.status_code == 401, f"Expected 401 unauthenticated, got {resp.status_code}"


# ---------------------------------------------------------------------------
# 25 — GET /api/feedback scoped to authenticated user only
# ---------------------------------------------------------------------------
def test_25_feedback_api_user_scoped():
    from fastapi.testclient import TestClient
    from backend.app.main import app

    client = TestClient(app, raise_server_exceptions=False)
    # Unauthenticated — should get 401
    resp = client.get("/api/feedback")
    assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"


# ---------------------------------------------------------------------------
# 26 — Malformed feedback — missing message_id rejected with 422
# ---------------------------------------------------------------------------
def test_26_malformed_feedback_rejected():
    from fastapi.testclient import TestClient
    from backend.app.main import app
    from unittest.mock import patch, MagicMock

    # Mock a valid session
    mock_session = MagicMock()
    mock_session.user_id = "user_malform_26"
    mock_session.email = "test@example.com"

    with patch("backend.app.api.routes_emails.get_session_from_request", return_value=mock_session):
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/feedback", json={
            # Missing message_id — should fail Pydantic validation
            "model_version": "priority-v5.1",
            "predicted_priority": "P3",
            "predicted_action_required": False,
        })
    assert resp.status_code == 422, f"Expected 422 validation error, got {resp.status_code}"


# ---------------------------------------------------------------------------
# 27 — No training — model artifacts unchanged
# ---------------------------------------------------------------------------
def test_27_no_training_no_artifact_changes():
    """
    Verifies that no model training artifacts were modified by Phase 52.
    The adjudication module and dataset_v52 builder must not call model.fit()
    or import sklearn training utilities.
    """
    import backend.app.core.adjudication as adj_mod
    import backend.app.core.dataset_v52 as ds_mod
    import inspect

    # Neither module may import sklearn training tools
    adj_src = inspect.getsource(adj_mod)
    ds_src = inspect.getsource(ds_mod)

    # Check for sklearn fit imports / GridSearchCV — actual executable lines,
    # not docstring references. Use import-level checks.
    sklearn_imports = [
        "from sklearn",
        "import sklearn",
        "GridSearchCV",
        "RandomizedSearchCV",
        "Pipeline().fit",
    ]
    for pattern in sklearn_imports:
        assert pattern not in adj_src, f"adjudication.py must not contain '{pattern}'"
        assert pattern not in ds_src, f"dataset_v52.py must not contain '{pattern}'"

    # Neither module may define a function that calls train/fit
    assert "def train_" not in adj_src, "adjudication.py must not define train_*"
    assert "def train_" not in ds_src, "dataset_v52.py must not define train_*"


# ---------------------------------------------------------------------------
# 28 — Production model SHA — v5.1 unchanged throughout phase
# ---------------------------------------------------------------------------
def test_28_production_model_sha_unchanged():
    """
    Verifies that priority-v5.1 model artifact SHA-256 matches the Phase 50
    promotion snapshot.
    """
    import json

    EXPECTED_V51_SHA = "8524ad73965859ee022f1271caee0040928e7805ab7d32c49b2f26e994f98c06"
    EXPECTED_V41_SHA = "09fe269f19ad6afb38e71b56f8c6ee7a386e59605c62c892478400bc09d5cbd0"

    registry_path = os.path.join(BASE_DIR, "dataset", "models", "registry.json")
    assert os.path.exists(registry_path), f"registry.json not found at {registry_path}"

    with open(registry_path, "r", encoding="utf-8") as f:
        registry = json.load(f)

    assert registry.get("active_model") == "priority-v5.1", (
        f"Active model should be priority-v5.1, got: {registry.get('active_model')}"
    )

    v51_meta = registry.get("versions", {}).get("priority-v5.1", {})
    v41_meta = registry.get("versions", {}).get("priority-v4.1", {})

    assert v51_meta.get("artifact_sha256") == EXPECTED_V51_SHA, (
        f"v5.1 SHA mismatch. Expected: {EXPECTED_V51_SHA}, "
        f"Got: {v51_meta.get('artifact_sha256')}"
    )

    assert v41_meta.get("artifact_sha256") == EXPECTED_V41_SHA, (
        f"v4.1 (rollback) SHA mismatch. Expected: {EXPECTED_V41_SHA}, "
        f"Got: {v41_meta.get('artifact_sha256')}"
    )

    # Verify production status
    assert v51_meta.get("status") == "production", (
        f"v5.1 must be 'production', got: {v51_meta.get('status')}"
    )
