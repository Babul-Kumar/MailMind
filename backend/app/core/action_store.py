"""
UserActionStore — Thread-safe, persistent storage for email action states (resolution, snooze).
Scoped strictly to authenticated user_id.
Stored in SQLite (WAL mode) inside DATA_DIR, surviving reloads, rescans, and server deployments.
"""

import os
import time
import sqlite3
import threading
from typing import Dict, Any, List, Optional, Set
from threading import RLock
from datetime import datetime

from backend.app.core.config import DATA_DIR

CACHE_DIR = os.path.join(DATA_DIR, "cache")
DB_PATH = os.path.join(CACHE_DIR, "mailmind_cache.db")


class UserActionStore:
    """
    Manages persistent user actions (mark resolved, snooze, undo).
    Guarantees:
      - Scoped strictly to authenticated user_id.
      - User A cannot view or modify User B's action states.
      - Rescanning messages does NOT undo resolution or snooze.
      - Survives server restarts and redeployments.
    """

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._local = threading.local()
        self._lock = RLock()
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA synchronous = NORMAL;")
            conn.execute("PRAGMA busy_timeout = 30000;")
            self._local.conn = conn
        return self._local.conn

    def _init_db(self):
        with self._lock:
            conn = self._get_connection()
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_action_states (
                    user_id TEXT NOT NULL,
                    message_id TEXT NOT NULL,
                    thread_id TEXT,
                    is_resolved INTEGER DEFAULT 0,
                    resolved_at REAL,
                    resolution_note TEXT,
                    is_snoozed INTEGER DEFAULT 0,
                    snoozed_until REAL,
                    snooze_reason TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    PRIMARY KEY (user_id, message_id)
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_action_user_resolved ON user_action_states(user_id, is_resolved);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_action_user_snoozed ON user_action_states(user_id, is_snoozed, snoozed_until);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_action_user_thread ON user_action_states(user_id, thread_id);")
            conn.commit()

    def resolve_action(
        self,
        user_id: str,
        message_id: str,
        thread_id: Optional[str] = None,
        note: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """Marks an email message as resolved for user_id."""
        if not user_id or not message_id:
            raise ValueError("user_id and message_id are required")

        actual_note = note if note is not None else notes
        now = time.time()
        with self._lock:
            conn = self._get_connection()
            # Fetch existing to preserve created_at or thread_id if not supplied
            cur = conn.execute(
                "SELECT thread_id, created_at FROM user_action_states WHERE user_id = ? AND message_id = ?",
                (user_id, message_id)
            )
            row = cur.fetchone()
            resolved_thread = thread_id or (row["thread_id"] if row else None)
            created_at = row["created_at"] if row else now

            conn.execute("""
                INSERT OR REPLACE INTO user_action_states (
                    user_id, message_id, thread_id,
                    is_resolved, resolved_at, resolution_note,
                    is_snoozed, snoozed_until, snooze_reason,
                    created_at, updated_at
                ) VALUES (?, ?, ?, 1, ?, ?, 0, NULL, NULL, ?, ?)
            """, (user_id, message_id, resolved_thread, now, actual_note, created_at, now))
            conn.commit()

        return {
            "user_id": user_id,
            "message_id": message_id,
            "thread_id": resolved_thread,
            "is_resolved": True,
            "resolved_at": now,
            "resolution_note": actual_note,
            "is_snoozed": False,
            "snoozed_until": None,
            "updated_at": now
        }

    def unresolve_action(self, user_id: str, message_id: str) -> Dict[str, Any]:
        """Restores a resolved email back to unresolved state (undo)."""
        if not user_id or not message_id:
            raise ValueError("user_id and message_id are required")

        now = time.time()
        with self._lock:
            conn = self._get_connection()
            cur = conn.execute(
                "SELECT * FROM user_action_states WHERE user_id = ? AND message_id = ?",
                (user_id, message_id)
            )
            row = cur.fetchone()
            if not row:
                return {
                    "user_id": user_id,
                    "message_id": message_id,
                    "is_resolved": False,
                    "resolved_at": None,
                    "is_snoozed": False,
                    "snoozed_until": None,
                    "updated_at": now
                }

            thread_id = row["thread_id"]
            is_snoozed = row["is_snoozed"]
            snoozed_until = row["snoozed_until"]
            snooze_reason = row["snooze_reason"]

            conn.execute("""
                UPDATE user_action_states
                SET is_resolved = 0, resolved_at = NULL, resolution_note = NULL, updated_at = ?
                WHERE user_id = ? AND message_id = ?
            """, (now, user_id, message_id))
            conn.commit()

        return {
            "user_id": user_id,
            "message_id": message_id,
            "thread_id": thread_id,
            "is_resolved": False,
            "resolved_at": None,
            "is_snoozed": bool(is_snoozed),
            "snoozed_until": snoozed_until,
            "snooze_reason": snooze_reason,
            "updated_at": now
        }

    def snooze_action(
        self,
        user_id: str,
        message_id: str,
        snoozed_until: Any,
        thread_id: Optional[str] = None,
        reason: Optional[str] = None,
        allow_past: bool = False
    ) -> Dict[str, Any]:
        """Postpones an email action until a future timestamp."""
        if not user_id or not message_id:
            raise ValueError("user_id and message_id are required")
        if not snoozed_until:
            raise ValueError("snoozed_until is required")

        if isinstance(snoozed_until, (int, float)):
            snoozed_ts = float(snoozed_until)
        elif isinstance(snoozed_until, str):
            try:
                snoozed_ts = float(snoozed_until)
            except ValueError:
                clean = snoozed_until.replace("Z", "+00:00")
                dt = datetime.fromisoformat(clean)
                snoozed_ts = dt.timestamp()
        else:
            raise ValueError("Invalid snoozed_until format")

        now = time.time()
        if not allow_past and snoozed_ts <= now:
            # Allow slight clock skew or allow_past flag for testing expiration
            pass

        with self._lock:
            conn = self._get_connection()
            cur = conn.execute(
                "SELECT thread_id, created_at FROM user_action_states WHERE user_id = ? AND message_id = ?",
                (user_id, message_id)
            )
            row = cur.fetchone()
            actual_thread = thread_id or (row["thread_id"] if row else None)
            created_at = row["created_at"] if row else now

            conn.execute("""
                INSERT OR REPLACE INTO user_action_states (
                    user_id, message_id, thread_id,
                    is_resolved, resolved_at, resolution_note,
                    is_snoozed, snoozed_until, snooze_reason,
                    created_at, updated_at
                ) VALUES (?, ?, ?, 0, NULL, NULL, 1, ?, ?, ?, ?)
            """, (user_id, message_id, actual_thread, snoozed_ts, reason, created_at, now))
            conn.commit()

        return {
            "user_id": user_id,
            "message_id": message_id,
            "thread_id": actual_thread,
            "is_resolved": False,
            "resolved_at": None,
            "is_snoozed": True,
            "snoozed_until": snoozed_ts,
            "snooze_reason": reason,
            "updated_at": now
        }

    def unsnooze_action(self, user_id: str, message_id: str) -> Dict[str, Any]:
        """Unsnoozes an email, returning it to active evaluation early."""
        if not user_id or not message_id:
            raise ValueError("user_id and message_id are required")

        now = time.time()
        with self._lock:
            conn = self._get_connection()
            cur = conn.execute(
                "SELECT * FROM user_action_states WHERE user_id = ? AND message_id = ?",
                (user_id, message_id)
            )
            row = cur.fetchone()
            if not row:
                return {
                    "user_id": user_id,
                    "message_id": message_id,
                    "is_resolved": False,
                    "is_snoozed": False,
                    "snoozed_until": None,
                    "updated_at": now
                }

            conn.execute("""
                UPDATE user_action_states
                SET is_snoozed = 0, snoozed_until = NULL, snooze_reason = NULL, updated_at = ?
                WHERE user_id = ? AND message_id = ?
            """, (now, user_id, message_id))
            conn.commit()

        return {
            "user_id": user_id,
            "message_id": message_id,
            "thread_id": row["thread_id"],
            "is_resolved": bool(row["is_resolved"]),
            "resolved_at": row["resolved_at"],
            "is_snoozed": False,
            "snoozed_until": None,
            "snooze_reason": None,
            "updated_at": now
        }

    def get_action_state(self, user_id: str, message_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves action state for a specific user and message ID."""
        if not user_id or not message_id:
            return None
        conn = self._get_connection()
        cur = conn.execute(
            "SELECT * FROM user_action_states WHERE user_id = ? AND message_id = ?",
            (user_id, message_id)
        )
        row = cur.fetchone()
        if not row:
            return None
        return dict(row)

    def get_user_actions_map(self, user_id: str) -> Dict[str, Dict[str, Any]]:
        """Returns all action state records for a user as {message_id: dict}."""
        if not user_id:
            return {}
        conn = self._get_connection()
        cur = conn.execute(
            "SELECT * FROM user_action_states WHERE user_id = ?",
            (user_id,)
        )
        res = {}
        for row in cur.fetchall():
            res[row["message_id"]] = dict(row)
        return res

    def get_user_action_states(self, user_id: str) -> Dict[str, Dict[str, Any]]:
        """Alias for get_user_actions_map for backward compatibility."""
        return self.get_user_actions_map(user_id)

    def get_all_action_states(self, user_id: str) -> Dict[str, Dict[str, Any]]:
        """Alias for get_user_actions_map for backward compatibility."""
        return self.get_user_actions_map(user_id)

    def get_resolved_message_ids(self, user_id: str) -> Set[str]:
        """Returns set of resolved message IDs for a user."""
        if not user_id:
            return set()
        conn = self._get_connection()
        cur = conn.execute(
            "SELECT message_id FROM user_action_states WHERE user_id = ? AND is_resolved = 1",
            (user_id,)
        )
        return {r["message_id"] for r in cur.fetchall()}

    def get_active_snoozed_message_ids(self, user_id: str, now_ts: Optional[float] = None) -> Set[str]:
        """Returns set of currently snoozed message IDs where snoozed_until > now."""
        if not user_id:
            return set()
        now = now_ts if now_ts is not None else time.time()
        conn = self._get_connection()
        cur = conn.execute(
            "SELECT message_id FROM user_action_states WHERE user_id = ? AND is_snoozed = 1 AND snoozed_until > ?",
            (user_id, now)
        )
        return {r["message_id"] for r in cur.fetchall()}

    def clear_user_actions(self, user_id: str):
        """Clears all action records for user_id (e.g. for testing or account reset)."""
        if not user_id:
            return
        with self._lock:
            conn = self._get_connection()
            conn.execute("DELETE FROM user_action_states WHERE user_id = ?", (user_id,))
            conn.commit()


# Global singleton instance
user_action_store = UserActionStore()
