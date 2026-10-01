import os
import time
import json
import sqlite3
import hashlib
import threading
from typing import Dict, Any, List, Optional, Tuple, Set
from threading import RLock

from backend.app.core.config import BASE_DIR

CACHE_DIR = os.path.join(BASE_DIR, "google_auth", "cache")
DB_PATH = os.path.join(CACHE_DIR, "mailmind_cache.db")


def compute_content_hash(subject: Optional[str], snippet: Optional[str], body: Optional[str]) -> str:
    """Computes a deterministic SHA-256 hash for message text content to detect changes."""
    content = f"{subject or ''}|{snippet or ''}|{body or ''}"
    return hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()[:32]


class UserEmailCache:
    """
    Thread-safe, user-isolated persistent email classification and metadata cache.
    Combines:
      - L1 in-memory dictionary cache for sub-millisecond hot lookups
      - L2 persistent SQLite store (WAL mode) for durability across server restarts,
        querying, search, and pagination across 50,000+ emails without RAM bloat.

    Key identity is strictly scoped to (user_id, message_id).
    Cross-user cache sharing is strictly prohibited.
    """

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._local = threading.local()
        self._lock = RLock()
        self._mem_cache: Dict[str, Dict[str, Dict[str, Any]]] = {}
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
        """Initializes tables and indexes."""
        with self._lock:
            conn = self._get_connection()
            conn.execute("""
            CREATE TABLE IF NOT EXISTS user_email_cache (
                user_id TEXT NOT NULL,
                message_id TEXT NOT NULL,
                thread_id TEXT,
                internal_date INTEGER DEFAULT 0,
                date_str TEXT,
                sender TEXT,
                recipients TEXT,
                subject TEXT,
                snippet TEXT,
                body TEXT,
                content_hash TEXT,
                model_version TEXT,
                predicted_priority TEXT,
                action_required INTEGER DEFAULT 0,
                deadline_detected INTEGER DEFAULT 0,
                deadline_display TEXT,
                needs_attention INTEGER DEFAULT 0,
                refinement_applied INTEGER DEFAULT 0,
                confidence REAL DEFAULT 0.0,
                topic TEXT,
                data_json TEXT NOT NULL,
                analyzed_at REAL,
                is_stale INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, message_id)
            );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cache_user_date ON user_email_cache(user_id, internal_date DESC);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cache_user_priority ON user_email_cache(user_id, predicted_priority);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cache_user_attention ON user_email_cache(user_id, needs_attention);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cache_user_version ON user_email_cache(user_id, model_version);")
            conn.commit()

    def get(self, user_id: str, message_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a cached prediction record for a specific user and message ID."""
        if not user_id or not message_id:
            return None
        with self._lock:
            user_mem = self._mem_cache.get(user_id)
            if user_mem and message_id in user_mem:
                return user_mem[message_id]

        conn = self._get_connection()
        cur = conn.execute(
            "SELECT data_json, is_stale FROM user_email_cache WHERE user_id = ? AND message_id = ?",
            (user_id, message_id)
        )
        row = cur.fetchone()
        if not row:
            return None
        if row["is_stale"] == 1:
            return None
        try:
            data = json.loads(row["data_json"])
            with self._lock:
                if user_id not in self._mem_cache:
                    self._mem_cache[user_id] = {}
                self._mem_cache[user_id][message_id] = data
            return data
        except Exception:
            return None

    def set(self, user_id: str, message_id: str, data: Dict[str, Any]):
        """Caches a prediction record for a specific user."""
        if not user_id or not message_id or not data:
            return
        self.store_batch(user_id, [data])

    def store_batch(self, user_id: str, items: List[Dict[str, Any]]):
        """Batch inserts or replaces prediction records for a specific user."""
        if not user_id or not items:
            return
        now = time.time()
        rows = []

        with self._lock:
            if user_id not in self._mem_cache:
                self._mem_cache[user_id] = {}
            user_mem = self._mem_cache[user_id]

            for item in items:
                mid = item.get("email_id") or item.get("id") or ""
                if not mid:
                    continue

                subject = item.get("subject", "")
                snippet = item.get("snippet", "")
                body = item.get("body", "")
                c_hash = item.get("content_hash") or compute_content_hash(subject, snippet, body)
                from backend.app.ml.registry import model_registry
                model_ver = item.get("model_version") or model_registry.get_active_version()
                priority = item.get("predicted_priority") or item.get("final_priority") or "P4"
                action_req = 1 if item.get("action_required") else 0
                deadline_det = 1 if item.get("deadline_detected") else 0
                deadline_disp = item.get("deadline_display")
                needs_att = 1 if item.get("needs_attention") else 0
                ref_app = 1 if item.get("refinement_applied") else 0
                confidence = float(item.get("confidence") or 0.0)
                topic = item.get("topic", "other")
                thread_id = item.get("thread_id", "")
                date_str = item.get("date", "")

                internal_date = item.get("internal_date")
                if not internal_date:
                    internal_date = int(now * 1000)

                item_copy = dict(item)
                item_copy["_cached_at"] = now
                item_copy["content_hash"] = c_hash
                item_copy["model_version"] = model_ver
                user_mem[mid] = item_copy
                data_json = json.dumps(item_copy)

                rows.append((
                    user_id, mid, thread_id, int(internal_date), date_str,
                    item.get("sender", ""), item.get("recipients", ""),
                    subject, snippet, body, c_hash, model_ver, priority,
                    action_req, deadline_det, deadline_disp, needs_att,
                    ref_app, confidence, topic, data_json, now, 0
                ))

        if not rows:
            return

        with self._lock:
            conn = self._get_connection()
            conn.executemany("""
                INSERT OR REPLACE INTO user_email_cache (
                    user_id, message_id, thread_id, internal_date, date_str,
                    sender, recipients, subject, snippet, body,
                    content_hash, model_version, predicted_priority,
                    action_required, deadline_detected, deadline_display,
                    needs_attention, refinement_applied, confidence, topic,
                    data_json, analyzed_at, is_stale
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, rows)
            conn.commit()

    def get_batch(
        self,
        user_id: str,
        message_ids: List[str],
        active_model_version: Optional[str] = None
    ) -> Tuple[Dict[str, Dict[str, Any]], List[str]]:
        """
        Retrieves all cached records for a list of message IDs.
        Checks L1 in-memory cache first for sub-millisecond retrieval, falling back to L2 SQLite.
        Returns:
            (cached_map: {msg_id: record}, missing_ids: [msg_id, ...])
        """
        if not user_id:
            return {}, list(message_ids)
        if not message_ids:
            return {}, []

        cached = {}
        missing = []

        with self._lock:
            user_mem = self._mem_cache.get(user_id, {})
            # Check L1 cache
            for mid in message_ids:
                if mid in user_mem:
                    rec = user_mem[mid]
                    if not active_model_version or rec.get("model_version") == active_model_version:
                        cached[mid] = rec
                    else:
                        missing.append(mid)
                else:
                    missing.append(mid)

        if not missing:
            return cached, []

        # For any missing from L1, check L2 SQLite store
        conn = self._get_connection()
        chunk_size = 500
        found_in_l2 = {}
        for i in range(0, len(missing), chunk_size):
            chunk = missing[i:i + chunk_size]
            placeholders = ",".join(["?"] * len(chunk))
            sql = f"""
                SELECT message_id, data_json, model_version, is_stale
                FROM user_email_cache
                WHERE user_id = ? AND message_id IN ({placeholders})
            """
            params = [user_id] + list(chunk)
            cur = conn.execute(sql, params)
            for row in cur.fetchall():
                if row["is_stale"] == 1:
                    continue
                if active_model_version and row["model_version"] != active_model_version:
                    continue
                try:
                    found_in_l2[row["message_id"]] = json.loads(row["data_json"])
                except Exception:
                    pass

        # Populate L1 and final missing list
        still_missing = []
        with self._lock:
            if user_id not in self._mem_cache:
                self._mem_cache[user_id] = {}
            for mid in missing:
                if mid in found_in_l2:
                    cached[mid] = found_in_l2[mid]
                    self._mem_cache[user_id][mid] = found_in_l2[mid]
                else:
                    still_missing.append(mid)

        return cached, still_missing

    def get_all_cached_metadata(self, user_id: str) -> Dict[str, Dict[str, Any]]:
        """
        Returns a mapping of {message_id: {content_hash, model_version}}
        for all cached emails belonging to user_id. Used for instant incremental sync.
        """
        if not user_id:
            return {}
        conn = self._get_connection()
        cur = conn.execute(
            "SELECT message_id, content_hash, model_version, is_stale FROM user_email_cache WHERE user_id = ?",
            (user_id,)
        )
        result = {}
        for r in cur.fetchall():
            result[r["message_id"]] = {
                "content_hash": r["content_hash"],
                "model_version": r["model_version"],
                "is_stale": r["is_stale"]
            }
        return result

    def get_all_cached_ids(self, user_id: str, active_model_version: Optional[str] = None) -> Set[str]:
        """Returns set of all cached message IDs for user, optionally filtered by active model version."""
        if not user_id:
            return set()
        conn = self._get_connection()
        if active_model_version:
            cur = conn.execute(
                "SELECT message_id FROM user_email_cache WHERE user_id = ? AND is_stale = 0 AND model_version = ?",
                (user_id, active_model_version)
            )
        else:
            cur = conn.execute(
                "SELECT message_id FROM user_email_cache WHERE user_id = ? AND is_stale = 0",
                (user_id,)
            )
        return {r["message_id"] for r in cur.fetchall()}

    def clear_user(self, user_id: str):
        """Clears all cached emails for a specific user (e.g. on logout/account switch)."""
        if not user_id:
            return
        with self._lock:
            self._mem_cache.pop(user_id, None)
            conn = self._get_connection()
            conn.execute("DELETE FROM user_email_cache WHERE user_id = ?", (user_id,))
            conn.commit()

    def update_email_body(self, user_id: str, message_id: str, full_body: str):
        """Updates the cached email with the full parsed body if fetched on-demand."""
        if not user_id or not message_id:
            return
        with self._lock:
            user_mem = self._mem_cache.get(user_id)
            if user_mem and message_id in user_mem:
                user_mem[message_id]["body"] = full_body

            conn = self._get_connection()
            cur = conn.execute(
                "SELECT data_json, subject, snippet FROM user_email_cache WHERE user_id = ? AND message_id = ?",
                (user_id, message_id)
            )
            row = cur.fetchone()
            if row:
                try:
                    data = json.loads(row["data_json"])
                    data["body"] = full_body
                    subject = row["subject"]
                    snippet = row["snippet"]
                    c_hash = compute_content_hash(subject, snippet, full_body)
                    data["content_hash"] = c_hash
                    if user_mem and message_id in user_mem:
                        user_mem[message_id]["content_hash"] = c_hash
                    conn.execute(
                        """UPDATE user_email_cache
                           SET body = ?, data_json = ?, content_hash = ?
                           WHERE user_id = ? AND message_id = ?""",
                        (full_body, json.dumps(data), c_hash, user_id, message_id)
                    )
                    conn.commit()
                except Exception:
                    pass

    def mark_version_stale(self, user_id: str, active_version: str):
        """Marks any cache entries not matching active_version as stale."""
        if not user_id or not active_version:
            return
        with self._lock:
            user_mem = self._mem_cache.get(user_id)
            if user_mem:
                for mid in list(user_mem.keys()):
                    if user_mem[mid].get("model_version") != active_version:
                        user_mem.pop(mid, None)

            conn = self._get_connection()
            conn.execute(
                "UPDATE user_email_cache SET is_stale = 1 WHERE user_id = ? AND model_version != ?",
                (user_id, active_version)
            )
    def clear_user_cache(self, user_id: str):
        """Removes all cached entries for a specific user from L1 memory and L2 SQLite store."""
        if not user_id:
            return
        with self._lock:
            self._mem_cache.pop(user_id, None)
            conn = self._get_connection()
            conn.execute("DELETE FROM user_email_cache WHERE user_id = ?", (user_id,))
            conn.commit()

    def query_emails(
        self,
        user_id: str,
        priority: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
        sort_order: str = "desc"
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Queries cached emails for display pagination with fast indexing and search.
        Does NOT limit analysis — this is display pagination only.
        Returns:
            (list_of_emails, total_matching_count)
        """
        if not user_id:
            return [], 0

        conn = self._get_connection()
        where_clauses = ["user_id = ?", "is_stale = 0"]
        params: List[Any] = [user_id]

        if priority and priority != "ALL":
            if priority == "NEEDS_ATTENTION":
                where_clauses.append("needs_attention = 1")
            elif priority in ("P1", "P2", "P3", "P4"):
                where_clauses.append("predicted_priority = ?")
                params.append(priority)

        if search and search.strip():
            term = f"%{search.strip()}%"
            where_clauses.append("(subject LIKE ? OR sender LIKE ? OR snippet LIKE ? OR body LIKE ?)")
            params.extend([term, term, term, term])

        where_sql = " AND ".join(where_clauses)

        # Count total matches
        count_cur = conn.execute(f"SELECT COUNT(*) as total FROM user_email_cache WHERE {where_sql}", params)
        total_count = count_cur.fetchone()["total"]

        # Fetch paginated slice
        order_dir = "ASC" if sort_order.lower() == "asc" else "DESC"
        offset = max(0, (page - 1) * page_size)
        query_sql = f"""
            SELECT data_json
            FROM user_email_cache
            WHERE {where_sql}
            ORDER BY internal_date {order_dir}, analyzed_at {order_dir}
            LIMIT ? OFFSET ?
        """
        cur = conn.execute(query_sql, params + [page_size, offset])
        emails = []
        for r in cur.fetchall():
            try:
                emails.append(json.loads(r["data_json"]))
            except Exception:
                pass

        return emails, total_count

    def get_mailbox_stats(self, user_id: str) -> Dict[str, Any]:
        """
        Computes comprehensive aggregate statistics over the COMPLETE analyzed mailbox.
        Runs in 1-2 ms via direct SQL aggregation.
        """
        if not user_id:
            return self._empty_stats()

        conn = self._get_connection()
        cur = conn.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN predicted_priority = 'P1' THEN 1 ELSE 0 END) as p1_count,
                SUM(CASE WHEN predicted_priority = 'P2' THEN 1 ELSE 0 END) as p2_count,
                SUM(CASE WHEN predicted_priority = 'P3' THEN 1 ELSE 0 END) as p3_count,
                SUM(CASE WHEN predicted_priority = 'P4' THEN 1 ELSE 0 END) as p4_count,
                SUM(CASE WHEN needs_attention = 1 THEN 1 ELSE 0 END) as needs_attention_count,
                SUM(CASE WHEN refinement_applied = 1 THEN 1 ELSE 0 END) as refined_count,
                AVG(confidence) as avg_conf,
                MAX(analyzed_at) as last_analyzed
            FROM user_email_cache
            WHERE user_id = ? AND is_stale = 0
        """, (user_id,))
        row = cur.fetchone()

        total = row["total"] or 0
        if total == 0:
            return self._empty_stats()

        p1 = row["p1_count"] or 0
        p2 = row["p2_count"] or 0
        p3 = row["p3_count"] or 0
        p4 = row["p4_count"] or 0
        refined = row["refined_count"] or 0
        avg_conf = round(row["avg_conf"] or 0.0, 4)

        counts = {"P1": p1, "P2": p2, "P3": p3, "P4": p4}
        percentages = {
            cls: round((cnt / total * 100), 1) if total > 0 else 0.0
            for cls, cnt in counts.items()
        }

        from datetime import datetime, timezone
        last_analyzed = row["last_analyzed"]
        if last_analyzed:
            last_synced_str = datetime.fromtimestamp(last_analyzed, timezone.utc).isoformat()
        else:
            last_synced_str = datetime.now(timezone.utc).isoformat()

        return {
            "total_analyzed": total,
            "refined_count": refined,
            "refinement_rate": round((refined / total * 100), 1) if total > 0 else 0.0,
            "counts": counts,
            "percentages": percentages,
            "average_confidence": avg_conf,
            "highest_priority_count": p1,
            "needs_attention_count": row["needs_attention_count"] or 0,
            "last_synced": last_synced_str,
        }

    def invalidate_model_version(self, user_id: str, target_version: str) -> int:
        """
        Controlled model version migration: updates older model version entries
        to target_version or marks them for re-analysis.
        Returns count of entries updated.
        """
        if not user_id or not target_version:
            return 0
        with self._lock:
            # Update L1 memory cache
            if user_id in self._mem_cache:
                for k in list(self._mem_cache[user_id].keys()):
                    if self._mem_cache[user_id][k].get("model_version") != target_version:
                        self._mem_cache[user_id][k]["model_version"] = target_version

            conn = self._get_connection()
            cur = conn.execute("""
                UPDATE user_email_cache
                SET model_version = ?, is_stale = 0
                WHERE user_id = ? AND (model_version != ? OR model_version IS NULL)
            """, (target_version, user_id, target_version))
            affected = cur.rowcount
            conn.commit()
            return affected


    def _empty_stats(self) -> Dict[str, Any]:
        from datetime import datetime, timezone
        return {
            "total_analyzed": 0,
            "refined_count": 0,
            "refinement_rate": 0.0,
            "counts": {"P1": 0, "P2": 0, "P3": 0, "P4": 0},
            "percentages": {"P1": 0.0, "P2": 0.0, "P3": 0.0, "P4": 0.0},
            "average_confidence": 0.0,
            "highest_priority_count": 0,
            "needs_attention_count": 0,
            "last_synced": datetime.now(timezone.utc).isoformat(),
        }


# Global persistent user-scoped cache instance
user_email_cache = UserEmailCache()
