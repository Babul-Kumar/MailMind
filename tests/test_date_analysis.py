"""
Automated Test Suite for Date-Based Email Analysis, Incremental Processing,
Cache Reuse, Historical Mailbox, and Smart Action Queue Date-Invariance.
Verifies all contract specifications and ensures production model immutability.
"""

import time
import json
import pytest
from datetime import datetime, timezone, timedelta, date
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.cache import user_email_cache, compute_content_hash, ACTIVE_MODEL_HASH
from backend.app.core.session import session_manager, SessionData
from backend.app.core.date_utils import (
    calculate_period_boundaries,
    validate_date_range,
    resolve_timezone,
    SUPPORTED_PERIODS,
    DEFAULT_PERIOD
)
from backend.app.core.action_store import user_action_store
from backend.app.ml.registry import model_registry

client = TestClient(app)

TEST_USER_A = "test_user_date_a"
TEST_USER_B = "test_user_date_b"
TEST_EMAIL_A = "user_a@example.com"
TEST_EMAIL_B = "user_b@example.com"


@pytest.fixture(autouse=True)
def setup_test_users():
    """Sets up isolated sessions and cleans test data for each test run."""
    now = time.time()
    user_email_cache.clear_user(TEST_USER_A)
    user_email_cache.clear_user(TEST_USER_B)

    # Create Session A
    session_a = SessionData(
        session_id="session_date_a_token",
        user_id=TEST_USER_A,
        email=TEST_EMAIL_A,
        credentials={"token": "fake_token_a", "refresh_token": "fake_refresh_a"},
        created_at=now,
        expires_at=now + 3600
    )
    session_manager._sessions["session_date_a_token"] = session_a

    # Create Session B
    session_b = SessionData(
        session_id="session_date_b_token",
        user_id=TEST_USER_B,
        email=TEST_EMAIL_B,
        credentials={"token": "fake_token_b", "refresh_token": "fake_refresh_b"},
        created_at=now,
        expires_at=now + 3600
    )
    session_manager._sessions["session_date_b_token"] = session_b

    yield

    user_email_cache.clear_user(TEST_USER_A)
    user_email_cache.clear_user(TEST_USER_B)
    session_manager._sessions.pop("session_date_a_token", None)
    session_manager._sessions.pop("session_date_b_token", None)


# =============================================================================
# 1. DATE RANGE CALCULATION & BOUNDARY TESTS
# =============================================================================

class TestDateRangeEngine:
    def test_this_month_boundary_utc(self):
        fixed_now = datetime(2026, 11, 15, 14, 30, 0, tzinfo=timezone.utc)
        b = calculate_period_boundaries(period="this_month", tz_name="UTC", now=fixed_now)
        assert b["period"] == "this_month"
        assert b["start_iso"].startswith("2026-11-01T00:00:00")
        assert b["end_iso"].startswith("2026-11-15T14:30:00")
        assert b["start_ts_sec"] < b["end_ts_sec"]

    def test_this_month_boundary_kolkata(self):
        fixed_now = datetime(2026, 11, 15, 14, 30, 0, tzinfo=timezone.utc)
        b = calculate_period_boundaries(period="this_month", tz_name="Asia/Kolkata", now=fixed_now)
        # Nov 1 00:00 IST is Oct 31 18:30 UTC
        assert b["start_iso"].startswith("2026-10-31T18:30:00")

    def test_last_1_month_calendar_subtraction(self):
        fixed_now = datetime(2026, 11, 3, 12, 0, 0, tzinfo=timezone.utc)
        b = calculate_period_boundaries(period="last_1_month", tz_name="UTC", now=fixed_now)
        assert b["start_iso"].startswith("2026-10-03T12:00:00")
        assert b["end_iso"].startswith("2026-11-03T12:00:00")

    def test_last_2_months_calendar_subtraction(self):
        fixed_now = datetime(2026, 11, 3, 12, 0, 0, tzinfo=timezone.utc)
        b = calculate_period_boundaries(period="last_2_months", tz_name="UTC", now=fixed_now)
        assert b["start_iso"].startswith("2026-09-03T12:00:00")
        assert b["end_iso"].startswith("2026-11-03T12:00:00")

    def test_last_3_months_calendar_subtraction(self):
        fixed_now = datetime(2026, 11, 3, 12, 0, 0, tzinfo=timezone.utc)
        b = calculate_period_boundaries(period="last_3_months", tz_name="UTC", now=fixed_now)
        assert b["start_iso"].startswith("2026-08-03T12:00:00")
        assert b["end_iso"].startswith("2026-11-03T12:00:00")

    def test_last_1_year_calendar_subtraction(self):
        fixed_now = datetime(2026, 11, 3, 12, 0, 0, tzinfo=timezone.utc)
        b = calculate_period_boundaries(period="last_1_year", tz_name="UTC", now=fixed_now)
        assert b["start_iso"].startswith("2025-11-03T12:00:00")

    def test_all_time_boundaries(self):
        b = calculate_period_boundaries(period="all_time", tz_name="UTC")
        assert b["start_iso"] is None
        assert b["start_ts_sec"] == 0.0
        assert b["gmail_query"] == ""

    def test_custom_range_valid(self):
        s_date = "2026-08-01"
        e_date = "2026-10-31"
        b = calculate_period_boundaries(
            period="custom",
            tz_name="UTC",
            custom_start_date=s_date,
            custom_end_date=e_date
        )
        assert b["period"] == "custom"
        assert b["start_iso"].startswith("2026-08-01T00:00:00")
        assert "after:2026/07/31" in b["gmail_query"]

    def test_custom_range_start_after_end_rejected(self):
        with pytest.raises(ValueError, match="cannot be after end_date"):
            validate_date_range("2026-11-01", "2026-10-01", tz_name="UTC")

    def test_custom_range_future_date_rejected(self):
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        with pytest.raises(ValueError, match="cannot be in the future"):
            validate_date_range("2026-01-01", tomorrow, tz_name="UTC")

    def test_custom_range_malformed_rejected(self):
        with pytest.raises(ValueError, match="Invalid start_date"):
            validate_date_range("not-a-date", "2026-10-01", tz_name="UTC")

    def test_month_end_and_leap_year(self):
        # Leap year 2024 Feb 29
        fixed_leap = datetime(2024, 2, 29, 10, 0, 0, tzinfo=timezone.utc)
        b = calculate_period_boundaries(period="this_month", tz_name="UTC", now=fixed_leap)
        assert b["start_iso"].startswith("2024-02-01T00:00:00")

        # 3 months prior to May 31 lands on Feb 29 in a leap year
        fixed_may = datetime(2024, 5, 31, 10, 0, 0, tzinfo=timezone.utc)
        b3 = calculate_period_boundaries(period="last_3_months", tz_name="UTC", now=fixed_may)
        assert b3["start_iso"].startswith("2024-02-29T10:00:00")


# =============================================================================
# 2. ANALYSIS CONFIGURATION API TESTS
# =============================================================================

class TestAnalysisConfigAPI:
    def test_get_config_default(self):
        res = client.get("/api/analysis/config", headers={"Authorization": "Bearer session_date_a_token"})
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["period"] == "last_3_months"
        assert data["timezone"] == "UTC"

    def test_put_config_valid(self):
        res = client.put(
            "/api/analysis/config",
            json={"period": "this_month", "timezone": "Asia/Kolkata"},
            headers={"Authorization": "Bearer session_date_a_token"}
        )
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["period"] == "this_month"
        assert data["timezone"] == "Asia/Kolkata"

        # Verify persistence on subsequent GET
        get_res = client.get("/api/analysis/config", headers={"Authorization": "Bearer session_date_a_token"})
        assert get_res.json()["data"]["period"] == "this_month"
        assert get_res.json()["data"]["timezone"] == "Asia/Kolkata"

    def test_put_config_invalid_period(self):
        res = client.put(
            "/api/analysis/config",
            json={"period": "invalid_period_name"},
            headers={"Authorization": "Bearer session_date_a_token"}
        )
        assert res.status_code == 422

    def test_put_config_custom_validation_error(self):
        res = client.put(
            "/api/analysis/config",
            json={
                "period": "custom",
                "custom_start_date": "2026-11-01",
                "custom_end_date": "2026-10-01"
            },
            headers={"Authorization": "Bearer session_date_a_token"}
        )
        assert res.status_code == 422
        assert "cannot be after end_date" in res.text


# =============================================================================
# 3. INCREMENTAL ANALYSIS & CACHE REUSE TESTS
# =============================================================================

class TestIncrementalAnalysisEngine:
    def test_cache_reuse_and_idempotency(self):
        now = time.time()
        now_ms = int(now * 1000)

        # Pre-seed 3 emails in cache: 2 inside last 3 months, 1 from 6 months ago
        email_recent_1 = {
            "email_id": "msg_recent_1",
            "subject": "Recent Invoice Q3",
            "snippet": "Invoice attached",
            "body": "Invoice attached please pay",
            "internal_date": now_ms - (10 * 86400 * 1000),  # 10 days ago
            "predicted_priority": "P2",
            "action_required": 1,
            "confidence": 0.88
        }
        email_recent_2 = {
            "email_id": "msg_recent_2",
            "subject": "Recent Security Notification",
            "snippet": "New device login",
            "body": "New device login detected",
            "internal_date": now_ms - (2 * 86400 * 1000),  # 2 days ago
            "predicted_priority": "P1",
            "action_required": 1,
            "confidence": 0.95
        }
        email_old = {
            "email_id": "msg_old_1",
            "subject": "Old Welcome Email",
            "snippet": "Welcome to our service",
            "body": "Welcome to our service",
            "internal_date": now_ms - (180 * 86400 * 1000),  # 180 days ago (~6 months)
            "predicted_priority": "P4",
            "confidence": 0.99
        }

        user_email_cache.store_batch(TEST_USER_A, [email_recent_1, email_recent_2, email_old])

        # Test Analysis Summary for last_3_months
        res = client.get("/api/analysis/summary?period=last_3_months", headers={"Authorization": "Bearer session_date_a_token"})
        assert res.status_code == 200
        data = res.json()["data"]
        # Should count exactly the 2 emails falling in the last 3 months
        assert data["total_eligible"] == 2
        assert data["analyzed"] == 2
        assert data["pending"] == 0
        assert data["reused_from_cache"] == 2
        assert data["progress_percentage"] == 100.0

    def test_job_creation_idempotency(self):
        # Create initial job
        job, is_new = user_email_cache.create_or_get_analysis_job(
            user_id=TEST_USER_A,
            gmail_account_id=TEST_EMAIL_A,
            period="last_3_months",
            total_eligible=150,
            already_analyzed=100
        )
        assert is_new is True
        job_id = job["job_id"]
        assert job["status"] == "running"

        # Subsequent identical request returns same job without launching duplicate
        job_dup, is_new_dup = user_email_cache.create_or_get_analysis_job(
            user_id=TEST_USER_A,
            gmail_account_id=TEST_EMAIL_A,
            period="last_3_months"
        )
        assert is_new_dup is False
        assert job_dup["job_id"] == job_id

        # Update job progress
        up_job = user_email_cache.update_analysis_job(
            job_id=job_id,
            status="completed",
            processed_count=150
        )
        assert up_job["status"] == "completed"
        assert up_job["processed_count"] == 150


# =============================================================================
# 4. MAILBOX VIEWS: RECENT MAIL & ALL HISTORY TESTS
# =============================================================================

class TestMailboxViews:
    def test_recent_mail_respects_date_boundaries(self):
        now = time.time()
        now_ms = int(now * 1000)

        # Seed 1 inside last 3 months, 1 older than 3 months
        msg_in = {
            "email_id": "msg_in_scope",
            "subject": "Recent Urgent Task",
            "internal_date": now_ms - (5 * 86400 * 1000),
            "predicted_priority": "P1",
            "confidence": 0.92
        }
        msg_out = {
            "email_id": "msg_out_of_scope",
            "subject": "Old Archived Project",
            "internal_date": now_ms - (120 * 86400 * 1000),  # 4 months ago
            "predicted_priority": "P2",
            "confidence": 0.85
        }
        user_email_cache.store_batch(TEST_USER_A, [msg_in, msg_out])

        # Query Recent Mail for last_3_months
        res = client.get("/api/emails/recent?period=last_3_months", headers={"Authorization": "Bearer session_date_a_token"})
        assert res.status_code == 200
        items = res.json()["data"]["items"]
        item_ids = [it["id"] for it in items]

        assert "msg_in_scope" in item_ids
        assert "msg_out_of_scope" not in item_ids  # Excluded from Recent Mail

    def test_all_history_includes_all_messages(self):
        now = time.time()
        now_ms = int(now * 1000)

        msg_recent = {
            "email_id": "hist_msg_recent",
            "subject": "Recent Meeting Notes",
            "internal_date": now_ms - (2 * 86400 * 1000),
            "predicted_priority": "P3"
        }
        msg_old = {
            "email_id": "hist_msg_old",
            "subject": "2023 Tax Receipt",
            "internal_date": now_ms - (400 * 86400 * 1000),
            "predicted_priority": "P4"
        }
        user_email_cache.store_batch(TEST_USER_A, [msg_recent, msg_old])

        # Query All History without date bounds
        res = client.get("/api/emails/history", headers={"Authorization": "Bearer session_date_a_token"})
        assert res.status_code == 200
        items = res.json()["data"]["items"]
        item_ids = [it["id"] for it in items]

        # Both recent and older historical messages must appear
        assert "hist_msg_recent" in item_ids
        assert "hist_msg_old" in item_ids

    def test_all_history_raw_unanalyzed_messages(self):
        now = time.time()
        now_ms = int(now * 1000)

        raw_msg = {
            "email_id": "raw_historical_1",
            "subject": "Unanalyzed Newsletter",
            "snippet": "Check out this newsletter",
            "sender": "news@daily.com",
            "internal_date": now_ms - (300 * 86400 * 1000),
            "date": "2025-01-01T00:00:00Z"
        }
        user_email_cache.store_raw_history_batch(TEST_USER_A, [raw_msg])

        res = client.get("/api/emails/history?analyzed=false", headers={"Authorization": "Bearer session_date_a_token"})
        assert res.status_code == 200
        items = res.json()["data"]["items"]
        assert len(items) == 1
        assert items[0]["id"] == "raw_historical_1"
        assert items[0]["is_analyzed"] is False
        assert items[0]["original_priority"] is None


# =============================================================================
# 5. SMART ACTION QUEUE DATE-INVARIANCE TESTS
# =============================================================================

class TestActionQueueDateInvariance:
    def test_needs_attention_surfaces_older_unresolved_actions(self):
        now = time.time()
        now_ms = int(now * 1000)

        # Seed an unresolved action from 60 days ago (outside 'last_3_months' or 'this_month')
        msg_old_action = {
            "email_id": "old_action_msg",
            "subject": "Suspicious login from Russia",
            "snippet": "We noticed a suspicious login",
            "body": "Security Incident: Unrecognized IP login",
            "internal_date": now_ms - (60 * 86400 * 1000),
            "predicted_priority": "P1",
            "action_required": 1,
            "confidence": 0.98
        }
        user_email_cache.store_batch(TEST_USER_A, [msg_old_action])

        # Even if user selected "this_month", /api/actions/attention MUST return the action
        res = client.get("/api/actions/attention", headers={"Authorization": "Bearer session_date_a_token"})
        assert res.status_code == 200
        data = res.json()["data"]

        all_actions = data.get("urgent", []) + data.get("due_soon", []) + data.get("other_active", []) + data.get("older", [])
        action_ids = [em.get("email_id") or em.get("id") for em in all_actions]
        assert "old_action_msg" in action_ids


# =============================================================================
# 6. SECURITY & MULTI-USER ISOLATION TESTS
# =============================================================================

class TestSecurityAndIsolation:
    def test_cross_user_preference_isolation(self):
        # User A sets this_month
        client.put(
            "/api/analysis/config",
            json={"period": "this_month", "timezone": "Asia/Kolkata"},
            headers={"Authorization": "Bearer session_date_a_token"}
        )

        # User B sets last_1_year
        client.put(
            "/api/analysis/config",
            json={"period": "last_1_year", "timezone": "America/New_York"},
            headers={"Authorization": "Bearer session_date_b_token"}
        )

        # Verify User A gets this_month
        res_a = client.get("/api/analysis/config", headers={"Authorization": "Bearer session_date_a_token"})
        assert res_a.json()["data"]["period"] == "this_month"
        assert res_a.json()["data"]["timezone"] == "Asia/Kolkata"

        # Verify User B gets last_1_year
        res_b = client.get("/api/analysis/config", headers={"Authorization": "Bearer session_date_b_token"})
        assert res_b.json()["data"]["period"] == "last_1_year"
        assert res_b.json()["data"]["timezone"] == "America/New_York"

    def test_unauthenticated_request_rejected(self):
        res = client.get("/api/analysis/config")
        assert res.status_code == 401

        res_recent = client.get("/api/emails/recent")
        assert res_recent.status_code == 401


# =============================================================================
# 7. FROZEN PRODUCTION MODEL INTEGRITY TEST
# =============================================================================

class TestFrozenModelIntegrity:
    def test_model_artifact_hash_unchanged(self):
        import hashlib
        p = "dataset/models/priority-v5.1-candidate/model.joblib"
        with open(p, "rb") as f:
            computed_hash = hashlib.sha256(f.read()).hexdigest()
        assert computed_hash == ACTIVE_MODEL_HASH
        assert computed_hash == "8524ad73965859ee022f1271caee0040928e7805ab7d32c49b2f26e994f98c06"

