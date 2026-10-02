"""
routes_phase51.py — Phase 51 Production Monitoring API
=======================================================
Read-only monitoring endpoints for production v5.1 observability.

All endpoints:
  - Require a valid session (user authentication).
  - Are strictly user-scoped.
  - Are READ-ONLY — no model changes, no retraining.
  - Exclude OAuth tokens, credentials, and raw email body.

No automated retraining or promotion is triggered by these endpoints.
"""
import logging
from fastapi import APIRouter, HTTPException, Request, Query

from backend.app.core.session import get_session_from_request
from backend.app.core.phase51_monitor import phase51_monitor

logger = logging.getLogger("mailmind.phase51_api")
router = APIRouter(tags=["Phase51-Monitoring"])


def _require_session(request: Request):
    """Shared auth guard."""
    session = get_session_from_request(request)
    if not session:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return session


# ---------------------------------------------------------------------------
# 1. Master Summary
# ---------------------------------------------------------------------------
@router.get("/api/monitoring/phase51/summary")
def phase51_summary(request: Request):
    """Complete Phase 51 monitoring summary combining all signals."""
    session = _require_session(request)
    try:
        summary = phase51_monitor.get_full_summary(session.user_id)
        return {"status": "success", "phase51": summary}
    except Exception as exc:
        logger.error("phase51_summary error: %s", exc)
        raise HTTPException(status_code=500, detail=f"Phase 51 summary failed: {exc}")


# ---------------------------------------------------------------------------
# 2. Distribution
# ---------------------------------------------------------------------------
@router.get("/api/monitoring/phase51/distribution")
def phase51_distribution(
    request: Request,
    window: str = Query("all", pattern="^(last_24h|last_7d|last_30d|all)$"),
):
    """P1/P2/P3/P4 distribution with time windows and drift analysis."""
    session = _require_session(request)
    try:
        dist = phase51_monitor.get_distribution(session.user_id, window=window)
        return {"status": "success", "distribution": dist}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Distribution failed: {exc}")


# ---------------------------------------------------------------------------
# 3. Confidence
# ---------------------------------------------------------------------------
@router.get("/api/monitoring/phase51/confidence")
def phase51_confidence(request: Request):
    """Per-priority confidence monitoring with drift detection."""
    session = _require_session(request)
    try:
        conf = phase51_monitor.get_confidence(session.user_id)
        return {"status": "success", "confidence": conf}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Confidence failed: {exc}")


# ---------------------------------------------------------------------------
# 4. Feedback
# ---------------------------------------------------------------------------
@router.get("/api/monitoring/phase51/feedback")
def phase51_feedback(request: Request):
    """Feedback monitoring with correction matrix and deduplication tracking."""
    session = _require_session(request)
    try:
        fb = phase51_monitor.get_feedback(session.user_id)
        return {"status": "success", "feedback": fb}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Feedback failed: {exc}")


# ---------------------------------------------------------------------------
# 5. P2/P3 Boundary
# ---------------------------------------------------------------------------
@router.get("/api/monitoring/phase51/p2-p3-boundary")
def phase51_p2_p3_boundary(request: Request):
    """P2/P3 boundary confusion diagnostic."""
    session = _require_session(request)
    try:
        boundary = phase51_monitor.get_p2_p3_boundary(session.user_id)
        return {"status": "success", "p2_p3_boundary": boundary}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"P2/P3 boundary failed: {exc}")


# ---------------------------------------------------------------------------
# 6. Safety
# ---------------------------------------------------------------------------
@router.get("/api/monitoring/phase51/safety")
def phase51_safety(request: Request):
    """Safety monitoring: P1 retention, critical downgrades, escalations."""
    session = _require_session(request)
    try:
        safety = phase51_monitor.get_safety(session.user_id)
        return {"status": "success", "safety": safety}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Safety failed: {exc}")


# ---------------------------------------------------------------------------
# 7. Action / Deadline
# ---------------------------------------------------------------------------
@router.get("/api/monitoring/phase51/action-deadline")
def phase51_action_deadline(request: Request):
    """Action Required and Deadline distribution monitoring."""
    session = _require_session(request)
    try:
        ad = phase51_monitor.get_action_deadline(session.user_id)
        return {"status": "success", "action_deadline": ad}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Action/Deadline failed: {exc}")


# ---------------------------------------------------------------------------
# 8. Needs Attention
# ---------------------------------------------------------------------------
@router.get("/api/monitoring/phase51/needs-attention")
def phase51_needs_attention(request: Request):
    """Needs Attention breakdown with contribution analysis."""
    session = _require_session(request)
    try:
        na = phase51_monitor.get_needs_attention(session.user_id)
        return {"status": "success", "needs_attention": na}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Needs Attention failed: {exc}")


# ---------------------------------------------------------------------------
# 9. Drift
# ---------------------------------------------------------------------------
@router.get("/api/monitoring/phase51/drift")
def phase51_drift(request: Request):
    """Domain/distribution drift analysis."""
    session = _require_session(request)
    try:
        drift = phase51_monitor.get_drift(session.user_id)
        return {"status": "success", "drift": drift}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Drift failed: {exc}")


# ---------------------------------------------------------------------------
# 10. Latency
# ---------------------------------------------------------------------------
@router.get("/api/monitoring/phase51/latency")
def phase51_latency(request: Request):
    """Model and system latency monitoring with baseline comparison."""
    session = _require_session(request)
    try:
        lat = phase51_monitor.get_latency(session.user_id)
        return {"status": "success", "latency": lat}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Latency failed: {exc}")


# ---------------------------------------------------------------------------
# 11. Cache / Errors
# ---------------------------------------------------------------------------
@router.get("/api/monitoring/phase51/cache-errors")
def phase51_cache_errors(request: Request):
    """Cache hit rates, model-version isolation, and error monitoring."""
    session = _require_session(request)
    try:
        ce = phase51_monitor.get_cache_errors(session.user_id)
        return {"status": "success", "cache_errors": ce}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Cache/Error failed: {exc}")


# ---------------------------------------------------------------------------
# 12. Alerts
# ---------------------------------------------------------------------------
@router.get("/api/monitoring/phase51/alerts")
def phase51_alerts(request: Request):
    """Current alert evaluation across all monitoring signals."""
    session = _require_session(request)
    try:
        alerts = phase51_monitor.get_alerts(session.user_id)
        return {"status": "success", "alerts": alerts}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Alerts failed: {exc}")


# ---------------------------------------------------------------------------
# 13. v5.2 Readiness
# ---------------------------------------------------------------------------
@router.get("/api/monitoring/phase51/v52-readiness")
def phase51_v52_readiness(request: Request):
    """Evidence-based v5.2 readiness assessment."""
    session = _require_session(request)
    try:
        readiness = phase51_monitor.get_v52_readiness(session.user_id)
        return {"status": "success", "v52_readiness": readiness}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"v5.2 readiness failed: {exc}")


# ---------------------------------------------------------------------------
# 14. Privacy Audit
# ---------------------------------------------------------------------------
@router.get("/api/monitoring/phase51/privacy-audit")
def phase51_privacy_audit(request: Request):
    """Scans monitoring artifacts for sensitive data."""
    session = _require_session(request)
    try:
        audit = phase51_monitor.privacy_audit()
        return {"status": "success", "privacy_audit": audit}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Privacy audit failed: {exc}")
