"""
routes_adjudication.py — Phase 52 Adjudication & Feedback Review API
======================================================================
Endpoints for the human adjudication workflow and dataset-v5.2 candidate.

All endpoints:
  - Require a valid session (authentication enforced).
  - Are user-scoped unless noted as admin-level.
  - Are READ-ONLY except POST /api/adjudication/adjudicate.
  - Never expose raw email body, OAuth tokens, or another user's data.
  - Never trigger model training or model promotion.

Governance:
  - Rejected / NEEDS_CONTEXT feedback MUST NOT enter training.
  - ACCEPTED feedback enters the candidate pool only after human review.
  - The v5.2 candidate is CANDIDATE ONLY — never promoted automatically.
"""
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Request, Query
from pydantic import BaseModel

from backend.app.core.session import get_session_from_request
from backend.app.core.feedback import feedback_manager
from backend.app.core.adjudication import adjudication_manager, VALID_STATUSES
from backend.app.core.dataset_v52 import dataset_v52_builder

logger = logging.getLogger("mailmind.adjudication_api")
router = APIRouter(tags=["Adjudication"])


def _require_session(request: Request):
    session = get_session_from_request(request)
    if not session:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return session


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------
class AdjudicationRequest(BaseModel):
    """Body for POST /api/adjudication/adjudicate."""
    feedback_id: str
    adjudication_status: str          # ACCEPTED | REJECTED | NEEDS_CONTEXT | DUPLICATE
    adjudication_reason: str
    corrected_priority: Optional[str] = None   # Required when status=ACCEPTED


# ---------------------------------------------------------------------------
# 1. Deduplication statistics
# ---------------------------------------------------------------------------
@router.get("/api/adjudication/dedup-stats")
def adjudication_dedup_stats(request: Request):
    """
    Returns deduplication breakdown:
    - raw_feedback_events: every row in feedback.jsonl
    - unique_feedback_cases: deduped by (user_id, message_id)
    - duplicate_submissions: raw - unique
    - priority_correction_cases, safety_cases, p2_p3_boundary_cases, deadline_cases
    """
    session = _require_session(request)
    try:
        stats = feedback_manager.get_dedup_stats(session.user_id)
        return {"status": "success", "dedup_stats": stats}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Dedup stats failed: {exc}")


# ---------------------------------------------------------------------------
# 2. Adjudication queue (pending review)
# ---------------------------------------------------------------------------
@router.get("/api/adjudication/queue")
def adjudication_queue(request: Request):
    """
    Returns the pending adjudication queue for the authenticated user.
    Deduped by (user_id, message_id).
    Prioritisation: safety > P2/P3 > deadline > other.
    Does NOT expose another user's feedback.
    """
    session = _require_session(request)
    try:
        queue = adjudication_manager.get_pending_queue(user_id=session.user_id)
        return {
            "status": "success",
            "pending_count": len(queue),
            "queue": queue,
            "note": "Prioritised: safety cases first, then P2/P3 boundary, then deadlines.",
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Queue failed: {exc}")


# ---------------------------------------------------------------------------
# 3. Submit adjudication decision
# ---------------------------------------------------------------------------
@router.post("/api/adjudication/adjudicate")
def submit_adjudication(request: Request, body: AdjudicationRequest):
    """
    Records a human adjudication decision.

    Status must be one of: ACCEPTED, REJECTED, NEEDS_CONTEXT, DUPLICATE.
    ACCEPTED requires corrected_priority (P1/P2/P3/P4) and a reason.
    REJECTED/NEEDS_CONTEXT/DUPLICATE require a reason.

    FORBIDDEN: This endpoint NEVER triggers model training or promotion.
    """
    session = _require_session(request)

    if body.adjudication_status not in (VALID_STATUSES - {"PENDING_REVIEW"}):
        raise HTTPException(
            status_code=422,
            detail=(
                f"Invalid status '{body.adjudication_status}'. "
                "Must be ACCEPTED, REJECTED, NEEDS_CONTEXT, or DUPLICATE."
            ),
        )
    if not body.adjudication_reason or not body.adjudication_reason.strip():
        raise HTTPException(
            status_code=422,
            detail="adjudication_reason is required and must be non-empty."
        )

    try:
        record = adjudication_manager.adjudicate(
            feedback_id=body.feedback_id,
            adjudicator_id=session.user_id,
            status=body.adjudication_status,
            reason=body.adjudication_reason,
            corrected_priority=body.corrected_priority,
        )
        return {
            "status": "success",
            "adjudication": record,
            "note": "No model training or promotion triggered by this action.",
        }
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.error("adjudication error: %s", exc)
        raise HTTPException(status_code=500, detail=f"Adjudication failed: {exc}")


# ---------------------------------------------------------------------------
# 4. All cases with adjudication status
# ---------------------------------------------------------------------------
@router.get("/api/adjudication/cases")
def adjudication_cases(request: Request):
    """
    Returns adjudication stats for the authenticated user:
    total cases, pending, accepted, rejected, needs-context, duplicates.
    """
    session = _require_session(request)
    try:
        stats = adjudication_manager.get_stats(user_id=session.user_id)
        return {"status": "success", "cases": stats}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Cases failed: {exc}")


# ---------------------------------------------------------------------------
# 5. Accepted training candidates
# ---------------------------------------------------------------------------
@router.get("/api/adjudication/accepted")
def adjudication_accepted(request: Request):
    """
    Returns accepted adjudicated records eligible for dataset-v5.2.
    Only ACCEPTED + eligible_for_training=True records are shown.
    Does not include raw email content.
    """
    session = _require_session(request)
    try:
        pool = adjudication_manager.get_candidate_pool()
        # Filter to this user only
        user_pool = [r for r in pool if r.get("user_id") == session.user_id]
        return {
            "status": "success",
            "accepted_count": len(user_pool),
            "accepted": user_pool,
            "governance": "These examples may enter dataset-v5.2 only after human review and leakage audit.",
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Accepted cases failed: {exc}")


# ---------------------------------------------------------------------------
# 6. P2/P3 Boundary review queue
# ---------------------------------------------------------------------------
@router.get("/api/adjudication/p2-p3-review")
def adjudication_p2_p3_review(request: Request):
    """
    P2/P3 boundary cases — pending feedback with P2↔P3 transitions.
    Each case is analysed for:
    - genuine priority boundary error
    - action detection error
    - deadline detection error
    - topic/domain drift
    - user preference vs model error
    """
    session = _require_session(request)
    try:
        queue = adjudication_manager.get_p2_p3_queue(user_id=session.user_id)
        return {
            "status": "success",
            "p2_p3_boundary_count": len(queue),
            "queue": queue,
            "review_guidance": (
                "Assess whether each P2↔P3 correction is a genuine model error "
                "or a user preference. Consider: action_required, deadline_detected, "
                "topic, and operational consequence. Do not automatically accept "
                "user feedback as ground truth."
            ),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"P2/P3 review failed: {exc}")


# ---------------------------------------------------------------------------
# 7. Safety queue
# ---------------------------------------------------------------------------
@router.get("/api/adjudication/safety-queue")
def adjudication_safety_queue(request: Request):
    """
    Safety-critical cases: OTP, MFA, password reset, security alerts,
    account compromise, authentication failures, infrastructure incidents.

    Phase 52-G invariant: 0 critical P1 downgrades.
    If any case shows a critical downgrade, it is flagged here.
    No automatic correction is made.
    """
    session = _require_session(request)
    try:
        queue = adjudication_manager.get_safety_queue(user_id=session.user_id)
        # Flag any lower→P1 escalations as safety-critical
        safety_critical = [
            r for r in queue
            if (r.get("corrected_priority") == "P1"
                and r.get("predicted_priority", r.get("original_priority", "")) != "P1")
        ]
        return {
            "status": "success",
            "safety_queue_count": len(queue),
            "safety_critical_count": len(safety_critical),
            "queue": queue,
            "safety_critical": safety_critical,
            "invariant": "0 critical P1 downgrades. If any safety case is confirmed, preserve v5.1 and require human adjudication.",
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Safety queue failed: {exc}")


# ---------------------------------------------------------------------------
# 8. Deadline review queue
# ---------------------------------------------------------------------------
@router.get("/api/adjudication/deadline-queue")
def adjudication_deadline_queue(request: Request):
    """
    Deadline-involving feedback cases.
    Checks: deadline_detected, deadline_datetime, deadline_precision,
    deadline_status, action_required, original/corrected priority.
    """
    session = _require_session(request)
    try:
        queue = adjudication_manager.get_deadline_queue(user_id=session.user_id)
        return {
            "status": "success",
            "deadline_queue_count": len(queue),
            "queue": queue,
            "review_guidance": (
                "Verify the deadline is genuine — not email arrival date, "
                "newsletter publication date, or historical event date. "
                "A deadline may affect attention without directly determining priority."
            ),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Deadline queue failed: {exc}")


# ---------------------------------------------------------------------------
# 9. Dataset-v5.2 candidate info + readiness
# ---------------------------------------------------------------------------
@router.get("/api/adjudication/v52-candidate")
def adjudication_v52_candidate(request: Request):
    """
    Builds (or rebuilds) the dataset-v5.2 candidate and returns readiness report.

    This endpoint:
      - Reads only accepted adjudicated records
      - Runs the leakage audit
      - Returns candidate size, distribution, readiness state
      - DOES NOT train any model
      - DOES NOT promote any model
    """
    session = _require_session(request)
    try:
        result = dataset_v52_builder.build()
        return {
            "status": "success",
            "candidate_status": "CANDIDATE — NOT TRAINED — NOT PRODUCTION",
            "v52_candidate": result,
            "governance": {
                "training_occurred": False,
                "promotion_occurred": False,
                "fabricated_data": False,
                "v51_still_active": True,
                "v41_still_rollback": True,
            },
        }
    except Exception as exc:
        logger.error("v52_candidate error: %s", exc)
        raise HTTPException(status_code=500, detail=f"v5.2 candidate build failed: {exc}")
