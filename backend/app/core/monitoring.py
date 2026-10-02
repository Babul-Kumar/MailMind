"""
monitoring.py — Phase 43 Production Monitoring Layer
======================================================
Read-only observability over the live production system.

This module queries:
  - user_email_cache SQLite DB  (priority/confidence/action/deadline columns)
  - dataset/feedback/feedback.jsonl  (user corrections)

It does NOT:
  - Train or retrain any model.
  - Write to any model artifact or registry.
  - Mix data across users.
  - Store raw email body or OAuth credentials.
  - Declare alerts or trigger automatic changes.

All reports are user-scoped. Aggregates are computed via SQL for performance.
"""

import os
import json
import sqlite3
import logging
import statistics
from typing import Dict, Any, List, Optional

from backend.app.core.config import BASE_DIR
from backend.app.core.cache import user_email_cache, DB_PATH

logger = logging.getLogger("mailmind.monitoring")

FEEDBACK_DIR = os.path.join(BASE_DIR, "dataset", "feedback")
FEEDBACK_FILE = os.path.join(FEEDBACK_DIR, "feedback.jsonl")

# ---------------------------------------------------------------------------
# Phase 42 production baseline (V4.1 promotion snapshot).
# Used as a reference for drift indicators — NOT as hard alert thresholds.
# ---------------------------------------------------------------------------
V41_BASELINE = {
    "model_version": "priority-v4.1",
    "dataset_version": "dataset-v4.1",
    "promoted_at": "2026-10-02T14:23:34Z",
    "P1_pct": 1.36,   # 235 / 17322
    "P2_pct": 85.47,  # 14806 / 17322
    "P3_pct": 1.03,   # 179 / 17322
    "P4_pct": 12.12,  # 2099 / 17322
    "action_required_count": 521,
    "needs_attention_count": 644,
    "total_messages": 17322,
}


def _get_conn() -> sqlite3.Connection:
    """Opens a read-only connection to the cache DB for monitoring queries."""
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=10.0)
    conn.row_factory = sqlite3.Row
    return conn


class ProductionMonitor:
    """
    Provides read-only monitoring reports for a given authenticated user.
    All methods accept user_id to enforce strict user isolation.
    """

    # ------------------------------------------------------------------
    # 1. Distribution report
    # ------------------------------------------------------------------
    def get_distribution_report(self, user_id: str) -> Dict[str, Any]:
        """
        Returns the current P1/P2/P3/P4 distribution for the user's cached
        mailbox, along with drift indicators vs. the V4.1 Phase 42 baseline.

        Drift is reported as absolute percentage-point delta. It is an
        observation, NOT a diagnosis of model degradation.
        """
        try:
            conn = _get_conn()
            cur = conn.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN predicted_priority = 'P1' THEN 1 ELSE 0 END) as p1,
                    SUM(CASE WHEN predicted_priority = 'P2' THEN 1 ELSE 0 END) as p2,
                    SUM(CASE WHEN predicted_priority = 'P3' THEN 1 ELSE 0 END) as p3,
                    SUM(CASE WHEN predicted_priority = 'P4' THEN 1 ELSE 0 END) as p4,
                    SUM(CASE WHEN action_required = 1 THEN 1 ELSE 0 END) as action_req,
                    SUM(CASE WHEN needs_attention = 1 THEN 1 ELSE 0 END) as needs_att,
                    SUM(CASE WHEN deadline_detected = 1 THEN 1 ELSE 0 END) as deadline_det
                FROM user_email_cache
                WHERE user_id = ? AND is_stale = 0
            """, (user_id,))
            row = cur.fetchone()
            conn.close()
        except Exception as exc:
            logger.warning("monitoring.distribution: DB read failed: %s", exc)
            return self._empty_distribution()

        total = row["total"] or 0
        if total == 0:
            return self._empty_distribution()

        p1, p2, p3, p4 = row["p1"] or 0, row["p2"] or 0, row["p3"] or 0, row["p4"] or 0

        def pct(n):
            return round(n / total * 100, 2) if total > 0 else 0.0

        current = {
            "P1_pct": pct(p1), "P2_pct": pct(p2),
            "P3_pct": pct(p3), "P4_pct": pct(p4),
        }

        drift = {
            k: round(current[k] - V41_BASELINE[k], 2)
            for k in ["P1_pct", "P2_pct", "P3_pct", "P4_pct"]
        }

        return {
            "total_messages": total,
            "counts": {"P1": p1, "P2": p2, "P3": p3, "P4": p4},
            "percentages": current,
            "action_required_count": row["action_req"] or 0,
            "needs_attention_count": row["needs_att"] or 0,
            "deadline_detected_count": row["deadline_det"] or 0,
            "baseline": {k: V41_BASELINE[k] for k in ["P1_pct", "P2_pct", "P3_pct", "P4_pct"]},
            "drift_vs_baseline_pct_pts": drift,
            "drift_note": (
                "Drift values are observations only. "
                "Do not interpret as model degradation without multi-signal confirmation."
            ),
        }

    def _empty_distribution(self) -> Dict[str, Any]:
        return {
            "total_messages": 0,
            "counts": {"P1": 0, "P2": 0, "P3": 0, "P4": 0},
            "percentages": {"P1_pct": 0.0, "P2_pct": 0.0, "P3_pct": 0.0, "P4_pct": 0.0},
            "action_required_count": 0,
            "needs_attention_count": 0,
            "deadline_detected_count": 0,
            "baseline": {k: V41_BASELINE[k] for k in ["P1_pct", "P2_pct", "P3_pct", "P4_pct"]},
            "drift_vs_baseline_pct_pts": {"P1_pct": 0.0, "P2_pct": 0.0, "P3_pct": 0.0, "P4_pct": 0.0},
            "drift_note": "No data yet.",
        }

    # ------------------------------------------------------------------
    # 2. Confidence distribution report
    # ------------------------------------------------------------------
    def get_confidence_report(self, user_id: str) -> Dict[str, Any]:
        """
        Returns per-priority confidence distribution statistics:
        count, mean, median, p10, p25, p75, p90.

        Low-confidence P1 and low-confidence P2 are flagged as review candidates.
        High-confidence P3/P4 are flagged as review candidates (potential over-de-escalation).
        """
        try:
            conn = _get_conn()
            cur = conn.execute("""
                SELECT predicted_priority, confidence
                FROM user_email_cache
                WHERE user_id = ? AND is_stale = 0
                ORDER BY predicted_priority, confidence
            """, (user_id,))
            rows = cur.fetchall()
            conn.close()
        except Exception as exc:
            logger.warning("monitoring.confidence: DB read failed: %s", exc)
            return {"by_priority": {}, "review_candidates": {}}

        buckets: Dict[str, List[float]] = {"P1": [], "P2": [], "P3": [], "P4": []}
        for row in rows:
            p = row["predicted_priority"]
            c = row["confidence"]
            if p in buckets and c is not None:
                buckets[p].append(float(c))

        def percentile(data: List[float], pct: float) -> float:
            if not data:
                return 0.0
            sorted_d = sorted(data)
            k = (len(sorted_d) - 1) * pct / 100
            lo, hi = int(k), min(int(k) + 1, len(sorted_d) - 1)
            return round(sorted_d[lo] + (sorted_d[hi] - sorted_d[lo]) * (k - lo), 4)

        def stats(data: List[float]) -> Dict[str, Any]:
            if not data:
                return {"count": 0, "mean": 0.0, "median": 0.0,
                        "p10": 0.0, "p25": 0.0, "p75": 0.0, "p90": 0.0}
            return {
                "count": len(data),
                "mean": round(statistics.mean(data), 4),
                "median": round(statistics.median(data), 4),
                "p10": percentile(data, 10),
                "p25": percentile(data, 25),
                "p75": percentile(data, 75),
                "p90": percentile(data, 90),
            }

        by_priority = {p: stats(buckets[p]) for p in ["P1", "P2", "P3", "P4"]}

        # Review candidate flags (informational only)
        LOW_CONF_THRESHOLD = 0.40
        HIGH_CONF_THRESHOLD = 0.70
        p1_low = sum(1 for c in buckets["P1"] if c < LOW_CONF_THRESHOLD)
        p2_low = sum(1 for c in buckets["P2"] if c < LOW_CONF_THRESHOLD)
        p3_high = sum(1 for c in buckets["P3"] if c >= HIGH_CONF_THRESHOLD)
        p4_high = sum(1 for c in buckets["P4"] if c >= HIGH_CONF_THRESHOLD)

        return {
            "by_priority": by_priority,
            "review_candidates": {
                "low_confidence_P1": p1_low,
                "low_confidence_P2": p2_low,
                "high_confidence_P3": p3_high,
                "high_confidence_P4": p4_high,
                "note": (
                    "These are review suggestions, not corrections. "
                    "Confidence does not equal correctness."
                ),
            },
        }

    # ------------------------------------------------------------------
    # 3. Safety event monitoring
    # ------------------------------------------------------------------
    def get_safety_events(self, user_id: str) -> Dict[str, Any]:
        """
        Surfaces potentially safety-critical prediction patterns:
        - OTP/security emails predicted below P1
        - Payment failure emails predicted as non-actionable
        - Active deadline emails predicted as non-actionable

        These are surface-only reports. No automatic prediction changes.
        Source: feedback.jsonl entries flagged by user corrections.
        """
        feedback = self._load_user_feedback(user_id)

        otp_below_p1: List[Dict] = []
        security_below_p2: List[Dict] = []
        payment_non_actionable: List[Dict] = []
        deadline_non_actionable: List[Dict] = []

        for rec in feedback:
            ftype = rec.get("feedback_type", "")
            orig_p = rec.get("predicted_priority", "")
            corr_p = rec.get("corrected_priority", "")
            topic = rec.get("original_topic", "")

            # OTP predicted below P1 and corrected to P1
            if (topic in ("otp", "security", "authentication")
                    and orig_p != "P1" and corr_p == "P1"):
                otp_below_p1.append({
                    "message_id": rec.get("message_id"),
                    "original_priority": orig_p,
                    "corrected_priority": corr_p,
                    "topic": topic,
                    "timestamp": rec.get("feedback_timestamp"),
                })

            # Security below P2
            if (topic in ("security", "authentication", "account")
                    and orig_p not in ("P1", "P2") and corr_p in ("P1", "P2")):
                security_below_p2.append({
                    "message_id": rec.get("message_id"),
                    "original_priority": orig_p,
                    "corrected_priority": corr_p,
                    "topic": topic,
                    "timestamp": rec.get("feedback_timestamp"),
                })

            # Payment flagged as non-actionable
            if (ftype == "action_required_wrong"
                    and topic == "payment"
                    and not rec.get("predicted_action_required")
                    and rec.get("corrected_action_required")):
                payment_non_actionable.append({
                    "message_id": rec.get("message_id"),
                    "timestamp": rec.get("feedback_timestamp"),
                })

            # Deadline flagged as non-actionable
            if (ftype == "deadline_wrong"
                    and rec.get("deadline_correction") is True):
                deadline_non_actionable.append({
                    "message_id": rec.get("message_id"),
                    "timestamp": rec.get("feedback_timestamp"),
                })

        return {
            "otp_below_p1": otp_below_p1,
            "security_below_p2": security_below_p2,
            "payment_non_actionable": payment_non_actionable,
            "deadline_flagged_non_actionable": deadline_non_actionable,
            "total_safety_events": (
                len(otp_below_p1) + len(security_below_p2)
                + len(payment_non_actionable) + len(deadline_non_actionable)
            ),
            "note": (
                "Safety events are user-reported corrections requiring human review. "
                "Do not automatically change model predictions based on this list."
            ),
        }

    # ------------------------------------------------------------------
    # 4. Feedback / correction rate statistics
    # ------------------------------------------------------------------
    def get_feedback_stats(self, user_id: str) -> Dict[str, Any]:
        """
        Computes correction rates from the user's feedback records:
        - Overall correction rate
        - Correction rate by original priority
        - P→P correction matrix
        """
        feedback = self._load_user_feedback(user_id)
        if not feedback:
            return self._empty_feedback_stats()

        total = len(feedback)
        priority_corrections: Dict[str, int] = {"P1": 0, "P2": 0, "P3": 0, "P4": 0}
        priority_totals: Dict[str, int] = {"P1": 0, "P2": 0, "P3": 0, "P4": 0}
        matrix: Dict[str, Dict[str, int]] = {
            p: {"P1": 0, "P2": 0, "P3": 0, "P4": 0}
            for p in ["P1", "P2", "P3", "P4"]
        }

        for rec in feedback:
            orig = rec.get("predicted_priority", "")
            corr = rec.get("corrected_priority")
            ftype = rec.get("feedback_type", "priority_wrong")

            if orig in priority_totals:
                priority_totals[orig] += 1

            # Only count as a correction if corrected_priority is set and differs
            if corr and corr != orig and ftype == "priority_wrong":
                if orig in priority_corrections:
                    priority_corrections[orig] += 1
                if orig in matrix and corr in matrix[orig]:
                    matrix[orig][corr] += 1

        total_priority_corrections = sum(priority_corrections.values())

        def rate(n, d):
            return round(n / d * 100, 2) if d > 0 else 0.0

        correction_rate_by_priority = {
            p: rate(priority_corrections[p], priority_totals[p])
            for p in ["P1", "P2", "P3", "P4"]
        }

        # Notable escalations/de-escalations
        p2_to_lower = matrix["P2"]["P3"] + matrix["P2"]["P4"]
        lower_to_p2 = matrix["P3"]["P2"] + matrix["P4"]["P2"]
        p1_to_lower = matrix["P1"]["P2"] + matrix["P1"]["P3"] + matrix["P1"]["P4"]
        lower_to_p1 = matrix["P2"]["P1"] + matrix["P3"]["P1"] + matrix["P4"]["P1"]

        return {
            "total_feedback": total,
            "total_priority_corrections": total_priority_corrections,
            "overall_correction_rate_pct": rate(total_priority_corrections, total),
            "correction_rate_by_priority": correction_rate_by_priority,
            "correction_matrix": matrix,
            "notable": {
                "P2_to_P3_or_P4": p2_to_lower,
                "P3_or_P4_to_P2": lower_to_p2,
                "P1_to_lower": p1_to_lower,
                "lower_to_P1": lower_to_p1,
                "safety_critical_lower_to_P1_note": (
                    "lower_to_P1 corrections indicate the model may be missing "
                    "critical emails. Treat as safety-critical evidence for dataset-v5."
                ),
            },
        }

    def _empty_feedback_stats(self) -> Dict[str, Any]:
        return {
            "total_feedback": 0,
            "total_priority_corrections": 0,
            "overall_correction_rate_pct": 0.0,
            "correction_rate_by_priority": {"P1": 0.0, "P2": 0.0, "P3": 0.0, "P4": 0.0},
            "correction_matrix": {
                p: {"P1": 0, "P2": 0, "P3": 0, "P4": 0} for p in ["P1", "P2", "P3", "P4"]
            },
            "notable": {
                "P2_to_P3_or_P4": 0, "P3_or_P4_to_P2": 0,
                "P1_to_lower": 0, "lower_to_P1": 0,
                "safety_critical_lower_to_P1_note": (
                    "No feedback yet. Submit corrections via POST /api/feedback."
                ),
            },
        }

    # ------------------------------------------------------------------
    # 5. Drift indicators
    # ------------------------------------------------------------------
    def get_drift_indicators(self, user_id: str) -> Dict[str, Any]:
        """
        Compares current production distribution against the V4.1 baseline.
        Reports observed changes without interpretation as model degradation.
        """
        dist = self.get_distribution_report(user_id)
        drift = dist.get("drift_vs_baseline_pct_pts", {})
        current_pcts = dist.get("percentages", {})

        flags: List[str] = []
        # Flag large shifts for awareness (±10 pp is a notable shift for manual review)
        for key, delta in drift.items():
            if abs(delta) >= 10.0:
                flags.append(
                    f"{key}: {delta:+.2f} pp vs baseline "
                    f"(current {current_pcts.get(key, 0):.2f}%)"
                )

        return {
            "distribution_drift": drift,
            "notable_shifts": flags,
            "baseline_reference": "Phase 42 V4.1 promotion snapshot",
            "interpretation_note": (
                "Distribution shifts may reflect changes in incoming email patterns, "
                "not model degradation. Do NOT declare model drift from a single metric."
            ),
        }

    # ------------------------------------------------------------------
    # 6. Dataset-v5 readiness
    # ------------------------------------------------------------------
    def get_v5_readiness(self, user_id: str) -> Dict[str, Any]:
        """
        Evaluates readiness criteria for launching a dataset-v5 curation effort.
        These are informational — they do not trigger automatic retraining.
        """
        feedback = self._load_user_feedback(user_id)
        stats = self.get_feedback_stats(user_id)
        dist = self.get_distribution_report(user_id)

        total_fb = stats["total_feedback"]
        priority_corrections = stats["total_priority_corrections"]
        correction_rate = stats["overall_correction_rate_pct"]
        lower_to_p1 = stats["notable"]["lower_to_P1"]
        p2_to_lower = stats["notable"]["P2_to_P3_or_P4"]
        lower_to_p2 = stats["notable"]["P3_or_P4_to_P2"]

        # Readiness criteria (all informational)
        criteria = {
            "minimum_feedback_volume": {
                "target": 50,
                "current": total_fb,
                "met": total_fb >= 50,
            },
            "minimum_priority_corrections": {
                "target": 20,
                "current": priority_corrections,
                "met": priority_corrections >= 20,
            },
            "safety_critical_examples": {
                "target": "any lower→P1 corrections",
                "current": lower_to_p1,
                "note": "Include all lower→P1 corrections in v5 regardless of volume.",
            },
            "p2_boundary_examples": {
                "target": "≥10 examples per direction",
                "P2_to_lower": p2_to_lower,
                "lower_to_P2": lower_to_p2,
                "met": p2_to_lower >= 10 and lower_to_p2 >= 10,
            },
            "human_adjudication_required": {
                "note": (
                    "All feedback must pass human review before inclusion in dataset-v5. "
                    "No automatic promotion from feedback to training data."
                )
            },
        }

        gates_met = sum(
            1 for k, v in criteria.items()
            if isinstance(v, dict) and v.get("met") is True
        )
        total_gates = 3  # feedback_volume, priority_corrections, p2_boundary

        return {
            "dataset_v5_readiness": criteria,
            "gates_met": gates_met,
            "total_gates": total_gates,
            "ready_to_curate": gates_met >= total_gates,
            "pipeline": [
                "Production prediction",
                "User correction → POST /api/feedback",
                "Feedback store (feedback.jsonl)",
                "Review queue (pending_review status)",
                "Human adjudication",
                "dataset-v5 candidate examples",
                "Offline training",
                "Candidate model",
                "Holdout evaluation",
                "Promotion gate",
            ],
            "forbidden": "Production prediction → automatic training (NEVER)",
        }

    # ------------------------------------------------------------------
    # 7. Full monitoring summary
    # ------------------------------------------------------------------
    def get_summary(self, user_id: str) -> Dict[str, Any]:
        """
        Master summary for the /api/monitoring/summary endpoint.
        Combines model state, distribution, feedback counts, and drift.
        """
        from backend.app.ml.registry import model_registry

        active_version = model_registry.get_active_version()
        meta = model_registry.get_active_metadata()

        dist = self.get_distribution_report(user_id)
        fb_stats = self.get_feedback_stats(user_id)

        return {
            "production_model": {
                "model_version": active_version,
                "dataset_version": meta.get("dataset_version", ""),
                "status": meta.get("status", ""),
                "promoted_at": meta.get("promoted_at", ""),
                "artifact_sha256": meta.get("artifact_sha256", ""),
            },
            "rollback_model": {
                "model_version": "priority-v3",
                "status": "retired (rollback-ready)",
                "artifact_sha256": "fa69e6a5cfafb8b24c5941dbb8fb08a208addfc4f39e38fa47df0a7cd7040b56",
            },
            "mailbox_distribution": {
                "total_messages": dist["total_messages"],
                "P1_pct": dist["percentages"].get("P1_pct", 0.0),
                "P2_pct": dist["percentages"].get("P2_pct", 0.0),
                "P3_pct": dist["percentages"].get("P3_pct", 0.0),
                "P4_pct": dist["percentages"].get("P4_pct", 0.0),
                "action_required_count": dist["action_required_count"],
                "needs_attention_count": dist["needs_attention_count"],
            },
            "feedback": {
                "total_feedback": fb_stats["total_feedback"],
                "correction_rate_pct": fb_stats["overall_correction_rate_pct"],
            },
            "drift_vs_baseline": dist.get("drift_vs_baseline_pct_pts", {}),
            "observation_phase": "Phase 43",
            "retraining_status": "NOT ACTIVE — observation only",
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _load_user_feedback(self, user_id: str) -> List[Dict[str, Any]]:
        """Loads all feedback records for the given user_id. User-scoped."""
        if not os.path.exists(FEEDBACK_FILE):
            return []
        records: List[Dict[str, Any]] = []
        try:
            with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                        if rec.get("user_id") == user_id:
                            records.append(rec)
                    except Exception:
                        pass
        except Exception as exc:
            logger.warning("monitoring: failed to load feedback: %s", exc)
        return records


# Global singleton
production_monitor = ProductionMonitor()
