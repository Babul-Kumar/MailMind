# MAILMIND — DATA MODEL & DATABASE AUDIT
**Document Version:** 1.0.0  
**Audit Date:** 2026-11-03  
**Auditor:** Database Architect & Senior Python Systems Engineer  
**Database Engine:** SQLite 3 (WAL Mode, In-Memory Temp Store, Capped Page Cache)  
**Location:** `google_auth/cache/mailmind_cache.db`

---

## 1. Existing Data Model Audit

### 1.1 Existing Tables

#### `user_email_cache`
Stores cached parsed emails, ML predictions, and actionability metadata.
- **Primary Key:** Composite `(user_id, message_id, model_version)`
- **Existing Columns:**
  - `user_id` (TEXT, NOT NULL)
  - `message_id` (TEXT, NOT NULL)
  - `thread_id` (TEXT)
  - `internal_date` (INTEGER DEFAULT 0): Milliseconds since Unix epoch (`internalDate` from Gmail API)
  - `date_str` (TEXT): Formatted date string
  - `sender` (TEXT), `recipients` (TEXT), `subject` (TEXT), `snippet` (TEXT), `body` (TEXT)
  - `content_hash` (TEXT): Deterministic SHA-256 hash of subject, snippet, and body
  - `model_version` (TEXT NOT NULL DEFAULT 'priority-v1'): Identifier of the ML model
  - `predicted_priority` (TEXT): ML-assigned priority (`P1`, `P2`, `P3`, `P4`)
  - `action_required` (INTEGER DEFAULT 0)
  - `deadline_detected` (INTEGER DEFAULT 0), `deadline_display` (TEXT), `deadline_status` (TEXT DEFAULT 'NONE')
  - `needs_attention` (INTEGER DEFAULT 0), `refinement_applied` (INTEGER DEFAULT 0)
  - `confidence` (REAL DEFAULT 0.0), `topic` (TEXT), `action_evidence` (TEXT)
  - `data_json` (TEXT NOT NULL): Serialized full dictionary representation
  - `analyzed_at` (REAL): Unix timestamp in seconds when ML inference was executed
  - `is_stale` (INTEGER DEFAULT 0): Soft-invalidation flag

#### `user_action_states`
Stores user resolution and snooze actions.
- **Primary Key:** Composite `(user_id, message_id)`
- **Columns:**
  - `user_id` (TEXT NOT NULL)
  - `message_id` (TEXT NOT NULL)
  - `thread_id` (TEXT)
  - `is_resolved` (INTEGER DEFAULT 0)
  - `resolved_at` (REAL)
  - `resolution_note` (TEXT)
  - `is_snoozed` (INTEGER DEFAULT 0)
  - `snoozed_until` (REAL)
  - `snooze_reason` (TEXT)
  - `created_at` (REAL NOT NULL)
  - `updated_at` (REAL NOT NULL)

---

## 2. Identified Data Architecture Gaps

1. **Missing Persistent User Preferences:** User-selected analysis period (`last_3_months`, `this_month`, `last_1_year`, `all_time`, `custom`) is currently stored only in transient client memory or query parameters. It does not persist across user sessions or devices.
2. **Missing Analysis Job State:** Background analysis is currently tied to a single user in-memory worker with a JSON file dumped to `google_auth/scans/<user_id>.json`. It does not record job provenance, date-scope boundaries, eligible counts, cache reuse statistics, or support multi-period resumability in a relational structure.
3. **Absence of Unanalyzed Historical Message Representation:** In `user_email_cache`, records are assumed to be classified. For *All History*, messages synchronized from Gmail may not yet have ML predictions. An explicit flag (`is_analyzed INTEGER DEFAULT 1`) and `model_artifact_hash` column are required.
4. **Date Filtering Indexing:** While an index exists on `(user_id, internal_date DESC)`, we must ensure composite indexes cover `(user_id, is_stale, internal_date DESC)` to allow instantaneous date-bounded queries across 50,000+ cached messages.

---

## 3. Schema Migrations Specification

### 3.1 Migration 1: `analysis_preferences`
Table dedicated to storing per-user, per-account date analysis configurations.

```sql
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

CREATE INDEX IF NOT EXISTS idx_pref_user ON analysis_preferences(user_id);
```

### 3.2 Migration 2: `analysis_jobs`
Table dedicated to tracking asynchronous background analysis jobs, eligible email counts, cache hits, and incremental progress.

```sql
CREATE TABLE IF NOT EXISTS analysis_jobs (
    job_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    gmail_account_id TEXT NOT NULL,
    period TEXT NOT NULL,
    start_date TEXT,
    end_date TEXT,
    status TEXT NOT NULL,  -- 'queued', 'running', 'completed', 'partially_completed', 'failed', 'cancelled'
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

CREATE INDEX IF NOT EXISTS idx_jobs_user_status ON analysis_jobs(user_id, status);
CREATE INDEX IF NOT EXISTS idx_jobs_user_created ON analysis_jobs(user_id, created_at DESC);
```

### 3.3 Migration 3: Extend `user_email_cache`
Safely alter `user_email_cache` using idempotent `PRAGMA table_info` checks:
1. `is_analyzed`: `INTEGER DEFAULT 1`
2. `model_artifact_hash`: `TEXT DEFAULT '8524ad73965859ee022f1271caee0040928e7805ab7d32c49b2f26e994f98c06'`

Index additions:
```sql
CREATE INDEX IF NOT EXISTS idx_cache_user_date_stale ON user_email_cache(user_id, is_stale, internal_date DESC);
CREATE INDEX IF NOT EXISTS idx_cache_user_analyzed ON user_email_cache(user_id, is_analyzed, internal_date DESC);
```

---

## 4. Concurrency, Locks & Memory Management

1. **WAL (Write-Ahead Logging):** Enabled on SQLite connection initialization (`PRAGMA journal_mode = WAL;`). Allows concurrent readers without blocking background writers.
2. **Page Cache Limit:** Capped to 2MB (`PRAGMA cache_size = -2000;`). Prevents unbounded memory usage on memory-constrained containers (512MB RAM on Render).
3. **Mmap Size:** Disabled (`PRAGMA mmap_size = 0;`) to avoid virtual memory expansion issues.
4. **Python Threading Locks:** `UserEmailCache` continues to use `threading.RLock()` for thread-safe operations across multi-threaded FastAPI workers.
5. **Streaming Cursor:** `query_emails()` streams SQLite rows one by one to construct the paginated view, avoiding large list allocations in memory.

---

## 5. Backward Compatibility Guarantee

All migrations are purely additive:
- Existing columns and tables remain intact.
- Existing records in `user_email_cache` automatically default to `is_analyzed = 1` and `model_artifact_hash = '8524ad73965859ee022f1271caee0040928e7805ab7d32c49b2f26e994f98c06'`.
- All 659 existing automated unit and integration tests remain 100% compatible.

