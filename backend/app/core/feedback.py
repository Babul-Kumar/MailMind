"""
feedback.py — Phase 43 Enhanced Feedback System
=================================================
Stores human correction data for future offline dataset curation.

DESIGN INVARIANTS:
  - Feedback does NOT trigger online retraining.
  - Feedback is NOT automatically promoted to training data.
  - All records are user-scoped (user_id is mandatory on write, filterable on read).
  - No raw email body, OAuth tokens, or credentials are stored here.
  - The feedback pipeline is:
      User correction → feedback.jsonl → human review → dataset-v5 candidate
                                     ↑
                      NOT: → automatic training (FORBIDDEN)
"""
import os
import json
import time
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from backend.app.core.config import BASE_DIR

FEEDBACK_DIR = os.path.join(BASE_DIR, "dataset", "feedback")
FEEDBACK_FILE = os.path.join(FEEDBACK_DIR, "feedback.jsonl")

# Valid feedback type identifiers
VALID_FEEDBACK_TYPES = frozenset([
    "priority_wrong",
    "action_required_wrong",
    "deadline_wrong",
    "topic_wrong",
    "general",
])


class FeedbackSubmission(BaseModel):
    """
    Structured user correction record. All correction fields are optional;
    at least one corrected_* field should be set for the record to be useful.

    Phase 43 additions:
      - thread_id: preserves email thread context
      - feedback_type: categorical classification of correction type
      - original_confidence: model confidence at prediction time
      - original_topic: model-assigned topic at prediction time
      - original_deadline_detected: model's deadline detection flag
    """
    # Required identifiers
    message_id: str
    model_version: str

    # Thread context (Phase 43)
    thread_id: Optional[str] = None

    # Feedback classification (Phase 43)
    feedback_type: str = Field(default="priority_wrong")

    # Original model prediction
    predicted_priority: str
    original_confidence: Optional[float] = None
    original_topic: Optional[str] = None
    original_deadline_detected: Optional[bool] = None

    # User corrections
    predicted_action_required: bool
    corrected_priority: Optional[str] = None
    corrected_action_required: Optional[bool] = None
    deadline_correction: Optional[bool] = None
    corrected_deadline_display: Optional[str] = None
    topic_correction: Optional[str] = None

    # Free-text annotation
    notes: Optional[str] = None


class FeedbackManager:
    """
    Stores human-reviewed corrections in a user-scoped append-only JSONL file.

    Feedback accumulates for future human-adjudicated dataset version creation
    (e.g. dataset-v5). It does NOT trigger online retraining or automatic model
    changes at any point.
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

        Args:
            submission: Validated FeedbackSubmission model.
            user_id: Authenticated user identifier (injected by route handler).
            **kwargs: Alternative dict-based submission (for legacy callers).

        Returns:
            The persisted record dict (includes status and timestamp).
        """
        data = submission.model_dump() if submission is not None else kwargs

        # Normalise feedback_type
        ftype = data.get("feedback_type", "priority_wrong")
        if ftype not in VALID_FEEDBACK_TYPES:
            ftype = "general"

        record = {
            **data,
            "feedback_type": ftype,
            "user_id": user_id,
            "feedback_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "status": "pending_review",
        }
        # Explicit guard: no OAuth tokens, no raw body, no credentials
        for forbidden in ("access_token", "refresh_token", "credentials", "raw_body"):
            record.pop(forbidden, None)

        with open(FEEDBACK_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
        return record

    def list_feedback(
        self,
        user_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Returns recent feedback records, optionally filtered to a single user.

        Args:
            user_id: If provided, only records for this user are returned.
                     If None, returns the most recent records across all users
                     (used only by internal monitoring, not exposed publicly).
            limit: Maximum number of records to return (most recent first).
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

    def get_feedback_count(self, user_id: str) -> int:
        """Returns the total number of feedback records for a given user."""
        return len(self.list_feedback(user_id=user_id, limit=100_000))


feedback_manager = FeedbackManager()
