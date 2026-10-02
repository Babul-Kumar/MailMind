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


# ---------------------------------------------------------------------------
# Phase 48: Candidate Shadow Monitoring Endpoints (Session-Gated, User-Scoped)
# ---------------------------------------------------------------------------
from backend.app.core.shadow_monitor import shadow_monitor


@router.get("/api/monitoring/shadow/summary")
def shadow_monitoring_summary(request: Request):
    """
    Returns summary statistics for candidate shadow inference:
    total shadowed, agreement/divergence rates, critical P1 downgrades,
    action/deadline differences, and median/P95 latency.
    """
    session = _require_session(request)
    try:
        summary = shadow_monitor.get_summary(session.user_id)
        return {"status": "success", "shadow_summary": summary}
    except Exception as exc:
        logger.error("shadow_monitoring_summary error: %s", exc)
        raise HTTPException(status_code=500, detail=f"Shadow summary failed: {exc}")


@router.get("/api/monitoring/shadow/distribution")
def shadow_monitoring_distribution(request: Request):
    """
    Returns class distributions (P1/P2/P3/P4) comparing active production
    versus shadow candidate model for the authenticated user.
    """
    session = _require_session(request)
    try:
        dist = shadow_monitor.get_distribution(session.user_id)
        return {"status": "success", "shadow_distribution": dist}
    except Exception as exc:
        logger.error("shadow_monitoring_distribution error: %s", exc)
        raise HTTPException(status_code=500, detail=f"Shadow distribution failed: {exc}")


@router.get("/api/monitoring/shadow/divergence")
def shadow_monitoring_divergence(request: Request, limit: int = 100):
    """
    Returns top diverged prediction records (priority changed, action changed,
    or deadline changed) without raw email body or credentials.
    """
    session = _require_session(request)
    try:
        records = shadow_monitor.get_divergence_records(session.user_id, limit=limit)
        return {"status": "success", "divergence_count": len(records), "records": records}
    except Exception as exc:
        logger.error("shadow_monitoring_divergence error: %s", exc)
        raise HTTPException(status_code=500, detail=f"Shadow divergence failed: {exc}")


@router.get("/api/monitoring/shadow/safety")
def shadow_monitoring_safety(request: Request):
    """
    Performs deterministic safety audit across high-risk categories (OTP, MFA,
    account compromise, security alerts, password resets, payment failures, etc.)
    and reports any critical P1 downgrades.
    """
    session = _require_session(request)
    try:
        safety = shadow_monitor.get_safety_audit(session.user_id)
        return {"status": "success", "shadow_safety": safety}
    except Exception as exc:
        logger.error("shadow_monitoring_safety error: %s", exc)
        raise HTTPException(status_code=500, detail=f"Shadow safety failed: {exc}")


@router.get("/api/monitoring/shadow/performance")
def shadow_monitoring_performance(request: Request):
    """
    Returns latency comparison (active median/P95 vs shadow median/P95)
    and overhead measurements.
    """
    session = _require_session(request)
    try:
        perf = shadow_monitor.get_performance(session.user_id)
        return {"status": "success", "shadow_performance": perf}
    except Exception as exc:
        logger.error("shadow_monitoring_performance error: %s", exc)
        raise HTTPException(status_code=500, detail=f"Shadow performance failed: {exc}")


@router.get("/api/monitoring/shadow/transitions")
def shadow_monitoring_transitions(request: Request):
    """
    Returns the complete 4x4 active -> shadow priority transition matrix
    and highlights notable escalation and de-escalation patterns.
    """
    session = _require_session(request)
    try:
        transitions = shadow_monitor.get_transitions(session.user_id)
        return {"status": "success", "shadow_transitions": transitions}
    except Exception as exc:
        logger.error("shadow_monitoring_transitions error: %s", exc)
        raise HTTPException(status_code=500, detail=f"Shadow transitions failed: {exc}")


@router.get("/api/monitoring/shadow/feedback-correlation")
def shadow_monitoring_feedback_correlation(request: Request):
    """
    Correlates user corrections on active model with candidate shadow predictions
    to evaluate observational agreement with human feedback.
    """
    session = _require_session(request)
    try:
        corr = shadow_monitor.get_feedback_correlation(session.user_id)
        return {"status": "success", "feedback_correlation": corr}
    except Exception as exc:
        logger.error("shadow_monitoring_feedback_correlation error: %s", exc)
        raise HTTPException(status_code=500, detail=f"Shadow feedback correlation failed: {exc}")


# ---------------------------------------------------------------------------
# Phase 49: Controlled Canary Deployment & Safety Gate Endpoints
# ---------------------------------------------------------------------------

@router.get("/api/monitoring/canary/status")
def canary_monitoring_status(request: Request):
    """
    Returns current Canary deployment status, stage, percentages, active model,
    candidate model, and artifact integrity.
    """
    session = _require_session(request)
    try:
        from backend.app.core.canary_monitor import canary_monitor
        summary = canary_monitor.get_summary(session.user_id)
        return {"status": "success", "canary_status": summary}
    except Exception as exc:
        logger.error("canary_monitoring_status error: %s", exc)
        raise HTTPException(status_code=500, detail=f"Canary status failed: {exc}")


@router.get("/api/monitoring/canary/metrics")
def canary_monitoring_metrics(request: Request):
    """
    Returns side-by-side metric comparison between Control (priority-v4.1)
    and Canary (priority-v5.1).
    """
    session = _require_session(request)
    try:
        from backend.app.core.canary_monitor import canary_monitor
        metrics = canary_monitor.get_metrics_comparison(session.user_id)
        return {"status": "success", "canary_metrics": metrics}
    except Exception as exc:
        logger.error("canary_monitoring_metrics error: %s", exc)
        raise HTTPException(status_code=500, detail=f"Canary metrics failed: {exc}")


@router.get("/api/monitoring/canary/safety")
def canary_monitoring_safety(request: Request):
    """
    Returns safety-critical category retention and audit of sensitive messages
    (OTP, MFA, password reset, security alert).
    """
    session = _require_session(request)
    try:
        from backend.app.core.canary_monitor import canary_monitor
        safety = canary_monitor.get_safety_audit()
        return {"status": "success", "canary_safety": safety}
    except Exception as exc:
        logger.error("canary_monitoring_safety error: %s", exc)
        raise HTTPException(status_code=500, detail=f"Canary safety audit failed: {exc}")


@router.get("/api/monitoring/canary/feedback")
def canary_monitoring_feedback(request: Request):
    """
    Compares user feedback and corrections between Control (v4.1) and Canary (v5.1).
    """
    session = _require_session(request)
    try:
        from backend.app.core.canary_monitor import canary_monitor
        fb = canary_monitor.get_feedback_comparison()
        return {"status": "success", "canary_feedback": fb}
    except Exception as exc:
        logger.error("canary_monitoring_feedback error: %s", exc)
        raise HTTPException(status_code=500, detail=f"Canary feedback failed: {exc}")


@router.get("/api/monitoring/canary/gates")
def canary_monitoring_gates(request: Request):
    """
    Evaluates all 13 Phase 49 Promotion Gates deterministically.
    """
    session = _require_session(request)
    try:
        from backend.app.core.canary_monitor import canary_monitor
        gates = canary_monitor.evaluate_safety_gates()
        return {"status": "success", "safety_gates": gates}
    except Exception as exc:
        logger.error("canary_monitoring_gates error: %s", exc)
        raise HTTPException(status_code=500, detail=f"Safety gate evaluation failed: {exc}")


@router.post("/api/monitoring/canary/stage")
def set_canary_stage(request: Request, stage: int):
    """
    Admin control to set the active canary stage (0=0%, 1=5%, 2=10%, 3=25%, 4=50%).
    Requires active session. Does not allow auto-promotion to 100%.
    """
    session = _require_session(request)
    try:
        from backend.app.ml.canary_router import canary_router
        result = canary_router.set_stage(stage)
        return {"status": "success", "canary_status": result}
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err))
    except Exception as exc:
        logger.error("set_canary_stage error: %s", exc)
        raise HTTPException(status_code=500, detail=f"Setting canary stage failed: {exc}")


@router.post("/api/monitoring/canary/rollback")
def rollback_canary(request: Request):
    """
    Admin emergency rollback: sets canary percentage to 0% and routes 100% of traffic
    back to active production model (priority-v4.1).
    """
    session = _require_session(request)
    try:
        from backend.app.ml.canary_router import canary_router
        result = canary_router.rollback()
        return {"status": "success", "message": "Emergency rollback executed", "canary_status": result}
    except Exception as exc:
        logger.error("rollback_canary error: %s", exc)
        raise HTTPException(status_code=500, detail=f"Rollback failed: {exc}")


