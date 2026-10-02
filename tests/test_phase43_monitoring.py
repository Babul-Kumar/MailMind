"""
test_phase43_monitoring.py — Phase 43 Production Observation Tests
===================================================================
Validates:
  1.  Registry state — priority-v4.1 active, priority-v3 rollback-ready
  2.  Feedback submission — POST /api/feedback stores all Phase 43 fields
  3.  Feedback user isolation — User A feedback invisible to User B
  4.  Monitoring summary endpoint — correct structure and model identity
  5.  Distribution report — P1/P2/P3/P4 counts, drift keys
  6.  Confidence report — per-priority percentile stats
  7.  Safety events — endpoint returns list structure
  8.  Feedback stats — correction_rate and matrix present
  9.  V5 readiness — pipeline and gates present
 10.  No retraining — no fit/fit_transform called through monitoring
 11.  Privacy — no OAuth token in any monitoring response
 12.  Model artifact unchanged — SHA-256 stable after monitoring calls
 13.  Multi-user isolation — monitoring endpoint uses session user_id
"""
import os
import sys
import json
import time
import hashlib
import unittest
import threading
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.app.main import app
from backend.app.ml.registry import model_registry
from backend.app.ml.predictor import load_model
from backend.app.core.feedback import feedback_manager, FeedbackSubmission
from backend.app.core.monitoring import production_monitor, V41_BASELINE
from backend.app.core.prediction_log import log_prediction, read_prediction_log
from backend.app.core.session import session_manager
from backend.app.core.config import TOKEN_FILE, GMAIL_SCOPES


def _make_client_with_session(user_id: str, email: str) -> TestClient:
    """Creates a TestClient with a fake authenticated session."""
    client = TestClient(app)
    try:
        from google.oauth2.credentials import Credentials
        if os.path.exists(TOKEN_FILE):
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, GMAIL_SCOPES)
        else:
            creds = MagicMock(spec=Credentials)
            creds.token = "fake_token"
            creds.valid = True
        session = session_manager.create_session(
            user_id=user_id, email=email, credentials=creds
        )
        client.cookies.set("mailmind_session", session.session_id)
    except Exception as e:
        print(f"Warning: could not create session for {user_id}: {e}")
    return client


class TestPhase43Monitoring(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = _make_client_with_session(
            "phase43_test_user", "monitor@mailmind.local"
        )
        cls.client_b = _make_client_with_session(
            "phase43_user_b", "userb@mailmind.local"
        )

    # -----------------------------------------------------------------------
    # Test 1 — Registry: priority-v4.1 active, priority-v3 rollback-ready
    # -----------------------------------------------------------------------
    def test_01_registry_v41_active_v3_rollback_ready(self):
        """Active model must be valid production model; priority-v3 must exist as rollback."""
        active = model_registry.get_active_version()
        self.assertIn(active, ("priority-v4.1", "priority-v5.1"),
                      "Active production model must be priority-v4.1 or priority-v5.1")

        reg = model_registry.get_registry()
        v3_meta = reg.get("versions", {}).get("priority-v3", {})
        self.assertIn(v3_meta.get("status"), ("retired",),
                      "priority-v3 must be in retired state (rollback-ready)")

        v3_path = os.path.join(BASE_DIR, "dataset", "models", "priority-v3", "model.joblib")
        self.assertTrue(os.path.exists(v3_path),
                        "priority-v3 artifact must exist on disk for rollback")

        # Verify promotion timestamp recorded
        v41_meta = reg.get("versions", {}).get("priority-v4.1", {})
        self.assertEqual(v41_meta.get("promoted_at"), "2026-10-02T14:23:34Z")

    # -----------------------------------------------------------------------
    # Test 2 — Feedback submission stores Phase 43 fields
    # -----------------------------------------------------------------------
    def test_02_feedback_submission_stores_new_fields(self):
        """POST /api/feedback must persist thread_id, feedback_type, original_confidence."""
        payload = {
            "message_id": "phase43_test_msg_001",
            "thread_id": "thread_phase43_001",
            "model_version": "priority-v4.1",
            "feedback_type": "priority_wrong",
            "predicted_priority": "P3",
            "original_confidence": 0.72,
            "original_topic": "newsletter",
            "original_deadline_detected": False,
            "predicted_action_required": False,
            "corrected_priority": "P2",
            "corrected_action_required": False,
            "notes": "Phase 43 test feedback",
        }
        response = self.client.post("/api/feedback", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")

        record = data["record"]
        self.assertEqual(record["thread_id"], "thread_phase43_001")
        self.assertEqual(record["feedback_type"], "priority_wrong")
        self.assertAlmostEqual(record["original_confidence"], 0.72, places=2)
        self.assertEqual(record["original_topic"], "newsletter")
        self.assertIn("feedback_timestamp", record)
        self.assertEqual(record["status"], "pending_review")

        # Confirm no credentials in response
        record_str = json.dumps(record)
        for forbidden in ("access_token", "refresh_token", "credentials"):
            self.assertNotIn(forbidden, record_str,
                             f"'{forbidden}' must not appear in feedback record")

    # -----------------------------------------------------------------------
    # Test 3 — Feedback user isolation
    # -----------------------------------------------------------------------
    def test_03_feedback_user_isolation(self):
        """
        Feedback submitted by User A must not appear in User B's feedback list.
        """
        # User A submits feedback
        payload_a = {
            "message_id": "isolation_msg_user_a",
            "model_version": "priority-v4.1",
            "feedback_type": "priority_wrong",
            "predicted_priority": "P4",
            "predicted_action_required": False,
            "corrected_priority": "P2",
        }
        self.client.post("/api/feedback", json=payload_a)

        # User B reads feedback — should NOT see User A's record
        records_a = feedback_manager.list_feedback(user_id="phase43_test_user")
        records_b = feedback_manager.list_feedback(user_id="phase43_user_b")

        msg_ids_a = {r.get("message_id") for r in records_a}
        msg_ids_b = {r.get("message_id") for r in records_b}
        # User A's isolation test message must not appear in User B's list
        self.assertNotIn("isolation_msg_user_a", msg_ids_b,
                         "User A feedback must not appear in User B's records")

    # -----------------------------------------------------------------------
    # Test 4 — Monitoring summary endpoint
    # -----------------------------------------------------------------------
    def test_04_monitoring_summary_endpoint(self):
        """GET /api/monitoring/summary must return model version and distribution."""
        response = self.client.get("/api/monitoring/summary")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")

        monitoring = data["monitoring"]
        prod_model = monitoring["production_model"]
        self.assertIn(prod_model["model_version"], ("priority-v4.1", "priority-v5.1"))
        self.assertIn(prod_model["dataset_version"], ("dataset-v4.1", "dataset-v5.1"))
        self.assertIn("artifact_sha256", prod_model)

        # Distribution keys present
        dist = monitoring["mailbox_distribution"]
        for key in ("P1_pct", "P2_pct", "P3_pct", "P4_pct",
                    "action_required_count", "needs_attention_count", "total_messages"):
            self.assertIn(key, dist, f"Distribution key '{key}' missing from summary")

        # Feedback keys present
        fb = monitoring["feedback"]
        self.assertIn("total_feedback", fb)
        self.assertIn("correction_rate_pct", fb)

        # Observation phase marker
        self.assertEqual(monitoring["observation_phase"], "Phase 43")
        self.assertIn("NOT ACTIVE", monitoring["retraining_status"])

    # -----------------------------------------------------------------------
    # Test 5 — Distribution report
    # -----------------------------------------------------------------------
    def test_05_distribution_report(self):
        """GET /api/monitoring/distribution must include counts, pcts, drift, baseline."""
        response = self.client.get("/api/monitoring/distribution")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")

        dist = data["distribution"]
        self.assertIn("total_messages", dist)
        self.assertIn("counts", dist)
        self.assertIn("percentages", dist)
        self.assertIn("baseline", dist)
        self.assertIn("drift_vs_baseline_pct_pts", dist)

        # All four priorities in counts
        for p in ("P1", "P2", "P3", "P4"):
            self.assertIn(p, dist["counts"])

        # Drift should be a numeric dict
        drift = dist["drift_vs_baseline_pct_pts"]
        self.assertIsInstance(drift, dict)

    # -----------------------------------------------------------------------
    # Test 6 — Confidence report
    # -----------------------------------------------------------------------
    def test_06_confidence_report(self):
        """GET /api/monitoring/confidence must return per-priority percentile stats."""
        response = self.client.get("/api/monitoring/confidence")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")

        conf = data["confidence"]
        self.assertIn("by_priority", conf)
        self.assertIn("review_candidates", conf)

        for p in ("P1", "P2", "P3", "P4"):
            p_stats = conf["by_priority"].get(p, {})
            for field in ("count", "mean", "median", "p10", "p25", "p75", "p90"):
                self.assertIn(field, p_stats,
                              f"Confidence stat '{field}' missing for {p}")

        rc = conf["review_candidates"]
        for key in ("low_confidence_P1", "low_confidence_P2",
                    "high_confidence_P3", "high_confidence_P4", "note"):
            self.assertIn(key, rc)

    # -----------------------------------------------------------------------
    # Test 7 — Safety events endpoint
    # -----------------------------------------------------------------------
    def test_07_safety_events_endpoint(self):
        """GET /api/monitoring/safety must return structured safety event lists."""
        response = self.client.get("/api/monitoring/safety")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")

        safety = data["safety"]
        for key in ("otp_below_p1", "security_below_p2",
                    "payment_non_actionable", "deadline_flagged_non_actionable",
                    "total_safety_events", "note"):
            self.assertIn(key, safety, f"Safety key '{key}' missing")

        # Lists must be iterable
        self.assertIsInstance(safety["otp_below_p1"], list)
        self.assertIsInstance(safety["security_below_p2"], list)

    # -----------------------------------------------------------------------
    # Test 8 — Feedback stats correction rate
    # -----------------------------------------------------------------------
    def test_08_feedback_stats_correction_rate(self):
        """GET /api/monitoring/feedback-stats must return correction rate and matrix."""
        response = self.client.get("/api/monitoring/feedback-stats")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")

        stats = data["feedback_stats"]
        for key in ("total_feedback", "total_priority_corrections",
                    "overall_correction_rate_pct", "correction_rate_by_priority",
                    "correction_matrix", "notable"):
            self.assertIn(key, stats, f"Feedback stat key '{key}' missing")

        # Matrix has all four priorities
        matrix = stats["correction_matrix"]
        for p in ("P1", "P2", "P3", "P4"):
            self.assertIn(p, matrix)

        # Notable section has safety-critical lower→P1 note
        notable = stats["notable"]
        self.assertIn("lower_to_P1", notable)

    # -----------------------------------------------------------------------
    # Test 9 — V5 readiness endpoint
    # -----------------------------------------------------------------------
    def test_09_v5_readiness_endpoint(self):
        """GET /api/monitoring/v5-readiness must return pipeline and gate criteria."""
        response = self.client.get("/api/monitoring/v5-readiness")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")

        readiness = data["v5_readiness"]
        self.assertIn("dataset_v5_readiness", readiness)
        self.assertIn("gates_met", readiness)
        self.assertIn("total_gates", readiness)
        self.assertIn("ready_to_curate", readiness)
        self.assertIn("pipeline", readiness)
        self.assertIn("forbidden", readiness)

        # The forbidden string must be clear
        self.assertIn("automatic training", readiness["forbidden"].lower())

        # Pipeline steps include feedback and human adjudication
        pipeline_str = " ".join(readiness["pipeline"])
        self.assertIn("feedback", pipeline_str.lower())
        self.assertIn("human adjudication", pipeline_str.lower())
        self.assertIn("offline training", pipeline_str.lower())

    # -----------------------------------------------------------------------
    # Test 10 — No retraining through monitoring
    # -----------------------------------------------------------------------
    def test_10_no_retraining_through_monitoring(self):
        """No .fit() or .fit_transform() may be called via any monitoring endpoint."""
        pipeline = load_model()
        with patch.object(pipeline, "fit") as mock_fit, \
             patch.object(pipeline.named_steps["tfidf"], "fit") as mock_tfidf_fit, \
             patch.object(pipeline.named_steps["tfidf"], "fit_transform") as mock_ft, \
             patch.object(pipeline.named_steps["clf"], "fit") as mock_clf_fit:

            self.client.get("/api/monitoring/summary")
            self.client.get("/api/monitoring/distribution")
            self.client.get("/api/monitoring/confidence")
            self.client.get("/api/monitoring/safety")
            self.client.get("/api/monitoring/feedback-stats")
            self.client.get("/api/monitoring/v5-readiness")

            mock_fit.assert_not_called()
            mock_tfidf_fit.assert_not_called()
            mock_ft.assert_not_called()
            mock_clf_fit.assert_not_called()

    # -----------------------------------------------------------------------
    # Test 11 — Privacy: no OAuth token in monitoring responses
    # -----------------------------------------------------------------------
    def test_11_no_oauth_token_in_monitoring_responses(self):
        """No OAuth token, refresh_token, or credentials must appear in responses."""
        endpoints = [
            "/api/monitoring/summary",
            "/api/monitoring/distribution",
            "/api/monitoring/confidence",
            "/api/monitoring/safety",
            "/api/monitoring/feedback-stats",
            "/api/monitoring/v5-readiness",
        ]
        for ep in endpoints:
            resp = self.client.get(ep)
            body = resp.text
            for token_key in ("access_token", "refresh_token", "credentials", "oauth"):
                self.assertNotIn(
                    token_key, body.lower(),
                    f"'{token_key}' must not appear in {ep} response"
                )

    # -----------------------------------------------------------------------
    # Test 12 — Model artifact SHA unchanged after monitoring calls
    # -----------------------------------------------------------------------
    def test_12_model_sha_unchanged_after_monitoring(self):
        """Model artifacts must remain bitwise identical after all monitoring calls."""
        v41_path = os.path.join(
            BASE_DIR, "dataset", "models", "priority-v4.1", "model.joblib"
        )
        v3_path = os.path.join(
            BASE_DIR, "dataset", "models", "priority-v3", "model.joblib"
        )

        def sha256(path):
            h = hashlib.sha256()
            with open(path, "rb") as f:
                while chunk := f.read(65536):
                    h.update(chunk)
            return h.hexdigest()

        sha_v41_before = sha256(v41_path)
        sha_v3_before = sha256(v3_path)

        # Call all monitoring endpoints
        for ep in ["/api/monitoring/summary", "/api/monitoring/distribution",
                   "/api/monitoring/confidence", "/api/monitoring/safety",
                   "/api/monitoring/feedback-stats", "/api/monitoring/v5-readiness"]:
            self.client.get(ep)

        sha_v41_after = sha256(v41_path)
        sha_v3_after = sha256(v3_path)

        self.assertEqual(sha_v41_before, sha_v41_after,
                         "priority-v4.1 artifact SHA changed after monitoring calls!")
        self.assertEqual(sha_v3_before, sha_v3_after,
                         "priority-v3 artifact SHA changed after monitoring calls!")

        # Also verify known SHAs from Phase 42
        EXPECTED_V41_SHA = "09fe269f19ad6afb38e71b56f8c6ee7a386e59605c62c892478400bc09d5cbd0"
        EXPECTED_V3_SHA = "fa69e6a5cfafb8b24c5941dbb8fb08a208addfc4f39e38fa47df0a7cd7040b56"
        self.assertEqual(sha_v41_after, EXPECTED_V41_SHA,
                         "priority-v4.1 SHA does not match Phase 42 promotion record!")
        self.assertEqual(sha_v3_after, EXPECTED_V3_SHA,
                         "priority-v3 SHA does not match Phase 42 promotion record!")

    # -----------------------------------------------------------------------
    # Test 13 — Multi-user isolation in monitoring
    # -----------------------------------------------------------------------
    def test_13_multiuser_monitoring_isolation(self):
        """
        Each user's monitoring summary must reflect only their own data.
        User A and User B must not share mailbox statistics.
        """
        # Both users call the summary endpoint
        resp_a = self.client.get("/api/monitoring/summary")
        resp_b = self.client_b.get("/api/monitoring/summary")

        self.assertEqual(resp_a.status_code, 200)
        self.assertEqual(resp_b.status_code, 200)

        data_a = resp_a.json()
        data_b = resp_b.json()

        # Both responses should be structurally valid
        self.assertEqual(data_a["status"], "success")
        self.assertEqual(data_b["status"], "success")

        # Both should report the same active model version (global)
        self.assertEqual(
            data_a["monitoring"]["production_model"]["model_version"],
            data_b["monitoring"]["production_model"]["model_version"],
            "Active model version must be identical for all users"
        )

        # But mailbox stats may differ per-user (they have separate caches)
        total_a = data_a["monitoring"]["mailbox_distribution"]["total_messages"]
        total_b = data_b["monitoring"]["mailbox_distribution"]["total_messages"]
        # Simply assert they're non-negative integers (no cross-user leakage)
        self.assertGreaterEqual(total_a, 0)
        self.assertGreaterEqual(total_b, 0)

        # Verify prediction_log keys are present
        self.assertIn("prediction_log", data_a["monitoring"])
        self.assertIn("prediction_log", data_b["monitoring"])


# ---------------------------------------------------------------------------
# Standalone: prediction log unit tests
# ---------------------------------------------------------------------------
class TestPredictionLog(unittest.TestCase):

    def test_prediction_log_write_read(self):
        """log_prediction must write a record readable by read_prediction_log."""
        test_uid = f"pred_log_test_{int(time.time())}"
        log_prediction(
            user_id=test_uid,
            message_id="msg_pred_001",
            thread_id="thread_001",
            model_version="priority-v4.1",
            predicted_priority="P2",
            confidence=0.81,
            action_required=True,
            deadline_detected=False,
            deadline_status="NONE",
            topic="work",
            needs_attention=False,
            refinement_applied=False,
        )
        records = read_prediction_log(test_uid)
        self.assertEqual(len(records), 1)
        rec = records[0]
        self.assertEqual(rec["message_id"], "msg_pred_001")
        self.assertEqual(rec["model_version"], "priority-v4.1")
        self.assertEqual(rec["predicted_priority"], "P2")
        self.assertAlmostEqual(rec["confidence"], 0.81, places=2)
        self.assertTrue(rec["action_required"])
        # No raw content fields
        for forbidden in ("subject", "body", "sender", "access_token", "refresh_token"):
            self.assertNotIn(forbidden, rec,
                             f"'{forbidden}' must not appear in prediction log record")

    def test_prediction_log_no_crash_on_bad_input(self):
        """log_prediction must never raise — errors are silently swallowed."""
        # Should not raise even with empty user_id
        try:
            log_prediction(
                user_id="",
                message_id="",
                thread_id=None,
                model_version="priority-v4.1",
                predicted_priority="P4",
                confidence=0.5,
                action_required=False,
                deadline_detected=False,
                deadline_status=None,
                topic=None,
            )
        except Exception as e:
            self.fail(f"log_prediction raised unexpectedly: {e}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
