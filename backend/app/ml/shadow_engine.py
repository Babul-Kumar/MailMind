"""
shadow_engine.py — Phase 48 Live Shadow Inference & Evidence Collection Engine
=============================================================================
Provides production-safe, non-blocking shadow inference for candidate models
(specifically priority-v5.1) running alongside active production (priority-v4.1).

Architectural Invariants:
  1. USER-FACING IMMUTABILITY: Production classification always comes from active model.
     Shadow predictions are NEVER written to user_email_cache or exposed to user UI.
  2. STRICT FAILURE ISOLATION: Any failure in shadow loading, inference, or persistence
     is trapped and logged. Shadow failures MUST NEVER break production inference.
  3. STRICT USER ISOLATION: All shadow records are scoped to user_id.
     No cross-user cache access or cross-user record visibility.
  4. NO RAW CONTENT OR CREDENTIALS: Raw email bodies, headers, and OAuth tokens
     are strictly prohibited from shadow storage.
  5. DEDUPLICATION: (user_id, message_id, shadow_model_version) is deterministic.
     Repeated scans skip already-shadowed messages unless explicitly forced.
"""

import os
import re
import time
import json
import uuid
import sqlite3
import hashlib
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, List, Optional, Set, Tuple

import joblib
import numpy as np

from backend.app.core.config import BASE_DIR
from backend.app.ml.registry import model_registry
from backend.app.ml.predictor import load_model, predict_email, predict_batch

logger = logging.getLogger("mailmind.shadow_engine")

# Storage locations
SHADOW_DB_DIR = os.path.join(BASE_DIR, "google_auth", "cache")
SHADOW_DB_PATH = os.path.join(SHADOW_DB_DIR, "mailmind_shadow.db")
SHADOW_LOGS_DIR = os.path.join(BASE_DIR, "dataset", "monitoring", "shadow_logs")

_shadow_lock = threading.RLock()
_shadow_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="mailmind-shadow")

_CACHED_SHADOW_PIPELINE = None
_CACHED_SHADOW_VERSION = None


def invalidate_shadow_pipeline():
    """Invalidates the in-memory cached shadow pipeline."""
    global _CACHED_SHADOW_PIPELINE, _CACHED_SHADOW_VERSION
    with _shadow_lock:
        _CACHED_SHADOW_PIPELINE = None
        _CACHED_SHADOW_VERSION = None


def get_shadow_version() -> str:
    """Returns candidate model version from registry (defaults to priority-v5.1)."""
    try:
        reg = model_registry.get_registry()
        return reg.get("candidate_model", "priority-v5.1")
    except Exception as exc:
        logger.warning("Failed to read candidate model version from registry: %s", exc)
        return "priority-v5.1"


def get_shadow_model_path() -> str:
    """Returns the absolute path to candidate model artifact."""
    ver = get_shadow_version()
    # Candidate directory convention: priority-v5.1-candidate/model.joblib or priority-v5.1/model.joblib
    p1 = os.path.join(BASE_DIR, "dataset", "models", f"{ver}-candidate", "model.joblib")
    if os.path.exists(p1):
        return p1
    p2 = os.path.join(BASE_DIR, "dataset", "models", ver, "model.joblib")
    if os.path.exists(p2):
        return p2
    return p1


def load_shadow_model():
    """
    Safely loads the candidate model artifact.
    Wrapped in try/except; returns None if model cannot be loaded.
    """
    global _CACHED_SHADOW_PIPELINE, _CACHED_SHADOW_VERSION
    shadow_version = get_shadow_version()

    with _shadow_lock:
        if _CACHED_SHADOW_PIPELINE is not None and _CACHED_SHADOW_VERSION == shadow_version:
            return _CACHED_SHADOW_PIPELINE

        path = get_shadow_model_path()
        if not os.path.exists(path):
            logger.warning("Shadow model artifact not found at %s", path)
            return None

        try:
            pipeline = joblib.load(path)
            setattr(pipeline, "_model_version", shadow_version)
            _CACHED_SHADOW_PIPELINE = pipeline
            _CACHED_SHADOW_VERSION = shadow_version
            logger.info("Loaded shadow model %s from %s", shadow_version, path)
            return _CACHED_SHADOW_PIPELINE
        except Exception as exc:
            logger.error("Failed to load shadow model from %s: %s", path, exc)
            return None


# ---------------------------------------------------------------------------
# Deterministic Safety Categories (Section 9)
# ---------------------------------------------------------------------------

_PATTERNS_OTP = re.compile(
    r"\b(one[- ]time password|otp\b|verification code|security code|login code|passcode|confirm code)\b",
    re.IGNORECASE
)
_PATTERNS_MFA = re.compile(
    r"\b(two[- ]factor|2fa\b|multi[- ]factor|mfa\b|duo mobile|authenticator app|push notification to verify)\b",
    re.IGNORECASE
)
_PATTERNS_SECURITY = re.compile(
    r"\b(security alert|unauthorized (access|login|sign[- ]in)|suspicious activity|compromised account|new sign[- ]in|new device login|password (has been )?changed)\b",
    re.IGNORECASE
)
_PATTERNS_PASSWORD_RESET = re.compile(
    r"\b(reset your password|password reset (link|request)|forgot password|temporary password)\b",
    re.IGNORECASE
)
_PATTERNS_PAYMENT_FAILURE = re.compile(
    r"\b(payment (failed|declined|unsuccessful)|billing (problem|issue|failed)|subscription (suspended|cancelled|lapsed)|overdue balance|card declined)\b",
    re.IGNORECASE
)
_PATTERNS_URGENT_INCIDENT = re.compile(
    r"\b(system outage|service disruption|critical outage|sev[- ]?1|p1 incident|service degradation|emergency maintenance)\b",
    re.IGNORECASE
)
_PATTERNS_ACCOUNT_ACTIVATION = re.compile(
    r"\b(activate your account|verify your email|confirm your email|complete your registration|welcome to .* verify)\b",
    re.IGNORECASE
)
_PATTERNS_DEADLINE = re.compile(
    r"\b(due date|deadline|submit before|expires on|complete by|respond by|homework due|project due)\b",
    re.IGNORECASE
)


def classify_safety_category(subject: Optional[str], body: Optional[str]) -> Optional[str]:
    """
    Deterministically identifies if an email belongs to a high-risk safety category.
    Returns: 'OTP', 'MFA', 'account_compromise', 'security_alert', 'password_reset',
             'urgent_incident', 'payment_failure', 'account_activation', 'deadline', or None.
    """
    text = f"{subject or ''} {body or ''}"
    if not text.strip():
        return None

    if _PATTERNS_OTP.search(text):
        return "OTP"
    if _PATTERNS_MFA.search(text):
        return "MFA"
    if _PATTERNS_PASSWORD_RESET.search(text):
        return "password_reset"
    if _PATTERNS_SECURITY.search(text):
        if "compromis" in text.lower():
            return "account_compromise"
        return "security_alert"
    if _PATTERNS_PAYMENT_FAILURE.search(text):
        return "payment_failure"
    if _PATTERNS_URGENT_INCIDENT.search(text):
        return "urgent_incident"
    if _PATTERNS_ACCOUNT_ACTIVATION.search(text):
        return "account_activation"
    if _PATTERNS_DEADLINE.search(text):
        return "deadline"

    return None


# ---------------------------------------------------------------------------
# Shadow Storage Engine (SQLite + JSONL)
# ---------------------------------------------------------------------------

def _get_shadow_db_connection() -> sqlite3.Connection:
    """Opens a connection to the dedicated shadow database."""
    os.makedirs(SHADOW_DB_DIR, exist_ok=True)
    conn = sqlite3.connect(SHADOW_DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA busy_timeout = 30000;")
    return conn


def initialize_shadow_db():
    """Initializes the shadow table schema and performance indexes."""
    with _shadow_lock:
        conn = _get_shadow_db_connection()
        conn.execute("""
        CREATE TABLE IF NOT EXISTS shadow_predictions (
            shadow_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            message_id TEXT NOT NULL,
            thread_id TEXT,
            timestamp TEXT NOT NULL,
            active_model_version TEXT NOT NULL,
            shadow_model_version TEXT NOT NULL,
            active_prediction TEXT NOT NULL,
            shadow_prediction TEXT NOT NULL,
            active_confidence REAL NOT NULL,
            shadow_confidence REAL NOT NULL,
            priority_changed INTEGER NOT NULL,
            action_required_active INTEGER NOT NULL,
            action_required_shadow INTEGER NOT NULL,
            deadline_detected_active INTEGER NOT NULL,
            deadline_detected_shadow INTEGER NOT NULL,
            deadline_status_active TEXT NOT NULL,
            deadline_status_shadow TEXT NOT NULL,
            needs_attention_active INTEGER NOT NULL,
            needs_attention_shadow INTEGER NOT NULL,
            latency_active_ms REAL NOT NULL,
            latency_shadow_ms REAL NOT NULL,
            prediction_diverged INTEGER NOT NULL,
            safety_category TEXT,
            UNIQUE(user_id, message_id, shadow_model_version)
        );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_shadow_user_model ON shadow_predictions(user_id, shadow_model_version);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_shadow_diverged ON shadow_predictions(user_id, prediction_diverged);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_shadow_safety ON shadow_predictions(user_id, safety_category);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_shadow_time ON shadow_predictions(user_id, timestamp);")
        conn.commit()
        conn.close()


initialize_shadow_db()


def get_already_shadowed_ids(user_id: str, message_ids: List[str], shadow_model_version: str) -> Set[str]:
    """
    Returns the set of message_ids that have already been evaluated by this shadow model for this user.
    Enforces Section 5 (No Duplicate Shadow Work).
    """
    if not message_ids:
        return set()

    try:
        conn = _get_shadow_db_connection()
        # Query in chunks to avoid SQLite variable limit
        chunk_size = 500
        shadowed = set()
        for i in range(0, len(message_ids), chunk_size):
            chunk = message_ids[i:i + chunk_size]
            placeholders = ",".join("?" for _ in chunk)
            params = [user_id, shadow_model_version] + chunk
            cur = conn.execute(
                f"SELECT message_id FROM shadow_predictions WHERE user_id = ? AND shadow_model_version = ? AND message_id IN ({placeholders})",
                params
            )
            for row in cur.fetchall():
                shadowed.add(row["message_id"])
        conn.close()
        return shadowed
    except Exception as exc:
        logger.warning("Failed to query already shadowed IDs: %s", exc)
        return set()


def store_shadow_records(records: List[Dict[str, Any]]):
    """
    Stores shadow prediction records into the dedicated SQLite database and user-scoped JSONL log.
    Ensures zero raw email body and zero credentials.
    """
    if not records:
        return

    with _shadow_lock:
        try:
            conn = _get_shadow_db_connection()
            conn.executemany("""
            INSERT OR REPLACE INTO shadow_predictions (
                shadow_id, user_id, message_id, thread_id, timestamp,
                active_model_version, shadow_model_version,
                active_prediction, shadow_prediction,
                active_confidence, shadow_confidence,
                priority_changed,
                action_required_active, action_required_shadow,
                deadline_detected_active, deadline_detected_shadow,
                deadline_status_active, deadline_status_shadow,
                needs_attention_active, needs_attention_shadow,
                latency_active_ms, latency_shadow_ms,
                prediction_diverged, safety_category
            ) VALUES (
                :shadow_id, :user_id, :message_id, :thread_id, :timestamp,
                :active_model_version, :shadow_model_version,
                :active_prediction, :shadow_prediction,
                :active_confidence, :shadow_confidence,
                :priority_changed,
                :action_required_active, :action_required_shadow,
                :deadline_detected_active, :deadline_detected_shadow,
                :deadline_status_active, :deadline_status_shadow,
                :needs_attention_active, :needs_attention_shadow,
                :latency_active_ms, :latency_shadow_ms,
                :prediction_diverged, :safety_category
            )
            """, records)
            conn.commit()
            conn.close()
        except Exception as exc:
            logger.error("Failed to store shadow records to SQLite: %s", exc)

        # Append-only user-scoped JSONL log
        try:
            os.makedirs(SHADOW_LOGS_DIR, exist_ok=True)
            # Group records by user_id
            by_user: Dict[str, List[Dict[str, Any]]] = {}
            for r in records:
                by_user.setdefault(r["user_id"], []).append(r)

            for uid, user_records in by_user.items():
                uid_hash = hashlib.sha256(uid.encode("utf-8")).hexdigest()[:16]
                log_path = os.path.join(SHADOW_LOGS_DIR, f"shadow_{uid_hash}.jsonl")
                with open(log_path, "a", encoding="utf-8") as f:
                    for r in user_records:
                        f.write(json.dumps(r) + "\n")
        except Exception as exc:
            logger.warning("Failed to append to shadow JSONL log: %s", exc)


# ---------------------------------------------------------------------------
# Shadow Prediction Engine (Synchronous & Vectorized Batch)
# ---------------------------------------------------------------------------

class ShadowInferenceEngine:
    """
    Executes candidate model shadow inference in parallel with or following active inference.
    """

    def shadow_single_message(
        self,
        user_id: str,
        email_data: Dict[str, Any],
        active_prediction: Optional[Dict[str, Any]] = None,
        force: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Runs shadow inference on a single email.
        If already shadowed and not forced, returns existing record.
        Failure never propagates.
        """
        try:
            shadow_version = get_shadow_version()
            active_version = model_registry.get_active_version()
            message_id = email_data.get("email_id") or email_data.get("id") or email_data.get("message_id")
            if not message_id:
                return None

            if not force:
                existing = get_already_shadowed_ids(user_id, [message_id], shadow_version)
                if message_id in existing:
                    return None

            # Get active prediction if not provided
            if active_prediction is None:
                t0 = time.perf_counter()
                active_pipeline = load_model()
                active_prediction = predict_email(email_data, pipeline=active_pipeline)
                latency_active = (time.perf_counter() - t0) * 1000.0
            else:
                latency_active = active_prediction.get("latency_ms", 1.0)

            shadow_pipeline = load_shadow_model()
            if shadow_pipeline is None:
                logger.warning("Shadow pipeline unavailable; skipping shadow inference.")
                return None

            t_s0 = time.perf_counter()
            shadow_result = predict_email(email_data, pipeline=shadow_pipeline)
            latency_shadow = (time.perf_counter() - t_s0) * 1000.0

            act_p = active_prediction.get("final_priority") or active_prediction.get("predicted_priority", "P4")
            sh_p = shadow_result.get("final_priority") or shadow_result.get("predicted_priority", "P4")

            act_act = bool(active_prediction.get("action_required", False))
            sh_act = bool(shadow_result.get("action_required", False))

            act_dl = bool(active_prediction.get("deadline_detected", False))
            sh_dl = bool(shadow_result.get("deadline_detected", False))

            act_dl_st = str(active_prediction.get("deadline_status", "NONE"))
            sh_dl_st = str(shadow_result.get("deadline_status", "NONE"))

            act_na = bool(active_prediction.get("needs_attention", False))
            sh_na = bool(shadow_result.get("needs_attention", False))

            diverged = (act_p != sh_p) or (act_act != sh_act) or (act_dl != sh_dl)

            subj = email_data.get("subject", "")
            body = email_data.get("body", "")
            safety_cat = classify_safety_category(subj, body)

            record = {
                "shadow_id": f"sh_{uuid.uuid4().hex[:12]}",
                "user_id": str(user_id),
                "message_id": str(message_id),
                "thread_id": str(email_data.get("thread_id") or ""),
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "active_model_version": active_version,
                "shadow_model_version": shadow_version,
                "active_prediction": act_p,
                "shadow_prediction": sh_p,
                "active_confidence": round(float(active_prediction.get("confidence", 0.0)), 4),
                "shadow_confidence": round(float(shadow_result.get("confidence", 0.0)), 4),
                "priority_changed": int(act_p != sh_p),
                "action_required_active": int(act_act),
                "action_required_shadow": int(sh_act),
                "deadline_detected_active": int(act_dl),
                "deadline_detected_shadow": int(sh_dl),
                "deadline_status_active": act_dl_st,
                "deadline_status_shadow": sh_dl_st,
                "needs_attention_active": int(act_na),
                "needs_attention_shadow": int(sh_na),
                "latency_active_ms": round(latency_active, 2),
                "latency_shadow_ms": round(latency_shadow, 2),
                "prediction_diverged": int(diverged),
                "safety_category": safety_cat
            }

            store_shadow_records([record])
            return record

        except Exception as exc:
            logger.error("Error in shadow_single_message: %s", exc)
            return None

    def shadow_batch(
        self,
        user_id: str,
        emails: List[Dict[str, Any]],
        active_predictions: List[Dict[str, Any]],
        force: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Executes vectorized batch shadow prediction for high throughput.
        Skips already shadowed messages unless forced.
        """
        if not emails or not active_predictions:
            return []

        try:
            shadow_version = get_shadow_version()
            active_version = model_registry.get_active_version()

            # Align emails and active predictions by ID
            email_map = {}
            for e in emails:
                mid = e.get("email_id") or e.get("id") or e.get("message_id")
                if mid:
                    email_map[mid] = e

            paired_items = []
            for a in active_predictions:
                mid = a.get("email_id") or a.get("id") or a.get("message_id")
                if mid and mid in email_map:
                    paired_items.append((email_map[mid], a))

            if not paired_items:
                return []

            all_mids = [em.get("email_id") or em.get("id") or em.get("message_id") for em, _ in paired_items]
            all_mids = [mid for mid in all_mids if mid]
            already_shadowed = set() if force else get_already_shadowed_ids(user_id, all_mids, shadow_version)

            to_process = [
                (em, act) for em, act in paired_items
                if (em.get("email_id") or em.get("id") or em.get("message_id")) not in already_shadowed
            ]
            if not to_process:
                return []

            shadow_pipeline = load_shadow_model()
            if shadow_pipeline is None:
                logger.warning("Shadow pipeline unavailable; skipping batch.")
                return []

            to_eval_emails = [item[0] for item in to_process]
            t_s0 = time.perf_counter()
            shadow_results = predict_batch(to_eval_emails, pipeline=shadow_pipeline)
            total_shadow_ms = (time.perf_counter() - t_s0) * 1000.0
            per_item_shadow_ms = total_shadow_ms / max(1, len(to_eval_emails))

            records = []
            now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

            for (em, act_pred), sh_pred in zip(to_process, shadow_results):
                mid = em.get("email_id") or em.get("id") or em.get("message_id")
                act_p = act_pred.get("final_priority") or act_pred.get("predicted_priority", "P4")
                sh_p = sh_pred.get("final_priority") or sh_pred.get("predicted_priority", "P4")

                act_act = bool(act_pred.get("action_required", False))
                sh_act = bool(sh_pred.get("action_required", False))

                act_dl = bool(act_pred.get("deadline_detected", False))
                sh_dl = bool(sh_pred.get("deadline_detected", False))

                act_dl_st = str(act_pred.get("deadline_status", "NONE"))
                sh_dl_st = str(sh_pred.get("deadline_status", "NONE"))

                act_na = bool(act_pred.get("needs_attention", False))
                sh_na = bool(sh_pred.get("needs_attention", False))

                diverged = (act_p != sh_p) or (act_act != sh_act) or (act_dl != sh_dl)
                safety_cat = classify_safety_category(em.get("subject", ""), em.get("body", ""))

                rec = {
                    "shadow_id": f"sh_{uuid.uuid4().hex[:12]}",
                    "user_id": str(user_id),
                    "message_id": str(mid),
                    "thread_id": str(em.get("thread_id") or act_pred.get("thread_id") or ""),
                    "timestamp": now_iso,
                    "active_model_version": active_version,
                    "shadow_model_version": shadow_version,
                    "active_prediction": act_p,
                    "shadow_prediction": sh_p,
                    "active_confidence": round(float(act_pred.get("confidence", 0.0)), 4),
                    "shadow_confidence": round(float(sh_pred.get("confidence", 0.0)), 4),
                    "priority_changed": int(act_p != sh_p),
                    "action_required_active": int(act_act),
                    "action_required_shadow": int(sh_act),
                    "deadline_detected_active": int(act_dl),
                    "deadline_detected_shadow": int(sh_dl),
                    "deadline_status_active": act_dl_st,
                    "deadline_status_shadow": sh_dl_st,
                    "needs_attention_active": int(act_na),
                    "needs_attention_shadow": int(sh_na),
                    "latency_active_ms": round(float(act_pred.get("latency_ms", 1.0)), 2),
                    "latency_shadow_ms": round(per_item_shadow_ms, 2),
                    "prediction_diverged": int(diverged),
                    "safety_category": safety_cat
                }
                records.append(rec)

            store_shadow_records(records)
            return records

        except Exception as exc:
            logger.error("Error in shadow_batch: %s", exc)
            return []

    def shadow_batch_async(
        self,
        user_id: str,
        emails: List[Dict[str, Any]],
        active_predictions: List[Dict[str, Any]]
    ):
        """
        Dispatches shadow prediction to background thread pool.
        Fire-and-forget: returns immediately so production request is never blocked.
        """
        try:
            _shadow_executor.submit(self.shadow_batch, user_id, emails, active_predictions)
        except Exception as exc:
            logger.warning("Failed to submit async shadow job: %s", exc)


# Global singleton instance
shadow_engine = ShadowInferenceEngine()
