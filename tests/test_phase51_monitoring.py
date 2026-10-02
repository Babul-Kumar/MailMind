"""
test_phase51_monitoring.py — Phase 51 Comprehensive Monitoring Tests
=====================================================================
Validates the Phase 51 production monitoring system:
  - All monitoring endpoints return structured responses
  - Safety constraints are upheld
  - User-scoped isolation
  - Read-only invariants
  - Privacy guarantees
  - Alert configuration consistency
  - v5.2 readiness report structure
  - No retraining, no model promotion, no credential leakage
"""

import os
import sys
import json
import time
import pytest
import sqlite3
import hashlib
import tempfile
from unittest.mock import patch, MagicMock

# Ensure project root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.app.core.phase51_monitor import (
    Phase51Monitor, phase51_monitor,
    ALERT_CONFIG, V51_BASELINE, SAFETY_CATEGORIES,
    _classify_severity, _parse_ts,
)


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture
def monitor():
    """Fresh Phase51Monitor instance for each test."""
    return Phase51Monitor()


@pytest.fixture
def mock_cache_db(tmp_path):
    """Creates a temporary SQLite cache DB with test data."""
    db_path = str(tmp_path / "test_cache.db")
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE user_email_cache (
            user_id TEXT NOT NULL,
            message_id TEXT NOT NULL,
            thread_id TEXT,
            internal_date INTEGER DEFAULT 0,
            date_str TEXT,
            sender TEXT,
            recipients TEXT,
            subject TEXT,
            snippet TEXT,
            body TEXT,
            content_hash TEXT,
            model_version TEXT NOT NULL DEFAULT 'priority-v5.1',
            predicted_priority TEXT,
            action_required INTEGER DEFAULT 0,
            deadline_detected INTEGER DEFAULT 0,
            deadline_display TEXT,
            needs_attention INTEGER DEFAULT 0,
            refinement_applied INTEGER DEFAULT 0,
            confidence REAL DEFAULT 0.0,
            topic TEXT,
            data_json TEXT NOT NULL,
            analyzed_at REAL,
            is_stale INTEGER DEFAULT 0,
            deadline_status TEXT DEFAULT 'NONE',
            action_evidence TEXT,
            PRIMARY KEY (user_id, message_id, model_version)
        );
    """)

    # Seed test data: 100 messages
    test_user = "test_user_1"
    priorities = ["P1"] * 2 + ["P2"] * 70 + ["P3"] * 8 + ["P4"] * 20
    topics = ["security"] * 5 + ["academic"] * 30 + ["saas"] * 20 + ["newsletter"] * 15 + ["other"] * 30
    now = time.time()

    for i, (p, t) in enumerate(zip(priorities, topics)):
        conf = 0.55 + (i % 20) * 0.02
        action = 1 if p in ("P1", "P2") and i % 3 == 0 else 0
        deadline = 1 if i % 10 == 0 else 0
        needs_att = 1 if p == "P1" or (p == "P2" and action) else 0
        dl_status = "ACTIVE" if deadline and p in ("P1", "P2") else "NONE"
        conn.execute(
            """INSERT INTO user_email_cache (
                user_id, message_id, model_version, predicted_priority, confidence,
                topic, action_required, deadline_detected, needs_attention,
                deadline_status, subject, sender, data_json, analyzed_at, is_stale
            ) VALUES (?, ?, 'priority-v5.1', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
            (test_user, f"msg_{i}", p, round(conf, 4), t, action, deadline,
             needs_att, dl_status, f"Test Subject {i}", f"sender{i}@example.com",
             json.dumps({"test": True}), now - i * 60),
        )

    # Add data for second user to test isolation
    for i in range(5):
        conn.execute(
            """INSERT INTO user_email_cache (
                user_id, message_id, model_version, predicted_priority, confidence,
                topic, data_json, analyzed_at, is_stale
            ) VALUES (?, ?, 'priority-v5.1', 'P4', 0.8, 'other', ?, ?, 0)""",
            ("test_user_2", f"msg2_{i}", json.dumps({"test": True}), now - i * 60),
        )

    conn.commit()
    conn.close()
    return db_path, test_user


@pytest.fixture
def mock_feedback(tmp_path):
    """Creates a temporary feedback JSONL file with test data."""
    fb_file = str(tmp_path / "feedback.jsonl")
    records = [
        {
            "user_id": "test_user_1", "message_id": "msg_10",
            "feedback_type": "priority_wrong", "predicted_priority": "P2",
            "corrected_priority": "P3", "model_version": "priority-v5.1",
            "original_topic": "academic", "feedback_timestamp": "2026-10-02T12:00:00Z",
        },
        {
            "user_id": "test_user_1", "message_id": "msg_20",
            "feedback_type": "priority_wrong", "predicted_priority": "P3",
            "corrected_priority": "P2", "model_version": "priority-v5.1",
            "original_topic": "saas", "feedback_timestamp": "2026-10-02T12:05:00Z",
        },
        {
            "user_id": "test_user_1", "message_id": "msg_30",
            "feedback_type": "action_required_wrong", "predicted_priority": "P2",
            "model_version": "priority-v5.1", "original_topic": "newsletter",
            "feedback_timestamp": "2026-10-02T12:10:00Z",
        },
        {
            "user_id": "test_user_2", "message_id": "msg2_1",
            "feedback_type": "priority_wrong", "predicted_priority": "P4",
            "corrected_priority": "P1", "model_version": "priority-v5.1",
            "feedback_timestamp": "2026-10-02T13:00:00Z",
        },
    ]
    with open(fb_file, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")
    return fb_file


# ===========================================================================
# A. Distribution Monitoring Tests
# ===========================================================================

class TestDistributionMonitoring:
    def test_distribution_returns_structure(self, monitor, mock_cache_db):
        db_path, user_id = mock_cache_db
        with patch("backend.app.core.phase51_monitor.DB_PATH", db_path):
            result = monitor.get_distribution(user_id)
            assert "total_messages" in result
            assert "counts" in result
            assert "percentages" in result
            assert "baseline" in result
            assert "drift_pp" in result
            assert "severity" in result
            assert result["total_messages"] == 100

    def test_distribution_priorities_present(self, monitor, mock_cache_db):
        db_path, user_id = mock_cache_db
        with patch("backend.app.core.phase51_monitor.DB_PATH", db_path):
            result = monitor.get_distribution(user_id)
            for p in ["P1", "P2", "P3", "P4"]:
                assert p in result["counts"]
                assert p in result["percentages"]
                assert p in result["drift_pp"]

    def test_distribution_drift_calculation(self, monitor, mock_cache_db):
        db_path, user_id = mock_cache_db
        with patch("backend.app.core.phase51_monitor.DB_PATH", db_path):
            result = monitor.get_distribution(user_id)
            for p in ["P1", "P2", "P3", "P4"]:
                expected_drift = round(result["percentages"][p] - V51_BASELINE[f"{p}_pct"], 2)
                assert result["drift_pp"][p] == expected_drift

    def test_distribution_time_windows(self, monitor, mock_cache_db):
        db_path, user_id = mock_cache_db
        with patch("backend.app.core.phase51_monitor.DB_PATH", db_path):
            for w in ["last_24h", "last_7d", "last_30d", "all"]:
                result = monitor.get_distribution(user_id, window=w)
                assert result["window"] == w
                assert result["total_messages"] >= 0

    def test_distribution_empty_user(self, monitor, mock_cache_db):
        db_path, _ = mock_cache_db
        with patch("backend.app.core.phase51_monitor.DB_PATH", db_path):
            result = monitor.get_distribution("nonexistent_user")
            assert result["total_messages"] == 0
            assert result["severity"] == "NORMAL"


# ===========================================================================
# B. Confidence Monitoring Tests
# ===========================================================================

class TestConfidenceMonitoring:
    def test_confidence_returns_structure(self, monitor, mock_cache_db):
        db_path, user_id = mock_cache_db
        with patch("backend.app.core.phase51_monitor.DB_PATH", db_path):
            result = monitor.get_confidence(user_id)
            assert "by_priority" in result
            assert "overall" in result
            assert "severity" in result
            assert "low_confidence_rate_pct" in result

    def test_confidence_per_priority_stats(self, monitor, mock_cache_db):
        db_path, user_id = mock_cache_db
        with patch("backend.app.core.phase51_monitor.DB_PATH", db_path):
            result = monitor.get_confidence(user_id)
            for p in ["P1", "P2", "P3", "P4"]:
                stats = result["by_priority"][p]
                assert "count" in stats
                assert "mean" in stats
                assert "median" in stats

    def test_confidence_note_present(self, monitor, mock_cache_db):
        db_path, user_id = mock_cache_db
        with patch("backend.app.core.phase51_monitor.DB_PATH", db_path):
            result = monitor.get_confidence(user_id)
            assert "model-output signal" in result["note"]


# ===========================================================================
# C. Feedback Monitoring Tests
# ===========================================================================

class TestFeedbackMonitoring:
    def test_feedback_returns_structure(self, monitor, mock_feedback):
        with patch("backend.app.core.phase51_monitor.FEEDBACK_FILE", mock_feedback):
            result = monitor.get_feedback("test_user_1")
            assert "total_feedback_events" in result
            assert "correction_matrix" in result
            assert "by_feedback_type" in result
            assert result["total_feedback_events"] == 3

    def test_feedback_user_isolation(self, monitor, mock_feedback):
        with patch("backend.app.core.phase51_monitor.FEEDBACK_FILE", mock_feedback):
            r1 = monitor.get_feedback("test_user_1")
            r2 = monitor.get_feedback("test_user_2")
            assert r1["total_feedback_events"] == 3
            assert r2["total_feedback_events"] == 1

    def test_feedback_correction_matrix_structure(self, monitor, mock_feedback):
        with patch("backend.app.core.phase51_monitor.FEEDBACK_FILE", mock_feedback):
            result = monitor.get_feedback("test_user_1")
            matrix = result["correction_matrix"]
            for p in ["P1", "P2", "P3", "P4"]:
                assert p in matrix
                for q in ["P1", "P2", "P3", "P4"]:
                    assert q in matrix[p]

    def test_feedback_correction_counts(self, monitor, mock_feedback):
        with patch("backend.app.core.phase51_monitor.FEEDBACK_FILE", mock_feedback):
            result = monitor.get_feedback("test_user_1")
            # P2 → P3 and P3 → P2 from test data
            assert result["correction_matrix"]["P2"]["P3"] == 1
            assert result["correction_matrix"]["P3"]["P2"] == 1

    def test_feedback_no_retraining_note(self, monitor, mock_feedback):
        with patch("backend.app.core.phase51_monitor.FEEDBACK_FILE", mock_feedback):
            result = monitor.get_feedback("test_user_1")
            assert "NOT automatically retrain" in result["note"]


# ===========================================================================
# D. P2/P3 Boundary Tests
# ===========================================================================

class TestP2P3Boundary:
    def test_boundary_returns_structure(self, monitor, mock_feedback, mock_cache_db):
        db_path, user_id = mock_cache_db
        with patch("backend.app.core.phase51_monitor.DB_PATH", db_path), \
             patch("backend.app.core.phase51_monitor.FEEDBACK_FILE", mock_feedback):
            result = monitor.get_p2_p3_boundary(user_id)
            assert "p2_to_p3_count" in result
            assert "p3_to_p2_count" in result
            assert "severity" in result

    def test_boundary_counts(self, monitor, mock_feedback, mock_cache_db):
        db_path, user_id = mock_cache_db
        with patch("backend.app.core.phase51_monitor.DB_PATH", db_path), \
             patch("backend.app.core.phase51_monitor.FEEDBACK_FILE", mock_feedback):
            result = monitor.get_p2_p3_boundary(user_id)
            assert result["boundary_total"] == 2


# ===========================================================================
# E. Safety Monitoring Tests
# ===========================================================================

class TestSafetyMonitoring:
    def test_safety_returns_structure(self, monitor, mock_cache_db, mock_feedback):
        db_path, user_id = mock_cache_db
        with patch("backend.app.core.phase51_monitor.DB_PATH", db_path), \
             patch("backend.app.core.phase51_monitor.FEEDBACK_FILE", mock_feedback):
            result = monitor.get_safety(user_id)
            assert "p1_count" in result
            assert "p1_retention_pct" in result
            assert "p1_downgrade_count" in result
            assert "severity" in result

    def test_safety_no_p1_downgrades(self, monitor, mock_cache_db, mock_feedback):
        """No P1 downgrades in test data for user 1."""
        db_path, user_id = mock_cache_db
        with patch("backend.app.core.phase51_monitor.DB_PATH", db_path), \
             patch("backend.app.core.phase51_monitor.FEEDBACK_FILE", mock_feedback):
            result = monitor.get_safety(user_id)
            assert result["p1_downgrade_count"] == 0
            assert result["severity"] == "NORMAL"


# ===========================================================================
# F. Action/Deadline Tests
# ===========================================================================

class TestActionDeadline:
    def test_action_deadline_structure(self, monitor, mock_cache_db):
        db_path, user_id = mock_cache_db
        with patch("backend.app.core.phase51_monitor.DB_PATH", db_path):
            result = monitor.get_action_deadline(user_id)
            assert "action_required" in result
            assert "deadline_detected" in result
            assert "deadline_status" in result
            assert "decoupling_note" in result

    def test_action_deadline_decoupling(self, monitor, mock_cache_db):
        db_path, user_id = mock_cache_db
        with patch("backend.app.core.phase51_monitor.DB_PATH", db_path):
            result = monitor.get_action_deadline(user_id)
            assert "P2 ≠ Action Required" in result["decoupling_note"]


# ===========================================================================
# G. Needs Attention Tests
# ===========================================================================

class TestNeedsAttention:
    def test_needs_attention_structure(self, monitor, mock_cache_db):
        db_path, user_id = mock_cache_db
        with patch("backend.app.core.phase51_monitor.DB_PATH", db_path):
            result = monitor.get_needs_attention(user_id)
            assert "needs_attention_count" in result
            assert "breakdown" in result
            assert "definition_note" in result

    def test_needs_attention_definition(self, monitor, mock_cache_db):
        db_path, user_id = mock_cache_db
        with patch("backend.app.core.phase51_monitor.DB_PATH", db_path):
            result = monitor.get_needs_attention(user_id)
            assert "NOT simply P1 + P2" in result["definition_note"]


# ===========================================================================
# H. Drift Tests
# ===========================================================================

class TestDrift:
    def test_drift_structure(self, monitor, mock_cache_db):
        db_path, user_id = mock_cache_db
        with patch("backend.app.core.phase51_monitor.DB_PATH", db_path):
            result = monitor.get_drift(user_id)
            assert "topic_distribution" in result
            assert "subject_length_stats" in result
            assert "top_sender_domains" in result

    def test_drift_sender_note(self, monitor, mock_cache_db):
        db_path, user_id = mock_cache_db
        with patch("backend.app.core.phase51_monitor.DB_PATH", db_path):
            result = monitor.get_drift(user_id)
            assert "NEVER used as a priority rule" in result["sender_domain_note"]


# ===========================================================================
# I. Cache/Error Tests
# ===========================================================================

class TestCacheErrors:
    def test_cache_errors_structure(self, monitor, mock_cache_db):
        db_path, user_id = mock_cache_db
        with patch("backend.app.core.phase51_monitor.DB_PATH", db_path):
            result = monitor.get_cache_errors(user_id)
            assert "total_cached_predictions" in result
            assert "by_model_version" in result
            assert "isolation_verified" in result

    def test_cache_isolation(self, monitor, mock_cache_db):
        db_path, user_id = mock_cache_db
        with patch("backend.app.core.phase51_monitor.DB_PATH", db_path):
            result = monitor.get_cache_errors(user_id)
            assert result["isolation_verified"] is True
            assert "NONE" in result["v41_v51_contamination_risk"]


# ===========================================================================
# J. Alerts Tests
# ===========================================================================

class TestAlerts:
    def test_alerts_structure(self, monitor, mock_cache_db, mock_feedback):
        db_path, user_id = mock_cache_db
        with patch("backend.app.core.phase51_monitor.DB_PATH", db_path), \
             patch("backend.app.core.phase51_monitor.FEEDBACK_FILE", mock_feedback):
            result = monitor.get_alerts(user_id)
            assert "alert_count" in result
            assert "alerts" in result
            assert "config" in result
            assert isinstance(result["alerts"], list)

    def test_alerts_no_auto_changes(self, monitor, mock_cache_db, mock_feedback):
        db_path, user_id = mock_cache_db
        with patch("backend.app.core.phase51_monitor.DB_PATH", db_path), \
             patch("backend.app.core.phase51_monitor.FEEDBACK_FILE", mock_feedback):
            result = monitor.get_alerts(user_id)
            assert "monitoring signals only" in result["note"]


# ===========================================================================
# K. v5.2 Readiness Tests
# ===========================================================================

class TestV52Readiness:
    def test_readiness_structure(self, monitor, mock_cache_db, mock_feedback):
        db_path, user_id = mock_cache_db
        with patch("backend.app.core.phase51_monitor.DB_PATH", db_path), \
             patch("backend.app.core.phase51_monitor.FEEDBACK_FILE", mock_feedback):
            result = monitor.get_v52_readiness(user_id)
            assert "state" in result
            assert "evidence" in result
            assert "criteria" in result
            assert "forbidden" in result
            assert "lifecycle" in result

    def test_readiness_forbidden_actions(self, monitor, mock_cache_db, mock_feedback):
        db_path, user_id = mock_cache_db
        with patch("backend.app.core.phase51_monitor.DB_PATH", db_path), \
             patch("backend.app.core.phase51_monitor.FEEDBACK_FILE", mock_feedback):
            result = monitor.get_v52_readiness(user_id)
            forbidden_str = " ".join(result["forbidden"])
            assert "NOT automatically create" in forbidden_str
            assert "NOT automatically train" in forbidden_str
            assert "NOT automatically promote" in forbidden_str

    def test_readiness_lifecycle_order(self, monitor, mock_cache_db, mock_feedback):
        db_path, user_id = mock_cache_db
        with patch("backend.app.core.phase51_monitor.DB_PATH", db_path), \
             patch("backend.app.core.phase51_monitor.FEEDBACK_FILE", mock_feedback):
            result = monitor.get_v52_readiness(user_id)
            lifecycle = result["lifecycle"]
            assert lifecycle[0] == "Production Monitoring"
            assert "Explicit Promotion" in lifecycle


# ===========================================================================
# L. Privacy Audit Tests
# ===========================================================================

class TestPrivacyAudit:
    def test_privacy_audit_clean(self, monitor, tmp_path):
        pred_dir = str(tmp_path / "pred_logs")
        os.makedirs(pred_dir)
        fb_file = str(tmp_path / "feedback.jsonl")
        clean_record = {"user_id": "u1", "predicted_priority": "P2"}
        with open(fb_file, "w") as f:
            f.write(json.dumps(clean_record) + "\n")

        with patch("backend.app.core.phase51_monitor.PREDICTION_LOG_DIR", pred_dir), \
             patch("backend.app.core.phase51_monitor.FEEDBACK_FILE", fb_file):
            result = monitor.privacy_audit()
            assert result["passed"] is True
            assert result["violation_count"] == 0

    def test_privacy_audit_detects_token(self, monitor, tmp_path):
        pred_dir = str(tmp_path / "pred_logs")
        os.makedirs(pred_dir)
        fb_file = str(tmp_path / "feedback.jsonl")
        bad_record = {"user_id": "u1", "access_token": "ya29.SENSITIVE"}
        with open(fb_file, "w") as f:
            f.write(json.dumps(bad_record) + "\n")

        with patch("backend.app.core.phase51_monitor.PREDICTION_LOG_DIR", pred_dir), \
             patch("backend.app.core.phase51_monitor.FEEDBACK_FILE", fb_file):
            result = monitor.privacy_audit()
            assert result["passed"] is False
            assert result["violation_count"] >= 1


# ===========================================================================
# M. Multi-User Isolation Tests
# ===========================================================================

class TestMultiUserIsolation:
    def test_isolation_verification(self, monitor, mock_cache_db, mock_feedback):
        db_path, _ = mock_cache_db
        with patch("backend.app.core.phase51_monitor.DB_PATH", db_path), \
             patch("backend.app.core.phase51_monitor.FEEDBACK_FILE", mock_feedback):
            result = monitor.verify_isolation(["test_user_1", "test_user_2"])
            assert result["isolation_passed"] is True
            assert result["per_user"]["test_user_1"]["message_count"] == 100
            assert result["per_user"]["test_user_2"]["message_count"] == 5


# ===========================================================================
# N. Alert Configuration Tests
# ===========================================================================

class TestAlertConfiguration:
    def test_config_has_required_keys(self):
        required = [
            "p1_downgrade_threshold",
            "distribution_shift_watch_pp",
            "distribution_shift_alert_pp",
            "confidence_drift_watch",
            "confidence_drift_alert",
            "latency_regression_watch_factor",
            "latency_regression_alert_factor",
            "error_rate_watch_pct",
            "threshold_documentation",
        ]
        for key in required:
            assert key in ALERT_CONFIG, f"Missing: {key}"

    def test_alert_thresholds_ordered(self):
        assert ALERT_CONFIG["distribution_shift_watch_pp"] < ALERT_CONFIG["distribution_shift_alert_pp"]
        assert ALERT_CONFIG["confidence_drift_watch"] < ALERT_CONFIG["confidence_drift_alert"]
        assert ALERT_CONFIG["latency_regression_watch_factor"] < ALERT_CONFIG["latency_regression_alert_factor"]
        assert ALERT_CONFIG["error_rate_watch_pct"] < ALERT_CONFIG["error_rate_alert_pct"]


# ===========================================================================
# O. Utility Function Tests
# ===========================================================================

class TestUtilities:
    def test_classify_severity_normal(self):
        assert _classify_severity(1.0, 5.0, 10.0) == "NORMAL"

    def test_classify_severity_watch(self):
        assert _classify_severity(6.0, 5.0, 10.0) == "WATCH"

    def test_classify_severity_alert(self):
        assert _classify_severity(11.0, 5.0, 10.0) == "ALERT"

    def test_classify_severity_negative(self):
        assert _classify_severity(-7.0, 5.0, 10.0) == "WATCH"
        assert _classify_severity(-12.0, 5.0, 10.0) == "ALERT"

    def test_parse_ts_valid(self):
        result = _parse_ts("2026-10-02T12:00:00Z")
        assert result is not None
        assert result.year == 2026

    def test_parse_ts_invalid(self):
        assert _parse_ts("not-a-date") is None
        assert _parse_ts("") is None
        assert _parse_ts(None) is None


# ===========================================================================
# P. Baseline Integrity Tests
# ===========================================================================

class TestBaselineIntegrity:
    def test_baseline_model_version(self):
        assert V51_BASELINE["model_version"] == "priority-v5.1"

    def test_baseline_latency_keys(self):
        lb = V51_BASELINE["latency_baseline"]
        assert "phase49_median_ms" in lb
        assert "phase50_median_ms" in lb
        assert lb["phase49_median_ms"] == 1.75
        assert lb["phase50_median_ms"] == 3.90

    def test_baseline_priorities_sum(self):
        total = (V51_BASELINE["P1_pct"] + V51_BASELINE["P2_pct"] +
                 V51_BASELINE["P3_pct"] + V51_BASELINE["P4_pct"])
        assert abs(total - 99.98) < 0.1  # Should be ~100%


# ===========================================================================
# Q. Full Summary Integration Test
# ===========================================================================

class TestFullSummary:
    def test_full_summary_structure(self, monitor, mock_cache_db, mock_feedback):
        db_path, user_id = mock_cache_db
        with patch("backend.app.core.phase51_monitor.DB_PATH", db_path), \
             patch("backend.app.core.phase51_monitor.FEEDBACK_FILE", mock_feedback):
            result = monitor.get_full_summary(user_id)
            required_keys = [
                "production_model", "rollback_model", "distribution",
                "confidence", "feedback", "p2_p3_boundary", "safety",
                "action_deadline", "needs_attention", "drift",
                "cache_errors", "alerts", "v52_readiness",
                "observation_phase", "retraining_status", "governance",
            ]
            for key in required_keys:
                assert key in result, f"Missing: {key}"

    def test_full_summary_retraining_status(self, monitor, mock_cache_db, mock_feedback):
        db_path, user_id = mock_cache_db
        with patch("backend.app.core.phase51_monitor.DB_PATH", db_path), \
             patch("backend.app.core.phase51_monitor.FEEDBACK_FILE", mock_feedback):
            result = monitor.get_full_summary(user_id)
            assert "NOT ACTIVE" in result["retraining_status"]
            assert "No automated retraining" in result["governance"]

    def test_full_summary_observation_phase(self, monitor, mock_cache_db, mock_feedback):
        db_path, user_id = mock_cache_db
        with patch("backend.app.core.phase51_monitor.DB_PATH", db_path), \
             patch("backend.app.core.phase51_monitor.FEEDBACK_FILE", mock_feedback):
            result = monitor.get_full_summary(user_id)
            assert result["observation_phase"] == "Phase 51"


# ===========================================================================
# R. Read-Only Invariant Tests
# ===========================================================================

class TestReadOnlyInvariants:
    """Verifies that monitoring functions do NOT mutate any data."""

    def test_distribution_does_not_mutate(self, monitor, mock_cache_db):
        db_path, user_id = mock_cache_db
        with patch("backend.app.core.phase51_monitor.DB_PATH", db_path):
            # Get initial state
            r1 = monitor.get_distribution(user_id)
            # Call again
            r2 = monitor.get_distribution(user_id)
            assert r1["total_messages"] == r2["total_messages"]
            assert r1["counts"] == r2["counts"]

    def test_feedback_does_not_mutate(self, monitor, mock_feedback):
        with patch("backend.app.core.phase51_monitor.FEEDBACK_FILE", mock_feedback):
            r1 = monitor.get_feedback("test_user_1")
            r2 = monitor.get_feedback("test_user_1")
            assert r1["total_feedback_events"] == r2["total_feedback_events"]

    def test_monitoring_opens_readonly_connection(self, monitor, mock_cache_db):
        """Verify that _get_ro_conn opens in read-only mode."""
        db_path, _ = mock_cache_db
        with patch("backend.app.core.phase51_monitor.DB_PATH", db_path):
            from backend.app.core.phase51_monitor import _get_ro_conn
            conn = _get_ro_conn()
            # Attempt to write should fail
            try:
                conn.execute("INSERT INTO user_email_cache (user_id, message_id, model_version, data_json) VALUES ('x', 'x', 'x', '{}')")
                conn.commit()
                assert False, "Write should have failed on read-only connection"
            except sqlite3.OperationalError:
                pass  # Expected
            finally:
                conn.close()
