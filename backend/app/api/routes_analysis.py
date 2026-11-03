"""
API Route Controller for Date-Based Email Analysis, Preferences, and Incremental Jobs.
Enforces multi-user isolation, idempotency, and frozen ML model immutability.
"""

import time
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator
from fastapi import APIRouter, HTTPException, Request, Query

from backend.app.core.session import get_session_from_request
from backend.app.core.cache import user_email_cache
from backend.app.core.date_utils import (
    calculate_period_boundaries,
    validate_date_range,
    SUPPORTED_PERIODS,
    DEFAULT_PERIOD,
    DEFAULT_TIMEZONE,
    resolve_timezone
)
from backend.app.gmail.service import get_user_gmail_service
from backend.app.gmail.scan_engine import scan_manager, ScanJobState
from backend.app.ml.registry import model_registry

logger = logging.getLogger("mailmind.analysis")
router = APIRouter(prefix="/api/analysis", tags=["Analysis"])


# -----------------------------------------------------------------------------
# Request & Response Schemas
# -----------------------------------------------------------------------------

class AnalysisConfigRequest(BaseModel):
    period: str = Field(..., description="Analysis period (this_month, last_3_months, last_1_year, all_time, custom)")
    timezone: Optional[str] = Field(default=DEFAULT_TIMEZONE, description="User IANA timezone")
    custom_start_date: Optional[str] = Field(None, description="Start date (YYYY-MM-DD) for custom period")
    custom_end_date: Optional[str] = Field(None, description="End date (YYYY-MM-DD) for custom period")

    @field_validator("period")
    @classmethod
    def validate_period(cls, v: str) -> str:
        clean = str(v).lower().strip()
        if clean not in SUPPORTED_PERIODS:
            raise ValueError(f"Unsupported period '{v}'. Must be one of: {list(SUPPORTED_PERIODS.keys())}")
        return clean


class AnalysisStartRequest(BaseModel):
    period: Optional[str] = Field(None, description="Analysis period")
    timezone: Optional[str] = Field(default=DEFAULT_TIMEZONE, description="User IANA timezone")
    start_date: Optional[str] = Field(None, description="Start date (YYYY-MM-DD) for custom period")
    end_date: Optional[str] = Field(None, description="End date (YYYY-MM-DD) for custom period")
    force_reanalysis: bool = Field(default=False, description="Whether to bypass cache and reanalyze")


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------

@router.get("/config")
def get_analysis_config(request: Request):
    """
    Returns the authenticated user's persisted date-analysis preference.
    Defaults to 'last_3_months' if no prior preference was saved.
    """
    session = get_session_from_request(request)
    if not session:
        raise HTTPException(status_code=401, detail="Authentication required. Please connect your Gmail account.")

    pref = user_email_cache.get_analysis_preference(session.user_id, session.email)
    return {
        "status": "success",
        "data": pref
    }


@router.put("/config")
def update_analysis_config(request: Request, body: AnalysisConfigRequest):
    """
    Updates the authenticated user's persisted date-analysis preference.
    Validates custom date boundaries and timezone.
    """
    session = get_session_from_request(request)
    if not session:
        raise HTTPException(status_code=401, detail="Authentication required. Please connect your Gmail account.")

    tz = resolve_timezone(body.timezone)
    tz_key = tz.key

    # Validate custom date range if selected
    if body.period == "custom":
        try:
            validate_date_range(body.custom_start_date, body.custom_end_date, tz_name=tz_key)
        except ValueError as val_err:
            raise HTTPException(status_code=422, detail=str(val_err))

    updated_pref = user_email_cache.set_analysis_preference(
        user_id=session.user_id,
        gmail_account_id=session.email,
        period=body.period,
        timezone_str=tz_key,
        custom_start_date=body.custom_start_date,
        custom_end_date=body.custom_end_date
    )

    # Determine if any unanalyzed eligible emails exist in this period
    boundaries = calculate_period_boundaries(
        period=body.period,
        tz_name=tz_key,
        custom_start_date=body.custom_start_date,
        custom_end_date=body.custom_end_date
    )

    return {
        "status": "success",
        "message": "Analysis configuration updated successfully.",
        "data": {
            **updated_pref,
            "date_boundaries": boundaries,
            "analysis_required": not scan_manager.is_scanning(session.user_id)
        }
    }


@router.get("/summary")
def get_analysis_summary(
    request: Request,
    period: Optional[str] = Query(default=None, description="Optional period override")
):
    """
    Returns metrics and coverage for the selected analysis period.
    Derived purely from actual database and scan status without fabricated metrics.
    """
    session = get_session_from_request(request)
    if not session:
        raise HTTPException(status_code=401, detail="Authentication required. Please connect your Gmail account.")

    user_id = session.user_id
    pref = user_email_cache.get_analysis_preference(user_id, session.email)
    target_period = (period or pref.get("period") or DEFAULT_PERIOD).lower().strip()
    if target_period not in SUPPORTED_PERIODS:
        target_period = DEFAULT_PERIOD

    boundaries = calculate_period_boundaries(
        period=target_period,
        tz_name=pref.get("timezone", DEFAULT_TIMEZONE),
        custom_start_date=pref.get("custom_start_date"),
        custom_end_date=pref.get("custom_end_date")
    )

    # Determine user active model version
    try:
        from backend.app.ml.canary_router import canary_router
        _, route_info = canary_router.get_pipeline_for_user(user_id)
        user_model_version = route_info.get("model_version")
    except Exception:
        user_model_version = model_registry.get_active_version()

    stats = user_email_cache.get_mailbox_stats(
        user_id=user_id,
        model_version=user_model_version,
        start_ts=boundaries["start_ts_sec"] if boundaries["start_ts_sec"] > 0 else None,
        end_ts=boundaries["end_ts_sec"]
    )

    total_cached = stats.get("total_analyzed", 0)

    # Check live background scan status
    is_scanning = scan_manager.is_scanning(user_id)
    scan_status = scan_manager.get_status(user_id)

    status_str = "running" if is_scanning else "completed" if total_cached > 0 else "idle"
    total_eligible = scan_status.get("total", total_cached) if is_scanning else total_cached
    analyzed_count = scan_status.get("analyzed", total_cached) if is_scanning else total_cached
    pending_count = max(0, total_eligible - analyzed_count) if is_scanning else 0
    failed_count = scan_status.get("failed", 0)
    reused_from_cache = scan_status.get("cached", total_cached) if is_scanning else total_cached

    prog_pct = round((analyzed_count / total_eligible * 100), 2) if total_eligible > 0 else 100.0 if total_cached > 0 else 0.0

    return {
        "status": "success",
        "data": {
            "period": target_period,
            "timezone": pref.get("timezone", DEFAULT_TIMEZONE),
            "date_boundaries": {
                "start_iso": boundaries["start_iso"],
                "end_iso": boundaries["end_iso"],
                "start_ts_ms": boundaries["start_ts_ms"],
                "end_ts_ms": boundaries["end_ts_ms"]
            },
            "total_eligible": total_eligible,
            "analyzed": analyzed_count,
            "pending": pending_count,
            "failed": failed_count,
            "reused_from_cache": reused_from_cache,
            "progress_percentage": prog_pct,
            "status": status_str,
            "last_analyzed_at": stats.get("last_synced")
        }
    }


@router.post("/start")
def start_analysis_job(request: Request, body: AnalysisStartRequest):
    """
    Initiates or resumes incremental background ML analysis for the requested period.
    Idempotent: Reuses existing active jobs and valid cached predictions.
    """
    session = get_session_from_request(request)
    if not session:
        raise HTTPException(status_code=401, detail="Authentication required. Please connect your Gmail account.")

    user_id = session.user_id
    pref = user_email_cache.get_analysis_preference(user_id, session.email)
    target_period = (body.period or pref.get("period") or DEFAULT_PERIOD).lower().strip()
    if target_period not in SUPPORTED_PERIODS:
        target_period = DEFAULT_PERIOD

    tz_str = body.timezone or pref.get("timezone", DEFAULT_TIMEZONE)
    tz = resolve_timezone(tz_str)

    custom_start = body.start_date or (pref.get("custom_start_date") if target_period == "custom" else None)
    custom_end = body.end_date or (pref.get("custom_end_date") if target_period == "custom" else None)

    if target_period == "custom":
        try:
            validate_date_range(custom_start, custom_end, tz_name=tz.key)
        except ValueError as val_err:
            raise HTTPException(status_code=422, detail=str(val_err))

    boundaries = calculate_period_boundaries(
        period=target_period,
        tz_name=tz.key,
        custom_start_date=custom_start,
        custom_end_date=custom_end
    )

    # Persist the selected period if different from current
    if target_period != pref.get("period"):
        user_email_cache.set_analysis_preference(
            user_id=user_id,
            gmail_account_id=session.email,
            period=target_period,
            timezone_str=tz.key,
            custom_start_date=custom_start,
            custom_end_date=custom_end
        )

    # Check if a scan is already active for this user
    if scan_manager.is_scanning(user_id):
        active_status = scan_manager.get_status(user_id)
        latest_job = user_email_cache.get_latest_analysis_job(user_id)
        job_id = latest_job["job_id"] if latest_job else f"job_{user_id[:8]}"
        return {
            "status": "success",
            "message": "Analysis job already running.",
            "data": {
                "job_id": job_id,
                "status": "running",
                "period": target_period,
                "total_eligible": active_status.get("total", 0),
                "already_analyzed": active_status.get("analyzed", 0),
                "pending": max(0, active_status.get("total", 0) - active_status.get("analyzed", 0)),
                "reused_from_cache": active_status.get("cached", 0)
            }
        }

    # Verify Gmail service connectivity
    try:
        service = get_user_gmail_service(session=session)
    except PermissionError:
        raise HTTPException(status_code=401, detail="Authentication required. Please connect your Gmail account.")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Gmail API connection error: {str(e)}")

    # Check cached stats in date range
    try:
        from backend.app.ml.canary_router import canary_router
        _, route_info = canary_router.get_pipeline_for_user(user_id)
        user_model_version = route_info.get("model_version")
    except Exception:
        user_model_version = model_registry.get_active_version()

    stats = user_email_cache.get_mailbox_stats(
        user_id=user_id,
        model_version=user_model_version,
        start_ts=boundaries["start_ts_sec"] if boundaries["start_ts_sec"] > 0 else None,
        end_ts=boundaries["end_ts_sec"]
    )
    cached_count = stats.get("total_analyzed", 0)

    # Create persistent job in database
    job_record, is_new = user_email_cache.create_or_get_analysis_job(
        user_id=user_id,
        gmail_account_id=session.email,
        period=target_period,
        start_date=boundaries["start_iso"],
        end_date=boundaries["end_iso"],
        total_eligible=cached_count,
        already_analyzed=cached_count,
        reused_from_cache=cached_count
    )

    # Launch background scan engine scoped to date boundaries
    scan_manager.start_scan(
        user_id=user_id,
        service=service,
        scope="mailbox",
        mode="full" if body.force_reanalysis else "incremental",
        query=boundaries["gmail_query"] or None,
        force_rescan=body.force_reanalysis,
        period=target_period,
        analysis_job_id=job_record["job_id"]
    )

    return {
        "status": "success",
        "data": {
            "job_id": job_record["job_id"],
            "status": "running",
            "period": target_period,
            "total_eligible": cached_count,
            "already_analyzed": cached_count,
            "pending": 0,
            "reused_from_cache": cached_count,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
    }


@router.get("/status")
def get_analysis_status(
    request: Request,
    job_id: Optional[str] = Query(default=None, description="Optional job ID to inspect")
):
    """
    Returns current analysis job progress and metrics.
    """
    session = get_session_from_request(request)
    if not session:
        raise HTTPException(status_code=401, detail="Authentication required. Please connect your Gmail account.")

    user_id = session.user_id

    # If specific job_id requested, retrieve from DB
    if job_id:
        db_job = user_email_cache.get_analysis_job(job_id)
        if not db_job or db_job["user_id"] != user_id:
            raise HTTPException(status_code=404, detail="Analysis job not found.")
        total = db_job.get("total_eligible", 0)
        proc = db_job.get("processed_count", 0)
        pct = round((proc / total * 100), 2) if total > 0 else (100.0 if db_job["status"] == "completed" else 0.0)
        return {
            "status": "success",
            "data": {
                "job_id": db_job["job_id"],
                "status": db_job["status"],
                "period": db_job["period"],
                "total_eligible": total,
                "processed": proc,
                "pending": max(0, total - proc),
                "failed": db_job.get("failed_count", 0),
                "reused_from_cache": db_job.get("reused_from_cache", 0),
                "progress_percentage": pct,
                "started_at": datetime.fromtimestamp(db_job["created_at"], timezone.utc).isoformat() if db_job.get("created_at") else None,
                "updated_at": datetime.fromtimestamp(db_job["updated_at"], timezone.utc).isoformat() if db_job.get("updated_at") else None,
                "completed_at": datetime.fromtimestamp(db_job["completed_at"], timezone.utc).isoformat() if db_job.get("completed_at") else None,
                "error": db_job.get("error")
            }
        }

    # Otherwise return live background scan status combined with latest DB job
    scan_status = scan_manager.get_status(user_id)
    is_scanning = scan_manager.is_scanning(user_id)
    latest_job = user_email_cache.get_latest_analysis_job(user_id)

    status_str = "running" if is_scanning else (latest_job["status"] if latest_job else "idle")
    total = scan_status.get("total", 0) or (latest_job.get("total_eligible", 0) if latest_job else 0)
    analyzed = scan_status.get("analyzed", 0) or (latest_job.get("processed_count", 0) if latest_job else 0)
    pending = max(0, total - analyzed) if is_scanning else 0
    pct = scan_status.get("progress_percent", 0.0)
    if not is_scanning and total > 0:
        pct = 100.0

    return {
        "status": "success",
        "data": {
            "job_id": latest_job["job_id"] if latest_job else f"job_{user_id[:8]}",
            "status": status_str,
            "period": scan_status.get("period") or (latest_job.get("period") if latest_job else DEFAULT_PERIOD),
            "total_eligible": total,
            "processed": analyzed,
            "pending": pending,
            "failed": scan_status.get("failed", 0),
            "reused_from_cache": scan_status.get("cached", 0),
            "progress_percentage": pct,
            "started_at": scan_status.get("started_at"),
            "updated_at": scan_status.get("updated_at"),
            "completed_at": scan_status.get("completed_at"),
            "error": scan_status.get("error")
        }
    }
