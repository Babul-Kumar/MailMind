"""
prediction_log.py — Phase 43 Production Prediction Log
========================================================
Append-only JSONL log of every prediction generated in production.

Design rules:
  - APPEND ONLY — never mutate or delete entries.
  - USER-SCOPED — log directory is per user_id hash; entries carry user_id.
  - NO RAW CONTENT — subject/body/sender are never written to this log.
  - NO CREDENTIALS — OAuth tokens, access tokens are strictly excluded.
  - NOT FOR TRAINING — this log is evidence for review; it feeds dataset-v5
    only after human adjudication. Automatic training from this log is
    explicitly prohibited.
"""
import os
import json
import time
import hashlib
import logging
import threading
from typing import Dict, Any, Optional, List
from backend.app.core.config import BASE_DIR

logger = logging.getLogger("mailmind.prediction_log")

PREDICTION_LOG_DIR = os.path.join(BASE_DIR, "dataset", "monitoring", "prediction_logs")
_log_lock = threading.Lock()


def _log_path_for_user(user_id: str) -> str:
    """Returns the per-user prediction log path using a SHA-256 prefix for privacy."""
    uid_hash = hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:16]
    os.makedirs(PREDICTION_LOG_DIR, exist_ok=True)
    return os.path.join(PREDICTION_LOG_DIR, f"predictions_{uid_hash}.jsonl")


def log_prediction(
    user_id: str,
    message_id: str,
    thread_id: Optional[str],
    model_version: str,
    predicted_priority: str,
    confidence: float,
    action_required: bool,
    deadline_detected: bool,
    deadline_status: Optional[str],
    topic: Optional[str],
    needs_attention: bool = False,
    refinement_applied: bool = False,
) -> None:
    """
    Appends one prediction record to the user-scoped prediction log.

    This function is designed to be called fire-and-forget from the inference
    path. Any exception is caught and logged at WARNING level so it never
    breaks a production response.

    IMPORTANT: Raw email content (subject, body, sender) is deliberately
    excluded. OAuth tokens and credentials must never be passed here.
    """
    try:
        record = {
            "user_id": user_id,
            "message_id": message_id,
            "thread_id": thread_id or "",
            "model_version": model_version,
            "predicted_priority": predicted_priority,
            "confidence": round(float(confidence), 4),
            "action_required": bool(action_required),
            "deadline_detected": bool(deadline_detected),
            "deadline_status": deadline_status or "NONE",
            "topic": topic or "other",
            "needs_attention": bool(needs_attention),
            "refinement_applied": bool(refinement_applied),
            "prediction_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        path = _log_path_for_user(user_id)
        with _log_lock:
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
    except Exception as exc:
        logger.warning("prediction_log: failed to write entry: %s", exc)


def read_prediction_log(user_id: str, limit: int = 500) -> List[Dict[str, Any]]:
    """
    Reads the most recent `limit` prediction records for the given user.
    Returns an empty list if no log exists yet.
    """
    path = _log_path_for_user(user_id)
    if not os.path.exists(path):
        return []
    records: List[Dict[str, Any]] = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except Exception:
                        pass
    except Exception as exc:
        logger.warning("prediction_log: failed to read log: %s", exc)
    return records[-limit:]


def prediction_log_stats(user_id: str) -> Dict[str, Any]:
    """
    Returns lightweight aggregate statistics over the prediction log for
    a given user. Used by the monitoring summary endpoint.
    """
    records = read_prediction_log(user_id, limit=10_000)
    if not records:
        return {
            "total_logged": 0,
            "by_priority": {"P1": 0, "P2": 0, "P3": 0, "P4": 0},
            "by_model_version": {},
            "action_required_count": 0,
            "deadline_detected_count": 0,
        }

    by_priority: Dict[str, int] = {"P1": 0, "P2": 0, "P3": 0, "P4": 0}
    by_version: Dict[str, int] = {}
    action_count = 0
    deadline_count = 0

    for r in records:
        p = r.get("predicted_priority", "P4")
        by_priority[p] = by_priority.get(p, 0) + 1
        v = r.get("model_version", "unknown")
        by_version[v] = by_version.get(v, 0) + 1
        if r.get("action_required"):
            action_count += 1
        if r.get("deadline_detected"):
            deadline_count += 1

    return {
        "total_logged": len(records),
        "by_priority": by_priority,
        "by_model_version": by_version,
        "action_required_count": action_count,
        "deadline_detected_count": deadline_count,
    }
