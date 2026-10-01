import re

PRIORITY_MAPPING = {
    'P1': 'Critical / Urgent',
    'P2': 'Important / Actionable',
    'P3': 'Routine / Informational',
    'P4': 'Low / Promotional / Noise'
}

PRIORITY_DESCRIPTIONS = {
    'P1': 'Critical / Urgent',
    'P2': 'Important / Actionable',
    'P3': 'Routine / Informational',
    'P4': 'Low / Promotional / Noise'
}

PRIORITY_RANK = {'P1': 4, 'P2': 3, 'P3': 2, 'P4': 1}

# =========================================================================
# HEURISTIC ENGINE V2 (FROZEN FROM PHASE 20)
# =========================================================================

BOILERPLATE_PATTERNS = [
    re.compile(r"(\r?\n|\r)?[-*=_~]{3,}\s*(?:Original Message|Forwarded by|Disclaimer|Confidentiality Notice).*", re.I | re.DOTALL),
    re.compile(r"This (?:message|e-mail|communication)(?: and any attachments)? (?:is|may contain|is intended).*?(?:privileged|confidential).*?(?:notify|delete|destroy).*", re.I | re.DOTALL),
    re.compile(r"The information (?:contained in|transmitted by) this (?:e-mail|message).*?(?:attorney-client privilege|confidential).*?(?:notify|delete|destroy).*", re.I | re.DOTALL),
    re.compile(r"\*{5,}\s*This e-mail is the property of Enron Corp\..*?\*{5,}", re.I | re.DOTALL),
    re.compile(r"CONFIDENTIALITY NOTICE:?.*?(?:delete|notify|destroy).*", re.I | re.DOTALL),
    re.compile(r"PRIVILEGED AND CONFIDENTIAL.*?(?:delete|notify|destroy).*", re.I | re.DOTALL),
    re.compile(r"If you have received this (?:e-mail|message|transmission) in error.*?(?:delete|notify).*", re.I | re.DOTALL),
    re.compile(r"Any other use of the email by you is prohibited\..*", re.I | re.DOTALL)
]


def clean_body_for_scoring(body_original: str) -> str:
    """
    Strips common legal disclaimers, confidentiality footers, and automated routing notices.
    """
    if not isinstance(body_original, str) or not body_original.strip():
        return ""
    cleaned = body_original
    for pat in BOILERPLATE_PATTERNS:
        cleaned = pat.sub("", cleaned)
    return cleaned.strip()


def score_email_v2(row) -> str:
    """
    Evaluates heuristic priority score for an email row.
    Preserved for historical calibration and backward compatibility.
    """
    # Simple rule-based evaluation if needed
    subject = str(row.get("subject", "") or "").lower()
    body = clean_body_for_scoring(str(row.get("body", "") or "")).lower()
    text = f"{subject} {body}"

    if any(k in text for k in ["urgent", "emergency", "critical outage", "asap", "immediate attention"]):
        return "P1"
    if any(k in text for k in ["action required", "approval", "please respond", "deadline", "meeting", "review"]):
        return "P2"
    if any(k in text for k in ["update", "fyi", "newsletter", "summary", "report", "status"]):
        return "P3"
    return "P4"
