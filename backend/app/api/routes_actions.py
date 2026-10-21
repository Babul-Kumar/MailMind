"""
Routes for Smart Action Queue — Mark Resolved, Snooze, and Action Queue endpoints.
All actions are strictly scoped to the authenticated session.user_id.
User A can NEVER inspect or mutate User B's action states.
"""

import time
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Request, Query

from backend.app.core.session import get_session_from_request
from backend.app.core.action_store import user_action_store
from backend.app.core.action_policy import (
    classify_action_queue,
    evaluate_actionability,
    DEFAULT_AGE_THRESHOLD_DAYS,
)
from backend.app.core.cache import user_email_cache
from backend.app.ml.registry import model_registry

logger = logging.getLogger("mailmind.actions")
router = APIRouter(prefix="/api/actions", tags=["Actions"])


# -----------------------------------------------------------------------------
# Request Schemas
# -----------------------------------------------------------------------------

class ResolveRequest(BaseModel):
    message_id: str = Field(..., min_length=1, max_length=128, description="Gmail message ID")
    thread_id: Optional[str] = Field(None, max_length=128, description="Gmail thread ID")
    note: Optional[str] = Field(None, max_length=500, description="Optional resolution note")


class UnresolveRequest(BaseModel):
    message_id: str = Field(..., min_length=1, max_length=128, description="Gmail message ID")


class SnoozeRequest(BaseModel):
    message_id: str = Field(..., min_length=1, max_length=128, description="Gmail message ID")
    thread_id: Optional[str] = Field(None, max_length=128, description="Gmail thread ID")
    snooze_until: float = Field(..., description="Unix timestamp (in seconds) until which to snooze")
    snooze_reason: Optional[str] = Field(None, max_length=200, description="Preset or custom reason")


class UnsnoozeRequest(BaseModel):
    message_id: str = Field(..., min_length=1, max_length=128, description="Gmail message ID")


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------

@router.post("/resolve")
def resolve_action(request: Request, body: ResolveRequest):
    """
    Marks an email action as resolved for the authenticated user.
    Server-side persistence ensures state survives reloads, rescans, and redeployments.
    Zero Gmail mutation (does not archive, mark read, or delete).
    """
    session = get_session_from_request(request)
    if not session:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please connect your Gmail account."
        )

    try:
        updated_state = user_action_store.resolve_action(
            user_id=session.user_id,
            message_id=body.message_id,
            thread_id=body.thread_id,
            note=body.note
        )
        return {
            "status": "success",
            "message": "Action marked as resolved.",
            "action_state": updated_state
        }
    except Exception as e:
        logger.error("Failed to resolve action for user %s, mid %s: %s", session.user_id, body.message_id, e)
        raise HTTPException(status_code=500, detail=f"Failed to record resolution: {str(e)}")


@router.post("/unresolve")
def unresolve_action(request: Request, body: UnresolveRequest):
    """
    Reverts (undoes) a previously marked resolution.
    Restores email to active or older queue based on its age and deadline.
    """
    session = get_session_from_request(request)
    if not session:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please connect your Gmail account."
        )

    try:
        updated_state = user_action_store.unresolve_action(
            user_id=session.user_id,
            message_id=body.message_id
        )
        return {
            "status": "success",
            "message": "Resolution undone.",
            "action_state": updated_state
        }
    except Exception as e:
        logger.error("Failed to unresolve action for user %s, mid %s: %s", session.user_id, body.message_id, e)
        raise HTTPException(status_code=500, detail=f"Failed to undo resolution: {str(e)}")


@router.post("/snooze")
def snooze_action(request: Request, body: SnoozeRequest):
    """
    Postpones an actionable item until a specified future timestamp.
    Hidden from the active queue until the scheduled return time.
    """
    session = get_session_from_request(request)
    if not session:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please connect your Gmail account."
        )

    now_ts = datetime.now(timezone.utc).timestamp()
    if body.snooze_until <= now_ts:
        raise HTTPException(
            status_code=400,
            detail="Snooze time must be in the future."
        )

    # Maximum snooze time: 1 year into the future
    if body.snooze_until > now_ts + (365 * 86400.0):
        raise HTTPException(
            status_code=400,
            detail="Snooze time cannot exceed 1 year."
        )

    try:
        updated_state = user_action_store.snooze_action(
            user_id=session.user_id,
            message_id=body.message_id,
            snooze_until_ts=body.snooze_until,
            thread_id=body.thread_id,
            reason=body.snooze_reason
        )
        return {
            "status": "success",
            "message": "Action snoozed.",
            "action_state": updated_state
        }
    except Exception as e:
        logger.error("Failed to snooze action for user %s, mid %s: %s", session.user_id, body.message_id, e)
        raise HTTPException(status_code=500, detail=f"Failed to snooze action: {str(e)}")


@router.post("/unsnooze")
def unsnooze_action(request: Request, body: UnsnoozeRequest):
    """
    Clears an active snooze immediately, returning the item to its calculated queue.
    """
    session = get_session_from_request(request)
    if not session:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please connect your Gmail account."
        )

    try:
        updated_state = user_action_store.unsnooze_action(
            user_id=session.user_id,
            message_id=body.message_id
        )
        return {
            "status": "success",
            "message": "Snooze cancelled.",
            "action_state": updated_state
        }
    except Exception as e:
        logger.error("Failed to unsnooze action for user %s, mid %s: %s", session.user_id, body.message_id, e)
        raise HTTPException(status_code=500, detail=f"Failed to unsnooze action: {str(e)}")


@router.get("/queue")
def get_action_queue(
    request: Request,
    sort_by: str = Query(default="urgent", description="Active queue sort: urgent, newest, deadline, oldest"),
    older_sort_by: str = Query(default="oldest", description="Older actions sort: oldest, newest, urgent"),
    threshold_days: float = Query(default=DEFAULT_AGE_THRESHOLD_DAYS, ge=1.0, le=90.0, description="Age cutoff in days (default 8.0)")
):
    """
    Retrieves the complete Smart Action Queue for the authenticated user:
      - Active queue (items <= 8 days, or verified future deadline / critical incident exception)
      - Older actions (items > 8 days without exception)
      - Snoozed items (awaiting wake-up)
      - Exact, derived counts (Urgent, Due soon, Other active, Older, Snoozed, Resolved)
    """
    session = get_session_from_request(request)
    if not session:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please connect your Gmail account."
        )

    # Determine the model version assigned to this user via canary router
    try:
        from backend.app.ml.canary_router import canary_router
        _, route_info = canary_router.get_pipeline_for_user(user_id)
        user_model_version = route_info.get("model_version")
    except Exception:
        user_model_version = model_registry.get_active_version()

    # Query all cached emails for user
    all_cached_emails, _ = user_email_cache.query_emails(
        user_id=user_id,
        priority=None,  # All priorities
        search=None,
        page=1,
        page_size=10000,
        model_version=user_model_version
    )
    # If no emails found under user_model_version, fallback to querying all un-stale cached emails for this user
    if not all_cached_emails:
        all_cached_emails, _ = user_email_cache.query_emails(
            user_id=user_id,
            priority=None,
            search=None,
            page=1,
            page_size=10000,
            model_version=None
        )

    # Fetch user action states map
    if hasattr(user_action_store, "get_user_action_states"):
        action_states_map = user_action_store.get_user_action_states(user_id)
    elif hasattr(user_action_store, "get_all_action_states"):
        action_states_map = user_action_store.get_all_action_states(user_id)
    elif hasattr(user_action_store, "get_user_actions_map"):
        action_states_map = user_action_store.get_user_actions_map(user_id)
    else:
        action_states_map = {}
    if not isinstance(action_states_map, dict):
        action_states_map = {}
    now_ts = datetime.now(timezone.utc).timestamp()

    queue_data = classify_action_queue(
        emails=all_cached_emails,
        action_states_map=action_states_map,
        now_ts=now_ts,
        age_threshold_days=threshold_days,
        sort_by=sort_by,
        older_sort_by=older_sort_by
    )

    return {
        "status": "success",
        "data": queue_data
    }


@router.get("/summary")
def get_action_summary(
    request: Request,
    threshold_days: float = Query(default=DEFAULT_AGE_THRESHOLD_DAYS, ge=1.0, le=90.0)
):
    """
    Lightweight summary endpoint returning exact counts for the Smart Action Queue.
    Used for sidebar badge and top navigation sync.
    """
    session = get_session_from_request(request)
    if not session:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please connect your Gmail account."
        )

    # Determine the model version assigned to this user via canary router
    try:
        from backend.app.ml.canary_router import canary_router
        _, route_info = canary_router.get_pipeline_for_user(user_id)
        user_model_version = route_info.get("model_version")
    except Exception:
        user_model_version = model_registry.get_active_version()

    all_cached_emails, _ = user_email_cache.query_emails(
        user_id=user_id,
        priority=None,
        search=None,
        page=1,
        page_size=10000,
        model_version=user_model_version
    )
    if not all_cached_emails:
        all_cached_emails, _ = user_email_cache.query_emails(
            user_id=user_id,
            priority=None,
            search=None,
            page=1,
            page_size=10000,
            model_version=None
        )

    if hasattr(user_action_store, "get_user_action_states"):
        action_states_map = user_action_store.get_user_action_states(user_id)
    elif hasattr(user_action_store, "get_all_action_states"):
        action_states_map = user_action_store.get_all_action_states(user_id)
    elif hasattr(user_action_store, "get_user_actions_map"):
        action_states_map = user_action_store.get_user_actions_map(user_id)
    else:
        action_states_map = {}
    if not isinstance(action_states_map, dict):
        action_states_map = {}
    now_ts = datetime.now(timezone.utc).timestamp()

    queue_data = classify_action_queue(
        emails=all_cached_emails,
        action_states_map=action_states_map,
        now_ts=now_ts,
        age_threshold_days=threshold_days
    )

    return {
        "status": "success",
        "counts": queue_data["counts"]
    }
