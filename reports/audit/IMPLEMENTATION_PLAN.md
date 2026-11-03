# MAILMIND — DATE-BASED EMAIL ANALYSIS IMPLEMENTATION PLAN
**Document Version:** 1.0.0  
**Date:** 2026-11-03  
**Status:** Approved for Implementation  
**Target Architecture:** Multi-view Mailbox, Date-Scoped Incremental Analysis, React Dashboard

---

## 1. Overview & Objectives

This implementation plan outlines the step-by-step technical execution for adding date-scoped email analysis, incremental ML inference, cache reuse, and historical mailbox browsing to MailMind, complete with a clean React interface.

### Non-Negotiable Invariants
1. **Frozen Production Model:** `priority-v5.1` (SHA-256: `8524ad73965859ee022f1271caee0040928e7805ab7d32c49b2f26e994f98c06`) remains 100% frozen. No retraining, parameter modification, or prompt engineering replacements.
2. **Action Invariance:** The *Needs Attention* queue displays all unresolved actions regardless of the selected analysis period.
3. **Data Preservation:** Switching analysis periods or browsing history never deletes older synchronized messages or analysis records.
4. **Zero Full-Sync Re-triggering:** Switching between already analyzed periods reuses 100% of cached results without calling Gmail APIs.

---

## 2. Phase-by-Phase Execution Plan

### Phase 0: Repository Audit & Architecture Design (COMPLETED)
- Inspect existing codebase (`backend/app/gmail/scan_engine.py`, `backend/app/core/cache.py`, `backend/app/api/routes_emails.py`, `backend/app/core/action_policy.py`).
- Author `DATE_ANALYSIS_AUDIT.md`.
- Author `API_CONTRACTS.md`.
- Author `DATA_MODEL_AUDIT.md`.
- Author `IMPLEMENTATION_PLAN.md`.

---

### Phase 1: Backend Data Model & Migrations
1. Update `backend/app/core/cache.py` with automatic, idempotent SQLite schema migrations:
   - Create `analysis_preferences` table with `(user_id, gmail_account_id)` primary key.
   - Create `analysis_jobs` table for persistent job tracking and resumability.
   - Extend `user_email_cache` with `is_analyzed` and `model_artifact_hash` columns.
   - Add composite indexes for date queries and analyzed status.
2. Implement preference and job persistence methods in `UserEmailCache`:
   - `get_analysis_preference(user_id, gmail_account_id)`
   - `set_analysis_preference(user_id, gmail_account_id, period, ...)`
   - `create_or_get_analysis_job(...)`
   - `update_analysis_job(...)`
   - `get_active_analysis_job(user_id)`

---

### Phase 2: Date Range Engine (`backend/app/core/date_utils.py`)
1. Implement canonical period definitions:
   - `this_month`: 1st day of month at 00:00:00 through current time in target timezone.
   - `last_3_months`: Current time minus 3 calendar months (`relativedelta(months=3)`) through current time.
   - `last_1_year`: Current time minus 12 calendar months (`relativedelta(years=1)`) through current time.
   - `all_time`: Epoch 0 through current time.
   - `custom`: Inclusive start date (`00:00:00`) to inclusive end date (`23:59:59.999`).
2. Input validation:
   - Reject start date > end date.
   - Reject end date in the future.
   - Validate IANA timezones using `zoneinfo.ZoneInfo`.
3. Gmail query builder:
   - Generate Gmail search query syntax (e.g. `after:YYYY/MM/DD before:YYYY/MM/DD`) respecting date boundaries.
4. Timestamps returned in UTC ISO 8601 and epoch milliseconds for SQLite comparisons.

---

### Phase 3: Incremental Analysis Engine
1. Update `backend/app/gmail/scan_engine.py`:
   - Extend `MailboxScanJob` and `scan_manager` to support date-scoped jobs (`start_ts`, `end_ts`, `period`).
   - Use Gmail query filter during discovery to fetch only message IDs falling in the period.
   - Compare discovered IDs with `user_email_cache` to identify already-analyzed IDs vs missing IDs.
   - If missing IDs exist, fetch metadata and predict in batches of 25.
   - Store predictions and update `analysis_jobs` progress counters atomically.
   - Prevent duplicate concurrent jobs for the same user and scope.

---

### Phase 4: API Route Controllers
1. Author `backend/app/api/routes_analysis.py`:
   - `GET /api/analysis/config`
   - `PUT /api/analysis/config`
   - `GET /api/analysis/summary`
   - `POST /api/analysis/start`
   - `GET /api/analysis/status`
2. Update `backend/app/api/routes_emails.py`:
   - Add `GET /api/emails/recent` with period filtering and pagination.
   - Add `GET /api/emails/history` for browsing historical messages with `is_analyzed` flags.
   - Preserve existing `GET /api/emails` and `GET /api/emails/{message_id}`.
3. Update `backend/app/api/routes_actions.py`:
   - Add `GET /api/actions/attention` ensuring all active actions are surfaced across all dates.
4. Mount `routes_analysis.py` in `backend/app/main.py`.

---

### Phase 5: React Interface (`react_app/`)
1. Create `react_app/` structure:
   - `react_app/app.py`: Main entrypoint with multi-page navigation.
   - `react_app/client.py`: Thread-safe, session-aware HTTP client communicating with FastAPI backend.
   - `react_app/views/dashboard.py`: Period selector, progress bar, overview stats.
   - `react_app/views/recent_mail.py`: Recent Mail view with search, priority filtering, and pagination.
   - `react_app/views/history.py`: All History view with date range filter, unanalyzed badges, and manual trigger.
   - `react_app/views/needs_attention.py`: Action queue displaying unresolved security alerts and tasks.
   - `react_app/views/analytics.py`: Charts showing priority distribution, period coverage, and cache hit rates.
   - `react_app/views/settings.py`: Default period, timezone, and account configuration.

---

### Phase 6: Security, Isolation & Session Handoff
1. Verify user isolation in SQLite queries and in-memory caches.
2. Confirm session handoff protocol allows React to authenticate safely without leaking Google OAuth credentials or tokens into browser storage.
3. Verify CSRF protection and secure cookie policies.

---

### Phase 7: Automated Testing & Verification
1. Author `tests/test_date_analysis.py`:
   - Unit tests for `date_utils.py` (boundaries, leap year, month-end, timezones, validations).
   - Integration tests for `routes_analysis.py` (GET/PUT config, summary, start, status).
   - Incremental analysis tests (cache hit, partial analyze, job idempotency).
   - History endpoint tests (browsing without analyzing, pagination).
   - Smart action queue date-invariance tests.
2. Run complete test suite (all 659+ tests) to guarantee zero regressions.

---

### Phase 8: Final Documentation & Deployment Readiness
1. Author `DATE_ANALYSIS_IMPLEMENTATION.md`.
2. Update `reports/TEST_RESULTS.md`.
3. Author `DEPLOYMENT_GUIDE.md` and `ROLLBACK_GUIDE.md`.
4. Re-verify production model artifact SHA-256 hash before and after execution.

