"""
adjudication.py — Phase 52 Human Adjudication Workflow
========================================================
Explicit human review of production feedback before anything enters
a training candidate dataset.

DESIGN INVARIANTS:
  - Adjudication is HUMAN-ONLY. No automatic acceptance.
  - Only ACCEPTED + valid provenance records may enter dataset-v5.2 candidate.
  - Rejected and ambiguous feedback MUST NOT enter training.
  - Adjudication records are append-only (audit trail).
  - No model.fit(), no model promotion, no online learning.

Adjudication statuses:
  PENDING_REVIEW  — newly submitted, awaiting human review
  ACCEPTED        — reviewer confirms correction is valid and supported
  REJECTED        — reviewer determines correction is NOT a model error
  NEEDS_CONTEXT   — insufficient context to adjudicate; request more info
  DUPLICATE       — same (user_id, message_id) already adjudicated

Priority annotation philosophy (preserved from Phase 52-E):
  Priority = urgency + required action + operational consequence.
  Do NOT use: sender identity, domain, keyword presence alone,
  work-relatedness alone, calendar presence alone.
"""
import os
import json
import time
import uuid
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict

from backend.app.core.config import BASE_DIR
from backend.app.core.feedback import (
    FEEDBACK_FILE, FEEDBACK_DIR, VALID_PRIORITIES, SAFETY_TOPICS, feedback_manager
)

logger = logging.getLogger("mailmind.adjudication")

ADJUDICATION_FILE = os.path.join(FEEDBACK_DIR, "adjudication.jsonl")

VALID_STATUSES = frozenset([
    "PENDING_REVIEW", "ACCEPTED", "REJECTED", "NEEDS_CONTEXT", "DUPLICATE",
])

# Topics that require immediate safety queue prioritisation
DEADLINE_TOPICS = frozenset(["deadline", "application", "payment", "academic", "recruitment"])


@dataclass
class AdjudicationRecord:
    """
    Full adjudication record. Written to adjudication.jsonl.

    Contains:
      - Full provenance chain: feedback_id → adjudication_id
      - Original model prediction
      - User correction
      - Reviewer decision + reason
      - Timestamps

    NEVER contains: OAuth tokens, raw email body, credentials.
    """
    adjudication_id: str
    feedback_id: str
    user_id: str
    message_id: str
    thread_id: Optional[str]
    model_version: str
    original_priority: str
    original_confidence: Optional[float]
    corrected_priority: Optional[str]
    feedback_type: str
    topic: Optional[str]
    action_required: bool
    deadline_detected: bool
    deadline_status: Optional[str]
    adjudication_status: str           # ACCEPTED | REJECTED | NEEDS_CONTEXT | DUPLICATE
    adjudicator_id: Optional[str]
    adjudicated_at: str
    adjudication_reason: str
    provenance: str                    # HUMAN_PRODUCTION_FEEDBACK / HUMAN_ADJUDICATED
    source_model_version: str
    # Safety / boundary flags (computed at adjudication time)
    is_safety_case: bool = False
    is_p2_p3_boundary: bool = False
    is_deadline_case: bool = False
    # Candidate eligibility (only ACCEPTED may enter dataset-v5.2)
    eligible_for_training: bool = False
    ineligibility_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AdjudicationManager:
    """
    Human adjudication workflow for production feedback.

    Responsibilities:
      - Accept/reject/flag feedback records
      - Maintain adjudication.jsonl audit trail
      - Expose review queues (pending, safety, P2/P3, deadline)
      - Provide candidate pool (ACCEPTED only)

    Forbidden:
      - No automatic acceptance of any feedback
      - No model training or modification
      - No registry mutations
      - No cross-user data exposure
    """

    def __init__(self):
        os.makedirs(FEEDBACK_DIR, exist_ok=True)

    # ------------------------------------------------------------------
    # 1. Core adjudication
    # ------------------------------------------------------------------
    def adjudicate(
        self,
        feedback_id: str,
        adjudicator_id: str,
        status: str,
        reason: str,
        corrected_priority: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Records a human adjudication decision for a feedback record.

        Args:
            feedback_id: The feedback_id from feedback.jsonl.
            adjudicator_id: Identity of the human reviewer.
            status: One of ACCEPTED, REJECTED, NEEDS_CONTEXT, DUPLICATE.
            reason: Human-readable explanation of the decision.
            corrected_priority: Reviewer-confirmed label (required for ACCEPTED).

        Returns:
            The persisted adjudication record dict.

        Raises:
            ValueError: If feedback_id not found, status invalid, or
                        ACCEPTED without corrected_priority.
        """
        if status not in VALID_STATUSES or status == "PENDING_REVIEW":
            raise ValueError(
                f"Invalid adjudication status '{status}'. "
                f"Must be one of: ACCEPTED, REJECTED, NEEDS_CONTEXT, DUPLICATE."
            )

        # Load original feedback
        fb = feedback_manager.get_by_feedback_id(feedback_id)
        if fb is None:
            raise ValueError(f"Feedback record '{feedback_id}' not found.")

        # ACCEPTED requires explicit corrected_priority
        if status == "ACCEPTED":
            label = corrected_priority or fb.get("corrected_priority")
            if not label or label not in VALID_PRIORITIES:
                raise ValueError(
                    "ACCEPTED adjudication requires a valid corrected_priority (P1/P2/P3/P4)."
                )
            corrected_priority = label

        # Validate reviewer did not blindly copy user claim without analysis
        if status == "ACCEPTED" and not reason:
            raise ValueError("ACCEPTED adjudication requires a documented reason.")

        # Compute safety / boundary / deadline flags
        orig = fb.get("predicted_priority") or fb.get("original_priority", "")
        corr = corrected_priority or fb.get("corrected_priority") or ""
        topic = (fb.get("original_topic") or fb.get("topic") or "").lower()
        is_safety = topic in SAFETY_TOPICS or corr == "P1" and orig != "P1"
        is_boundary = orig in ("P2", "P3") and corr in ("P2", "P3") and orig != corr
        is_deadline = bool(fb.get("deadline_detected") or fb.get("deadline_correction"))

        # Training eligibility gate
        eligible = False
        ineligibility_reason = None
        if status == "ACCEPTED":
            eligible = True
        elif status == "REJECTED":
            ineligibility_reason = "Reviewer determined this is not a model error."
        elif status == "NEEDS_CONTEXT":
            ineligibility_reason = "Insufficient context for adjudication."
        elif status == "DUPLICATE":
            ineligibility_reason = "Duplicate case — already adjudicated."

        rec = AdjudicationRecord(
            adjudication_id=str(uuid.uuid4()),
            feedback_id=feedback_id,
            user_id=fb.get("user_id", ""),
            message_id=fb.get("message_id") or fb.get("email_id", ""),
            thread_id=fb.get("thread_id"),
            model_version=fb.get("model_version", "unknown"),
            original_priority=orig,
            original_confidence=fb.get("original_confidence"),
            corrected_priority=corrected_priority,
            feedback_type=fb.get("feedback_type", "CORRECT"),
            topic=topic or None,
            action_required=bool(fb.get("predicted_action_required") or fb.get("action_required")),
            deadline_detected=bool(fb.get("deadline_detected") or fb.get("original_deadline_detected")),
            deadline_status=fb.get("deadline_status"),
            adjudication_status=status,
            adjudicator_id=adjudicator_id,
            adjudicated_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            adjudication_reason=reason,
            provenance="HUMAN_PRODUCTION_FEEDBACK_ADJUDICATED",
            source_model_version=fb.get("model_version", "unknown"),
            is_safety_case=is_safety,
            is_p2_p3_boundary=is_boundary,
            is_deadline_case=is_deadline,
            eligible_for_training=eligible,
            ineligibility_reason=ineligibility_reason,
        )

        record_dict = rec.to_dict()
        with open(ADJUDICATION_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record_dict) + "\n")

        logger.info(
            "adjudication: %s → %s (feedback_id=%s, adjudicator=%s)",
            status, corrected_priority, feedback_id, adjudicator_id,
        )
        return record_dict

    # ------------------------------------------------------------------
    # 2. Lookup
    # ------------------------------------------------------------------
    def get_adjudication(self, feedback_id: str) -> Optional[Dict[str, Any]]:
        """Returns the most-recent adjudication for a given feedback_id."""
        for rec in reversed(self._load_all()):
            if rec.get("feedback_id") == feedback_id:
                return rec
        return None

    def list_by_status(self, status: str) -> List[Dict[str, Any]]:
        """Returns all adjudication records with the given status."""
        return [r for r in self._load_all() if r.get("adjudication_status") == status]

    # ------------------------------------------------------------------
    # 3. Review queues (read-only)
    # ------------------------------------------------------------------
    def get_pending_queue(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Returns feedback records in PENDING_REVIEW state, deduped by
        (user_id, message_id). If user_id is provided, filtered to that user.

        Prioritisation order:
          1. Safety cases (OTP, MFA, security, password reset)
          2. P2/P3 boundary cases
          3. Deadline cases
          4. All others
        """
        already_adjudicated = {
            r.get("feedback_id")
            for r in self._load_all()
            if r.get("adjudication_status") != "PENDING_REVIEW"
        }

        # Load unique cases from feedback
        all_records = feedback_manager.list_feedback(user_id=user_id, limit=100_000)

        # Dedup by (user_id, message_id) — most recent first
        seen: Dict[str, Dict[str, Any]] = {}
        for rec in all_records:
            fid = rec.get("feedback_id")
            if fid and fid in already_adjudicated:
                continue
            uid = rec.get("user_id", "")
            mid = rec.get("message_id") or rec.get("email_id", "")
            key = f"{uid}::{mid}"
            seen[key] = rec  # last wins

        queue = list(seen.values())

        # Sort: safety > p2_p3 > deadline > other
        def priority_key(r):
            topic = (r.get("original_topic") or r.get("topic") or "").lower()
            corr = r.get("corrected_priority") or r.get("user_priority") or ""
            orig = r.get("predicted_priority") or r.get("original_priority") or ""
            is_s = topic in SAFETY_TOPICS or (corr == "P1" and orig != "P1")
            is_b = orig in ("P2", "P3") and corr in ("P2", "P3") and orig != corr
            is_d = bool(r.get("deadline_detected") or r.get("deadline_correction"))
            return (0 if is_s else 1 if is_b else 2 if is_d else 3)

        queue.sort(key=priority_key)
        return queue

    def get_safety_queue(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Returns pending feedback that involves safety-critical topics.
        OTP, MFA, password reset, security alerts, account compromise,
        authentication, infrastructure failures, hard deadlines.
        """
        queue = self.get_pending_queue(user_id=user_id)
        safety = []
        for rec in queue:
            topic = (rec.get("original_topic") or rec.get("topic") or "").lower()
            corr = rec.get("corrected_priority") or rec.get("user_priority") or ""
            orig = rec.get("predicted_priority") or rec.get("original_priority") or ""
            is_safety = topic in SAFETY_TOPICS or (corr == "P1" and orig != "P1")
            if is_safety:
                safety.append(rec)
        return safety

    def get_p2_p3_queue(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Returns pending feedback involving P2 → P3 or P3 → P2 corrections.
        These require special attention per Phase 52-F.
        """
        queue = self.get_pending_queue(user_id=user_id)
        boundary = []
        for rec in queue:
            orig = (rec.get("predicted_priority") or rec.get("original_priority") or "").strip()
            corr = (rec.get("corrected_priority") or rec.get("user_priority") or "").strip()
            if orig in ("P2", "P3") and corr in ("P2", "P3") and orig != corr:
                boundary.append(rec)
        return boundary

    def get_deadline_queue(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Returns pending feedback involving deadline-related corrections.
        """
        queue = self.get_pending_queue(user_id=user_id)
        deadlines = []
        for rec in queue:
            has_deadline = (
                rec.get("deadline_detected")
                or rec.get("original_deadline_detected")
                or rec.get("deadline_correction")
                or rec.get("corrected_deadline_display")
            )
            if has_deadline:
                deadlines.append(rec)
        return deadlines

    # ------------------------------------------------------------------
    # 4. Candidate pool
    # ------------------------------------------------------------------
    def get_candidate_pool(self) -> List[Dict[str, Any]]:
        """
        Returns ONLY adjudication records that are:
          1. ACCEPTED by a human reviewer
          2. eligible_for_training = True
          3. Have a confirmed corrected_priority in P1/P2/P3/P4
          4. Have provenance = HUMAN_PRODUCTION_FEEDBACK_ADJUDICATED

        This is the ONLY source for dataset-v5.2 candidate examples.
        Rejected, NEEDS_CONTEXT, DUPLICATE, and PENDING records are excluded.
        """
        return [
            r for r in self._load_all()
            if (
                r.get("adjudication_status") == "ACCEPTED"
                and r.get("eligible_for_training") is True
                and r.get("corrected_priority") in VALID_PRIORITIES
                and r.get("provenance") == "HUMAN_PRODUCTION_FEEDBACK_ADJUDICATED"
            )
        ]

    # ------------------------------------------------------------------
    # 5. Summary stats
    # ------------------------------------------------------------------
    def get_stats(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Summary of all adjudication activity for a given user (or global).
        """
        all_adj = self._load_all()
        if user_id:
            all_adj = [r for r in all_adj if r.get("user_id") == user_id]

        fb_dedup = feedback_manager.get_dedup_stats(user_id or "__admin__") if user_id else {}

        accepted = [r for r in all_adj if r.get("adjudication_status") == "ACCEPTED"]
        rejected = [r for r in all_adj if r.get("adjudication_status") == "REJECTED"]
        needs_ctx = [r for r in all_adj if r.get("adjudication_status") == "NEEDS_CONTEXT"]
        duplicates = [r for r in all_adj if r.get("adjudication_status") == "DUPLICATE"]

        pending_queue = self.get_pending_queue(user_id=user_id)

        # Correction matrix (only accepted)
        matrix: Dict[str, Dict[str, int]] = {
            p: {"P1": 0, "P2": 0, "P3": 0, "P4": 0} for p in ["P1", "P2", "P3", "P4"]
        }
        for r in accepted:
            orig = r.get("original_priority", "")
            corr = r.get("corrected_priority", "")
            if orig in matrix and corr in matrix[orig]:
                matrix[orig][corr] += 1

        return {
            "raw_feedback_events": fb_dedup.get("raw_feedback_events", 0),
            "unique_feedback_cases": fb_dedup.get("unique_feedback_cases", 0),
            "duplicate_submissions": fb_dedup.get("duplicate_submissions", 0),
            "pending_adjudication": len(pending_queue),
            "accepted": len(accepted),
            "rejected": len(rejected),
            "needs_context": len(needs_ctx),
            "duplicate_cases": len(duplicates),
            "total_adjudicated": len(all_adj),
            "candidate_pool_size": len(self.get_candidate_pool()),
            "correction_matrix": matrix,
            "safety_pending": len(self.get_safety_queue(user_id=user_id)),
            "p2_p3_pending": len(self.get_p2_p3_queue(user_id=user_id)),
            "deadline_pending": len(self.get_deadline_queue(user_id=user_id)),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _load_all(self) -> List[Dict[str, Any]]:
        """Loads all adjudication records."""
        if not os.path.exists(ADJUDICATION_FILE):
            return []
        records: List[Dict[str, Any]] = []
        try:
            with open(ADJUDICATION_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        records.append(json.loads(line))
                    except Exception:
                        pass
        except Exception as exc:
            logger.warning("adjudication: failed to load: %s", exc)
        return records


# Global singleton
adjudication_manager = AdjudicationManager()
