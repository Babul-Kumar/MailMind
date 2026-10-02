"""
feedback.py — Phase 52 Enhanced Feedback System
=================================================
Stores human correction data for future offline dataset curation.

DESIGN INVARIANTS:
  - Feedback does NOT trigger online retraining.
  - Feedback is NOT automatically promoted to training data.
  - All records are user-scoped (user_id mandatory on write).
  - No raw email body, OAuth tokens, or credentials stored.
  - Deduplication: (user_id, message_id) is the unique case identity.
  - The feedback pipeline is:
      User correction → feedback.jsonl → human adjudication → dataset-v5.2 candidate
                                                          ↑
                           NOT: → automatic training (FORBIDDEN)

Phase 52 additions:
  - feedback_id (UUID4) — unique per submission
  - adjudication_status — PENDING_REVIEW (default)
  - provenance — HUMAN_PRODUCTION_FEEDBACK
  - get_unique_cases(user_id) — dedup by (user_id, message_id)
  - get_dedup_stats(user_id) — raw events vs unique cases vs adjudicated
  - Fixed list_feedback() — user-scoped in route calls; None only for admin
"""
import os
import json
import time
import uuid
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from backend.app.core.config import BASE_DIR

FEEDBACK_DIR = os.path.join(BASE_DIR, "dataset", "feedback")
FEEDBACK_FILE = os.path.join(FEEDBACK_DIR, "feedback.jsonl")

# ---------------------------------------------------------------------------
# Valid feedback type identifiers (Phase 52 — aligned to spec contract)
# ---------------------------------------------------------------------------
VALID_FEEDBACK_TYPES = frozenset([
    # Phase 43 / legacy types
    "priority_wrong",
    "action_required_wrong",
    "deadline_wrong",
    "topic_wrong",
    "general",
    # Phase 52 canonical types
    "ACCEPT",
    "CORRECT",
    "REJECT",
    "UNCERTAIN",
])

VALID_ADJUDICATION_STATUSES = frozenset([
    "PENDING_REVIEW",
    "ACCEPTED",
    "REJECTED",
    "NEEDS_CONTEXT",
    "DUPLICATE",
])

VALID_PRIORITIES = frozenset(["P1", "P2", "P3", "P4"])

SAFETY_TOPICS = frozenset([
    "otp", "mfa", "security", "security_alert", "password_reset",
    "account_compromise", "authentication", "infrastructure_failure",
    "banking_alert", "account",
])


class FeedbackSubmission(BaseModel):
    """
    Structured user correction record.

    Phase 43 fields preserved for backward compatibility.
    Phase 52 additions: feedback_id, adjudication_status, provenance.
    """
    # Required identifiers
    message_id: str
    model_version: str

    # Thread context (Phase 43)
    thread_id: Optional[str] = None

    # Feedback classification
    # Accepts both Phase 43 snake_case and Phase 52 canonical UPPER types
    feedback_type: str = Field(default="CORRECT")

    # Original model prediction
    predicted_priority: str
    original_confidence: Optional[float] = None
    original_topic: Optional[str] = None
    original_deadline_detected: Optional[bool] = None
    deadline_status: Optional[str] = None

    # User corrections
    predicted_action_required: bool = False
    corrected_priority: Optional[str] = None
    corrected_action_required: Optional[bool] = None
    deadline_correction: Optional[bool] = None
    corrected_deadline_display: Optional[str] = None
    topic_correction: Optional[str] = None

    # Optional user reason
    reason: Optional[str] = None
    notes: Optional[str] = None


class FeedbackManager:
    """
    Stores human-reviewed corrections in a user-scoped append-only JSONL file.

    Phase 52 guarantees:
      - Every record gets a unique feedback_id (UUID4).
      - adjudication_status is always PENDING_REVIEW at creation.
      - provenance is always HUMAN_PRODUCTION_FEEDBACK.
      - (user_id, message_id) is the unique case identity.
      - Deduplication is explicit: multiple submissions for the same
        (user_id, message_id) are preserved for auditability but counted
        as 1 unique case.
    """

    def __init__(self):
        os.makedirs(FEEDBACK_DIR, exist_ok=True)

    def record_feedback(
        self,
        submission: Optional[FeedbackSubmission] = None,
        user_id: str = "default_user",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Appends one user correction record to feedback.jsonl.

        Each record receives a unique feedback_id. Duplicate submissions
        from the same (user_id, message_id) are preserved for auditability
        but explicitly marked as duplicates in deduplication stats.

        FORBIDDEN: No OAuth tokens, no raw email body, no credentials.
        FORBIDDEN: No online retraining triggered from this path.
        """
        data = submission.model_dump() if submission is not None else dict(kwargs)

        # Normalise feedback_type
        ftype = data.get("feedback_type", "CORRECT")
        if ftype not in VALID_FEEDBACK_TYPES:
            ftype = "CORRECT"

        # Validate corrected_priority if present
        corr_p = data.get("corrected_priority")
        if corr_p and corr_p not in VALID_PRIORITIES:
            data["corrected_priority"] = None

        record = {
            **data,
            # Phase 52 new fields
            "feedback_id": str(uuid.uuid4()),
            "feedback_type": ftype,
            "adjudication_status": "PENDING_REVIEW",
            "provenance": "HUMAN_PRODUCTION_FEEDBACK",
            # Session-injected fields
            "user_id": user_id,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            # Legacy alias for backward compat
            "feedback_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "status": "pending_review",
        }

        # Explicit guard: no OAuth tokens, no raw body, no credentials
        for forbidden in ("access_token", "refresh_token", "credentials", "raw_body",
                          "password", "secret", "token"):
            record.pop(forbidden, None)

        with open(FEEDBACK_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
        return record

    def list_feedback(
        self,
        user_id: Optional[str] = None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """
        Returns recent feedback records, optionally filtered to a single user.

        IMPORTANT (Phase 52 fix):
          - All route handlers MUST pass user_id from session.
          - user_id=None is reserved for internal admin-level queries only.
          - Never expose user_id=None results to an authenticated user endpoint.
        """
        if not os.path.exists(FEEDBACK_FILE):
            return []
        records: List[Dict[str, Any]] = []
        try:
            with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                        if user_id is None or rec.get("user_id") == user_id:
                            records.append(rec)
                    except Exception:
                        pass
        except Exception:
            pass
        return records[-limit:]

    def get_unique_cases(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Returns the most-recent submission per unique (user_id, message_id) pair.

        Phase 52 deduplication contract:
          - Raw events: every submission row in feedback.jsonl
          - Unique cases: distinct (user_id, message_id) pairs
          - A case with 37 duplicate submissions counts as 1 unique case.
        """
        records = self.list_feedback(user_id=user_id, limit=100_000)
        seen: Dict[str, Dict[str, Any]] = {}
        for rec in records:
            mid = rec.get("message_id") or rec.get("email_id", "")
            key = f"{user_id}::{mid}"
            # Keep most-recent (last wins in append-only file)
            seen[key] = rec
        return list(seen.values())

    def get_dedup_stats(self, user_id: str) -> Dict[str, Any]:
        """
        Raw events vs unique cases breakdown.

        Distinguishes:
          1. Raw feedback events (all rows)
          2. Unique feedback cases (dedup by user_id, message_id)
          3. Priority correction cases (corrected_priority set and different)
          4. Safety cases (original_topic in SAFETY_TOPICS)
          5. P2/P3 boundary cases (P2↔P3 transitions)
          6. Deadline cases (deadline_detected or deadline_correction)
        """
        all_records = self.list_feedback(user_id=user_id, limit=100_000)
        unique_cases = self.get_unique_cases(user_id)

        priority_corrections = 0
        safety_cases = 0
        p2_p3_cases = 0
        deadline_cases = 0

        for rec in unique_cases:
            orig = rec.get("predicted_priority") or rec.get("original_priority", "")
            corr = rec.get("corrected_priority") or rec.get("user_priority", "")
            topic = (rec.get("original_topic") or rec.get("topic") or "").lower()

            if corr and corr != orig and corr in VALID_PRIORITIES:
                priority_corrections += 1

            if topic in SAFETY_TOPICS:
                safety_cases += 1

            if (orig in ("P2", "P3")) and (corr in ("P2", "P3")) and orig != corr:
                p2_p3_cases += 1

            if rec.get("deadline_detected") or rec.get("deadline_correction"):
                deadline_cases += 1

        # Count duplicates (raw - unique)
        duplicate_submissions = len(all_records) - len(unique_cases)

        return {
            "raw_feedback_events": len(all_records),
            "unique_feedback_cases": len(unique_cases),
            "duplicate_submissions": duplicate_submissions,
            "priority_correction_cases": priority_corrections,
            "safety_cases": safety_cases,
            "p2_p3_boundary_cases": p2_p3_cases,
            "deadline_cases": deadline_cases,
            "dedup_note": (
                "Unique cases are deduped by (user_id, message_id). "
                "Duplicate submissions preserve auditability but count as 1 case."
            ),
        }

    def get_feedback_count(self, user_id: str) -> int:
        """Returns the total number of feedback records for a given user."""
        return len(self.list_feedback(user_id=user_id, limit=100_000))

    def get_by_feedback_id(self, feedback_id: str) -> Optional[Dict[str, Any]]:
        """Looks up a specific feedback record by feedback_id."""
        if not os.path.exists(FEEDBACK_FILE):
            return None
        try:
            with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                        if rec.get("feedback_id") == feedback_id:
                            return rec
                    except Exception:
                        pass
        except Exception:
            pass
        return None


feedback_manager = FeedbackManager()
