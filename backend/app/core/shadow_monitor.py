"""
shadow_monitor.py — Phase 48 Read-Only Shadow Observability & Evidence Layer
=============================================================================
Provides strictly read-only analytical queries over the shadow inference database
for developer and admin monitoring endpoints.

Design Constraints:
  1. READ-ONLY: Never writes or mutates predictions or model registries.
  2. USER-ISOLATED: All queries are parameterized by user_id.
  3. PRIVACY COMPLIANT: Excludes raw email body, tokens, and credentials.
  4. OBSERVATIONAL: Does not declare alerts or trigger automated retraining.
"""

import os
import json
import sqlite3
import logging
from typing import Dict, Any, List, Optional
import numpy as np

from backend.app.core.config import BASE_DIR
from backend.app.ml.shadow_engine import (
    SHADOW_DB_PATH,
    _get_shadow_db_connection,
    get_shadow_version
)
from backend.app.ml.registry import model_registry

logger = logging.getLogger("mailmind.shadow_monitor")

FEEDBACK_FILE = os.path.join(BASE_DIR, "dataset", "feedback", "feedback.jsonl")


class ShadowMonitor:
    """
    Read-only aggregator for candidate shadow inference metrics and divergence audits.
    """

    def _get_read_conn(self) -> sqlite3.Connection:
        """Opens a read-only SQLite connection to the shadow database."""
        if not os.path.exists(SHADOW_DB_PATH):
            return _get_shadow_db_connection()
        conn = sqlite3.connect(f"file:{SHADOW_DB_PATH}?mode=ro", uri=True, timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def get_summary(self, user_id: str) -> Dict[str, Any]:
        """
        Master summary: total shadowed, agreement/divergence rates,
        critical P1 downgrades, latency, and primary transition counts.
        """
        shadow_ver = get_shadow_version()
        active_ver = model_registry.get_active_version()

        try:
            conn = self._get_read_conn()
            cur = conn.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN priority_changed = 0 THEN 1 ELSE 0 END) as agreement,
                    SUM(CASE WHEN priority_changed = 1 THEN 1 ELSE 0 END) as priority_diverged,
                    SUM(CASE WHEN prediction_diverged = 1 THEN 1 ELSE 0 END) as total_diverged,
                    SUM(CASE WHEN active_prediction = 'P1' AND shadow_prediction != 'P1' THEN 1 ELSE 0 END) as p1_downgrades,
                    SUM(CASE WHEN active_prediction = 'P2' AND shadow_prediction = 'P3' THEN 1 ELSE 0 END) as p2_to_p3,
                    SUM(CASE WHEN active_prediction = 'P3' AND shadow_prediction = 'P2' THEN 1 ELSE 0 END) as p3_to_p2,
                    SUM(CASE WHEN action_required_active != action_required_shadow THEN 1 ELSE 0 END) as action_diffs,
                    SUM(CASE WHEN deadline_detected_active != deadline_detected_shadow THEN 1 ELSE 0 END) as deadline_diffs,
                    SUM(CASE WHEN needs_attention_active != needs_attention_shadow THEN 1 ELSE 0 END) as needs_attention_diffs
                FROM shadow_predictions
                WHERE user_id = ? AND shadow_model_version = ?
            """, (user_id, shadow_ver))
            row = cur.fetchone()

            # Latency statistics
            lat_cur = conn.execute("""
                SELECT latency_active_ms, latency_shadow_ms
                FROM shadow_predictions
                WHERE user_id = ? AND shadow_model_version = ?
            """, (user_id, shadow_ver))
            lat_rows = lat_cur.fetchall()
            conn.close()

            total = row["total"] or 0
            agreement = row["agreement"] or 0
            p_diverged = row["priority_diverged"] or 0
            total_diverged = row["total_diverged"] or 0
            p1_downgrades = row["p1_downgrades"] or 0

            agreement_rate = (agreement / total * 100.0) if total > 0 else 100.0
            divergence_rate = (p_diverged / total * 100.0) if total > 0 else 0.0

            active_lats = [r["latency_active_ms"] for r in lat_rows if r["latency_active_ms"] is not None]
            shadow_lats = [r["latency_shadow_ms"] for r in lat_rows if r["latency_shadow_ms"] is not None]

            med_active = float(np.median(active_lats)) if active_lats else 0.0
            med_shadow = float(np.median(shadow_lats)) if shadow_lats else 0.0
            p95_shadow = float(np.percentile(shadow_lats, 95)) if shadow_lats else 0.0

            return {
                "active_model_version": active_ver,
                "shadow_model_version": shadow_ver,
                "total_shadowed": total,
                "agreement_count": agreement,
                "divergence_count": p_diverged,
                "total_diverged": total_diverged,
                "agreement_rate_pct": round(agreement_rate, 2),
                "divergence_rate_pct": round(divergence_rate, 2),
                "critical_p1_downgrades": p1_downgrades,
                "p2_to_p3_count": row["p2_to_p3"] or 0,
                "p3_to_p2_count": row["p3_to_p2"] or 0,
                "action_differences": row["action_diffs"] or 0,
                "deadline_differences": row["deadline_diffs"] or 0,
                "needs_attention_differences": row["needs_attention_diffs"] or 0,
                "latency_active_median_ms": round(med_active, 2),
                "latency_shadow_median_ms": round(med_shadow, 2),
                "latency_shadow_p95_ms": round(p95_shadow, 2),
                "status": "active_shadow_monitoring",
                "is_promoted": False
            }

        except Exception as exc:
            logger.error("get_summary failed: %s", exc)
            return {
                "active_model_version": active_ver,
                "shadow_model_version": shadow_ver,
                "total_shadowed": 0,
                "agreement_count": 0,
                "divergence_count": 0,
                "agreement_rate_pct": 100.0,
                "divergence_rate_pct": 0.0,
                "critical_p1_downgrades": 0,
                "error": str(exc)
            }

    def get_distribution(self, user_id: str) -> Dict[str, Any]:
        """
        Calculates P1/P2/P3/P4 distribution for both active and shadow models.
        """
        shadow_ver = get_shadow_version()
        active_ver = model_registry.get_active_version()

        try:
            conn = self._get_read_conn()
            cur = conn.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN active_prediction = 'P1' THEN 1 ELSE 0 END) as act_p1,
                    SUM(CASE WHEN active_prediction = 'P2' THEN 1 ELSE 0 END) as act_p2,
                    SUM(CASE WHEN active_prediction = 'P3' THEN 1 ELSE 0 END) as act_p3,
                    SUM(CASE WHEN active_prediction = 'P4' THEN 1 ELSE 0 END) as act_p4,
                    SUM(CASE WHEN shadow_prediction = 'P1' THEN 1 ELSE 0 END) as sh_p1,
                    SUM(CASE WHEN shadow_prediction = 'P2' THEN 1 ELSE 0 END) as sh_p2,
                    SUM(CASE WHEN shadow_prediction = 'P3' THEN 1 ELSE 0 END) as sh_p3,
                    SUM(CASE WHEN shadow_prediction = 'P4' THEN 1 ELSE 0 END) as sh_p4
                FROM shadow_predictions
                WHERE user_id = ? AND shadow_model_version = ?
            """, (user_id, shadow_ver))
            row = cur.fetchone()
            conn.close()

            total = row["total"] or 0
            if total == 0:
                return {
                    "total_messages": 0,
                    "active_model": active_ver,
                    "shadow_model": shadow_ver,
                    "active_distribution": {"P1": 0, "P2": 0, "P3": 0, "P4": 0},
                    "shadow_distribution": {"P1": 0, "P2": 0, "P3": 0, "P4": 0},
                    "deltas": {"P1": 0, "P2": 0, "P3": 0, "P4": 0}
                }

            act_counts = {
                "P1": row["act_p1"] or 0,
                "P2": row["act_p2"] or 0,
                "P3": row["act_p3"] or 0,
                "P4": row["act_p4"] or 0,
            }
            sh_counts = {
                "P1": row["sh_p1"] or 0,
                "P2": row["sh_p2"] or 0,
                "P3": row["sh_p3"] or 0,
                "P4": row["sh_p4"] or 0,
            }

            act_pct = {k: round(v / total * 100.0, 2) for k, v in act_counts.items()}
            sh_pct = {k: round(v / total * 100.0, 2) for k, v in sh_counts.items()}
            deltas = {k: round(sh_pct[k] - act_pct[k], 2) for k in act_pct}

            return {
                "total_messages": total,
                "active_model": active_ver,
                "shadow_model": shadow_ver,
                "active_counts": act_counts,
                "shadow_counts": sh_counts,
                "active_percentages": act_pct,
                "shadow_percentages": sh_pct,
                "percentage_deltas": deltas
            }

        except Exception as exc:
            logger.error("get_distribution failed: %s", exc)
            return {"error": str(exc)}

    def get_transitions(self, user_id: str) -> Dict[str, Any]:
        """
        Builds the complete 4x4 active -> shadow priority transition matrix,
        and isolates notable transitions.
        """
        shadow_ver = get_shadow_version()
        classes = ["P1", "P2", "P3", "P4"]
        matrix = {a: {s: 0 for s in classes} for a in classes}

        try:
            conn = self._get_read_conn()
            cur = conn.execute("""
                SELECT active_prediction, shadow_prediction, COUNT(*) as cnt
                FROM shadow_predictions
                WHERE user_id = ? AND shadow_model_version = ?
                GROUP BY active_prediction, shadow_prediction
            """, (user_id, shadow_ver))
            rows = cur.fetchall()
            conn.close()

            for r in rows:
                act = r["active_prediction"]
                sh = r["shadow_prediction"]
                if act in matrix and sh in matrix[act]:
                    matrix[act][sh] = r["cnt"]

            notable = {
                "p1_to_p2": matrix["P1"]["P2"],
                "p1_to_p3": matrix["P1"]["P3"],
                "p1_to_p4": matrix["P1"]["P4"],
                "p2_to_p3": matrix["P2"]["P3"],
                "p2_to_p4": matrix["P2"]["P4"],
                "p3_to_p2": matrix["P3"]["P2"],
                "p4_to_p2": matrix["P4"]["P2"],
                "p4_to_p1": matrix["P4"]["P1"],
                "p3_to_p1": matrix["P3"]["P1"],
            }

            return {
                "active_model": model_registry.get_active_version(),
                "shadow_model": shadow_ver,
                "transition_matrix": matrix,
                "notable_transitions": notable,
                "critical_p1_downgrades": notable["p1_to_p2"] + notable["p1_to_p3"] + notable["p1_to_p4"]
            }

        except Exception as exc:
            logger.error("get_transitions failed: %s", exc)
            return {"error": str(exc), "transition_matrix": matrix}

    def get_divergence_records(self, user_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Retrieves top diverged prediction records for deep inspection.
        Never includes raw body.
        """
        shadow_ver = get_shadow_version()
        try:
            conn = self._get_read_conn()
            cur = conn.execute("""
                SELECT
                    message_id, thread_id, timestamp,
                    active_prediction, shadow_prediction,
                    active_confidence, shadow_confidence,
                    priority_changed,
                    action_required_active, action_required_shadow,
                    deadline_detected_active, deadline_detected_shadow,
                    deadline_status_active, deadline_status_shadow,
                    needs_attention_active, needs_attention_shadow,
                    safety_category
                FROM shadow_predictions
                WHERE user_id = ? AND shadow_model_version = ? AND prediction_diverged = 1
                ORDER BY timestamp DESC
                LIMIT ?
            """, (user_id, shadow_ver, limit))
            rows = [dict(r) for r in cur.fetchall()]
            conn.close()
            return rows
        except Exception as exc:
            logger.error("get_divergence_records failed: %s", exc)
            return []

    def get_safety_audit(self, user_id: str) -> Dict[str, Any]:
        """
        Surfaces high-risk safety categories and produces explicit audit table records.
        Critical check: Zero active P1 safety messages may silently become P2/P3/P4.
        """
        shadow_ver = get_shadow_version()
        try:
            conn = self._get_read_conn()
            # Category distribution
            cur = conn.execute("""
                SELECT
                    safety_category,
                    COUNT(*) as total,
                    SUM(CASE WHEN active_prediction = shadow_prediction THEN 1 ELSE 0 END) as agreed,
                    SUM(CASE WHEN active_prediction != shadow_prediction THEN 1 ELSE 0 END) as diverged,
                    SUM(CASE WHEN active_prediction = 'P1' AND shadow_prediction != 'P1' THEN 1 ELSE 0 END) as p1_downgrades
                FROM shadow_predictions
                WHERE user_id = ? AND shadow_model_version = ? AND safety_category IS NOT NULL
                GROUP BY safety_category
            """, (user_id, shadow_ver))
            categories = [dict(r) for r in cur.fetchall()]

            # Specific P1 downgrade inspection
            p1_cur = conn.execute("""
                SELECT
                    message_id, safety_category,
                    active_prediction, shadow_prediction,
                    active_confidence, shadow_confidence,
                    action_required_active, action_required_shadow,
                    deadline_status_active, deadline_status_shadow
                FROM shadow_predictions
                WHERE user_id = ? AND shadow_model_version = ?
                  AND active_prediction = 'P1' AND shadow_prediction != 'P1'
                LIMIT 50
            """, (user_id, shadow_ver))
            downgrades = [dict(r) for r in p1_cur.fetchall()]

            # Audit table sample (known safety categories)
            audit_cur = conn.execute("""
                SELECT
                    safety_category as category,
                    message_id,
                    active_prediction, shadow_prediction,
                    action_required_active, action_required_shadow,
                    deadline_detected_active, deadline_detected_shadow,
                    CASE
                        WHEN active_prediction = shadow_prediction THEN 'AGREED'
                        WHEN active_prediction = 'P1' AND shadow_prediction != 'P1' THEN 'CRITICAL_DOWNGRADE'
                        WHEN active_prediction = 'P2' AND shadow_prediction = 'P3' THEN 'DE_ESCALATED'
                        WHEN active_prediction = 'P3' AND shadow_prediction = 'P2' THEN 'ESCALATED'
                        ELSE 'DIVERGED'
                    END as result,
                    CASE
                        WHEN active_prediction = shadow_prediction THEN 'Exact priority agreement'
                        WHEN active_prediction = 'P1' AND shadow_prediction != 'P1' THEN 'High severity downgrade'
                        WHEN active_prediction = 'P2' AND shadow_prediction = 'P3' THEN 'Routine confirmation de-escalation'
                        WHEN active_prediction = 'P3' AND shadow_prediction = 'P2' THEN 'Actionable escalation'
                        ELSE 'Boundary divergence'
                    END as reason
                FROM shadow_predictions
                WHERE user_id = ? AND shadow_model_version = ? AND safety_category IS NOT NULL
                ORDER BY CASE WHEN active_prediction = 'P1' AND shadow_prediction != 'P1' THEN 0 ELSE 1 END, timestamp DESC
                LIMIT 50
            """, (user_id, shadow_ver))
            audit_table = [dict(r) for r in audit_cur.fetchall()]

            conn.close()

            return {
                "categories": categories,
                "total_safety_messages": sum(c["total"] for c in categories),
                "total_p1_downgrades": sum(c["p1_downgrades"] for c in categories),
                "downgrade_records": downgrades,
                "audit_table": audit_table
            }

        except Exception as exc:
            logger.error("get_safety_audit failed: %s", exc)
            return {"error": str(exc), "categories": [], "total_p1_downgrades": 0, "audit_table": []}

    def get_performance(self, user_id: str) -> Dict[str, Any]:
        """
        Returns latency distribution and throughput statistics for active vs shadow model.
        """
        shadow_ver = get_shadow_version()
        try:
            conn = self._get_read_conn()
            cur = conn.execute("""
                SELECT latency_active_ms, latency_shadow_ms
                FROM shadow_predictions
                WHERE user_id = ? AND shadow_model_version = ?
            """, (user_id, shadow_ver))
            rows = cur.fetchall()
            conn.close()

            if not rows:
                return {
                    "total_samples": 0,
                    "active_latency_ms": {"median": 0, "p95": 0, "mean": 0},
                    "shadow_latency_ms": {"median": 0, "p95": 0, "mean": 0},
                    "overhead_ms": 0
                }

            act_lats = [r["latency_active_ms"] for r in rows if r["latency_active_ms"] is not None]
            sh_lats = [r["latency_shadow_ms"] for r in rows if r["latency_shadow_ms"] is not None]

            med_act = float(np.median(act_lats)) if act_lats else 0.0
            p95_act = float(np.percentile(act_lats, 95)) if act_lats else 0.0
            mean_act = float(np.mean(act_lats)) if act_lats else 0.0

            med_sh = float(np.median(sh_lats)) if sh_lats else 0.0
            p95_sh = float(np.percentile(sh_lats, 95)) if sh_lats else 0.0
            mean_sh = float(np.mean(sh_lats)) if sh_lats else 0.0

            return {
                "total_samples": len(rows),
                "active_latency_ms": {
                    "median": round(med_act, 2),
                    "p95": round(p95_act, 2),
                    "mean": round(mean_act, 2)
                },
                "shadow_latency_ms": {
                    "median": round(med_sh, 2),
                    "p95": round(p95_sh, 2),
                    "mean": round(mean_sh, 2)
                },
                "overhead_median_ms": round(max(0.0, med_sh - med_act), 2)
            }

        except Exception as exc:
            logger.error("get_performance failed: %s", exc)
            return {"error": str(exc)}

    def get_feedback_correlation(self, user_id: str) -> Dict[str, Any]:
        """
        Correlates user feedback records with shadow predictions to observe
        how the candidate performed against human corrections on active model.
        """
        shadow_ver = get_shadow_version()
        if not os.path.exists(FEEDBACK_FILE):
            return {"total_correlations": 0, "correlations": []}

        feedback_map = {}
        try:
            with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            fb = json.loads(line)
                            mid = fb.get("message_id") or fb.get("email_id")
                            if mid and fb.get("user_id") == user_id:
                                feedback_map[mid] = fb
                        except json.JSONDecodeError:
                            continue
        except Exception as exc:
            logger.warning("Error reading feedback file: %s", exc)
            return {"total_correlations": 0, "correlations": []}

        if not feedback_map:
            return {"total_correlations": 0, "correlations": []}

        correlations = []
        try:
            conn = self._get_read_conn()
            placeholders = ",".join("?" for _ in feedback_map.keys())
            cur = conn.execute(
                f"""
                SELECT message_id, active_prediction, shadow_prediction, active_confidence, shadow_confidence
                FROM shadow_predictions
                WHERE user_id = ? AND shadow_model_version = ? AND message_id IN ({placeholders})
                """,
                [user_id, shadow_ver] + list(feedback_map.keys())
            )
            rows = cur.fetchall()
            conn.close()

            for r in rows:
                mid = r["message_id"]
                fb = feedback_map[mid]
                corrected = fb.get("corrected_priority") or fb.get("user_priority")
                correlations.append({
                    "message_id": mid,
                    "active_prediction": r["active_prediction"],
                    "shadow_prediction": r["shadow_prediction"],
                    "corrected_priority": corrected,
                    "candidate_matches_correction": (r["shadow_prediction"] == corrected),
                    "active_matches_correction": (r["active_prediction"] == corrected),
                })

        except Exception as exc:
            logger.error("Error building feedback correlation: %s", exc)

        return {
            "total_correlations": len(correlations),
            "candidate_matched_user": sum(1 for c in correlations if c["candidate_matches_correction"]),
            "active_matched_user": sum(1 for c in correlations if c["active_matches_correction"]),
            "correlations": correlations
        }


# Global singleton instance
shadow_monitor = ShadowMonitor()
