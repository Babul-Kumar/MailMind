from datetime import datetime, timezone
import os
import time
import json
import sqlite3
import hashlib
import threading
from collections import OrderedDict
from typing import Dict, Any, List, Optional, Tuple, Set
from threading import RLock

from backend.app.core.config import DATA_DIR

CACHE_DIR = os.path.join(DATA_DIR, "cache")
DB_PATH = os.path.join(CACHE_DIR, "mailmind_cache.db")
MAX_L1_PER_USER = 500  # Strict memory ceiling per user (~2-5MB) preventing OOM on 512MB RAM containers
ACTIVE_MODEL_HASH = "8524ad73965859ee022f1271caee0040928e7805ab7d32c49b2f26e994f98c06"


def compute_content_hash(subject: Optional[str], snippet: Optional[str], body: Optional[str]) -> str:
    """Computes a deterministic SHA-256 hash for message text content to detect changes."""
    content = f"{subject or ''}|{snippet or ''}|{body or ''}"
    return hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()[:32]


class UserEmailCache:
    """
    Thread-safe, user-isolated persistent email cache.
    - L1 LRU in-memory cache (bounded to 100 items per user) for sub-millisecond hot lookups without RAM bloat.
    - L2 persistent SQLite store (WAL mode, capped 2MB page cache) for durable queries and pagination across 50,000+ emails.
    """

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._local = threading.local()
        self._lock = RLock()
        self._mem_cache: Dict[str, OrderedDict] = {}
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA synchronous = NORMAL;")
            conn.execute("PRAGMA cache_size = -2000;")  # Limit SQLite page cache to 2MB RAM
            conn.execute("PRAGMA temp_store = MEMORY;")
            conn.execute("PRAGMA mmap_size = 0;")       # Prevent virtual memory expansion on Render 512MB RAM
            conn.execute("PRAGMA busy_timeout = 30000;")
            self._local.conn = conn
        return self._local.conn

    def _init_db(self):
        """Initializes tables and indexes, ensuring version-aware composite primary key."""
        with self._lock:
            conn = self._get_connection()
            cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_email_cache';")
            if not cur.fetchone():
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
                    model_version TEXT NOT NULL DEFAULT 'priority-v1',
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
                    deadline_status TEXT DEFAULT 'NONE',
                    action_evidence TEXT,
                    PRIMARY KEY (user_id, message_id, model_version)
                );
                """)
            else:
                cols = conn.execute("PRAGMA table_info(user_email_cache);").fetchall()
                pk_cols = [c[1] for c in cols if c[5] > 0]
                if "model_version" not in pk_cols:
                    conn.execute("""
                    CREATE TABLE IF NOT EXISTS user_email_cache_v49 (
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
                        model_version TEXT NOT NULL DEFAULT 'priority-v1',
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
                        deadline_status TEXT DEFAULT 'NONE',
                        action_evidence TEXT,
                        PRIMARY KEY (user_id, message_id, model_version)
                    );
                    """)
                    conn.execute("""
                    INSERT OR IGNORE INTO user_email_cache_v49 (
                        user_id, message_id, thread_id, internal_date, date_str,
                        sender, recipients, subject, snippet, body, content_hash,
                        model_version, predicted_priority, action_required,
                        deadline_detected, deadline_display, needs_attention,
                        refinement_applied, confidence, topic, data_json, analyzed_at,
                        is_stale, deadline_status, action_evidence
                    )
                    SELECT
                        user_id, message_id, thread_id, internal_date, date_str,
                        sender, recipients, subject, snippet, body, content_hash,
                        COALESCE(model_version, 'priority-v1'), predicted_priority,
                        action_required, deadline_detected, deadline_display,
                        needs_attention, refinement_applied, confidence, topic,
                        data_json, analyzed_at, is_stale,
                        COALESCE(deadline_status, 'NONE'), action_evidence
                    FROM user_email_cache;
                    """)
                    conn.execute("DROP TABLE user_email_cache;")
                    conn.execute("ALTER TABLE user_email_cache_v49 RENAME TO user_email_cache;")

            conn.execute("CREATE INDEX IF NOT EXISTS idx_cache_user_date ON user_email_cache(user_id, internal_date DESC);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cache_user_priority ON user_email_cache(user_id, predicted_priority);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cache_user_attention ON user_email_cache(user_id, needs_attention);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cache_user_version ON user_email_cache(user_id, model_version);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cache_user_thread ON user_email_cache(user_id, thread_id);")

            # Extended fields for date analysis, provenance, and historical email status
            cache_cols = [c[1] for c in conn.execute("PRAGMA table_info(user_email_cache);").fetchall()]
            if "is_analyzed" not in cache_cols:
                conn.execute("ALTER TABLE user_email_cache ADD COLUMN is_analyzed INTEGER DEFAULT 1;")
            if "model_artifact_hash" not in cache_cols:
                conn.execute("ALTER TABLE user_email_cache ADD COLUMN model_artifact_hash TEXT DEFAULT '8524ad73965859ee022f1271caee0040928e7805ab7d32c49b2f26e994f98c06';")

            conn.execute("CREATE INDEX IF NOT EXISTS idx_cache_user_date_stale ON user_email_cache(user_id, is_stale, internal_date DESC);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cache_user_analyzed ON user_email_cache(user_id, is_analyzed, internal_date DESC);")

            # Create analysis_preferences table
            conn.execute("""
            CREATE TABLE IF NOT EXISTS analysis_preferences (
                user_id TEXT NOT NULL,
                gmail_account_id TEXT NOT NULL,
                selected_period TEXT NOT NULL DEFAULT 'last_3_months',
                custom_start_date TEXT,
                custom_end_date TEXT,
                timezone TEXT NOT NULL DEFAULT 'UTC',
                updated_at REAL NOT NULL,
                PRIMARY KEY (user_id, gmail_account_id)
            );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_pref_user ON analysis_preferences(user_id);")

            # Create analysis_jobs table
            conn.execute("""
            CREATE TABLE IF NOT EXISTS analysis_jobs (
                job_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                gmail_account_id TEXT NOT NULL,
                period TEXT NOT NULL,
                start_date TEXT,
                end_date TEXT,
                status TEXT NOT NULL,
                total_eligible INTEGER DEFAULT 0,
                already_analyzed INTEGER DEFAULT 0,
                processed_count INTEGER DEFAULT 0,
                failed_count INTEGER DEFAULT 0,
                reused_from_cache INTEGER DEFAULT 0,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                completed_at REAL,
                error TEXT
            );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_user_status ON analysis_jobs(user_id, status);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_user_created ON analysis_jobs(user_id, created_at DESC);")
            conn.commit()

    def _l1_get(self, user_id: str, key: Any) -> Optional[Dict[str, Any]]:
        user_mem = self._mem_cache.get(user_id)
        if user_mem and key in user_mem:
            user_mem.move_to_end(key)
            return user_mem[key]
        return None

    def _l1_put(self, user_id: str, key: Any, item: Dict[str, Any]):
        if user_id not in self._mem_cache:
            self._mem_cache[user_id] = OrderedDict()
        user_mem = self._mem_cache[user_id]
        if key in user_mem:
            user_mem.move_to_end(key)
        user_mem[key] = item
        if len(user_mem) > MAX_L1_PER_USER:
            user_mem.popitem(last=False)

    def get(self, user_id: str, message_id: str, model_version: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Retrieves a cached prediction record for a specific user and message ID."""
        if not user_id or not message_id:
            return None

        from backend.app.ml.registry import model_registry
        active_ver = model_registry.get_active_version()
        target_ver = model_version or active_ver

        with self._lock:
            hit = self._l1_get(user_id, (message_id, target_ver))
            if hit is not None:
                return hit
            hit_def = self._l1_get(user_id, message_id)
            if hit_def is not None and hit_def.get("model_version") == target_ver:
                return hit_def

        conn = self._get_connection()
        if model_version:
            cur = conn.execute(
                "SELECT data_json, thread_id, is_stale, model_version FROM user_email_cache WHERE user_id = ? AND message_id = ? AND model_version = ?",
                (user_id, message_id, model_version)
            )
        else:
            cur = conn.execute(
                "SELECT data_json, thread_id, is_stale, model_version FROM user_email_cache WHERE user_id = ? AND message_id = ? ORDER BY (model_version = ?) DESC, analyzed_at DESC LIMIT 1",
                (user_id, message_id, active_ver)
            )
        row = cur.fetchone()
        if not row or row["is_stale"] == 1:
            return None
        try:
            data = json.loads(row["data_json"])
            if not data.get("thread_id") and row["thread_id"]:
                data["thread_id"] = row["thread_id"]
            m_ver = row["model_version"] or data.get("model_version", "priority-v1")
            data["model_version"] = m_ver
            with self._lock:
                self._l1_put(user_id, (message_id, m_ver), data)
                if m_ver == active_ver or not self._l1_get(user_id, message_id):
                    self._l1_put(user_id, message_id, data)
            return data
        except Exception:
            return None

    def set(self, user_id: str, message_id: str, data: Dict[str, Any]):
        """Caches a prediction record for a specific user."""
        if not user_id or not message_id or not data:
            return
        self.store_batch(user_id, [data])

    def store_batch(self, user_id: str, items: List[Dict[str, Any]], model_version: Optional[str] = None):
        """Batch inserts or replaces prediction records for a specific user."""
        if not user_id or not items:
            return
        now = time.time()
        rows = []

        from backend.app.ml.registry import model_registry
        active_ver = model_registry.get_active_version()

        with self._lock:
            for item in items:
                mid = item.get("email_id") or item.get("id") or item.get("message_id") or ""
                if not mid:
                    continue

                subject = item.get("subject", "")
                snippet = item.get("snippet", "")
                body = item.get("body", "")
                c_hash = item.get("content_hash") or compute_content_hash(subject, snippet, body)
                model_ver = item.get("model_version") or model_version or active_ver
                priority = item.get("final_priority") or item.get("predicted_priority") or "P4"
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
                item_copy["id"] = mid
                item_copy["email_id"] = mid
                item_copy["_cached_at"] = now
                item_copy["content_hash"] = c_hash
                item_copy["model_version"] = model_ver
                item_copy["thread_id"] = thread_id
                item_copy["predicted_priority"] = priority
                item_copy["final_priority"] = priority
                if "deadline_status" in item:
                    item_copy["deadline_status"] = item["deadline_status"]
                if "action_evidence" in item:
                    item_copy["action_evidence"] = item["action_evidence"]

                item_copy["is_analyzed"] = True
                item_copy["model_artifact_hash"] = ACTIVE_MODEL_HASH

                self._l1_put(user_id, (mid, model_ver), item_copy)
                if model_ver == active_ver or not self._l1_get(user_id, mid):
                    self._l1_put(user_id, mid, item_copy)

                data_json = json.dumps(item_copy)
                rows.append((
                    user_id, mid, thread_id, int(internal_date), date_str,
                    item.get("sender", ""), item.get("recipients", ""),
                    subject, snippet, body, c_hash, model_ver, priority,
                    action_req, deadline_det, deadline_disp, needs_att,
                    ref_app, confidence, topic, data_json, now, 0, 1, ACTIVE_MODEL_HASH
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
                    data_json, analyzed_at, is_stale, is_analyzed, model_artifact_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, rows)
            conn.commit()

    def store_raw_history_batch(self, user_id: str, items: List[Dict[str, Any]]):
        """Stores synchronized email headers/metadata into cache without running ML prediction."""
        if not user_id or not items:
            return
        now = time.time()
        rows = []
        with self._lock:
            conn = self._get_connection()
            item_mids = [it.get("email_id") or it.get("id") or it.get("message_id") for it in items if (it.get("email_id") or it.get("id") or it.get("message_id"))]
            analyzed_mids = set()
            if item_mids:
                for chunk_idx in range(0, len(item_mids), 500):
                    chunk = item_mids[chunk_idx:chunk_idx + 500]
                    placeholders = ",".join("?" for _ in chunk)
                    cur = conn.execute(
                        f"SELECT message_id FROM user_email_cache WHERE user_id = ? AND message_id IN ({placeholders}) AND is_analyzed = 1",
                        [user_id] + chunk
                    )
                    analyzed_mids.update(r[0] for r in cur.fetchall())

            for item in items:
                mid = item.get("email_id") or item.get("id") or item.get("message_id") or ""
                if not mid or mid in analyzed_mids:
                    continue
                subject = item.get("subject", "")
                snippet = item.get("snippet", "")
                body = item.get("body", "")
                c_hash = item.get("content_hash") or compute_content_hash(subject, snippet, body)
                thread_id = item.get("thread_id", "")
                date_str = item.get("date", "")
                internal_date = item.get("internal_date") or int(now * 1000)

                item_copy = dict(item)
                item_copy["id"] = mid
                item_copy["email_id"] = mid
                item_copy["_cached_at"] = now
                item_copy["content_hash"] = c_hash
                item_copy["model_version"] = "none"
                item_copy["thread_id"] = thread_id
                item_copy["is_analyzed"] = False
                item_copy["predicted_priority"] = None
                item_copy["final_priority"] = None

                data_json = json.dumps(item_copy)
                rows.append((
                    user_id, mid, thread_id, int(internal_date), date_str,
                    item.get("sender", ""), item.get("recipients", ""),
                    subject, snippet, body, c_hash, "none", None,
                    0, 0, None, 0, 0, 0.0, "other", data_json, None, 0, 0, None
                ))

            if rows:
                conn.executemany("""
                    INSERT OR IGNORE INTO user_email_cache (
                        user_id, message_id, thread_id, internal_date, date_str,
                        sender, recipients, subject, snippet, body,
                        content_hash, model_version, predicted_priority,
                        action_required, deadline_detected, deadline_display,
                        needs_attention, refinement_applied, confidence, topic,
                        data_json, analyzed_at, is_stale, is_analyzed, model_artifact_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, rows)
                conn.commit()

    def get_batch(
        self,
        user_id: str,
        message_ids: List[str],
        active_model_version: Optional[str] = None
    ) -> Tuple[Dict[str, Dict[str, Any]], List[str]]:
        """Retrieves cached records for a list of message IDs from L1 LRU or L2 SQLite."""
        if not user_id:
            return {}, list(message_ids)
        if not message_ids:
            return {}, []

        cached = {}
        missing = []

        from backend.app.ml.registry import model_registry
        active_ver = model_registry.get_active_version()
        target_ver = active_model_version or active_ver

        with self._lock:
            for mid in message_ids:
                rec = self._l1_get(user_id, (mid, target_ver))
                if rec is None:
                    rec_cand = self._l1_get(user_id, mid)
                    if rec_cand and rec_cand.get("model_version") == target_ver:
                        rec = rec_cand
                if rec is not None:
                    cached[mid] = rec
                else:
                    missing.append(mid)

        if not missing:
            return cached, []

        conn = self._get_connection()
        chunk_size = 500
        found_in_l2: Dict[str, Tuple[Dict[str, Any], str]] = {}
        for i in range(0, len(missing), chunk_size):
            chunk = missing[i:i + chunk_size]
            placeholders = ",".join(["?"] * len(chunk))
            if active_model_version:
                sql = f"""
                    SELECT message_id, data_json, model_version, is_stale
                    FROM user_email_cache
                    WHERE user_id = ? AND message_id IN ({placeholders}) AND model_version = ?
                """
                params: List[Any] = [user_id] + list(chunk) + [active_model_version]
            else:
                sql = f"""
                    SELECT message_id, data_json, model_version, is_stale
                    FROM user_email_cache
                    WHERE user_id = ? AND message_id IN ({placeholders})
                    ORDER BY analyzed_at DESC
                """
                params = [user_id] + list(chunk)

            cur = conn.execute(sql, params)
            for row in cur.fetchall():
                if row["is_stale"] == 1:
                    continue
                if active_model_version and row["model_version"] != active_model_version:
                    continue
                mid = row["message_id"]
                if mid not in found_in_l2:
                    try:
                        found_in_l2[mid] = (json.loads(row["data_json"]), row["model_version"])
                    except Exception:
                        pass

        still_missing = []
        with self._lock:
            for mid in missing:
                if mid in found_in_l2:
                    data, m_ver = found_in_l2[mid]
                    cached[mid] = data
                    self._l1_put(user_id, (mid, m_ver), data)
                    self._l1_put(user_id, mid, data)
                else:
                    still_missing.append(mid)

        return cached, still_missing

    def get_all_cached_metadata(self, user_id: str) -> Dict[str, Dict[str, Any]]:
        """Returns {message_id: {content_hash, model_version}} for fast sync checks."""
        if not user_id:
            return {}
        conn = self._get_connection()
        cur = conn.execute(
            "SELECT message_id, content_hash, model_version, is_stale FROM user_email_cache WHERE user_id = ?",
            (user_id,)
        )
        return {
            r["message_id"]: {
                "content_hash": r["content_hash"],
                "model_version": r["model_version"],
                "is_stale": r["is_stale"]
            }
            for r in cur.fetchall()
        }

    def get_all_cached_ids(self, user_id: str, active_model_version: Optional[str] = None) -> Set[str]:
        """Returns set of all cached message IDs for user."""
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
        """Clears all cached emails, preferences, and jobs for a specific user."""
        if not user_id:
            return
        with self._lock:
            self._mem_cache.pop(user_id, None)
            conn = self._get_connection()
            conn.execute("DELETE FROM user_email_cache WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM analysis_preferences WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM analysis_jobs WHERE user_id = ?", (user_id,))
            conn.commit()

    def clear_user_cache(self, user_id: str):
        self.clear_user(user_id)

    def update_email_body(self, user_id: str, message_id: str, full_body: str):
        """Updates cached email with full body."""
        if not user_id or not message_id:
            return
        with self._lock:
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
                    c_hash = compute_content_hash(row["subject"], row["snippet"], full_body)
                    data["content_hash"] = c_hash
                    self._l1_put(user_id, message_id, data)
                    conn.execute(
                        "UPDATE user_email_cache SET body = ?, data_json = ?, content_hash = ? WHERE user_id = ? AND message_id = ?",
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
                for k in list(user_mem.keys()):
                    if user_mem[k].get("model_version") != active_version:
                        user_mem.pop(k, None)
            conn = self._get_connection()
            conn.execute(
                "UPDATE user_email_cache SET is_stale = 1 WHERE user_id = ? AND model_version != ?",
                (user_id, active_version)
            )
            conn.commit()

    def query_emails(
        self,
        user_id: str,
        priority: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
        sort_order: str = "desc",
        action_required: Optional[bool] = None,
        model_version: Optional[str] = None,
        now_ts: Optional[float] = None,
        start_ts: Optional[float] = None,
        end_ts: Optional[float] = None,
        is_analyzed: Optional[bool] = None,
        use_effective_priority: bool = False
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Queries cached emails with streaming pagination, date-range bounding, and dynamic priority aging."""
        if not user_id:
            return [], 0

        from backend.app.core.action_policy import evaluate_priority_aging

        if now_ts is None:
            now_ts = datetime.now(timezone.utc).timestamp()

        conn = self._get_connection()
        where_clauses = ["user_id = ?", "is_stale = 0"]
        params: List[Any] = [user_id]

        if model_version:
            where_clauses.append("model_version = ?")
            params.append(model_version)

        if start_ts is not None:
            s_ms = int(start_ts if start_ts > 1e11 else start_ts * 1000)
            where_clauses.append("internal_date >= ?")
            params.append(s_ms)

        if end_ts is not None:
            e_ms = int(end_ts if end_ts > 1e11 else end_ts * 1000)
            where_clauses.append("internal_date <= ?")
            params.append(e_ms)

        if is_analyzed is True:
            where_clauses.append("(is_analyzed = 1 OR (is_analyzed IS NULL AND predicted_priority IS NOT NULL))")
        elif is_analyzed is False:
            where_clauses.append("(is_analyzed = 0 OR (is_analyzed IS NULL AND predicted_priority IS NULL))")

        target_priority = None
        if priority and priority.strip():
            p_norm = priority.upper().strip()
            if p_norm != "ALL":
                target_priority = p_norm
                if use_effective_priority:
                    if p_norm == "P1":
                        where_clauses.append("predicted_priority = 'P1'")
                    elif p_norm == "P2":
                        where_clauses.append("predicted_priority IN ('P1', 'P2')")
                    elif p_norm == "P3":
                        where_clauses.append("predicted_priority IN ('P1', 'P2', 'P3')")
                else:
                    if p_norm in ("P1", "P2", "P3", "P4"):
                        where_clauses.append("predicted_priority = ?")
                        params.append(p_norm)
                if p_norm == "NEEDS_ATTENTION":
                    where_clauses.append("(needs_attention = 1 OR predicted_priority IN ('P1', 'P2') OR action_required = 1)")

        if action_required is True:
            where_clauses.append("action_required = 1")
        elif action_required is False:
            where_clauses.append("action_required = 0")

        if search and search.strip():
            term = f"%{search.strip()}%"
            where_clauses.append("(subject LIKE ? OR sender LIKE ? OR snippet LIKE ? OR body LIKE ?)")
            params.extend([term, term, term, term])

        where_sql = " AND ".join(where_clauses)
        order_dir = "ASC" if sort_order.lower() == "asc" else "DESC"

        query_sql = f"""
            SELECT data_json, message_id, thread_id, predicted_priority, is_analyzed
            FROM user_email_cache
            WHERE {where_sql}
            ORDER BY internal_date {order_dir}, analyzed_at {order_dir}, message_id {order_dir}
        """
        cur = conn.execute(query_sql, params)
        all_candidates = []
        # Stream rows row-by-row to prevent high RAM allocation
        for r in cur:
            try:
                em = json.loads(r["data_json"])
                if not em.get("thread_id") and r["thread_id"]:
                    em["thread_id"] = r["thread_id"]

                mid = em.get("id") or em.get("email_id") or em.get("message_id") or r["message_id"]
                em["id"] = mid
                em["email_id"] = mid

                raw_is_analyzed = r["is_analyzed"] if "is_analyzed" in r.keys() else 1
                if raw_is_analyzed == 0 or (not em.get("predicted_priority") and not r["predicted_priority"]):
                    em["is_analyzed"] = False
                    em["original_priority"] = None
                    em["effective_priority"] = None
                    em["final_priority"] = None
                    em["action_status"] = None
                    if target_priority:
                        continue
                    all_candidates.append(em)
                    continue

                em["is_analyzed"] = True
                orig_p = em.get("original_priority") or em.get("model_priority") or r["predicted_priority"] or em.get("final_priority") or em.get("predicted_priority") or "P4"
                em["original_priority"] = orig_p
                aging = evaluate_priority_aging(em, now_ts=now_ts)
                effective_p = aging["effective_priority"]
                em["effective_priority"] = effective_p
                em["action_status"] = aging["action_status"]
                em["is_demoted"] = aging["is_demoted"]
                em["demotion_reason"] = aging["demotion_reason"]
                em["final_priority"] = orig_p
                em["predicted_priority"] = orig_p

                if target_priority:
                    if target_priority == "NEEDS_ATTENTION":
                        if aging["is_otp_expired"] or (aging["deadline_status"] == "EXPIRED" and not aging["is_critical_incident"]):
                            continue
                        if not (em.get("action_required") or aging["deadline_status"] in ("UPCOMING", "OVERDUE") or aging["is_critical_incident"] or effective_p == "P1" or (effective_p == "P2" and em.get("action_required"))):
                            continue
                    elif target_priority in ("P1", "P2", "P3", "P4"):
                        check_p = effective_p if use_effective_priority else orig_p
                        if check_p != target_priority:
                            continue

                all_candidates.append(em)
            except Exception:
                pass

        total_count = len(all_candidates)
        offset = max(0, (page - 1) * page_size)
        return all_candidates[offset : offset + page_size], total_count

    def get_mailbox_stats(
        self,
        user_id: str,
        model_version: Optional[str] = None,
        start_ts: Optional[float] = None,
        end_ts: Optional[float] = None,
        use_effective_priority: bool = False
    ) -> Dict[str, Any]:
        """
        Fast aggregate mailbox stats.
        Supports date-range bounding and uses direct SQL for totals and baseline priority tiers.
        Evaluates dynamic needs_attention and aging for active queues.
        """
        if not user_id:
            return self._empty_stats()

        conn = self._get_connection()
        where_sql = "user_id = ? AND is_stale = 0"
        params: List[Any] = [user_id]
        if model_version:
            where_sql += " AND model_version = ?"
            params.append(model_version)

        if start_ts is not None:
            s_ms = int(start_ts if start_ts > 1e11 else start_ts * 1000)
            where_sql += " AND internal_date >= ?"
            params.append(s_ms)

        if end_ts is not None:
            e_ms = int(end_ts if end_ts > 1e11 else end_ts * 1000)
            where_sql += " AND internal_date <= ?"
            params.append(e_ms)

        cur = conn.execute(f"""
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
            WHERE {where_sql}
        """, params)
        row = cur.fetchone()

        total = row["total"] or 0
        if total == 0:
            return self._empty_stats()

        p1_cnt = row["p1_count"] or 0
        p2_cnt = row["p2_count"] or 0
        p3_cnt = row["p3_count"] or 0
        p4_cnt = row["p4_count"] or 0
        refined = row["refined_count"] or 0
        avg_conf = round(row["avg_conf"] or 0.0, 4)

        from backend.app.core.action_policy import evaluate_priority_aging
        p1_p2_cur = conn.execute(
            f"SELECT data_json, predicted_priority FROM user_email_cache WHERE {where_sql} AND predicted_priority IN ('P1', 'P2')",
            params
        )
        now_ts = datetime.now(timezone.utc).timestamp()
        dynamic_counts = {"P1": 0, "P2": 0, "P3": p3_cnt, "P4": p4_cnt}
        dynamic_needs_attention = 0

        for r in p1_p2_cur:
            try:
                em = json.loads(r["data_json"])
                aging = evaluate_priority_aging(em, now_ts=now_ts)
                ep = aging.get("effective_priority") or "P2"
                dynamic_counts[ep] = dynamic_counts.get(ep, 0) + 1
                if aging.get("queue_placement") == "ACTIVE" or (aging.get("action_status") == "ACTIVE" and aging.get("is_actionable")):
                    dynamic_needs_attention += 1
            except Exception:
                p_fb = r["predicted_priority"] or "P2"
                dynamic_counts[p_fb] = dynamic_counts.get(p_fb, 0) + 1

        tier_counts = dynamic_counts if use_effective_priority else {"P1": p1_cnt, "P2": p2_cnt, "P3": p3_cnt, "P4": p4_cnt}
        highest_count = dynamic_counts.get("P1", 0) if use_effective_priority else p1_cnt

        percentages = {
            cls: round((cnt / total * 100), 1) if total > 0 else 0.0
            for cls, cnt in tier_counts.items()
        }

        last_analyzed = row["last_analyzed"]
        last_synced_str = (
            datetime.fromtimestamp(last_analyzed, timezone.utc).isoformat()
            if last_analyzed else datetime.now(timezone.utc).isoformat()
        )

        return {
            "total_analyzed": total,
            "refined_count": refined,
            "refinement_rate": round((refined / total * 100), 1) if total > 0 else 0.0,
            "counts": tier_counts,
            "effective_counts": dynamic_counts,
            "percentages": percentages,
            "average_confidence": avg_conf,
            "highest_priority_count": highest_count,
            "needs_attention_count": dynamic_needs_attention or (row["needs_attention_count"] or 0),
            "last_synced": last_synced_str,
        }

    def invalidate_model_version(self, user_id: str, target_version: str) -> int:
        """Controlled model version migration."""
        if not user_id or not target_version:
            return 0
        with self._lock:
            self._mem_cache.pop(user_id, None)
            conn = self._get_connection()
            cur = conn.execute("""
                UPDATE user_email_cache
                SET model_version = ?, is_stale = 0
                WHERE user_id = ? AND (model_version != ? OR model_version IS NULL)
            """, (target_version, user_id, target_version))
            affected = cur.rowcount
            conn.commit()
            return affected

    def get_analysis_preference(self, user_id: str, gmail_account_id: Optional[str] = None) -> Dict[str, Any]:
        """Returns the user's saved analysis preference or default 'last_3_months'."""
        if not user_id:
            return {
                "period": "last_3_months",
                "timezone": "UTC",
                "custom_start_date": None,
                "custom_end_date": None,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
        conn = self._get_connection()
        if gmail_account_id:
            cur = conn.execute(
                "SELECT selected_period, custom_start_date, custom_end_date, timezone, updated_at FROM analysis_preferences WHERE user_id = ? AND gmail_account_id = ?",
                (user_id, gmail_account_id)
            )
        else:
            cur = conn.execute(
                "SELECT selected_period, custom_start_date, custom_end_date, timezone, updated_at FROM analysis_preferences WHERE user_id = ? ORDER BY updated_at DESC LIMIT 1",
                (user_id,)
            )
        row = cur.fetchone()
        if row:
            up_str = datetime.fromtimestamp(row["updated_at"], timezone.utc).isoformat() if row["updated_at"] else datetime.now(timezone.utc).isoformat()
            return {
                "period": row["selected_period"] or "last_3_months",
                "timezone": row["timezone"] or "UTC",
                "custom_start_date": row["custom_start_date"],
                "custom_end_date": row["custom_end_date"],
                "updated_at": up_str
            }
        return {
            "period": "last_3_months",
            "timezone": "UTC",
            "custom_start_date": None,
            "custom_end_date": None,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }

    def set_analysis_preference(
        self,
        user_id: str,
        gmail_account_id: str,
        period: str,
        timezone_str: str = "UTC",
        custom_start_date: Optional[str] = None,
        custom_end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Saves or updates user date analysis preference."""
        now = time.time()
        with self._lock:
            conn = self._get_connection()
            conn.execute("""
                INSERT OR REPLACE INTO analysis_preferences (
                    user_id, gmail_account_id, selected_period, custom_start_date, custom_end_date, timezone, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (user_id, gmail_account_id, period, custom_start_date, custom_end_date, timezone_str, now))
            conn.commit()

        return {
            "period": period,
            "timezone": timezone_str,
            "custom_start_date": custom_start_date,
            "custom_end_date": custom_end_date,
            "updated_at": datetime.fromtimestamp(now, timezone.utc).isoformat()
        }

    def create_or_get_analysis_job(
        self,
        user_id: str,
        gmail_account_id: str,
        period: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        total_eligible: int = 0,
        already_analyzed: int = 0,
        reused_from_cache: int = 0
    ) -> Tuple[Dict[str, Any], bool]:
        """
        Idempotently returns an active job if one is already running for this user and period/scope,
        or creates a new job record.
        Returns (job_dict, is_new).
        """
        import uuid
        now = time.time()
        with self._lock:
            conn = self._get_connection()
            cur = conn.execute(
                "SELECT * FROM analysis_jobs WHERE user_id = ? AND period = ? AND status IN ('queued', 'running') ORDER BY created_at DESC LIMIT 1",
                (user_id, period)
            )
            row = cur.fetchone()
            if row:
                return dict(row), False

            job_id = f"job_{uuid.uuid4().hex[:12]}"
            status = "completed" if total_eligible > 0 and already_analyzed >= total_eligible else "running"
            completed_at = now if status == "completed" else None

            conn.execute("""
                INSERT INTO analysis_jobs (
                    job_id, user_id, gmail_account_id, period, start_date, end_date,
                    status, total_eligible, already_analyzed, processed_count, failed_count,
                    reused_from_cache, created_at, updated_at, completed_at, error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job_id, user_id, gmail_account_id, period, start_date, end_date,
                status, total_eligible, already_analyzed, already_analyzed, 0,
                reused_from_cache, now, now, completed_at, None
            ))
            conn.commit()

            cur = conn.execute("SELECT * FROM analysis_jobs WHERE job_id = ?", (job_id,))
            return dict(cur.fetchone()), True

    def update_analysis_job(
        self,
        job_id: str,
        status: Optional[str] = None,
        processed_count: Optional[int] = None,
        failed_count: Optional[int] = None,
        already_analyzed: Optional[int] = None,
        total_eligible: Optional[int] = None,
        reused_from_cache: Optional[int] = None,
        error: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Updates job progress and status atomically."""
        now = time.time()
        with self._lock:
            conn = self._get_connection()
            cur = conn.execute("SELECT * FROM analysis_jobs WHERE job_id = ?", (job_id,))
            row = cur.fetchone()
            if not row:
                return None

            new_status = status or row["status"]
            new_processed = processed_count if processed_count is not None else row["processed_count"]
            new_failed = failed_count if failed_count is not None else row["failed_count"]
            new_already = already_analyzed if already_analyzed is not None else row["already_analyzed"]
            new_total = total_eligible if total_eligible is not None else row["total_eligible"]
            new_reused = reused_from_cache if reused_from_cache is not None else row["reused_from_cache"]
            new_error = error if error is not None else row["error"]
            completed_at = row["completed_at"]
            if new_status in ("completed", "failed", "cancelled") and not completed_at:
                completed_at = now

            conn.execute("""
                UPDATE analysis_jobs
                SET status = ?, processed_count = ?, failed_count = ?, already_analyzed = ?,
                    total_eligible = ?, reused_from_cache = ?, error = ?, updated_at = ?, completed_at = ?
                WHERE job_id = ?
            """, (
                new_status, new_processed, new_failed, new_already,
                new_total, new_reused, new_error, now, completed_at, job_id
            ))
            conn.commit()

            cur = conn.execute("SELECT * FROM analysis_jobs WHERE job_id = ?", (job_id,))
            return dict(cur.fetchone())

    def get_analysis_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_connection()
        cur = conn.execute("SELECT * FROM analysis_jobs WHERE job_id = ?", (job_id,))
        row = cur.fetchone()
        return dict(row) if row else None

    def get_latest_analysis_job(self, user_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_connection()
        cur = conn.execute(
            "SELECT * FROM analysis_jobs WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
            (user_id,)
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def _empty_stats(self) -> Dict[str, Any]:
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


user_email_cache = UserEmailCache()
email_cache = user_email_cache
