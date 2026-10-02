"""
feedback.py — Phase 53 Enhanced Production Feedback System
=============================================================
Stores human correction data for future offline dataset curation.

DESIGN INVARIANTS:
  - Feedback does NOT trigger online retraining.
  - Feedback is NOT automatically promoted to training data.
  - All records are user-scoped (user_id mandatory on write).
  - No raw email body, OAuth tokens, or credentials stored.
  - Deduplication: (user_id, message_id) is the unique case identity.
  - Model version and user identity are ENFORCED SERVER-SIDE.
  - Historical feedback (v1, v4.1) is separated from v5.1 production evidence.
  - The feedback pipeline is:
      User correction → feedback.jsonl → human adjudication → dataset-v5.2 candidate
                                                          ↑
                           NOT: → automatic training (FORBIDDEN)
"""
import os
import json
import time
import uuid
import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from backend.app.core.config import BASE_DIR

logger = logging.getLogger("mailmind.feedback")

FEEDBACK_DIR = os.path.join(BASE_DIR, "dataset", "feedback")
FEEDBACK_FILE = os.path.join(FEEDBACK_DIR, "feedback.jsonl")

# ---------------------------------------------------------------------------
# Valid identifiers (Phase 52 & Phase 53)
# ---------------------------------------------------------------------------
VALID_FEEDBACK_TYPES = frozenset([
    # Phase 43 / legacy types
    "priority_wrong",
    "action_required_wrong",
    "deadline_wrong",
    "topic_wrong",
    "general",
    # Phase 52 / 53 canonical types
    "ACCEPT",
    "CORRECT",
    "REJECT",
    "UNCERTAIN",
    "NOT_SURE",
])

VALID_ADJUDICATION_STATUSES = frozenset([
    "PENDING_REVIEW",
    "ACCEPTED",
    "REJECTED",
    "NEEDS_CONTEXT",
    "DUPLICATE",
])

VALID_PRIORITIES = frozenset(["P1", "P2", "P3", "P4"])

VALID_REASONS = frozenset([
    "priority_too_high",
    "priority_too_low",
    "action_misunderstood",
    "deadline_misunderstood",
    "context_missing",
    "other",
    # Legacy reasons
    "too_high",
    "too_low",
    "action_wrong",
    "deadline_wrong",
])

SAFETY_TOPICS = frozenset([
    "otp", "mfa", "security", "security_alert", "password_reset",
    "account_compromise", "authentication", "infrastructure_failure",
    "banking_alert", "account",
])


class FeedbackSubmission(BaseModel):
    """
    Structured user correction record submitted from client.

    Note: message_id is required. model_version, predicted_priority,
    and user identity are authoritatively validated/derived server-side.
    """
    message_id: str
    model_version: Optional[str] = "priority-v5.1"

    # Thread context
    thread_id: Optional[str] = None

    # Feedback classification
    feedback_type: str = Field(default="CORRECT")

    # Original model prediction (client view; overridden by server-side cache if present)
    predicted_priority: Optional[str] = "P4"
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

    # User reason
    reason: Optional[str] = None
    notes: Optional[str] = None


class FeedbackManager:
    """
    Stores human-reviewed corrections in a user-scoped append-only JSONL file.

    Guarantees:
      - Every record gets a unique feedback_id (UUID4).
      - adjudication_status is always PENDING_REVIEW at creation.
      - provenance is PRODUCTION_FEEDBACK for active model submissions.
      - (user_id, message_id) is the unique case identity.
      - Deduplication is explicit: multiple submissions for the same
        (user_id, message_id) are preserved for auditability but counted
        as 1 unique case.
      - Separates v5.1 production evidence from historical v1 / v4.1 feedback.
    """

    def __init__(self):
        os.makedirs(FEEDBACK_DIR, exist_ok=True)

    def record_feedback(
        self,
        submission: Optional[FeedbackSubmission] = None,
        user_id: str = "default_user",
        provenance: str = "HUMAN_PRODUCTION_FEEDBACK",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Appends one user correction record to feedback.jsonl.

        Each record receives a unique feedback_id. Duplicate submissions
        from the same (user_id, message_id) are preserved for auditability.
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

        # Validate reason if present
        reason = data.get("reason") or data.get("notes")
        if reason and reason not in VALID_REASONS:
            # Map legacy shorthand if applicable
            mapping = {
                "too_high": "priority_too_high",
                "too_low": "priority_too_low",
                "action_wrong": "action_misunderstood",
                "deadline_wrong": "deadline_misunderstood",
            }
            reason = mapping.get(reason, reason)

        now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        # Ensure model_version is set
        m_version = data.get("model_version") or "priority-v5.1"
        rec_provenance = kwargs.get("provenance") or data.get("provenance") or provenance

        record = {
            **data,
            "feedback_id": str(uuid.uuid4()),
            "feedback_type": ftype,
            "reason": reason,
            "adjudication_status": "PENDING_REVIEW",
            "provenance": rec_provenance,
            "user_id": user_id,
            "model_version": m_version,
            "created_at": now_str,
            "feedback_timestamp": now_str,
            "status": "pending_review",
        }

        # Explicit guard: no OAuth tokens, no raw body, no credentials
        for forbidden in (
            "access_token", "refresh_token", "credentials", "raw_body",
            "password", "secret", "token"
        ):
            record.pop(forbidden, None)

        with open(FEEDBACK_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
        return record

    def list_feedback(
        self,
        user_id: Optional[str] = None,
        model_version: Optional[str] = None,
        limit: int = 100_000,
    ) -> List[Dict[str, Any]]:
        """
        Returns recent feedback records, optionally filtered by user_id and model_version.
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
                        if user_id is not None and rec.get("user_id") != user_id:
                            continue
                        if model_version is not None:
                            rec_m = rec.get("model_version") or ""
                            if rec_m != model_version:
                                continue
                        records.append(rec)
                    except Exception:
                        pass
        except Exception:
            pass
        return records[-limit:]

    def get_unique_cases(
        self,
        user_id: str,
        model_version: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Returns the most-recent submission per unique (user_id, message_id) pair.
        Optionally filtered by model_version.
        """
        records = self.list_feedback(user_id=user_id, model_version=model_version, limit=100_000)
        seen: Dict[str, Dict[str, Any]] = {}
        for rec in records:
            mid = rec.get("message_id") or rec.get("email_id", "")
            key = f"{user_id}::{mid}"
            seen[key] = rec
        return list(seen.values())

    def get_dedup_stats(self, user_id: str) -> Dict[str, Any]:
        """
        Raw events vs unique cases breakdown for a user.
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

            if rec.get("deadline_detected") or rec.get("deadline_correction") or rec.get("original_deadline_detected"):
                deadline_cases += 1

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

    # ------------------------------------------------------------------
    # Phase 53: Model-Separated Production Metrics
    # ------------------------------------------------------------------
    def get_metrics_by_model(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Separates feedback records by model generation:
          1. all: complete history
          2. v5_1: priority-v5.1 (current production)
          3. v4_1: priority-v4.1 (rollback baseline)
          4. older: priority-v1, None, legacy
        """
        all_records = self.list_feedback(user_id=user_id, limit=100_000)

        v51_records = []
        v41_records = []
        older_records = []

        for rec in all_records:
            mv = rec.get("model_version")
            if mv == "priority-v5.1":
                v51_records.append(rec)
            elif mv == "priority-v4.1":
                v41_records.append(rec)
            else:
                older_records.append(rec)

        def _summarize(records):
            seen = set()
            corrections = 0
            accepts = 0
            not_sure = 0
            for r in records:
                mid = r.get("message_id") or r.get("email_id", "")
                uid = r.get("user_id", "")
                seen.add(f"{uid}::{mid}")

                ftype = r.get("feedback_type", "CORRECT")
                if ftype == "ACCEPT":
                    accepts += 1
                elif ftype == "NOT_SURE":
                    not_sure += 1
                elif r.get("corrected_priority") and r.get("corrected_priority") != r.get("predicted_priority"):
                    corrections += 1

            raw_count = len(records)
            unique_count = len(seen)
            dup_count = raw_count - unique_count
            corr_rate = round(corrections / unique_count * 100, 2) if unique_count > 0 else 0.0

            return {
                "raw_count": raw_count,
                "unique_cases": unique_count,
                "duplicate_count": dup_count,
                "corrections": corrections,
                "accepts": accepts,
                "not_sure": not_sure,
                "correction_rate_pct": corr_rate,
            }

        return {
            "all_feedback": _summarize(all_records),
            "v51_feedback": _summarize(v51_records),
            "v41_feedback": _summarize(v41_records),
            "older_feedback": _summarize(older_records),
            "separation_note": (
                "Historical feedback (v1, v4.1) is strictly separated from v5.1 "
                "production evidence. Zero v1/v4.1 entries are mixed into v5.1 metrics."
            ),
        }

    def get_v51_production_metrics(self, user_id: str) -> Dict[str, Any]:
        """
        Detailed metrics for priority-v5.1 production evidence only.
        """
        records = self.list_feedback(user_id=user_id, model_version="priority-v5.1", limit=100_000)
        unique_cases = self.get_unique_cases(user_id=user_id, model_version="priority-v5.1")

        accept_count = 0
        correct_count = 0
        not_sure_count = 0
        unique_corrections = 0

        p2_to_p3 = 0
        p3_to_p2 = 0
        safety_cases = 0
        deadline_cases = 0

        for r in unique_cases:
            ftype = r.get("feedback_type", "CORRECT")
            orig = r.get("predicted_priority", "")
            corr = r.get("corrected_priority")
            topic = (r.get("original_topic") or r.get("topic") or "").lower()

            if ftype == "ACCEPT":
                accept_count += 1
            elif ftype == "NOT_SURE":
                not_sure_count += 1
            else:
                correct_count += 1

            if corr and corr != orig and corr in VALID_PRIORITIES:
                unique_corrections += 1
                if orig == "P2" and corr == "P3":
                    p2_to_p3 += 1
                elif orig == "P3" and corr == "P2":
                    p3_to_p2 += 1

            if topic in SAFETY_TOPICS or (corr == "P1" and orig != "P1"):
                safety_cases += 1

            if r.get("deadline_detected") or r.get("deadline_correction") or r.get("original_deadline_detected"):
                deadline_cases += 1

        raw_count = len(records)
        unique_count = len(unique_cases)
        dup_count = raw_count - unique_count
        corr_rate = round(unique_corrections / unique_count * 100, 2) if unique_count > 0 else 0.0

        return {
            "model_version": "priority-v5.1",
            "raw_feedback_events": raw_count,
            "unique_feedback_cases": unique_count,
            "duplicate_events": dup_count,
            "accept_count": accept_count,
            "correct_count": correct_count,
            "not_sure_count": not_sure_count,
            "unique_corrections": unique_corrections,
            "correction_rate_pct": corr_rate,
            "p2_to_p3_corrections": p2_to_p3,
            "p3_to_p2_corrections": p3_to_p2,
            "safety_feedback_count": safety_cases,
            "deadline_feedback_count": deadline_cases,
            "status_statement": (
                "0 genuine v5.1 feedback cases observed."
                if unique_count == 0
                else f"{unique_count} genuine v5.1 feedback cases observed."
            ),
        }

    def get_quality_metrics(self, user_id: str, total_classified: int = 0) -> Dict[str, Any]:
        """
        Feedback quality rates normalized by classified messages.
        """
        v51_m = self.get_v51_production_metrics(user_id)
        raw = v51_m["raw_feedback_events"]
        unique = v51_m["unique_feedback_cases"]

        sub_rate = round(raw / total_classified * 100, 4) if total_classified > 0 else 0.0
        uniq_rate = round(unique / total_classified * 100, 4) if total_classified > 0 else 0.0
        dup_rate = round(v51_m["duplicate_events"] / raw * 100, 2) if raw > 0 else 0.0
        not_sure_rate = round(v51_m["not_sure_count"] / unique * 100, 2) if unique > 0 else 0.0

        from backend.app.core.adjudication import adjudication_manager
        adj_stats = adjudication_manager.get_stats(user_id=user_id)
        total_adj = adj_stats.get("total_adjudicated", 0)

        acc_rate = round(adj_stats.get("accepted", 0) / total_adj * 100, 2) if total_adj > 0 else 0.0
        rej_rate = round(adj_stats.get("rejected", 0) / total_adj * 100, 2) if total_adj > 0 else 0.0
        ctx_rate = round(adj_stats.get("needs_context", 0) / total_adj * 100, 2) if total_adj > 0 else 0.0

        return {
            "feedback_submission_rate_pct": sub_rate,
            "unique_feedback_rate_pct": uniq_rate,
            "correction_rate_pct": v51_m["correction_rate_pct"],
            "duplicate_rate_pct": dup_rate,
            "not_sure_rate_pct": not_sure_rate,
            "adjudication_acceptance_rate_pct": acc_rate,
            "adjudication_rejection_rate_pct": rej_rate,
            "needs_context_rate_pct": ctx_rate,
            "total_classified_emails": total_classified,
            "v51_unique_cases": unique,
            "admonition": "No feedback does not imply no model errors.",
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
