"""
routes_monitoring.py — Phase 43 ML Monitoring API
===================================================
Developer/admin-facing observability endpoints for production model behavior.

All endpoints:
  - Require a valid session (user authentication).
  - Are strictly user-scoped (monitoring data is computed per user_id).
  - Are READ-ONLY — no model changes, no retraining, no registry mutations.
  - Exclude OAuth tokens, credentials, and raw email body from all responses.

This router is separate from the user-facing email dashboard endpoints.
"""
import logging
from fastapi import APIRouter, HTTPException, Request

from backend.app.core.session import get_session_from_request
from backend.app.core.monitoring import production_monitor
from backend.app.core.prediction_log import prediction_log_stats
from backend.app.core.feedback import feedback_manager
from backend.app.ml.registry import model_registry

logger = logging.getLogger("mailmind.monitoring_api")
router = APIRouter(tags=["Monitoring"])


def _require_session(request: Request):
    """Shared auth guard for all monitoring endpoints."""
    session = get_session_from_request(request)
    if not session:
        raise HTTPException(
            status_code=401,
            detail="Authentication required to access monitoring data."
        )
    return session


# ---------------------------------------------------------------------------
# 1. Master summary
# ---------------------------------------------------------------------------
@router.get("/api/monitoring/summary")
def monitoring_summary(request: Request):
    """
    Master monitoring summary: production model state, mailbox distribution,
    feedback count, correction rate, and drift vs. Phase 42 baseline.

    This is the primary entry point for developer/admin observability.
    Keeps monitoring data strictly separate from the user-facing email dashboard.
    """
    session = _require_session(request)
    try:
        summary = production_monitor.get_summary(session.user_id)
        pred_log = prediction_log_stats(session.user_id)
        summary["prediction_log"] = pred_log
        return {"status": "success", "monitoring": summary}
    except Exception as exc:
        logger.error("monitoring_summary error: %s", exc)
        raise HTTPException(status_code=500, detail=f"Monitoring summary failed: {exc}")


# ---------------------------------------------------------------------------
# 2. Distribution report
# ---------------------------------------------------------------------------
@router.get("/api/monitoring/distribution")
def monitoring_distribution(request: Request):
    """
    Current P1/P2/P3/P4 distribution for the authenticated user's mailbox,
    compared against the V4.1 Phase 42 production baseline.

    Drift values are reported as absolute percentage-point deltas.
    Drift ≠ model degradation — do not act on a single metric.
    """
    session = _require_session(request)
    try:
        report = production_monitor.get_distribution_report(session.user_id)
        return {"status": "success", "distribution": report}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Distribution report failed: {exc}")


# ---------------------------------------------------------------------------
# 3. Confidence report
# ---------------------------------------------------------------------------
@router.get("/api/monitoring/confidence")
def monitoring_confidence(request: Request):
    """
    Per-priority confidence distribution statistics:
    count, mean, median, p10, p25, p75, p90.

    Also surfaces informational review candidates:
    - Low-confidence P1/P2 (model may be uncertain)
    - High-confidence P3/P4 (potential over-de-escalation)

    Confidence ≠ correctness. These flags are review suggestions only.
    """
    session = _require_session(request)
    try:
        report = production_monitor.get_confidence_report(session.user_id)
        return {"status": "success", "confidence": report}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Confidence report failed: {exc}")


# ---------------------------------------------------------------------------
# 4. Safety events
# ---------------------------------------------------------------------------
@router.get("/api/monitoring/safety")
def monitoring_safety(request: Request):
    """
    Lists potentially safety-critical prediction patterns reported by the user:
    - OTP/security emails predicted below P1 and corrected to P1
    - Security emails predicted below P2 and corrected to P2
    - Payment emails predicted as non-actionable but corrected
    - Deadline emails flagged as non-actionable by the user

    Source: user feedback records (feedback.jsonl), not live inference.
    No automatic prediction changes are made based on this list.
    """
    session = _require_session(request)
    try:
        events = production_monitor.get_safety_events(session.user_id)
        return {"status": "success", "safety": events}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Safety report failed: {exc}")


# ---------------------------------------------------------------------------
# 5. Feedback statistics
# ---------------------------------------------------------------------------
@router.get("/api/monitoring/feedback-stats")
def monitoring_feedback_stats(request: Request):
    """
    Correction rate statistics from the user's feedback records:
    - Overall correction rate
    - Correction rate by original priority (P1/P2/P3/P4)
    - Full P→P correction transition matrix
    - Notable escalation/de-escalation patterns
    """
    session = _require_session(request)
    try:
        stats = production_monitor.get_feedback_stats(session.user_id)
        return {"status": "success", "feedback_stats": stats}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Feedback stats failed: {exc}")


# ---------------------------------------------------------------------------
# 6. Dataset-v5 readiness
# ---------------------------------------------------------------------------
@router.get("/api/monitoring/v5-readiness")
def monitoring_v5_readiness(request: Request):
    """
    Evaluates readiness criteria for launching a dataset-v5 curation effort.

    Readiness gates (all informational — do not trigger automatic retraining):
    - Minimum feedback volume (≥50 records)
    - Minimum priority corrections (≥20)
    - P2 boundary examples in both directions (≥10 each)
    - Safety-critical lower→P1 examples (any count)

    Also displays the required pipeline from user correction to offline training.
    """
    session = _require_session(request)
    try:
        readiness = production_monitor.get_v5_readiness(session.user_id)
        return {"status": "success", "v5_readiness": readiness}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"V5 readiness check failed: {exc}")
