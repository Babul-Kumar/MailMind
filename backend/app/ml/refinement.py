import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Dict, Any, List, Optional, Tuple
from backend.app.ml.priority import PRIORITY_MAPPING

# ==============================================================================
# COMPILED CONTEXTUAL REGEX PATTERNS (MULTI-TOKEN)
# ==============================================================================

# --- Domain 1: Security & Account Integrity ---
SEC_P1_COMPROMISE = re.compile(
    r"\b(suspicious (?:sign-in|login|activity)|unauthorized (?:access|sign-in|login|transaction|activity)|"
    r"account (?:compromised|breached|locked|suspended)|password (?:has been )?changed|password reset requested|"
    r"credentials (?:compromised|leaked)|security breach|someone may have accessed|"
    r"someone knows your password|unrecognized login blocked)\b",
    re.IGNORECASE
)
SEC_P1_ACTION = re.compile(
    r"\b(immediately|secure your account now|contact support (?:immediately|now)|action required immediately|"
    r"reset your password (?:immediately|now)|if you did not (?:authorize|make|do|request)|if this was not you|"
    r"report unauthorized|take immediate action)\b",
    re.IGNORECASE
)

SEC_P2_AUTH = re.compile(
    r"\b(security alert|new (?:sign-in|login|device)|sign-in from new|"
    r"allowed (?:.*? )?access|granted (?:.*? )?access|access granted|"
    r"verify your identity|verification code|one-time password|\botp\b|"
    r"check (?:your )?account activity|review (?:your )?account activity|"
    r"unrecognized device|new browser|unusual activity detected|two-factor authentication code)\b",
    re.IGNORECASE
)
SEC_P2_ACTION = re.compile(
    r"\b(check (?:your )?account activity|secure your account|take a moment|"
    r"if (?:this wasn't you|this was not you|you didn't allow this|you did not do this)|"
    r"verify (?:it's you|your identity|this was you)|enter this code|valid for \d+ (?:minutes|hours)|"
    r"do not share this code|review activity|someone else may be trying to access)\b",
    re.IGNORECASE
)

SEC_P3_ROUTINE = re.compile(
    r"\b(privacy policy update|terms of service update|security settings updated|"
    r"security digest|monthly security summary|routine security checkup|privacy settings updated|"
    r"security recommendations|privacy guidelines|security guidelines|verification standards|"
    r"informational update|annual verification of (?:our )?privacy|"
    r"account (?:verification|email) (?:was |has been )?(?:successfully )?(?:completed|verified|confirmed)|"
    r"verification (?:was |has been )?(?:successfully )?(?:completed|successful)|"
    r"login verification was successful|account was verified(?: yesterday)?)\b",
    re.IGNORECASE
)

# --- Domain 2: Academic, Course & Educational Deadlines ---
ACAD_P2_ASSIGNMENT = re.compile(
    r"\b(assignment \d+|assignment|quiz \d+|quiz|exam|midterm|final exam|homework|lab assignment|term project|course assessment)\b",
    re.IGNORECASE
)
ACAD_P2_DEADLINE = re.compile(
    r"\b(deadline (?:for submitting|is|to submit|extended)|due (?:date|on|by|before)|"
    r"submit (?:your assignment|before|by|on)|submission (?:closes|deadline|is open|due)|"
    r"last date (?:for|to) submit|cutoff date|submission closing date)\b",
    re.IGNORECASE
)

ACAD_P3_INFORMATIONAL = re.compile(
    r"\b(solution(?:s)? (?:is|are|has been|have been)?\s*(?:released|published|available|uploaded)|"
    r"assignment \d+ solution|answer key|grades? (?:are )?(?:published|released|out|available)|"
    r"marks? (?:announced|published)|results? (?:announced|declared)|"
    r"lecture (?:notes?|video|slides?) (?:uploaded|available)|content is live now)\b",
    re.IGNORECASE
)

# --- Domain 3: Transactional, Operational & Financial ---
TX_P1_OVERDUE = re.compile(
    r"\b(payment overdue|account past due|immediate payment required|service suspension notice|"
    r"final notice before suspension|account suspended due to non-payment)\b",
    re.IGNORECASE
)

TX_P2_DUE = re.compile(
    r"\b(payment due|bill due|invoice due|payment reminder|upcoming payment|"
    r"statement is ready|bill is ready)\b",
    re.IGNORECASE
)

TX_P3_RECORD = re.compile(
    r"\b(payment received|payment successful|receipt for your|thank you for your payment|"
    r"order confirmation|booking confirmed|ticket confirmed)\b",
    re.IGNORECASE
)

# --- Domain 4: Promotional & Marketing Negation ---
PROMO_NEGATION = re.compile(
    r"\b(\d+%\s*off|save \$\d+|flat discount|limited time offer|coupon code|promo code|"
    r"shop now|buy now|special promotion|clearance sale|exclusive deal|best prices|"
    r"black friday|cyber monday|browse courses|explore our catalog)\b",
    re.IGNORECASE
)

# --- Domain 5: Topic Classification Patterns ---
TOPIC_PATTERNS = {
    "security": re.compile(r"\b(security|password|unauthorized|sign-in|login|suspicious|verification code|otp|two-factor|authenticat|breach|compromis|privacy policy|terms of service)\b", re.IGNORECASE),
    "academic": re.compile(r"\b(assignment|quiz|exam|nptel|lecture|course|syllabus|homework|grades?|marks?|solution released|iitm|learner|curriculum)\b", re.IGNORECASE),
    "billing": re.compile(r"\b(bill|invoice|payment|receipt|recharge|due date|statement|transaction|paid|overdue|fee)\b", re.IGNORECASE),
    "operational": re.compile(r"\b(profile|account|status|verification|registration|service|system|update|alert|notification|order placed|delivery|shipped|ticket)\b", re.IGNORECASE),
    "promotional": re.compile(r"\b(\d+%\s*off|discount|cashback|offer|sale|deal|coupon|flat|limited time|credit limit|apply now|shop now)\b", re.IGNORECASE),
    "newsletter": re.compile(r"\b(newsletter|weekly digest|monthly digest|roundup|top stories|insights|edition)\b", re.IGNORECASE),
}

# --- Domain 6: Optional Engagement Negation Patterns (Soft CTAs) ---
OPTIONAL_ENGAGEMENT_PATTERNS = re.compile(
    r"\b("
    r"review your (?:monthly |weekly |annual |yearly )?(?:activity |monthly )?(?:summary|achievements|stats|highlights|contributions)|"
    r"explore (?:recommended )?(?:jobs|courses|topics|opportunities|catalog|features)|"
    r"discover (?:new )?(?:courses|jobs|features|content|stories|tracks)(?: you may like)?|"
    r"check out (?:our |these |the )?(?:latest )?(?:features?|updates?|highlights?|deals?|courses?)|"
    r"read (?:this week's |today's |our )?(?:developer |weekly |monthly )?(?:digest|summary|roundup|edition|newsletter)|"
    r"browse (?:courses|jobs|catalogs?|products?|items?)|"
    r"see what's trending|trending now|stories for you|recommended for you|"
    r"take a moment to (?:check your settings|view your profile|explore)|"
    r"stay connected to|keep in touch with|follow us on|"
    r"we successfully reviewed your information to confirm"
    r")\b",
    re.IGNORECASE
)

# Strong operational requirement patterns (Categorized for evidence):
ACTION_ACTIVATION_PATTERNS = re.compile(
    r"\b("
    r"confirm (?:your )?(?:[\w\-]+ )?(?:account|email|signup|registration|subscription)|"
    r"verify (?:your )?(?:[\w\-]+ )?(?:account|email|student status|identity)|"
    r"activate (?:your )?(?:[\w\-]+ )?(?:account|subscription|profile|developer account|zoom account)|"
    r"click (?:this|the) link to confirm (?:your )?email|"
    r"validate (?:your )?email|complete (?:your )?(?:registration|account setup)|"
    r"action required: confirm your account"
    r")\b",
    re.IGNORECASE
)

ACTION_SECURITY_PATTERNS = re.compile(
    r"\b("
    r"reset (?:your )?password|secure your account|unauthorized (?:access|sign-in|login|activity)|"
    r"account (?:compromised|locked|suspended)|report unauthorized|if you did not (?:authorize|request|do this)|"
    r"someone may have accessed|someone knows your password|immediate verification required"
    r")\b",
    re.IGNORECASE
)

ACTION_VERIFICATION_PATTERNS = re.compile(
    r"\b("
    r"one.?time (?:password|passcode)|\botp\b|verification code|sign.?in code|access code|"
    r"enter (?:this|the|your)?\s*(?:verification\s+)?code|use (?:this|the|your)?\s*(?:mfa|otp|verification)?\s*(?:code|passcode) to|"
    r"valid (?:only )?for \d+(?::\d+)?\s*(?:minutes?|hours?|mins?)|expires? in \d+\s*(?:minutes?|mins?)"
    r")\b",
    re.IGNORECASE
)

ACTION_SUBMISSION_PATTERNS = re.compile(
    r"\b("
    r"submit (?:your )?(?:application|assignment|project|proposal|form|report|work|task|code)(?:\s+\d+)? (?:before|by|on)|"
    r"(?:submission|assignment|application) deadline|last date to submit|submissions? close[sd]?(?: on| by| before)?|"
    r"due (?:date|on|by|before)"
    r")\b",
    re.IGNORECASE
)

ACTION_PAYMENT_PATTERNS = re.compile(
    r"\b("
    r"pay (?:now|overdue|bill|invoice)|payment (?:due|overdue|is due tomorrow)|"
    r"invoice due|bill due|immediate payment required|account past due"
    r")\b",
    re.IGNORECASE
)

ACTION_SERVICE_PATTERNS = re.compile(
    r"\b("
    r"(?:project|service|portfolio|account|subscription|workspace) (?:will be|scheduled (?:to be|for)|is going to be) (?:deleted?|deletion|suspended|suspension|terminated|termination|deactivated|deactivation)|"
    r"unless you take action|take action (?:to prevent|before deletion)|"
    r"(?:take action|action required) to prevent (?:workspace |account |project |service )?deactivation|"
    r"complete (?:your )?(?:kyc verification|kyc)|verify your identity to continue"
    r")\b",
    re.IGNORECASE
)

ACTION_REQUIRED_PATTERNS = re.compile(
    r"\b(submit (?:before|by|on)|(?:submission|assignment|project|competition) deadline|due (?:date|on|by|before)|last date to submit|"
    r"action required|take action now|verify your (?:account|identity|email)|check (?:your )?account activity|"
    r"secure your account|immediately (?:reset|secure|verify|review|update)|reset (?:your )?password|"
    r"account compromised|unauthorized access|security breach|"
    r"pay (?:now|overdue|before|bill)|complete (?:your )?(?:verification|profile to continue|security|kyc)|"
    r"respond (?:by|before)|confirm your (?:email|identity|account|booking|attendance)|"
    r"valid (?:only )?for \d+(?::\d+)?\s*(?:minutes?|hours?|mins?)|enter (?:this|the|your)?\s*(?:verification\s+)?code|"
    r"use (?:this|the|your)?\s*(?:mfa|otp|verification)?\s*(?:code|passcode) to|(?:verification|security|sign-?in|login|access|mfa|reset) (?:code|passcode) (?:is|expires?|will expire)|"
    r"(?:one.?time (?:password|passcode)|\botp\b)(?:\s+(?:for|is|to|code|pin|will expire))?|password reset code|"
    r"(?:passcode|otp|code) (?:will expire|expires?)(?:\s+shortly)?|"
    r"if this wasn't you|someone may have accessed|"
    r"(?:services?|account|project|portfolio|subscription) (?:will be|scheduled to be|have been|is going to be) (?:deleted|suspended|paused|terminated|deactivated))\b",
    re.IGNORECASE
)

ACTION_NOT_REQUIRED_PATTERNS = re.compile(
    r"\b(solution (?:is|has been )?released|answer key|grades? (?:are )?published|"
    r"marks? (?:announced|published)|payment (?:received|successful)|receipt for your|"
    r"thank you for your|no action (?:is )?required|for your information|FYI|"
    r"successfully (?:updated|registered|submitted)|privacy policy update|"
    r"terms of (?:use|service) update|"
    r"weekly digest|newsletter|roundup|edition|"
    r"account (?:verification|email) (?:was |has been )?(?:successfully )?(?:completed|verified|confirmed)|"
    r"security settings (?:were|have been) (?:successfully )?updated|"
    r"successfully verified|verification (?:is )?complete)\b",
    re.IGNORECASE
)


def detect_topic(subject: str, body: str, sender: str) -> str:
    """Classifies the semantic topic of an email independently of priority."""
    for topic, pattern in TOPIC_PATTERNS.items():
        if pattern.search(subject):
            return topic
    text = f"{subject} {body} {sender}"
    for topic, pattern in TOPIC_PATTERNS.items():
        if pattern.search(text):
            return topic
    return "other"


def evaluate_action_layer(
    subject: str,
    body: str,
    final_priority: str = "P4",
    deadline_detected: bool = False
) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """
    Evaluates contextual evidence to determine whether immediate action or user response is required.
    Distinguishes Required Action (imperative + direct obligation + operational consequence)
    from Optional Engagement (soft CTAs, newsletters, passive browsing).

    Returns:
        (action_required, action_reason, action_evidence)
    """
    text = f"{subject} {body}".strip()
    if not text:
        return False, None, {
            "imperative": False,
            "operational_consequence": False,
            "deadline_present": False,
            "action_type": "none"
        }

    # 1. Promotional marketing negation (unless critical security/compromise is present)
    if PROMO_NEGATION.search(subject) and not re.search(r"\b(security alert|unauthorized|password reset)\b", subject, re.I):
        return False, None, {
            "imperative": False,
            "operational_consequence": False,
            "deadline_present": deadline_detected,
            "action_type": "none"
        }

    # 2. Informational completion / non-action notices (e.g. payment received, solutions released)
    if ACTION_NOT_REQUIRED_PATTERNS.search(text) and not (
        ACTION_ACTIVATION_PATTERNS.search(text) or
        ACTION_SECURITY_PATTERNS.search(text) or
        ACTION_VERIFICATION_PATTERNS.search(text) or
        ACTION_SUBMISSION_PATTERNS.search(text) or
        ACTION_SERVICE_PATTERNS.search(text) or
        ACTION_PAYMENT_PATTERNS.search(text)
    ):
        return False, None, {
            "imperative": False,
            "operational_consequence": False,
            "deadline_present": deadline_detected,
            "action_type": "none"
        }

    # 3. Check for soft optional engagement
    is_optional = bool(OPTIONAL_ENGAGEMENT_PATTERNS.search(text))

    # 4. Check for strong operational requirements
    action_type = "none"
    action_reason = None

    if ACTION_VERIFICATION_PATTERNS.search(text):
        action_type = "verification"
        action_reason = "Immediate verification required"
    elif ACTION_SECURITY_PATTERNS.search(text):
        action_type = "security"
        action_reason = "Account security action"
    elif ACTION_ACTIVATION_PATTERNS.search(text):
        if not re.search(r"\b(?:stay connected to|marketing updates|marketing emails|receive our latest updates via email)\b", text, re.I):
            action_type = "activation"
            action_reason = "Account activation required"
    elif ACTION_SERVICE_PATTERNS.search(text):
        action_type = "service"
        action_reason = "Service action required"
    elif ACTION_PAYMENT_PATTERNS.search(text):
        action_type = "payment"
        action_reason = "Payment action"
    elif ACTION_SUBMISSION_PATTERNS.search(text):
        action_type = "submission"
        action_reason = "Submission deadline"

    # If optional engagement matched and NO strong operational requirement matched:
    if is_optional and action_type == "none":
        return False, None, {
            "imperative": True,
            "operational_consequence": False,
            "deadline_present": deadline_detected,
            "action_type": "none"
        }

    if action_type != "none":
        return True, action_reason, {
            "imperative": True,
            "operational_consequence": True,
            "deadline_present": deadline_detected,
            "action_type": action_type
        }

    # Fallback to general ACTION_REQUIRED_PATTERNS if imperative and not optional
    if ACTION_REQUIRED_PATTERNS.search(text) and not is_optional:
        gen_reason = determine_action_reason(subject, body, "operational")
        return True, gen_reason, {
            "imperative": True,
            "operational_consequence": True,
            "deadline_present": deadline_detected,
            "action_type": "operational"
        }

    return False, None, {
        "imperative": False,
        "operational_consequence": False,
        "deadline_present": deadline_detected,
        "action_type": "none"
    }


def detect_action_required(subject: str, body: str, final_priority: str = "P4") -> bool:
    """Determines whether immediate action or user response is required."""
    act_req, _, _ = evaluate_action_layer(subject, body, final_priority)
    return act_req


# ==============================================================================
# DEADLINE EXTRACTION REGEX PATTERNS & UTILITIES
# ==============================================================================

MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "september": 9, "oct": 10, "october": 10,
    "nov": 11, "november": 11, "dec": 12, "december": 12
}

DEADLINE_CONTEXT = re.compile(
    r"\b((?:submission|assignment|registration|application|payment|competition)?\s*deadlines?|"
    r"due\s+(?:date|on|by|before)|"
    r"(?:submissions?|applications?|registration|contest|competition|portal)?\s*close[sd]?\s+(?:on|at|by|before|tomorrow)?|"
    r"(?:competition|contest|challenge|submission|registration|offer)\s+ends?(?:\s+(?:on|at|in|before|tomorrow))?|"
    r"ends?\s+(?:on|at|in)\s+(?:\d{1,2}\s+(?:hours|minutes|mins)|\d{1,2}\s+days)|"
    r"expires?\s+(?:on|in|at|within)|"
    r"last date\s+(?:to|for)|"
    r"valid\s+(?:only\s+)?(?:until|till|through|for)|"
    r"(?:remains?\s+)?active\s+(?:for|until|within)|"
    r"within\s+\d{1,2}\s+(?:hours|hrs|minutes|mins)|"
    r"(?:will be|scheduled to be|is going to be)\s+(?:deleted|suspended|paused|terminated|deactivated)(?:\s+(?:on|in|after|before))?|"
    r"(?:reconnect|migrate|submit|respond|pay)\s+(?:before|by))\b",
    re.IGNORECASE
)

MONTH_NAME_REGEX = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"

ISO_REGEX = re.compile(r"\b(202\d)-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])(?:\s+(\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM|am|pm|UTC|GMT)?))?\b")

TIME_BEFORE_MONTH_DAY = re.compile(
    rf"\b(?:at\s+)?(\d{{1,2}}(?::\d{{2}})?\s*(?:AM|PM|am|pm))\s+(?:on\s+)?({MONTH_NAME_REGEX})\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:\s*,\s*(202\d))?\b",
    re.IGNORECASE
)

TIME_BEFORE_DAY_MONTH = re.compile(
    rf"\b(?:at\s+)?(\d{{1,2}}(?::\d{{2}})?\s*(?:AM|PM|am|pm))\s+(?:on\s+)?(\d{{1,2}})(?:st|nd|rd|th)?\s+({MONTH_NAME_REGEX})(?:\s*,\s*(202\d))?\b",
    re.IGNORECASE
)

MONTH_DAY_REGEX = re.compile(
    rf"\b({MONTH_NAME_REGEX})\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:\s*,\s*(202\d))?(?:\s*(?:at\s+|,)?\s*(\d{{1,2}}(?::\d{{2}})?\s*(?:AM|PM|am|pm)))?\b",
    re.IGNORECASE
)

DAY_MONTH_REGEX = re.compile(
    rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({MONTH_NAME_REGEX})(?:\s*,\s*(202\d))?(?:\s*(?:at\s+|,)?\s*(\d{{1,2}}(?::\d{{2}})?\s*(?:AM|PM|am|pm)))?\b",
    re.IGNORECASE
)

RELATIVE_DAYS_REGEX = re.compile(
    r"\b(?:in\s+(\d+)\s+days|(?:by|closes?|due|ends?)\s+(tomorrow))\b",
    re.IGNORECASE
)

RELATIVE_HOURS_REGEX = re.compile(
    r"\b(?:(?:remains?\s+)?(?:active|valid)\s+(?:only\s+)?(?:for|within)|expires?\s+(?:in|within)|within|ends?\s+in)\s+(\d{1,2})\s*(?:hours|hrs)\b",
    re.IGNORECASE
)

# Matches sub-hour OTP/code expiry: "valid only for 05:00 mins", "expires in 5 minutes", "within 10 minutes"
RELATIVE_MINUTES_REGEX = re.compile(
    r"\b(?:(?:remains?\s+)?(?:active|valid)\s+(?:only\s+)?(?:for|within)|expires?\s+(?:in|within)|within|ends?\s+in)\s+(\d{1,2}(?::\d{2})?)\s*(?:minutes?|mins?)\b",
    re.IGNORECASE
)

WEEKDAY_REGEX = re.compile(
    r"\b(?:before|by|on)\s+(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b",
    re.IGNORECASE
)

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def normalize_time(time_str: str) -> Tuple[str, str]:
    """
    Normalizes time strings (e.g. '23:59PM', '23:59', '11:59 PM', '5 PM')
    to standard (iso_time 'HH:MM:SS', display_time 'h:mm AM/PM').
    Prevents invalid mixed formats like '23:59PM'.
    """
    clean = time_str.replace("UTC", "").replace("GMT", "").strip()
    match = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", clean, re.IGNORECASE)
    if not match:
        return clean, clean

    h_val = int(match.group(1))
    m_val = int(match.group(2)) if match.group(2) else 0
    meridiem = match.group(3).upper() if match.group(3) else None

    if h_val >= 24:
        h_val = 0

    if meridiem == "PM":
        h_24 = h_val if h_val >= 12 else h_val + 12
    elif meridiem == "AM":
        h_24 = 0 if h_val == 12 else (h_val % 12)
    else:  # No explicit AM/PM
        h_24 = h_val

    if h_24 == 0:
        disp_h = 12
        disp_meridiem = "AM"
    elif h_24 < 12:
        disp_h = h_24
        disp_meridiem = "AM"
    elif h_24 == 12:
        disp_h = 12
        disp_meridiem = "PM"
    else:
        disp_h = h_24 - 12
        disp_meridiem = "PM"

    iso_time = f"{h_24:02d}:{m_val:02d}:00"
    display_time = f"{disp_h}:{m_val:02d} {disp_meridiem}"
    return iso_time, display_time


def parse_reference_date(date_str: Optional[str]) -> datetime:
    """Parses email arrival date header (ISO or RFC 2822) or defaults to 2026-10-01."""
    if date_str:
        # Try ISO format
        try:
            clean_str = date_str.replace("Z", "+00:00")
            dt = datetime.fromisoformat(clean_str)
            return dt.replace(tzinfo=None)
        except Exception:
            pass
        # Try RFC 2822 format
        try:
            dt = parsedate_to_datetime(date_str)
            return dt.replace(tzinfo=None)
        except Exception:
            pass
    return datetime(2026, 10, 1, 10, 0, 0)


def determine_deadline_status(
    deadline_datetime_str: Optional[str],
    is_otp: bool = False,
    ref_date: Optional[str] = None,
    now_dt: Optional[datetime] = None
) -> str:
    """
    Classifies the operational state of a detected deadline into:
    ACTIVE, OVERDUE, EXPIRED, HISTORICAL, or NONE.
    """
    if not deadline_datetime_str:
        return "NONE"
    if now_dt is None:
        now_dt = datetime.now(timezone.utc).replace(tzinfo=None)

    try:
        clean_dl = deadline_datetime_str[:19]
        if "T" in clean_dl:
            dl_dt = datetime.fromisoformat(clean_dl)
        else:
            dl_dt = datetime.strptime(clean_dl, "%Y-%m-%d")

        if dl_dt >= now_dt:
            return "ACTIVE"
        if is_otp:
            return "EXPIRED"
        diff_days = (now_dt - dl_dt).total_seconds() / 86400.0
        if diff_days <= 30.0:
            return "OVERDUE"
        return "HISTORICAL"
    except Exception:
        return "HISTORICAL"


def extract_deadline(
    subject: str,
    body: str,
    email_date: Optional[str] = None,
    now_dt: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Extracts explicit, reliable deadline metadata from email subject and body.
    NEVER uses email_date as the deadline (email_date is solely a reference for relative offsets).
    
    Returns:
        deadline_detected: bool
        deadline_datetime: Optional[str] (ISO format YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)
        deadline_precision: "DATETIME" | "DATE" | "NONE"
        deadline_display: Optional[str] (Formatted for UI, e.g. "Oct 5, 2026 · 11:59 PM")
        deadline_status: "ACTIVE" | "OVERDUE" | "EXPIRED" | "HISTORICAL" | "NONE"
    """
    none_result = {
        "deadline_detected": False,
        "deadline_datetime": None,
        "deadline_precision": "NONE",
        "deadline_display": None,
        "deadline_status": "NONE"
    }
    
    text = f"{subject} {body}".strip()
    if not text:
        return none_result
        
    ref_dt = parse_reference_date(email_date)
    ref_year = ref_dt.year or 2026
    
    context_matches = list(DEADLINE_CONTEXT.finditer(text))
    if not context_matches:
        return none_result

    def is_near_context(span: Tuple[int, int]) -> bool:
        start, end = span
        for cm in context_matches:
            c_start, c_end = cm.span()
            if abs(start - c_end) <= 120 or abs(c_start - end) <= 120:
                return True
        return False

    def _make_res(dt_str: str, precision: str, display: str) -> Dict[str, Any]:
        is_otp = bool(
            RELATIVE_MINUTES_REGEX.search(text) or
            re.search(r"\b(?:one.?time (?:password|passcode)|\botp\b|login (?:otp|code|verification)|mfa code|verification code|sign.?in code|access code|password reset code)\b", text, re.I)
        )
        status = determine_deadline_status(dt_str, is_otp=is_otp, ref_date=email_date, now_dt=now_dt)
        return {
            "deadline_detected": True,
            "deadline_datetime": dt_str,
            "deadline_precision": precision,
            "deadline_display": display,
            "deadline_status": status
        }

    # 1. ISO pattern (e.g. 2026-09-30 23:59PM UTC)
    for iso_match in ISO_REGEX.finditer(text):
        if is_near_context(iso_match.span()):
            y, m, d, time_str = iso_match.groups()
            year = int(y)
            month = int(m)
            day = int(d)
            month_name = datetime(year, month, day).strftime("%b")
            if time_str:
                iso_t, disp_t = normalize_time(time_str)
                return _make_res(f"{year:04d}-{month:02d}-{day:02d}T{iso_t}", "DATETIME", f"{month_name} {day}, {year} · {disp_t}")
            else:
                return _make_res(f"{year:04d}-{month:02d}-{day:02d}", "DATE", f"{month_name} {day}, {year}")

    # 2. Time before Month Day (e.g. "close at 5 PM on October 10")
    for t_match in TIME_BEFORE_MONTH_DAY.finditer(text):
        if is_near_context(t_match.span()):
            time_str, m_name, d_str, y_str = t_match.groups()
            m_num = MONTHS.get(m_name.lower()[:3])
            if m_num:
                day = int(d_str)
                year = int(y_str) if y_str else ref_year
                month_abbr = datetime(year, m_num, 1).strftime("%b")
                iso_t, disp_t = normalize_time(time_str)
                return _make_res(f"{year:04d}-{m_num:02d}-{day:02d}T{iso_t}", "DATETIME", f"{month_abbr} {day}, {year} · {disp_t}")

    for t_match in TIME_BEFORE_DAY_MONTH.finditer(text):
        if is_near_context(t_match.span()):
            time_str, d_str, m_name, y_str = t_match.groups()
            m_num = MONTHS.get(m_name.lower()[:3])
            if m_num:
                day = int(d_str)
                year = int(y_str) if y_str else ref_year
                month_abbr = datetime(year, m_num, 1).strftime("%b")
                iso_t, disp_t = normalize_time(time_str)
                return _make_res(f"{year:04d}-{m_num:02d}-{day:02d}T{iso_t}", "DATETIME", f"{month_abbr} {day}, {year} · {disp_t}")

    # 3. Relative offsets ("in 5 days", "closes tomorrow")
    rel_match = RELATIVE_DAYS_REGEX.search(text)
    if rel_match:
        days_str, tom_str = rel_match.groups()
        if days_str:
            num_days = int(days_str)
            target_dt = ref_dt + timedelta(days=num_days)
            m_abbr = target_dt.strftime("%b")
            return _make_res(target_dt.strftime("%Y-%m-%d"), "DATE", f"Due in {num_days} days · {m_abbr} {target_dt.day}")
        elif tom_str:
            target_dt = ref_dt + timedelta(days=1)
            m_abbr = target_dt.strftime("%b")
            return _make_res(target_dt.strftime("%Y-%m-%d"), "DATE", f"Due tomorrow · {m_abbr} {target_dt.day}")

    # Relative minutes (e.g. "valid only for 05:00 mins", "expires in 5 minutes", "valid for 10 minutes")
    rel_mins_match = RELATIVE_MINUTES_REGEX.search(text)
    if rel_mins_match:
        raw_val = rel_mins_match.group(1)  # e.g. "5", "05:00"
        if ":" in raw_val:
            parts = raw_val.split(":")
            num_mins = int(parts[0])
            num_secs = int(parts[1]) if len(parts) > 1 else 0
        else:
            num_mins = int(raw_val)
            num_secs = 0
        target_dt = ref_dt + timedelta(minutes=num_mins, seconds=num_secs)
        m_abbr = target_dt.strftime("%b")
        disp_time = target_dt.strftime("%I:%M %p").lstrip("0")
        return _make_res(target_dt.strftime("%Y-%m-%dT%H:%M:%S"), "DATETIME", f"{m_abbr} {target_dt.day}, {target_dt.year} · {disp_time} (OTP expiry)")

    # Relative hours (e.g. "remains active for 12 hours", "expires in 12 hours", "valid for 24 hours")
    rel_hours_match = RELATIVE_HOURS_REGEX.search(text)
    if rel_hours_match:
        num_hours = int(rel_hours_match.group(1))
        target_dt = ref_dt + timedelta(hours=num_hours)
        m_abbr = target_dt.strftime("%b")
        disp_time = target_dt.strftime("%I:%M %p").lstrip("0")
        return _make_res(target_dt.strftime("%Y-%m-%dT%H:%M:%S"), "DATETIME", f"{m_abbr} {target_dt.day}, {target_dt.year} · {disp_time}")

    # 4. Month Day near context
    for m_match in MONTH_DAY_REGEX.finditer(text):
        if is_near_context(m_match.span()):
            m_name, d_str, y_str, time_str = m_match.groups()
            m_num = MONTHS.get(m_name.lower()[:3])
            if m_num:
                day = int(d_str)
                year = int(y_str) if y_str else ref_year
                month_abbr = datetime(year, m_num, 1).strftime("%b")
                if time_str:
                    iso_t, disp_t = normalize_time(time_str)
                    return _make_res(f"{year:04d}-{m_num:02d}-{day:02d}T{iso_t}", "DATETIME", f"{month_abbr} {day}, {year} · {disp_t}")
                else:
                    return _make_res(f"{year:04d}-{m_num:02d}-{day:02d}", "DATE", f"{month_abbr} {day}, {year}")

    # 5. Day Month near context
    for dm_match in DAY_MONTH_REGEX.finditer(text):
        if is_near_context(dm_match.span()):
            d_str, m_name, y_str, time_str = dm_match.groups()
            m_num = MONTHS.get(m_name.lower()[:3])
            if m_num:
                day = int(d_str)
                year = int(y_str) if y_str else ref_year
                month_abbr = datetime(year, m_num, 1).strftime("%b")
                if time_str:
                    iso_t, disp_t = normalize_time(time_str)
                    return _make_res(f"{year:04d}-{m_num:02d}-{day:02d}T{iso_t}", "DATETIME", f"{month_abbr} {day}, {year} · {disp_t}")
                else:
                    return _make_res(f"{year:04d}-{m_num:02d}-{day:02d}", "DATE", f"{month_abbr} {day}, {year}")

    # 6. Weekday near context ("before Friday")
    for wk_match in WEEKDAY_REGEX.finditer(text):
        if is_near_context(wk_match.span()):
            wk_day_str = wk_match.group(1).lower()
            if wk_day_str in WEEKDAYS:
                target_idx = WEEKDAYS.index(wk_day_str)
                cur_idx = ref_dt.weekday()
                diff = (target_idx - cur_idx) % 7
                if diff == 0:
                    diff = 7
                target_dt = ref_dt + timedelta(days=diff)
                m_abbr = target_dt.strftime("%b")
                return _make_res(target_dt.strftime("%Y-%m-%d"), "DATE", f"{wk_match.group(1)} · {m_abbr} {target_dt.day}")

    return none_result


def determine_action_reason(subject: str, body: str, topic: str) -> str:
    """Classifies a concise, data-grounded reason for the required action."""
    text = f"{subject} {body}".lower()

    # 0. Time-sensitive authentication code (OTP / MFA / login verification)
    if re.search(
        r"\b(?:one.?time (?:password|passcode)|\botp\b|login (?:otp|code|verification)|mfa code|"
        r"verification code|sign.?in code|access code|password reset code|"
        r"passcode will expire|code will expire|"
        r"valid (?:only )?for \d+(?::\d+)?\s*(?:minutes?|mins?)|expires? in \d+\s*(?:minutes?|mins?))\b",
        text
    ):
        return "Immediate verification required"

    # 1. Security / Account
    if re.search(r"\b(security alert|unauthorized|verify your (?:account|identity)|secure your account|reset (?:your )?password|check (?:your )?account activity|someone may have accessed)\b", text):
        return "Account security action"
        
    # 2. Service / Infrastructure
    if re.search(r"\b(?:project|services?|portfolio|account|subscription|workspace)\s+(?:will be|scheduled to be|is going to be|have been)\s+(?:deleted|suspended|paused|terminated|deactivated)\b", text) or \
       re.search(r"\b(?:services? have been suspended|projects? will be deleted|portfolio is going to be paused)\b", text):
        return "Service action"
        
    # 3. Submission / Assessment / Competition
    if re.search(r"\b(?:submission|assignment|project|competition|contest|quiz)\s+deadlines?|submit\s+(?:before|by|on)|last date to submit|submissions?\s+close\b", text):
        return "Submission deadline"
        
    # 4. Billing / Payment
    if re.search(r"\b(?:pay\s+(?:now|overdue|before|bill)|bill due|payment overdue|invoice overdue)\b", text):
        return "Payment action"
        
    # 5. Response / Confirmation
    if re.search(r"\b(?:confirm your (?:email|identity|account|booking)|update your application|respond\s+(?:by|before))\b", text):
        return "Response required"
        
    return "Action required"


def refine_priority(
    subject: str,
    body: str,
    sender: str,
    model_priority: str,
    confidence: float,
    email_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Evaluates multi-token contextual signals on top of the frozen ML model prediction.
    Enforces a strict decision hierarchy based on:
        Urgency + Required Action + Operational Consequence.
    """
    text = f"{subject} {body}".strip()
    subj = subject.strip()
    
    topic = detect_topic(subject, body, sender)

    # Empty content check
    if not text:
        return {
            "model_priority": model_priority,
            "final_priority": model_priority,
            "action_required": False,
            "action_reason": None,
            "topic": "other",
            "deadline_detected": False,
            "deadline_datetime": None,
            "deadline_precision": "NONE",
            "deadline_display": None,
            "refinement_applied": False,
            "refinement_reason": None,
            "refinement_signals": [],
            "review_suggested": False
        }

    signals: List[str] = []
    reason: Optional[str] = None
    refined_priority: Optional[str] = None

    # Check for promotional negation
    is_promo = bool(PROMO_NEGATION.search(text))

    # 1. Critical Financial / Overdue (P1)
    m_tx1 = TX_P1_OVERDUE.search(text)
    if m_tx1:
        signals.append(m_tx1.group(0))
        refined_priority = "P1"
        reason = "Urgent transactional notice: overdue payment or pending account suspension"

    # 2. Critical Security Alert: Account Compromise or Lockout (P1)
    if not refined_priority:
        m_sec1_comp = SEC_P1_COMPROMISE.search(text)
        m_sec1_act = SEC_P1_ACTION.search(text)
        if m_sec1_comp and m_sec1_act:
            signals.extend([m_sec1_comp.group(0), m_sec1_act.group(0)])
            refined_priority = "P1"
            reason = "Critical security alert: suspected account compromise or unauthorized access requiring immediate action"

    # 3. Actionable Financial Notice: Payment / Bill Due (P2)
    if not refined_priority and not is_promo:
        m_tx2 = TX_P2_DUE.search(text)
        if m_tx2:
            signals.append(m_tx2.group(0))
            refined_priority = "P2"
            reason = "Actionable financial notice: upcoming payment or bill deadline"

    # 4. Actionable Security Alert: Authorization / New Device / Verification (P2)
    if not refined_priority and not is_promo:
        m_sec2_auth = SEC_P2_AUTH.search(text)
        m_sec2_act = SEC_P2_ACTION.search(text)
        if m_sec2_auth and m_sec2_act:
            signals.extend([m_sec2_auth.group(0), m_sec2_act.group(0)])
            refined_priority = "P2"
            reason = "Security verification: user authorization or account activity review required"
        elif m_sec2_auth and any(term in subj.lower() for term in ["security alert", "verification code", "otp", "access granted"]):
            signals.append(m_sec2_auth.group(0))
            refined_priority = "P2"
            reason = "Security verification: account access or verification notice"

    # 5. Actionable Academic Notice: Assignment with Active Submission Deadline (P2)
    if not refined_priority and not is_promo:
        m_acad3_sol = ACAD_P3_INFORMATIONAL.search(text)
        is_solution_release = bool(
            m_acad3_sol and any(k in subj.lower() for k in ["solution", "answer key", "grade", "result", "score"])
        )
        if not is_solution_release:
            m_acad2_item = ACAD_P2_ASSIGNMENT.search(text)
            m_acad2_due = ACAD_P2_DEADLINE.search(text)
            if m_acad2_item and m_acad2_due:
                signals.extend([m_acad2_item.group(0), m_acad2_due.group(0)])
                refined_priority = "P2"
                reason = "Actionable academic notice: assignment or assessment with submission deadline"

    # 5b. Actionable Account Activation / Email Confirmation (Elevate P3/P4 -> P2)
    if not refined_priority and model_priority in ("P3", "P4") and not is_promo:
        m_act = ACTION_ACTIVATION_PATTERNS.search(text)
        if m_act and not re.search(r"\b(?:stay connected to|marketing updates|marketing emails|receive our latest updates via email)\b", text, re.I):
            signals.append(m_act.group(0))
            refined_priority = "P2"
            reason = "Account activation: email confirmation or account setup required"

    # 5c. Actionable Operational Service Notice: Project Deletion / Service Suspension (Elevate P3/P4 -> P2)
    if not refined_priority and model_priority in ("P3", "P4") and not is_promo:
        m_svc = ACTION_SERVICE_PATTERNS.search(text)
        if m_svc:
            signals.append(m_svc.group(0))
            refined_priority = "P2"
            reason = "Operational service notice: project deletion or service deactivation pending"

    # 5d. Actionable Password Reset Request (Elevate P3/P4 -> P2)
    if not refined_priority and model_priority in ("P3", "P4") and not is_promo:
        m_pwd = re.search(r"\b(reset your password|instructions to reset your password|password reset link)\b", text, re.I)
        if m_pwd:
            signals.append(m_pwd.group(0))
            refined_priority = "P2"
            reason = "Security action: user-requested password reset"

    # 6. Informational Academic Update: Solutions / Grades Released (P3)
    if not refined_priority and not is_promo:
        m_acad3 = ACAD_P3_INFORMATIONAL.search(text)
        if m_acad3:
            signals.append(m_acad3.group(0))
            refined_priority = "P3"
            reason = "Academic informational update: assignment solution, grades, or course content released"

    # 7. Routine Security Notice: Policy / Terms / Digest (P3)
    if not refined_priority and not is_promo:
        m_sec3 = SEC_P3_ROUTINE.search(text)
        if m_sec3:
            signals.append(m_sec3.group(0))
            refined_priority = "P3"
            reason = "Routine security update: policy, terms, or security settings notice"

    # 8. Transactional Record: Receipt / Confirmation (P3)
    if not refined_priority and not is_promo:
        m_tx3 = TX_P3_RECORD.search(text)
        if m_tx3:
            signals.append(m_tx3.group(0))
            refined_priority = "P3"
            reason = "Transactional record: payment receipt or booking confirmation"

    # Guardrails: High Confidence Model Preservation
    if confidence >= 0.75 and refined_priority != "P1":
        final_priority = model_priority
        refinement_applied = False
        final_reason = None
        final_signals = []
    elif refined_priority is not None and refined_priority != model_priority:
        final_priority = refined_priority
        refinement_applied = True
        final_reason = reason
        final_signals = list(dict.fromkeys(signals))
    else:
        final_priority = model_priority
        refinement_applied = False
        final_reason = None
        final_signals = []

    deadline_info = extract_deadline(subject, body, email_date)
    action_required, action_reason, action_evidence = evaluate_action_layer(
        subject, body, final_priority, deadline_detected=deadline_info["deadline_detected"]
    )
    if not deadline_info["deadline_detected"]:
        deadline_status = "NONE"
    else:
        dl_str = deadline_info["deadline_datetime"]
        is_otp = (action_reason == "Immediate verification required") or bool(
            re.search(r"\b(otp|verification code|sign-?in code|login code|one-time password|mfa code)\b", text, re.I)
        )
        deadline_status = determine_deadline_status(dl_str, is_otp=is_otp, ref_date=email_date)

    deadline_info["deadline_status"] = deadline_status
    review_suggested = refinement_applied or (confidence < 0.40)

    return {
        "model_priority": model_priority,
        "final_priority": final_priority,
        "action_required": action_required,
        "action_reason": action_reason,
        "action_evidence": action_evidence,
        "topic": topic,
        "deadline_detected": deadline_info["deadline_detected"],
        "deadline_datetime": deadline_info["deadline_datetime"],
        "deadline_precision": deadline_info["deadline_precision"],
        "deadline_display": deadline_info["deadline_display"],
        "deadline_status": deadline_status,
        "refinement_applied": refinement_applied,
        "refinement_reason": final_reason,
        "refinement_signals": final_signals,
        "review_suggested": review_suggested
    }
