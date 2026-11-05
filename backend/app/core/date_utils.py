"""
Date range calculation, validation, and Gmail query formatting for MailMind.
Supports calendar-month subtraction and timezone-aware boundary computation.
All internal boundaries are returned as strict UTC timestamps and ISO 8601 strings.
"""

from datetime import datetime, timezone, timedelta, time as dt_time
from typing import Dict, Any, Optional, Tuple
from zoneinfo import ZoneInfo
from dateutil.relativedelta import relativedelta


SUPPORTED_PERIODS = {
    "last_1_month": "Last 1 month",
    "last_2_months": "Last 2 months",
    "last_3_months": "Last 3 months",
    "this_month": "This month",
    "last_1_year": "Last 1 year",
    "last_year": "Last 1 year",
    "all_time": "All time",
    "custom": "Custom date range"
}

DEFAULT_PERIOD = "last_3_months"
DEFAULT_TIMEZONE = "UTC"


def resolve_timezone(tz_name: Optional[str] = None) -> ZoneInfo:
    """Safely resolves an IANA timezone string, falling back to UTC if None or invalid."""
    if not tz_name or not str(tz_name).strip():
        return ZoneInfo("UTC")
    try:
        return ZoneInfo(str(tz_name).strip())
    except Exception:
        return ZoneInfo("UTC")


def validate_date_range(
    start_date: Optional[str],
    end_date: Optional[str],
    tz_name: str = "UTC"
) -> Tuple[datetime, datetime]:
    """
    Validates a custom date range.
    Ensures:
      - Both start_date and end_date are provided and conform to YYYY-MM-DD.
      - start_date <= end_date.
      - end_date is not in the future relative to the given timezone.
    Returns:
      (start_datetime_utc, end_datetime_utc)
    Raises:
      ValueError if any validation rule is violated.
    """
    if not start_date or not str(start_date).strip():
        raise ValueError("start_date is required for custom period.")
    if not end_date or not str(end_date).strip():
        raise ValueError("end_date is required for custom period.")

    tz = resolve_timezone(tz_name)
    now_local = datetime.now(tz)
    today_local = now_local.date()

    try:
        s_date = datetime.strptime(str(start_date).strip(), "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(f"Invalid start_date '{start_date}'. Must be in YYYY-MM-DD format.")

    try:
        e_date = datetime.strptime(str(end_date).strip(), "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(f"Invalid end_date '{end_date}'. Must be in YYYY-MM-DD format.")

    if s_date > e_date:
        raise ValueError(f"start_date ({start_date}) cannot be after end_date ({end_date}).")

    if e_date > today_local:
        raise ValueError(f"end_date ({end_date}) cannot be in the future (today is {today_local.isoformat()}).")

    # Start boundary: 00:00:00 of s_date in user timezone
    start_local = datetime.combine(s_date, dt_time.min, tzinfo=tz)
    
    # End boundary: if e_date is today, end at current time; otherwise 23:59:59.999999 of e_date
    if e_date == today_local:
        end_local = now_local
    else:
        end_local = datetime.combine(e_date, dt_time.max, tzinfo=tz)

    start_utc = start_local.astimezone(timezone.utc)
    end_utc = end_local.astimezone(timezone.utc)
    return start_utc, end_utc


def calculate_period_boundaries(
    period: str = DEFAULT_PERIOD,
    tz_name: str = DEFAULT_TIMEZONE,
    custom_start_date: Optional[str] = None,
    custom_end_date: Optional[str] = None,
    now: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Computes precise start and end boundaries for an analysis period.
    Uses calendar-month subtraction (via relativedelta) for 'last_3_months' and 'last_1_year'.
    
    Returns a dictionary containing:
      - period: canonical period string
      - timezone: resolved timezone string
      - start_iso: UTC ISO 8601 string (or None for all_time)
      - end_iso: UTC ISO 8601 string
      - start_ts_sec: UTC Unix timestamp in seconds (or 0.0 for all_time)
      - end_ts_sec: UTC Unix timestamp in seconds
      - start_ts_ms: UTC Unix timestamp in milliseconds (or 0 for all_time)
      - end_ts_ms: UTC Unix timestamp in milliseconds
      - gmail_query: Gmail search filter syntax string (e.g. 'after:YYYY/MM/DD')
    """
    period_clean = str(period).lower().strip() if period else DEFAULT_PERIOD
    if period_clean == "last_year":
        period_clean = "last_1_year"
    if period_clean not in SUPPORTED_PERIODS:
        period_clean = DEFAULT_PERIOD

    tz = resolve_timezone(tz_name)
    now_utc = now.astimezone(timezone.utc) if now else datetime.now(timezone.utc)
    now_local = now_utc.astimezone(tz)

    start_utc: Optional[datetime] = None
    end_utc: datetime = now_utc

    if period_clean == "this_month":
        # First day of the current calendar month at 00:00:00 in user timezone
        first_of_month = now_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        start_utc = first_of_month.astimezone(timezone.utc)

    elif period_clean == "last_1_month":
        # Current time minus 1 calendar month preserving time of day
        one_month_ago = now_local - relativedelta(months=1)
        start_utc = one_month_ago.astimezone(timezone.utc)

    elif period_clean == "last_2_months":
        # Current time minus 2 calendar months preserving time of day
        two_months_ago = now_local - relativedelta(months=2)
        start_utc = two_months_ago.astimezone(timezone.utc)

    elif period_clean == "last_3_months":
        # Current time minus 3 calendar months preserving time of day
        three_months_ago = now_local - relativedelta(months=3)
        start_utc = three_months_ago.astimezone(timezone.utc)

    elif period_clean == "last_1_year":
        # Current time minus 12 calendar months preserving time of day
        one_year_ago = now_local - relativedelta(years=1)
        start_utc = one_year_ago.astimezone(timezone.utc)

    elif period_clean == "all_time":
        # Earliest available mailbox timestamp (Epoch 0)
        start_utc = datetime(1970, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    elif period_clean == "custom":
        if custom_start_date and custom_end_date:
            start_utc, end_utc = validate_date_range(custom_start_date, custom_end_date, tz_name=tz.key)
        else:
            # Fallback to last_3_months if custom dates missing
            period_clean = "last_3_months"
            three_months_ago = now_local - relativedelta(months=3)
            start_utc = three_months_ago.astimezone(timezone.utc)

    # Calculate timestamps
    start_ts_sec = start_utc.timestamp() if start_utc else 0.0
    end_ts_sec = end_utc.timestamp()
    start_ts_ms = int(start_ts_sec * 1000)
    end_ts_ms = int(end_ts_sec * 1000)

    # Gmail search query construction:
    # Gmail API query syntax uses 'after:YYYY/MM/DD' and 'before:YYYY/MM/DD' in integer days.
    # Buffer by 1 day earlier for 'after:' to avoid boundary drops due to timezone offsets.
    gmail_query = ""
    if period_clean != "all_time" and start_utc and start_utc.year > 1970:
        buffer_start = (start_utc - timedelta(days=1)).strftime("%Y/%m/%d")
        if period_clean == "custom" and custom_end_date:
            try:
                e_date_obj = datetime.strptime(custom_end_date, "%Y-%m-%d").date()
                buffer_end = (e_date_obj + timedelta(days=1)).strftime("%Y/%m/%d")
                gmail_query = f"after:{buffer_start} before:{buffer_end}"
            except Exception:
                gmail_query = f"after:{buffer_start}"
        else:
            gmail_query = f"after:{buffer_start}"

    return {
        "period": period_clean,
        "timezone": tz.key,
        "start_iso": start_utc.isoformat() if start_utc and start_utc.year > 1970 else None,
        "end_iso": end_utc.isoformat(),
        "start_ts_sec": start_ts_sec,
        "end_ts_sec": end_ts_sec,
        "start_ts_ms": start_ts_ms,
        "end_ts_ms": end_ts_ms,
        "gmail_query": gmail_query
    }

