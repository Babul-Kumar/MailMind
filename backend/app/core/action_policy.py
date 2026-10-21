"""
ActionPolicy — Deterministic actionability engine and queue classification.
Separates machine learning priority classification (P1-P4) from human actionability.
Applies:
  - 8-Day Age Policy with exact boundary cutoff (8.0 days / 691,200 seconds).
  - Exceptions for verified upcoming deadlines and unresolved critical incidents.
  - Intelligent handling of expired actions (e.g. OTP/verification codes leave active queue).
  - Conservative deadline categorization (upcoming, overdue, expired, uncertain, none).
  - Non-mutation: zero modifications to Gmail messages or ML model predictions.
"""

import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Dict, Any, List, Optional, Tuple, Set

DEFAULT_AGE_THRESHOLD_DAYS: float = 8.0
AGE_THRESHOLD_SECONDS: float = DEFAULT_AGE_THRESHOLD_DAYS * 86400.0  # Exactly 691,200.0 seconds

# Regex for detecting genuine critical security incidents or infrastructure breaches
CRITICAL_INCIDENT_PATTERN = re.compile(
    r"\b("
    r"suspicious (?:sign-in|login|activity)|"
    r"unauthorized (?:access|sign-in|login|transaction|activity)|"
    r"account (?:compromised|breached|locked|suspended)|"
    r"security breach|credentials (?:compromised|leaked)|"
    r"someone may have accessed your account|"
    r"service suspension notice|final notice before suspension|"
    r"account suspended due to non-payment|"
    r"(?:production|database|cluster|system|server)\s+(?:outage|down|failure|incident|unresponsive)|"
    r"critical (?:alert|incident|outage|failure)|"
    r"service (?:outage|down)"
    r")\b",
    re.IGNORECASE
)

def parse_timestamp_safe(val: Any) -> float:
    """Safely converts numeric or ISO string timestamp to epoch float."""
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        try:
            return float(val)
        except ValueError:
            try:
                clean = val.replace("Z", "+00:00")
                dt = datetime.fromisoformat(clean)
                return dt.timestamp()
            except Exception:
                pass
    return 0.0

# Regex for detecting OTP / verification code emails
OTP_PATTERN = re.compile(
    r"\b("
    r"verification code|one-time (?:password|passcode)|\botp\b|"
    r"two-factor authentication code|2fa code|security code|"
    r"login verification code|confirm your email code|"
    r"valid for \d+ (?:minutes?|mins?)"
    r")\b",
    re.IGNORECASE
)

# Regex for closed registration / expired event opportunities
CLOSED_OPPORTUNITY_PATTERN = re.compile(
    r"\b("
    r"registration (?:is now closed|has closed|ended)|"
    r"contest (?:has ended|is closed)|"
    r"applications? (?:are now closed|have closed|closed on)"
    r")\b",
    re.IGNORECASE
)


def get_email_timestamp(email: Dict[str, Any]) -> float:
    """
    Extracts the received timestamp of an email in seconds since Unix epoch.
    Prioritizes internal_date (integer ms epoch), then date string parsing.
    Returns 0.0 if timestamp cannot be determined safely.
    """
    internal_date = email.get("internal_date")
    if internal_date is not None:
        try:
            val = float(internal_date)
            # If in milliseconds (> 1e11), convert to seconds
            if val > 1e11:
                return val / 1000.0
            return val
        except (ValueError, TypeError):
            pass

    date_str = email.get("date") or email.get("date_str")
    if date_str:
        try:
            dt = parsedate_to_datetime(date_str)
            return dt.timestamp()
        except Exception:
            pass
        try:
            clean = date_str.replace("Z", "+00:00")
            dt = datetime.fromisoformat(clean)
            return dt.timestamp()
        except Exception:
            pass

    return 0.0


def calculate_email_age_seconds(email: Dict[str, Any], now_ts: Optional[float] = None) -> float:
    """
    Calculates email age in seconds from current time.
    Uses UTC epoch consistently.
    """
    if now_ts is None:
        now_ts = datetime.now(timezone.utc).timestamp()
    email_ts = get_email_timestamp(email)
    if email_ts <= 0:
        return 0.0
    return max(0.0, now_ts - email_ts)


def is_critical_incident(email: Dict[str, Any]) -> bool:
    """
    Determines if an email represents an unresolved critical security incident
    or severe operational threat (e.g. breach, account lock, compromised credentials).
    """
    subject = str(email.get("subject") or "")
    snippet = str(email.get("snippet") or "")
    body = str(email.get("body") or "")
    text = f"{subject} {snippet} {body[:500]}"
    return bool(CRITICAL_INCIDENT_PATTERN.search(text))


def is_otp_or_verification_code(email: Dict[str, Any]) -> bool:
    """
    Determines if an email is a temporary OTP or verification code.
    """
    subject = str(email.get("subject") or "")
    snippet = str(email.get("snippet") or "")
    body = str(email.get("body") or "")
    text = f"{subject} {snippet} {body[:500]}"
    return bool(OTP_PATTERN.search(text))


def evaluate_deadline_state(
    email: Dict[str, Any],
    now_ts: Optional[float] = None
) -> Tuple[str, Optional[str], Optional[str]]:
    """
    Evaluates conservative deadline state:
    Returns (status, display_text, next_step)
    Statuses:
      - 'UPCOMING': verified future deadline
      - 'OVERDUE': past deadline, but still actionable (e.g. late bill, assignment)
      - 'EXPIRED': deadline passed and action is no longer possible (e.g. OTP, closed registration)
      - 'UNCERTAIN': ambiguous date or unclear deadline
      - 'NONE': no deadline detected
    """
    if now_ts is None:
        now_ts = datetime.now(timezone.utc).timestamp()

    deadline_detected = bool(email.get("deadline_detected"))
    raw_status = (email.get("deadline_status") or "NONE").upper()
    deadline_dt_str = email.get("deadline_datetime")
    deadline_disp = email.get("deadline_display")
    subject = str(email.get("subject") or "")
    snippet = str(email.get("snippet") or "")
    text = f"{subject} {snippet}"

    if is_otp_or_verification_code(email):
        # OTPs are time-bounded to minutes
        age_sec = calculate_email_age_seconds(email, now_ts)
        # If older than 15 minutes, verification code is definitively expired
        if age_sec > 900.0 or raw_status == "EXPIRED":
            return "EXPIRED", "Code expired", "Request a new verification code"
        return "UPCOMING", deadline_disp or "Valid for a few minutes", "Enter code to verify"

    if CLOSED_OPPORTUNITY_PATTERN.search(text):
        return "EXPIRED", "Registration closed", "Check if registration has been extended or contact organizer"

    if not deadline_detected or not deadline_dt_str:
        if raw_status in ("ACTIVE", "OVERDUE"):
            return raw_status, deadline_disp, None
        return "NONE", None, None

    # Parse ISO deadline string to compare with now_ts
    try:
        clean_dl = deadline_dt_str[:19]
        if "T" in clean_dl:
            dl_dt = datetime.fromisoformat(clean_dl).replace(tzinfo=timezone.utc)
        else:
            dl_dt = datetime.strptime(clean_dl, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        dl_ts = dl_dt.timestamp()

        if dl_ts >= now_ts:
            # Future deadline
            diff_hours = (dl_ts - now_ts) / 3600.0
            if diff_hours <= 24.0:
                disp = "Due tomorrow" if diff_hours > 12 else "Due today"
            else:
                disp = deadline_disp or f"Due {dl_dt.strftime('%b %d')}"
            return "UPCOMING", disp, "Complete before deadline"
        else:
            # Past deadline - check if overdue or expired
            topic = str(email.get("topic") or "").lower()
            subject_body = f"{email.get('subject', '')} {email.get('body', '')}".lower()
            if "bill" in topic or "payment" in topic or "academic" in topic or any(w in subject_body for w in ["bill", "payment", "overdue", "assignment", "due"]):
                # Bills, payments, assignments remain overdue and actionable!
                return "OVERDUE", deadline_disp or "Overdue", "Review overdue task and complete payment or submission"
            
            diff_days = (now_ts - dl_ts) / 86400.0
            if diff_days <= 30.0:
                return "OVERDUE", deadline_disp or "Overdue", "Review task or contact sender"
            return "EXPIRED", deadline_disp or "Deadline passed", "Check if late submission is accepted"
    except Exception:
        # Date string was ambiguous or malformed
        return "UNCERTAIN", "Deadline unclear", "Review email for specific dates"


def evaluate_actionability(
    email: Dict[str, Any],
    action_state: Optional[Dict[str, Any]] = None,
    now_ts: Optional[float] = None,
    age_threshold_days: float = DEFAULT_AGE_THRESHOLD_DAYS
) -> Dict[str, Any]:
    """
    Evaluates an email's placement in the Smart Action Queue.
    Distinguishes:
      - Priority: ML classified priority (P1-P4) — preserved untouched.
      - Actionability: Whether an active task still exists.
      - Resolution: Persistent resolution state from user.
      - Snooze: Persistent snooze state until return time.
      - Placement:
          'ACTIVE': in Needs Attention active queue
          'OLDER': in Older actions collapsible section
          'RESOLVED': resolved by user
          'SNOOZED': currently snoozed
          'EXCLUDED': not actionable or expired with no remaining task
    """
    if now_ts is None:
        now_ts = datetime.now(timezone.utc).timestamp()

    age_threshold_sec = age_threshold_days * 86400.0
    age_sec = calculate_email_age_seconds(email, now_ts)
    age_days = round(age_sec / 86400.0, 2)

    priority = str(email.get("final_priority") or email.get("predicted_priority") or "P4").upper()
    action_required = bool(email.get("action_required"))
    if not action_required:
        subject = str(email.get("subject") or "")
        snippet = str(email.get("snippet") or "")
        body = str(email.get("body") or "")
        text = f"{subject} {snippet} {body[:500]}".strip()
        if text:
            from backend.app.ml.refinement import evaluate_action_layer
            dyn_req, dyn_reason, dyn_ev = evaluate_action_layer(subject, f"{snippet} {body[:500]}", priority)
            if dyn_req:
                action_required = True
                if not email.get("action_reason") and dyn_reason:
                    email["action_reason"] = dyn_reason
                if not email.get("action_evidence") and dyn_ev:
                    email["action_evidence"] = dyn_ev

    critical_incident = is_critical_incident(email)
    otp_email = is_otp_or_verification_code(email)

    # 1. Check user persistent action state (resolved or snoozed)
    is_resolved = False
    resolved_at = None
    is_snoozed = False
    snoozed_until = None

    if action_state:
        is_resolved = bool(action_state.get("is_resolved"))
        resolved_at = action_state.get("resolved_at")
        snoozed_until = action_state.get("snoozed_until")
        if snoozed_until:
            s_ts = parse_timestamp_safe(snoozed_until)
            if s_ts > now_ts:
                is_snoozed = True

    if is_resolved:
        return {
            "placement": "RESOLVED",
            "is_actionable": False,
            "is_resolved": True,
            "resolved_at": resolved_at,
            "is_snoozed": False,
            "snoozed_until": None,
            "age_days": age_days,
            "priority": priority,
            "reason": "Resolved by user",
            "deadline_status": "NONE",
            "deadline_display": None,
            "next_step": None,
            "is_critical_incident": critical_incident,
        }

    if is_snoozed:
        s_ts = parse_timestamp_safe(snoozed_until)
        s_disp = datetime.fromtimestamp(s_ts, tz=timezone.utc).strftime('%b %d, %H:%M UTC') if s_ts > 0 else str(snoozed_until)
        return {
            "placement": "SNOOZED",
            "is_actionable": True,
            "is_resolved": False,
            "resolved_at": None,
            "is_snoozed": True,
            "snoozed_until": snoozed_until,
            "age_days": age_days,
            "priority": priority,
            "reason": f"Snoozed until {s_disp}",
            "deadline_status": "NONE",
            "deadline_display": None,
            "next_step": "Awaiting snooze expiration",
            "is_critical_incident": critical_incident,
        }

    # 2. Evaluate Deadline Status and intelligent expiry
    dl_status, dl_disp, next_step = evaluate_deadline_state(email, now_ts)

    # 3. Check for expired actions (e.g. OTP older than validity period)
    if otp_email:
        if dl_status == "EXPIRED" or age_sec > 900.0:  # > 15 mins
            return {
                "placement": "EXCLUDED",
                "is_actionable": False,
                "is_resolved": False,
                "resolved_at": None,
                "is_snoozed": False,
                "snoozed_until": None,
                "age_days": age_days,
                "priority": priority,
                "reason": "Verification code expired",
                "deadline_status": "EXPIRED",
                "deadline_display": dl_disp,
                "next_step": next_step or "Request a new verification code",
                "is_critical_incident": False,
            }

    if dl_status == "EXPIRED" and not action_required and not critical_incident:
        return {
            "placement": "EXCLUDED",
            "is_actionable": False,
            "is_resolved": False,
            "resolved_at": None,
            "is_snoozed": False,
            "snoozed_until": None,
            "age_days": age_days,
            "priority": priority,
            "reason": "Opportunity or deadline has expired",
            "deadline_status": "EXPIRED",
            "deadline_display": dl_disp,
            "next_step": next_step,
            "is_critical_incident": False,
        }

    # 4. Determine baseline actionability
    # An email is actionable if:
    # - action_required is True
    # - OR has an upcoming or overdue deadline
    # - OR is a critical security/operational incident
    # - OR is P1/P2 with operational relevance
    is_actionable = (
        action_required or
        dl_status in ("UPCOMING", "OVERDUE") or
        critical_incident or
        (priority == "P1") or
        (priority == "P2" and action_required)
    )

    if not is_actionable:
        return {
            "placement": "EXCLUDED",
            "is_actionable": False,
            "is_resolved": False,
            "resolved_at": None,
            "is_snoozed": False,
            "snoozed_until": None,
            "age_days": age_days,
            "priority": priority,
            "reason": "Informational or non-actionable",
            "deadline_status": dl_status,
            "deadline_display": dl_disp,
            "next_step": None,
            "is_critical_incident": False,
        }

    # Determine concise, meaningful reason why it needs attention
    if critical_incident:
        reason = "Critical security incident or account alert"
    elif dl_status == "UPCOMING":
        reason = f"Upcoming deadline: {dl_disp}" if dl_disp else "Upcoming deadline"
    elif dl_status == "OVERDUE":
        reason = f"Overdue task: {dl_disp}" if dl_disp else "Overdue task requiring action"
    elif email.get("action_reason"):
        reason = email.get("action_reason")
    elif priority == "P1":
        reason = "High priority operational request"
    elif priority == "P2":
        reason = "Action required on important email"
    else:
        reason = "Action required"

    # 5. Apply the 8-Day Age Policy and its exceptions
    # Boundary condition:
    # age_sec <= age_threshold_sec: eligible for active queue
    # age_sec > age_threshold_sec: moves to older actions UNLESS an exception applies
    is_within_threshold = (age_sec <= age_threshold_sec)

    # Exceptions to 8-day rule:
    # Exception 1: Active upcoming future deadline that warrants continued attention
    has_active_future_deadline = (dl_status == "UPCOMING")
    # Exception 2: Unresolved critical incident (security breach, compromised account)
    has_unresolved_incident = critical_incident

    # Rule: Old P1 emails without a meaningful unresolved critical incident or active future deadline
    # do NOT bypass the age rule!
    if is_within_threshold:
        placement = "ACTIVE"
    else:
        if has_active_future_deadline or has_unresolved_incident:
            placement = "ACTIVE"
        else:
            placement = "OLDER"

    return {
        "placement": placement,
        "is_actionable": True,
        "is_resolved": False,
        "resolved_at": None,
        "is_snoozed": False,
        "snoozed_until": None,
        "age_days": age_days,
        "age_seconds": age_sec,
        "priority": priority,
        "reason": reason,
        "deadline_status": dl_status,
        "deadline_display": dl_disp,
        "next_step": ("Resolve urgent incident immediately" if critical_incident else (next_step or email.get("action_evidence", {}).get("next_step") or email.get("next_step") or ("Review email and respond" if action_required else "Review details"))),
        "is_critical_incident": critical_incident,
    }


def sort_action_items(items: List[Dict[str, Any]], sort_by: str = "urgent") -> List[Dict[str, Any]]:
    """
    Sorts actionable items deterministically with tie-breaking on (internal_date, message_id).
    Options:
      - 'urgent': Critical/P1 first, then due soonest, then newest
      - 'newest': Newest arrival date first
      - 'oldest': Oldest arrival date first (ideal for Older actions review)
      - 'deadline': Earliest deadline first
    """
    priority_order = {"P1": 0, "P2": 1, "P3": 2, "P4": 3}

    def _sort_key(item: Dict[str, Any]):
        policy = item.get("action_policy") or {}
        p_val = priority_order.get(item.get("predicted_priority") or item.get("final_priority"), 4)
        ts = get_email_timestamp(item)
        mid = str(item.get("email_id") or item.get("id") or item.get("message_id") or "")
        dl_status = policy.get("deadline_status", "NONE")
        is_crit = 0 if policy.get("is_critical_incident") else 1

        if sort_by == "oldest":
            # Oldest date first, then mid
            return (ts, mid)
        elif sort_by == "newest":
            # Newest date first (descending timestamp)
            return (-ts, mid)
        elif sort_by == "deadline":
            # UPCOMING first, then OVERDUE, then none
            dl_order = 0 if dl_status == "UPCOMING" else (1 if dl_status == "OVERDUE" else 2)
            dl_dt_str = item.get("deadline_datetime") or "9999-99-99"
            return (dl_order, dl_dt_str, -ts, mid)
        else:  # 'urgent' default
            # Critical incident first, then P1->P4, then upcoming deadline, then newest
            dl_order = 0 if dl_status in ("UPCOMING", "OVERDUE") else 1
            return (is_crit, p_val, dl_order, -ts, mid)

    return sorted(items, key=_sort_key)


def classify_action_queue(
    emails: List[Dict[str, Any]],
    action_states_map: Dict[str, Dict[str, Any]],
    now_ts: Optional[float] = None,
    age_threshold_days: float = DEFAULT_AGE_THRESHOLD_DAYS,
    sort_by: str = "urgent",
    older_sort_by: str = "oldest"
) -> Dict[str, Any]:
    """
    Processes a list of emails against the ActionPolicy and persistent user states.
    Produces:
      - active_queue: Items needing attention right now
      - older_actions: Collapsible items older than threshold without bypass
      - snoozed_items: Items temporarily hidden
      - resolved_items: Items marked resolved
      - exact counts:
          urgent_count
          due_soon_count
          other_active_count
          total_active_count
          older_count
          snoozed_count
          resolved_count
    """
    if now_ts is None:
        now_ts = datetime.now(timezone.utc).timestamp()

    active_queue = []
    older_actions = []
    snoozed_items = []
    resolved_items = []

    urgent_count = 0
    due_soon_count = 0
    other_active_count = 0

    for email in emails:
        mid = email.get("email_id") or email.get("id") or email.get("message_id") or ""
        state = action_states_map.get(mid)
        policy_eval = evaluate_actionability(
            email=email,
            action_state=state,
            now_ts=now_ts,
            age_threshold_days=age_threshold_days
        )

        # Attach evaluated policy to email copy
        email_augmented = dict(email)
        email_augmented["action_policy"] = policy_eval
        # Also attach top-level convenience flags for UI
        email_augmented["is_resolved"] = policy_eval["is_resolved"]
        email_augmented["is_snoozed"] = policy_eval["is_snoozed"]
        email_augmented["snoozed_until"] = policy_eval["snoozed_until"]
        email_augmented["queue_placement"] = policy_eval["placement"]
        email_augmented["action_reason"] = policy_eval["reason"]
        email_augmented["next_step"] = policy_eval["next_step"]

        placement = policy_eval["placement"]

        if placement == "ACTIVE":
            active_queue.append(email_augmented)
            # Categorize counts mutually exclusively
            # Priority 1 or Critical Incident = Urgent
            if policy_eval["priority"] == "P1" or policy_eval["is_critical_incident"]:
                urgent_count += 1
            elif policy_eval["deadline_status"] in ("UPCOMING", "OVERDUE"):
                due_soon_count += 1
            else:
                other_active_count += 1
        elif placement == "OLDER":
            older_actions.append(email_augmented)
        elif placement == "SNOOZED":
            snoozed_items.append(email_augmented)
        elif placement == "RESOLVED":
            resolved_items.append(email_augmented)

    # Sort queues deterministically
    sorted_active = sort_action_items(active_queue, sort_by=sort_by)
    sorted_older = sort_action_items(older_actions, sort_by=older_sort_by)
    sorted_snoozed = sort_action_items(snoozed_items, sort_by="newest")
    sorted_resolved = sort_action_items(resolved_items, sort_by="newest")

    total_active = len(sorted_active)
    assert total_active == (urgent_count + due_soon_count + other_active_count), "Active counts must sum exactly"

    return {
        "active_queue": sorted_active,
        "older_actions": sorted_older,
        "snoozed_items": sorted_snoozed,
        "resolved_items": sorted_resolved,
        "counts": {
            "urgent": urgent_count,
            "due_soon": due_soon_count,
            "other_active": other_active_count,
            "total_active": total_active,
            "older": len(sorted_older),
            "snoozed": len(sorted_snoozed),
            "resolved": len(sorted_resolved),
        },
        "age_threshold_days": age_threshold_days,
    }


def classify_action_queue_item(
    email: Dict[str, Any],
    action_state: Optional[Dict[str, Any]] = None,
    now_dt: Optional[datetime] = None,
    now_ts: Optional[float] = None
) -> Dict[str, Any]:
    """
    Convenience evaluation helper for a single email item.
    """
    if now_ts is None and now_dt is not None:
        now_ts = now_dt.timestamp()
    eval_res = evaluate_actionability(email, action_state=action_state, now_ts=now_ts)
    placement_map = {
        "ACTIVE": "ACTIVE_QUEUE",
        "OLDER": "OLDER_ACTIONS",
        "SNOOZED": "SNOOZED",
        "RESOLVED": "RESOLVED",
        "EXCLUDED": "EXPIRED_ACTIONS" if eval_res.get("deadline_status") == "EXPIRED" else "EXCLUDED"
    }
    return {
        **eval_res,
        "queue_placement": placement_map.get(eval_res["placement"], eval_res["placement"]),
        "is_older": eval_res["placement"] == "OLDER",
        "is_critical": eval_res["is_critical_incident"],
        "is_expired": eval_res.get("deadline_status") == "EXPIRED",
    }


def evaluate_action_queue(
    emails: List[Dict[str, Any]],
    user_action_states: Optional[Dict[str, Dict[str, Any]]] = None,
    now_dt: Optional[datetime] = None,
    now_ts: Optional[float] = None
) -> Dict[str, Any]:
    """
    Convenience evaluation helper for an entire mailbox queue.
    """
    if now_ts is None and now_dt is not None:
        now_ts = now_dt.timestamp()
    if user_action_states is None:
        user_action_states = {}
    res = classify_action_queue(emails, user_action_states, now_ts=now_ts)
    counts = res["counts"]
    # Provide normalized keys for test and UI flexibility
    counts["urgent_count"] = counts.get("urgent", 0)
    counts["due_soon_count"] = counts.get("due_soon", 0)
    counts["other_active_count"] = counts.get("other_active", 0)
    counts["active_total"] = counts.get("total_active", len(res["active_queue"]))
    counts["older_total"] = counts.get("older", len(res["older_actions"]))
    counts["snoozed_total"] = counts.get("snoozed", len(res["snoozed_items"]))
    counts["resolved_total"] = counts.get("resolved", len(res["resolved_items"]))
    return res


def generate_next_step(email: Dict[str, Any], deadline_status: str = "NONE") -> str:
    """
    Generates a concise, context-aware next step string for an action item.
    """
    if is_critical_incident(email):
        return "Resolve urgent incident immediately"
    if is_otp_or_verification_code(email):
        return "Enter verification code before expiry" if deadline_status != "EXPIRED" else "Verification code expired"
    if deadline_status == "OVERDUE":
        return "Review overdue item and submit or pay balance"
    if deadline_status == "UPCOMING":
        return "Complete required task before deadline"
    
    action_reason = email.get("action_reason") or ""
    if "download" in action_reason.lower() or "document" in action_reason.lower():
        return "Download available document or ticket"
    if "registration" in action_reason.lower():
        return "Review criteria and complete registration"
    if "review" in action_reason.lower():
        return "Review email and respond"
    return "Review email and take required action"

