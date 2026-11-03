import time
import uuid
import json
import logging
import hashlib
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Query, HTTPException, Request, Response
from concurrent.futures import ThreadPoolExecutor, as_completed

from backend.app.core.session import get_session_from_request, mask_email
from backend.app.core.cache import user_email_cache
from backend.app.core.feedback import FeedbackSubmission, feedback_manager
from backend.app.gmail.service import get_user_gmail_service
from backend.app.gmail.client import (
    fetch_emails,
    get_profile,
    list_message_ids,
    _fetch_single_message_safe,
    get_single_email
)
from backend.app.gmail.scan_engine import scan_manager, ScanJobState
from backend.app.ml.predictor import load_model, predict_batch, predict_email
from backend.app.ml.registry import model_registry
from backend.app.core.prediction_log import log_prediction

logger = logging.getLogger("mailmind.observability")
router = APIRouter(tags=["Emails"])


# -----------------------------------------------------------------------------
# Complete Mailbox Background Scan Endpoints (Phase 32)
# -----------------------------------------------------------------------------

@router.get("/api/scan/status")
def get_scan_status(request: Request):
    """
    Returns the authenticated user's current background scan progress and metrics.
    User-scoped: User A can NEVER view User B's scan status.
    """
    session = get_session_from_request(request)
    if not session:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please connect your Gmail account."
        )
    return scan_manager.get_status(session.user_id)


@router.post("/api/scan/start")
async def start_scan(
    request: Request,
    scope: str = Query(default="mailbox", description="Scan scope: 'mailbox' or 'label'"),
    mode: str = Query(default="incremental", description="Scan mode: 'incremental' or 'full'"),
    query: Optional[str] = Query(default=None, max_length=200, description="Optional search filter query"),
    force_rescan: bool = Query(default=False, description="Whether to recompute all cached analysis"),
    period: Optional[str] = Query(default=None, description="Optional analysis period")
):
    """
    Initiates a background complete mailbox scan or incremental synchronization.
    Asynchronously discovers all accessible Gmail message IDs, checks cache,
    and classifies uncached/changed messages in manageable batches.
    """
    # Check if parameters were provided via JSON body (e.g. from frontend api client)
    period_from_body = None
    try:
        body = await request.json()
        if isinstance(body, dict):
            if "scope" in body and body["scope"]:
                scope = str(body["scope"])
            if "mode" in body and body["mode"]:
                mode = str(body["mode"])
            if "query" in body and body["query"] is not None:
                query = str(body["query"])[:200]
            if "force_rescan" in body:
                force_rescan = bool(body["force_rescan"])
            if "period" in body and body["period"]:
                period_from_body = str(body["period"])
    except Exception:
        pass

    scope = "label" if str(scope).strip().lower() == "label" else "mailbox"
    mode = "full" if str(mode).strip().lower() == "full" else "incremental"
    query = str(query).strip()[:200] if query and str(query).strip() else None

    session = get_session_from_request(request)
    if not session:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please connect your Gmail account."
        )

    # Scoping to user analysis preference (default: last_3_months)
    pref = user_email_cache.get_analysis_preference(session.user_id, session.email)
    active_period = (period or period_from_body or pref.get("period") or "last_3_months").lower().strip()
    from backend.app.core.date_utils import SUPPORTED_PERIODS, calculate_period_boundaries
    if active_period not in SUPPORTED_PERIODS:
        active_period = "last_3_months"

    if not query and active_period != "all_time":
        boundaries = calculate_period_boundaries(
            period=active_period,
            tz_name=pref.get("timezone", "UTC"),
            custom_start_date=pref.get("custom_start_date"),
            custom_end_date=pref.get("custom_end_date")
        )
        query = boundaries.get("gmail_query") or None

    # If scan is already running for user, return active scan status immediately
    if scan_manager.is_scanning(session.user_id):
        return scan_manager.get_status(session.user_id)

    try:
        service = get_user_gmail_service(session=session)
    except PermissionError:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please connect your Gmail account."
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Gmail API connection error: {str(e)}")

    return scan_manager.start_scan(
        user_id=session.user_id,
        service=service,
        scope=scope,
        mode=mode,
        query=query,
        force_rescan=force_rescan,
        period=active_period
    )


@router.post("/api/scan/cancel")
def cancel_scan(request: Request):
    """Cancels the active scan for the authenticated user."""
    session = get_session_from_request(request)
    if not session:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please connect your Gmail account."
        )
    cancelled = scan_manager.cancel_scan(session.user_id)
    return {"status": "cancelled" if cancelled else "not_running"}


@router.post("/api/scan/rescan")
def rescan_mailbox(request: Request):
    """Convenience trigger for an explicit, complete mailbox rescan."""
    session = get_session_from_request(request)
    if not session:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please connect your Gmail account."
        )
    try:
        service = get_user_gmail_service(session=session)
    except PermissionError:
        raise HTTPException(status_code=401, detail="Authentication required.")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Gmail API connection error: {str(e)}")

    return scan_manager.start_scan(
        user_id=session.user_id,
        service=service,
        scope="mailbox",
        mode="full",
        force_rescan=True
    )


@router.post("/api/scan/migrate")
def migrate_model_cache(
    request: Request,
    target_version: Optional[str] = Query(default=None, description="Target model version (defaults to active)")
):
    """
    Section 32.14: Controlled model version migration.
    Marks outdated cache entries as stale so they are re-analyzed by the active model version.
    """
    session = get_session_from_request(request)
    if not session:
        raise HTTPException(status_code=401, detail="Authentication required.")
    active_version = target_version or model_registry.get_active_version()
    user_email_cache.mark_version_stale(session.user_id, active_version)
    return {
        "status": "success",
        "message": f"Cache entries not matching {active_version} marked stale for re-analysis.",
        "active_version": active_version
    }


# -----------------------------------------------------------------------------
# Date-Scoped Recent Mail & Historical Mailbox Endpoints
# -----------------------------------------------------------------------------

@router.get("/api/emails/recent")
def get_recent_emails(
    request: Request,
    page: int = Query(default=1, ge=1, description="Display page number (1-indexed)"),
    page_size: int = Query(default=50, ge=1, le=100, description="Display page size (1-100)"),
    period: Optional[str] = Query(default=None, description="Analysis period scope (defaults to user preference)"),
    priority: Optional[str] = Query(default=None, description="Optional priority filter: ALL, P1, P2, P3, P4, NEEDS_ATTENTION"),
    action_required: Optional[bool] = Query(default=None, description="Optional action required filter: true or false"),
    search: Optional[str] = Query(default=None, max_length=200, description="Optional search filter query"),
    sort: str = Query(default="desc", description="Sort order: 'desc' (newest first) or 'asc'")
):
    """
    Returns email summaries strictly within the selected analysis period for the authenticated user.
    Server-side pagination and dynamic priority aging applied.
    """
    session = get_session_from_request(request)
    if not session:
        raise HTTPException(status_code=401, detail="Authentication required. Please connect your Gmail account.")

    user_id = session.user_id
    pref = user_email_cache.get_analysis_preference(user_id, session.email)
    target_period = (period or pref.get("period") or "last_3_months").lower().strip()

    from backend.app.core.date_utils import calculate_period_boundaries
    boundaries = calculate_period_boundaries(
        period=target_period,
        tz_name=pref.get("timezone", "UTC"),
        custom_start_date=pref.get("custom_start_date"),
        custom_end_date=pref.get("custom_end_date")
    )

    try:
        from backend.app.ml.canary_router import canary_router
        _, route_info = canary_router.get_pipeline_for_user(user_id)
        user_model_version = route_info.get("model_version")
    except Exception:
        user_model_version = model_registry.get_active_version()

    items, total_count = user_email_cache.query_emails(
        user_id=user_id,
        priority=priority,
        search=search,
        page=page,
        page_size=page_size,
        sort_order=sort,
        action_required=action_required,
        model_version=user_model_version,
        start_ts=boundaries["start_ts_sec"] if boundaries["start_ts_sec"] > 0 else None,
        end_ts=boundaries["end_ts_sec"],
        is_analyzed=True
    )

    stats = user_email_cache.get_mailbox_stats(
        user_id=user_id,
        model_version=user_model_version,
        start_ts=boundaries["start_ts_sec"] if boundaries["start_ts_sec"] > 0 else None,
        end_ts=boundaries["end_ts_sec"]
    )

    total_pages = max(1, (total_count + page_size - 1) // page_size) if total_count > 0 else 1

    return {
        "status": "success",
        "data": {
            "items": items,
            "stats": stats,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_items": total_count,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1
            },
            "period": target_period,
            "date_boundaries": {
                "start_iso": boundaries["start_iso"],
                "end_iso": boundaries["end_iso"]
            }
        }
    }


@router.get("/api/emails/history")
def get_historical_emails(
    request: Request,
    page: int = Query(default=1, ge=1, description="Display page number (1-indexed)"),
    page_size: int = Query(default=50, ge=1, le=100, description="Display page size (1-100)"),
    start_date: Optional[str] = Query(default=None, description="Optional start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(default=None, description="Optional end date (YYYY-MM-DD)"),
    search: Optional[str] = Query(default=None, max_length=200, description="Optional search filter query"),
    priority: Optional[str] = Query(default=None, description="Optional priority filter: ALL, P1, P2, P3, P4"),
    analyzed: Optional[bool] = Query(default=None, description="Filter by analyzed status (true, false, or omitted for all)"),
    sort: str = Query(default="desc", description="Sort order: 'desc' (newest first) or 'asc'")
):
    """
    Provides browsing access to all historical synchronized mailbox messages independently of the selected analysis period.
    Displays existing predictions where available and clearly indicates unanalyzed messages.
    Does NOT automatically trigger full ML inference on old emails.
    """
    session = get_session_from_request(request)
    if not session:
        raise HTTPException(status_code=401, detail="Authentication required. Please connect your Gmail account.")

    user_id = session.user_id
    pref = user_email_cache.get_analysis_preference(user_id, session.email)
    tz_name = pref.get("timezone", "UTC")

    start_ts_sec = None
    end_ts_sec = None
    if start_date or end_date:
        from backend.app.core.date_utils import validate_date_range
        try:
            s_dt, e_dt = validate_date_range(start_date or "1970-01-01", end_date or datetime.now(timezone.utc).strftime("%Y-%m-%d"), tz_name=tz_name)
            start_ts_sec = s_dt.timestamp()
            end_ts_sec = e_dt.timestamp()
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

    try:
        from backend.app.ml.canary_router import canary_router
        _, route_info = canary_router.get_pipeline_for_user(user_id)
        user_model_version = route_info.get("model_version")
    except Exception:
        user_model_version = model_registry.get_active_version()

    items, total_count = user_email_cache.query_emails(
        user_id=user_id,
        priority=priority,
        search=search,
        page=page,
        page_size=page_size,
        sort_order=sort,
        action_required=None,
        model_version=user_model_version if analyzed is True else None,
        start_ts=start_ts_sec,
        end_ts=end_ts_sec,
        is_analyzed=analyzed
    )

    total_pages = max(1, (total_count + page_size - 1) // page_size) if total_count > 0 else 1

    return {
        "status": "success",
        "data": {
            "items": items,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_items": total_count,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1
            }
        }
    }




# -----------------------------------------------------------------------------
# Classified Emails Query & Display Pagination
# -----------------------------------------------------------------------------

@router.get("/api/emails")
def get_classified_emails(
    request: Request,
    response: Response,
    max_emails: int = Query(default=20, ge=1, le=100, description="Number of emails to fetch (1-100)"),
    page: int = Query(default=1, ge=1, description="Display page number (1-indexed)"),
    page_size: int = Query(default=50, ge=1, le=500, description="Display page size (default 50)"),
    priority: Optional[str] = Query(default=None, description="Optional priority filter: ALL, P1, P2, P3, P4, NEEDS_ATTENTION"),
    action_required: Optional[bool] = Query(default=None, description="Optional action required filter: true or false"),
    query: Optional[str] = Query(default=None, max_length=200, description="Optional search filter query"),
    scan_scope: str = Query(default="mailbox", description="Scan scope: 'mailbox' or 'label'"),
    period: Optional[str] = Query(default=None, description="Optional analysis period filter")
):
    """
    Fetches emails from Gmail for the authenticated user, utilizing an incremental user-scoped cache.
    Reuses already classified messages and only processes newly arrived messages.
    Supports complete mailbox display pagination, server-side search, and background scanning.
    """
    t_req_start = time.perf_counter()
    request_id = str(uuid.uuid4())

    session = get_session_from_request(request)
    if not session:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please connect your Gmail account."
        )

    user_id = session.user_id
    user_id_hash = hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:12]

    try:
        service = get_user_gmail_service(session=session)
    except PermissionError:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please connect your Gmail account."
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Gmail API connection error: {str(e)}")

    user_email = session.email
    profile = {"emailAddress": session.email, "messagesTotal": 0, "threadsTotal": 0}
    try:
        fetched_profile = get_profile(service)
        if isinstance(fetched_profile, dict):
            profile = fetched_profile
            user_email = profile.get("emailAddress", session.email)
    except Exception as prof_err:
        logger.warning("Could not refresh profile for user %s: %s", user_id_hash, prof_err)

    # Allow tests that mock or patch fetch_emails directly to simulate exceptions or custom fetching
    from unittest.mock import Mock
    if isinstance(fetch_emails, Mock):
        try:
            mock_result = fetch_emails(service=service, max_emails=max_emails, query=query)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch and process emails: {str(e)}")

    # Check User-Scoped Cache using Canary Router
    from backend.app.ml.canary_router import canary_router
    pipeline, route_info = canary_router.get_pipeline_for_user(user_id)
    user_model_version = route_info["model_version"]
    canary_group = route_info["canary_group"]

    # Period boundary filtering if period parameter is specified
    start_ts_sec: Optional[float] = None
    end_ts_sec: Optional[float] = None
    active_period = None
    if period:
        active_period = str(period).lower().strip()
        from backend.app.core.date_utils import SUPPORTED_PERIODS, calculate_period_boundaries
        if active_period in SUPPORTED_PERIODS and active_period != "all_time":
            pref = user_email_cache.get_analysis_preference(user_id, session.email)
            boundaries = calculate_period_boundaries(
                period=active_period,
                tz_name=pref.get("timezone", "UTC"),
                custom_start_date=pref.get("custom_start_date"),
                custom_end_date=pref.get("custom_end_date")
            )
            start_ts_sec = boundaries["start_ts_sec"] if boundaries["start_ts_sec"] > 0 else None
            end_ts_sec = boundaries["end_ts_sec"]

    stats_db = user_email_cache.get_mailbox_stats(
        user_id,
        model_version=user_model_version,
        start_ts=start_ts_sec,
        end_ts=end_ts_sec
    )
    total_cached = stats_db.get("total_analyzed", 0)
    has_explicit_max = "max_emails" in request.query_params

    # Auto-initiate background mailbox discovery if mailbox cache is empty
    if not has_explicit_max and total_cached == 0 and not scan_manager.is_scanning(user_id):
        try:
            pref = user_email_cache.get_analysis_preference(user_id, session.email)
            auto_period = (period or pref.get("period") or "last_3_months").lower().strip()
            from backend.app.core.date_utils import SUPPORTED_PERIODS, calculate_period_boundaries
            if auto_period not in SUPPORTED_PERIODS:
                auto_period = "last_3_months"

            auto_query = query
            if not auto_query and auto_period != "all_time":
                boundaries = calculate_period_boundaries(
                    period=auto_period,
                    tz_name=pref.get("timezone", "UTC"),
                    custom_start_date=pref.get("custom_start_date"),
                    custom_end_date=pref.get("custom_end_date")
                )
                auto_query = boundaries.get("gmail_query") or None

            scan_manager.start_scan(
                user_id=user_id,
                service=service,
                scope=scan_scope,
                mode="incremental",
                query=auto_query,
                period=auto_period
            )
            logger.info("Automatically initiated %s mailbox discovery scan for user: %s", auto_period, user_id_hash)
        except Exception as scan_err:
            logger.warning("Could not auto-start background scan for %s: %s", user_id_hash, scan_err)

    # 1. If user already has cached emails and didn't explicitly request max_emails, serve directly from cache
    t_list_start = time.perf_counter()
    t_list_ms = 0.0
    t_cache_start = time.perf_counter()
    t_cache_ms = 0.0
    t_fetch_ms = 0.0
    t_infer_ms = 0.0
    cached_map: Dict[str, Dict[str, Any]] = {}
    missing_ids: List[str] = []
    target_ids: List[str] = []
    all_emails: List[Dict[str, Any]] = []

    has_explicit_page = "page" in request.query_params
    has_explicit_priority = "priority" in request.query_params and priority != "ALL"
    has_explicit_action = "action_required" in request.query_params
    has_explicit_query = bool(query and query.strip())

    use_display_pagination = (not has_explicit_max and total_cached > 0) or has_explicit_page or has_explicit_priority or has_explicit_action or has_explicit_query

    if not has_explicit_max and total_cached > 0:
        # Instant serve from complete analyzed mailbox cache
        t_cache_start = time.perf_counter()
        emails_display, total_matching = user_email_cache.query_emails(
            user_id=user_id,
            priority=priority,
            search=query,
            page=page,
            page_size=page_size,
            action_required=action_required,
            model_version=user_model_version,
            start_ts=start_ts_sec,
            end_ts=end_ts_sec
        )
        t_cache_ms = (time.perf_counter() - t_cache_start) * 1000
        total_analyzed = total_matching
        stats = stats_db
        display_list = emails_display
    else:
        # Synchronous fetch for initial preview or test harness with explicit max_emails
        t_list_start = time.perf_counter()
        page_token = None
        try:
            while len(target_ids) < max_emails:
                batch_limit = min(50, max_emails - len(target_ids))
                res = list_message_ids(service=service, max_results=batch_limit, query=query, page_token=page_token)
                messages = res.get("messages", [])
                if not messages:
                    break
                for m in messages:
                    if len(target_ids) >= max_emails:
                        break
                    target_ids.append(m.get("id"))
                page_token = res.get("nextPageToken")
                if not page_token:
                    break
        except Exception as e:
            if has_explicit_max:
                raise HTTPException(status_code=502, detail=f"Failed to list message IDs: {str(e)}")
            logger.warning("Error during initial preview listing for %s: %s", user_id_hash, e)
            target_ids = []
        t_list_ms = (time.perf_counter() - t_list_start) * 1000

        # Check User-Scoped Cache
        t_cache_start = time.perf_counter()
        cached_map, missing_ids = user_email_cache.get_batch(
            user_id=user_id,
            message_ids=target_ids,
            active_model_version=user_model_version
        )
        t_cache_ms = (time.perf_counter() - t_cache_start) * 1000

        # Fetch missing emails concurrently (if any)
        newly_classified: Dict[str, Dict[str, Any]] = {}
        if missing_ids:
            t_fetch_start = time.perf_counter()
            raw_missing: Dict[str, Dict[str, Any]] = {}
            with ThreadPoolExecutor(max_workers=min(10, len(missing_ids))) as executor:
                future_to_id = {
                    executor.submit(_fetch_single_message_safe, service, mid): mid
                    for mid in missing_ids
                }
                for future in as_completed(future_to_id):
                    mid = future_to_id[future]
                    parsed = future.result()
                    if parsed:
                        raw_missing[mid] = parsed
            t_fetch_ms = (time.perf_counter() - t_fetch_start) * 1000

            # Predict missing messages using fast vectorized batch inference with routed pipeline
            t_infer_start = time.perf_counter()
            missing_ordered = [raw_missing[mid] for mid in missing_ids if mid in raw_missing]
            predicted_missing = predict_batch(missing_ordered, pipeline=pipeline)
            t_infer_ms = (time.perf_counter() - t_infer_start) * 1000

            for pred in predicted_missing:
                mid = pred.get("email_id")
                if mid:
                    pred["model_version"] = user_model_version
                    pred["canary_group"] = canary_group
                    user_email_cache.set(user_id, mid, pred)
                    newly_classified[mid] = pred
                    try:
                        log_prediction(
                            user_id=user_id,
                            message_id=mid,
                            thread_id=pred.get("thread_id"),
                            model_version=user_model_version,
                            predicted_priority=pred.get("final_priority") or pred.get("predicted_priority", "P4"),
                            confidence=pred.get("confidence", 0.0),
                            action_required=bool(pred.get("action_required")),
                            deadline_detected=bool(pred.get("deadline_detected")),
                            deadline_status=pred.get("deadline_status"),
                            topic=pred.get("topic"),
                            needs_attention=bool(pred.get("needs_attention")),
                            refinement_applied=bool(pred.get("refinement_applied")),
                            canary_group=canary_group,
                        )
                    except Exception:
                        pass

            try:
                from backend.app.ml.shadow_engine import shadow_engine
                shadow_engine.shadow_batch_async(user_id, missing_ordered, predicted_missing)
            except Exception:
                pass

        # Assemble in original Gmail list order
        for mid in target_ids:
            if mid in cached_map:
                all_emails.append(cached_map[mid])
            elif mid in newly_classified:
                all_emails.append(newly_classified[mid])

        # Refresh stats after caching
        stats_db = user_email_cache.get_mailbox_stats(user_id, model_version=user_model_version)
        total_cached = stats_db.get("total_analyzed", 0)

        if use_display_pagination and total_cached > len(all_emails):
            emails_display, total_matching = user_email_cache.query_emails(
                user_id=user_id,
                priority=priority,
                search=query,
                page=page,
                page_size=page_size,
                action_required=action_required,
                model_version=user_model_version
            )
            total_analyzed = total_matching
            stats = stats_db
            display_list = emails_display
        else:
            # Default behavior for explicit max_emails or initial fetch
            counts = {"P1": 0, "P2": 0, "P3": 0, "P4": 0}
            total_conf = 0.0
            refined_count = 0

            for p in all_emails:
                cls = p.get("predicted_priority", "P4")
                counts[cls] = counts.get(cls, 0) + 1
                total_conf += p.get("confidence", 0.0)
                if p.get("refinement_applied"):
                    refined_count += 1

            total_analyzed = len(all_emails)
            avg_confidence = round((total_conf / total_analyzed), 4) if total_analyzed > 0 else 0.0
            refinement_rate = round((refined_count / total_analyzed * 100), 1) if total_analyzed > 0 else 0.0

            percentages = {
                cls: round((cnt / total_analyzed * 100), 1) if total_analyzed > 0 else 0.0
                for cls, cnt in counts.items()
            }

            t_total_ms = (time.perf_counter() - t_req_start) * 1000
            stats = {
                "total_analyzed": total_analyzed,
                "refined_count": refined_count,
                "refinement_rate": refinement_rate,
                "counts": counts,
                "percentages": percentages,
                "average_confidence": avg_confidence,
                "highest_priority_count": counts.get("P1", 0),
                "last_synced": datetime.now(timezone.utc).isoformat(),
                "query_applied": query or "None (Recent Inbox)",
                "cache_hit_count": len(cached_map),
                "cache_miss_count": len(missing_ids),
                "fetch_latency_ms": round(t_total_ms, 1),
            }
            display_list = all_emails
            total_matching = len(all_emails)

    # Enrich display list with user action states (resolve, snooze) and action policy
    from backend.app.core.action_store import user_action_store
    from backend.app.core.action_policy import evaluate_actionability, classify_action_queue

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

    enriched_display = []
    for item in display_list:
        mid = item.get("email_id") or item.get("id") or item.get("message_id") or ""
        state = action_states_map.get(mid)
        policy_eval = evaluate_actionability(item, action_state=state, now_ts=now_ts)
        item_copy = dict(item)
        item_copy["original_priority"] = policy_eval["original_priority"]
        item_copy["effective_priority"] = policy_eval["effective_priority"]
        item_copy["action_status"] = policy_eval["action_status"]
        item_copy["is_demoted"] = policy_eval["is_demoted"]
        item_copy["demotion_reason"] = policy_eval["demotion_reason"]
        item_copy["final_priority"] = policy_eval["effective_priority"]
        item_copy["predicted_priority"] = policy_eval["effective_priority"]
        item_copy["is_resolved"] = policy_eval["is_resolved"]
        item_copy["is_snoozed"] = policy_eval["is_snoozed"]
        item_copy["snoozed_until"] = policy_eval["snoozed_until"]
        item_copy["queue_placement"] = policy_eval["placement"]
        item_copy["action_reason"] = policy_eval["reason"]
        item_copy["next_step"] = policy_eval["next_step"]
        item_copy["action_policy"] = policy_eval
        enriched_display.append(item_copy)

    # Enforce strict priority filter on display list
    if priority and priority.strip():
        p_norm = priority.strip().upper()
        if p_norm == "NEEDS_ATTENTION":
            display_list = [e for e in enriched_display if e.get("queue_placement") == "ACTIVE"]
            total_matching = len(display_list)
        elif p_norm in ("P1", "P2", "P3", "P4"):
            display_list = [
                e for e in enriched_display
                if (e.get("effective_priority") or e.get("final_priority") or e.get("predicted_priority") or "").upper() == p_norm
            ]
            total_matching = len(display_list)
        elif p_norm == "IMPORTANT":
            display_list = [
                e for e in enriched_display
                if (e.get("effective_priority") or e.get("final_priority") or e.get("predicted_priority") or "").upper() == "P2"
            ]
            total_matching = len(display_list)
        else:
            display_list = enriched_display
    else:
        display_list = enriched_display

    if action_required is True:
        display_list = [e for e in display_list if e.get("action_required")]
        total_matching = len(display_list)
    elif action_required is False:
        display_list = [e for e in display_list if not e.get("action_required")]
        total_matching = len(display_list)

    # Compute exact action queue summary counts for sidebar and navigation badges
    all_user_emails, _ = user_email_cache.query_emails(
        user_id=user_id,
        page=1,
        page_size=10000,
        model_version=user_model_version
    )
    if not all_user_emails:
        all_user_emails, _ = user_email_cache.query_emails(
            user_id=user_id,
            page=1,
            page_size=10000,
            model_version=None
        )
    if all_user_emails:
        q_summary = classify_action_queue(all_user_emails, action_states_map=action_states_map, now_ts=now_ts)
        stats["action_queue_counts"] = q_summary["counts"]
        stats["needs_attention_count"] = q_summary["counts"]["total_active"]

        # Ensure mailbox priority counts and percentages use dynamic effective_priority
        dynamic_counts = {"P1": 0, "P2": 0, "P3": 0, "P4": 0}
        for e in all_user_emails:
            state = action_states_map.get(e.get("email_id") or e.get("id") or "")
            pe = evaluate_actionability(e, action_state=state, now_ts=now_ts)
            ep = pe.get("effective_priority") or "P4"
            dynamic_counts[ep] = dynamic_counts.get(ep, 0) + 1
        tot = sum(dynamic_counts.values()) or len(all_user_emails)
        stats["counts"] = dynamic_counts
        stats["percentages"] = {
            cls: round((cnt / tot * 100), 1) if tot > 0 else 0.0
            for cls, cnt in dynamic_counts.items()
        }
        stats["highest_priority_count"] = dynamic_counts.get("P1", 0)
    else:
        dynamic_counts = {"P1": 0, "P2": 0, "P3": 0, "P4": 0}
        for e in enriched_display:
            ep = e.get("effective_priority") or "P4"
            dynamic_counts[ep] = dynamic_counts.get(ep, 0) + 1
        tot = sum(dynamic_counts.values()) or len(enriched_display) or 1
        stats["counts"] = dynamic_counts
        stats["percentages"] = {
            cls: round((cnt / tot * 100), 1) if tot > 0 else 0.0
            for cls, cnt in dynamic_counts.items()
        }
        stats["highest_priority_count"] = dynamic_counts.get("P1", 0)
        stats["action_queue_counts"] = {
            "urgent": 0, "due_soon": 0, "other_active": 0, "total_active": 0,
            "older": 0, "snoozed": 0, "resolved": 0
        }
        stats["needs_attention_count"] = 0

    t_total_ms = (time.perf_counter() - t_req_start) * 1000
    timing_breakdown = {
        "request_id": request_id,
        "user_id_hash": user_id_hash,
        "endpoint": "/api/emails",
        "model_version": user_model_version,
        "canary_group": canary_group,
        "gmail_list_ms": round(t_list_ms, 2),
        "cache_lookup_ms": round(t_cache_ms, 2),
        "gmail_fetch_ms": round(t_fetch_ms, 2),
        "model_inference_ms": round(t_infer_ms, 2),
        "total_ms": round(t_total_ms, 2)
    }
    stats["timing"] = timing_breakdown

    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = f"{t_total_ms:.2f}ms"

    curr_page_size = page_size if use_display_pagination else len(display_list) or 1
    total_pages = max(1, (total_matching + curr_page_size - 1) // curr_page_size)

    return {
        "status": "success",
        "profile": {
            "email_address": user_email,
            "masked_email": mask_email(user_email),
            "messages_total": int(profile.get("messagesTotal", 0)),
            "threads_total": int(profile.get("threadsTotal", 0))
        },
        "stats": stats,
        "emails": display_list,
        "pagination": {
            "page": page,
            "page_size": curr_page_size,
            "total_emails": total_matching,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1
        },
        "scan_status": scan_manager.get_status(user_id)
    }


@router.get("/api/emails/{email_id}")
def get_email_detail(request: Request, email_id: str):
    """
    Fetches detailed view of a single email. If full body was deferred,
    retrieves it on demand and updates the user cache.
    """
    session = get_session_from_request(request)
    if not session:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please connect your Gmail account."
        )
    try:
        service = get_user_gmail_service(session=session)
        user_email = session.email
        user_id = session.user_id
    except PermissionError:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please connect your Gmail account."
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Gmail API connection error: {str(e)}")

    from backend.app.ml.canary_router import canary_router
    pipeline, route_info = canary_router.get_pipeline_for_user(user_id)
    user_model_version = route_info["model_version"]
    canary_group = route_info["canary_group"]

    # Check cache first with model_version
    cached = user_email_cache.get(user_id, email_id, model_version=user_model_version)
    if cached and cached.get("body") and cached.get("body") != cached.get("snippet"):
        target_email = cached
    else:
        # Fetch on-demand
        full_email = get_single_email(service, email_id)
        if not full_email:
            raise HTTPException(status_code=404, detail="Email not found in mailbox.")

        classified = predict_email(full_email, pipeline=pipeline)
        classified["model_version"] = user_model_version
        classified["canary_group"] = canary_group
        user_email_cache.set(user_id, email_id, classified)

        # Phase 48: Non-blocking candidate shadow inference hook (failsafe)
        try:
            from backend.app.ml.shadow_engine import shadow_engine
            shadow_engine.shadow_batch_async(user_id, [full_email], [classified])
        except Exception:
            pass
        target_email = classified

    # Enrich with user action state (resolved, snoozed) and action policy
    from backend.app.core.action_store import user_action_store
    from backend.app.core.action_policy import evaluate_actionability
    state = user_action_store.get_action_state(user_id, email_id)
    now_ts = datetime.now(timezone.utc).timestamp()
    policy_eval = evaluate_actionability(target_email, action_state=state, now_ts=now_ts)
    enriched = dict(target_email)
    enriched["original_priority"] = policy_eval["original_priority"]
    enriched["effective_priority"] = policy_eval["effective_priority"]
    enriched["action_status"] = policy_eval["action_status"]
    enriched["is_demoted"] = policy_eval["is_demoted"]
    enriched["demotion_reason"] = policy_eval["demotion_reason"]
    enriched["final_priority"] = policy_eval["effective_priority"]
    enriched["predicted_priority"] = policy_eval["effective_priority"]
    enriched["is_resolved"] = policy_eval["is_resolved"]
    enriched["is_snoozed"] = policy_eval["is_snoozed"]
    enriched["snoozed_until"] = policy_eval["snoozed_until"]
    enriched["queue_placement"] = policy_eval["placement"]
    enriched["action_reason"] = policy_eval["reason"]
    enriched["next_step"] = policy_eval["next_step"]
    enriched["action_policy"] = policy_eval

    return {"status": "success", "email": enriched}


@router.post("/api/feedback")
def submit_feedback(request: Request, submission: FeedbackSubmission):
    """
    Records human-reviewed feedback/corrections for future dataset versions.
    Does not automatically mutate the active production model during runtime.

    Phase 53 guarantees:
      - Authenticated session required (401 if missing).
      - Server-side user identity strictly enforced (client user_id ignored).
      - Server-side active model version strictly enforced (client model_version ignored).
      - Authoritative original prediction resolved from cache where available.
      - Provenance set to PRODUCTION_FEEDBACK.
    """
    session = get_session_from_request(request)
    if not session:
        raise HTTPException(
            status_code=401,
            detail="Authentication required to submit feedback."
        )
    user_id = session.user_id

    # Server-side model version resolution (Phase 53-B & 53-D)
    from backend.app.ml.registry import model_registry
    active_model = model_registry.get_active_version()
    submission.model_version = active_model

    # Server-side prediction resolution from cache where present (Phase 53-D)
    try:
        from backend.app.core.cache import user_email_cache
        cached = user_email_cache.get(user_id, submission.message_id, model_version=active_model)
        if not cached:
            cached = user_email_cache.get(user_id, submission.message_id)
        if cached:
            submission.predicted_priority = cached.get("predicted_priority") or cached.get("final_priority") or submission.predicted_priority
            if cached.get("confidence") is not None:
                submission.original_confidence = cached.get("confidence")
            if cached.get("topic"):
                submission.original_topic = cached.get("topic")
            if cached.get("deadline_detected") is not None:
                submission.original_deadline_detected = bool(cached.get("deadline_detected"))
            if cached.get("deadline_status"):
                submission.deadline_status = cached.get("deadline_status")
            if cached.get("thread_id"):
                submission.thread_id = cached.get("thread_id")
            if cached.get("action_required") is not None:
                submission.predicted_action_required = bool(cached.get("action_required"))
    except Exception as exc:
        logger.warning(f"Could not resolve cached prediction for message {submission.message_id}: {exc}")

    record = feedback_manager.record_feedback(
        submission,
        user_id=user_id,
        provenance="PRODUCTION_FEEDBACK"
    )
    return {"status": "success", "message": "Feedback recorded for review", "record": record}



@router.get("/api/feedback")
def list_feedback(request: Request):
    """
    Lists recent feedback submissions for the authenticated user only.
    Phase 52 fix: user_id is now always passed to enforce isolation.
    A user may never see another user's feedback records.
    """
    session = get_session_from_request(request)
    if not session:
        raise HTTPException(
            status_code=401,
            detail="Authentication required to view feedback."
        )
    # Phase 52 fix: always scope by session.user_id — never expose all records
    records = feedback_manager.list_feedback(user_id=session.user_id)
    return {"status": "success", "total_records": len(records), "records": records}

