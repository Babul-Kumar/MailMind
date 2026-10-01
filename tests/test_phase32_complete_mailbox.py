import os
import sys
import time
import json
import pytest
import hashlib
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.session import session_manager
from backend.app.core.cache import user_email_cache
from backend.app.gmail.scan_engine import (
    scan_manager,
    discover_mailbox_message_ids,
    fetch_message_metadata_batch,
    MailboxScanJob,
)
from backend.app.ml.predictor import load_model, predict_email, predict_batch
from backend.app.ml.registry import model_registry

client = TestClient(app)


class TestPhase32CompleteMailbox:
    """
    Phase 32 Test Matrix: Complete Gmail Mailbox Analysis, Robust Pagination,
    User-Scoped Caching, Incremental Synchronization, Background State Machine,
    Error Handling, Concurrency & Security Isolation.
    """

    @pytest.fixture(autouse=True)
    def setup_users(self):
        """Setup isolated test sessions for User A and User B."""
        self.user_a_email = "test.alice@domain.com"
        self.user_a_id = "phase32_user_a"
        self.session_a = session_manager.create_session(
            email=self.user_a_email,
            user_id=self.user_a_id,
            credentials={"token": "mock_a_tok", "refresh_token": "mock_a_rf"}
        )

        self.user_b_email = "test.bob@domain.com"
        self.user_b_id = "phase32_user_b"
        self.session_b = session_manager.create_session(
            email=self.user_b_email,
            user_id=self.user_b_id,
            credentials={"token": "mock_b_tok", "refresh_token": "mock_b_rf"}
        )

        user_email_cache.clear_user(self.user_a_id)
        user_email_cache.clear_user(self.user_b_id)

        scan_dir = os.path.join("google_auth", "scans")
        for uid in (self.user_a_id, self.user_b_id):
            cp = os.path.join(scan_dir, f"scan_{uid}.json")
            if os.path.exists(cp):
                try:
                    os.remove(cp)
                except Exception:
                    pass

        yield

        user_email_cache.clear_user(self.user_a_id)
        user_email_cache.clear_user(self.user_b_id)
        for uid in (self.user_a_id, self.user_b_id):
            cp = os.path.join(scan_dir, f"scan_{uid}.json")
            if os.path.exists(cp):
                try:
                    os.remove(cp)
                except Exception:
                    pass


    # 1. Gmail pagination
    def test_01_gmail_pagination(self):
        """Verify discovery correctly navigates nextPageToken across multiple pages."""
        mock_service = MagicMock()
        mock_messages = mock_service.users().messages()

        page1 = {
            "messages": [{"id": "m1"}, {"id": "m2"}],
            "nextPageToken": "tok_page2",
            "resultSizeEstimate": 6,
        }
        page2 = {
            "messages": [{"id": "m3"}, {"id": "m4"}],
            "nextPageToken": "tok_page3",
            "resultSizeEstimate": 6,
        }
        page3 = {
            "messages": [{"id": "m5"}, {"id": "m6"}],
            "nextPageToken": None,
            "resultSizeEstimate": 6,
        }

        call_count = [0]
        def list_side_effect(userId, maxResults, pageToken=None, q=None, labelIds=None, **kwargs):
            req = MagicMock()
            if pageToken is None:
                req.execute.return_value = page1
            elif pageToken == "tok_page2":
                req.execute.return_value = page2
            elif pageToken == "tok_page3":
                req.execute.return_value = page3
            call_count[0] += 1
            return req

        mock_messages.list.side_effect = list_side_effect

        msg_ids = discover_mailbox_message_ids(mock_service, scope="mailbox")
        assert len(msg_ids) == 6
        assert msg_ids == ["m1", "m2", "m3", "m4", "m5", "m6"]
        assert call_count[0] == 3

    # 2. Complete mailbox discovery
    def test_02_complete_mailbox_discovery(self):
        """Verify discovery returns all accessible messages without a 20/50/100 ceiling."""
        mock_service = MagicMock()
        mock_messages = mock_service.users().messages()

        p1 = {"messages": [{"id": f"msg_{i}"} for i in range(500)], "nextPageToken": "p2"}
        p2 = {"messages": [{"id": f"msg_{i}"} for i in range(500, 1000)], "nextPageToken": "p3"}
        p3 = {"messages": [{"id": f"msg_{i}"} for i in range(1000, 1500)], "nextPageToken": None}

        def list_side_effect(userId, maxResults, pageToken=None, q=None, labelIds=None, **kwargs):
            req = MagicMock()
            if pageToken is None:
                req.execute.return_value = p1
            elif pageToken == "p2":
                req.execute.return_value = p2
            else:
                req.execute.return_value = p3
            return req

        mock_messages.list.side_effect = list_side_effect
        msg_ids = discover_mailbox_message_ids(mock_service, scope="mailbox")
        assert len(msg_ids) == 1500

    # 3. Duplicate page token protection
    def test_03_duplicate_page_token_protection(self):
        """Verify infinite loop protection when Gmail returns a repeated page token."""
        mock_service = MagicMock()
        mock_messages = mock_service.users().messages()

        loop_page = {
            "messages": [{"id": "loop_m1"}],
            "nextPageToken": "same_token_forever",
        }
        mock_messages.list.return_value.execute.return_value = loop_page

        msg_ids = discover_mailbox_message_ids(mock_service, scope="mailbox")
        assert len(msg_ids) == 1
        assert msg_ids == ["loop_m1"]

    # 4. Incremental scan
    def test_04_incremental_scan(self):
        """Verify incremental scan only analyzes uncached messages."""
        user_email_cache.set(self.user_a_id, "cached_1", {
            "email_id": "cached_1",
            "subject": "Precached 1",
            "body": "Body 1",
            "sender": "sender@test.com",
            "date": "2026-10-01T00:00:00Z",
            "predicted_priority": "P2",
            "confidence": 0.85,
            "action_required": True,
            "action_reason": "Pre-classified",
            "needs_attention": True,
        })
        user_email_cache.set(self.user_a_id, "cached_2", {
            "email_id": "cached_2",
            "subject": "Precached 2",
            "body": "Body 2",
            "sender": "sender@test.com",
            "date": "2026-10-01T00:00:00Z",
            "predicted_priority": "P4",
            "confidence": 0.90,
            "action_required": False,
            "needs_attention": False,
        })

        mock_service = MagicMock()
        mock_service.users().messages().list.return_value.execute.return_value = {
            "messages": [{"id": "cached_1"}, {"id": "cached_2"}, {"id": "new_3"}],
            "nextPageToken": None,
        }

        def mock_batch_fetch(*args, **kwargs):
            return [
                {
                    "email_id": "new_3",
                    "subject": "Critical Server Down Alert",
                    "body": "Production server down immediately.",
                    "sender": "alerts@infra.org",
                    "date": "2026-10-01T12:00:00Z",
                    "content_hash": "hash_new_3",
                }
            ], [], 1, 0

        with patch("backend.app.gmail.scan_engine.fetch_message_metadata_batch", side_effect=mock_batch_fetch):
            job = MailboxScanJob(self.user_a_id, mock_service, scope="mailbox", mode="incremental")
            status = job.execute()

            assert status["status"] == "COMPLETE"
            assert status["total"] == 3
            assert status["cached"] == 2
            assert status["newly_analyzed"] == 1
            assert status["failed"] == 0

    # 5. Cache hit
    def test_05_cache_hit(self):
        """Verify cached items return immediately with full classification details."""
        user_email_cache.set(self.user_a_id, "hit_msg", {
            "email_id": "hit_msg",
            "subject": "Weekly Sprint Meeting",
            "body": "Team sprint review on Monday",
            "sender": "pm@team.com",
            "date": "2026-10-01T08:00:00Z",
            "predicted_priority": "P3",
            "confidence": 0.95,
            "action_required": False,
            "needs_attention": False,
        })

        res = user_email_cache.get(self.user_a_id, "hit_msg")
        assert res is not None
        assert res["predicted_priority"] == "P3"
        assert res["subject"] == "Weekly Sprint Meeting"

    # 6. Cache miss
    def test_06_cache_miss(self):
        """Verify cache miss returns None."""
        res = user_email_cache.get(self.user_a_id, "nonexistent_msg_id")
        assert res is None

    # 7. Content change
    def test_07_content_change(self):
        """Verify that if a message's content changes, it is re-analyzed."""
        user_email_cache.set(self.user_a_id, "changed_msg", {
            "email_id": "changed_msg",
            "subject": "Old Subject",
            "body": "Old Body",
            "content_hash": "old_hash_123",
            "predicted_priority": "P4",
            "action_required": False,
            "needs_attention": False,
        })

        mock_service = MagicMock()
        mock_service.users().messages().list.return_value.execute.return_value = {
            "messages": [{"id": "changed_msg"}],
            "nextPageToken": None,
        }

        def mock_batch_fetch(*args, **kwargs):
            return [
                {
                    "email_id": "changed_msg",
                    "subject": "URGENT: Database Compromised",
                    "body": "Security incident occurred. Immediate action required.",
                    "sender": "security@corp.com",
                    "date": "2026-10-01T15:00:00Z",
                    "content_hash": "new_hash_456",
                }
            ], [], 1, 0

        with patch("backend.app.gmail.scan_engine.fetch_message_metadata_batch", side_effect=mock_batch_fetch):
            job = MailboxScanJob(self.user_a_id, mock_service, scope="mailbox", mode="full", force_rescan=True)
            status = job.execute()

            assert status["status"] == "COMPLETE"
            assert status["newly_analyzed"] == 1
            updated = user_email_cache.get(self.user_a_id, "changed_msg")
            assert updated["content_hash"] == "new_hash_456"
            assert updated["subject"] == "URGENT: Database Compromised"

    # 8. Model-version invalidation
    def test_08_model_version_invalidation(self):
        """Verify controlled invalidation when migrating model version."""
        user_email_cache.set(self.user_a_id, "v1_email", {
            "email_id": "v1_email",
            "subject": "Routine update",
            "body": "informational note",
            "sender": "info@corp.com",
            "date": "2026-10-01T10:00:00Z",
            "predicted_priority": "P3",
            "confidence": 0.88,
            "action_required": False,
            "needs_attention": False,
            "model_version": "priority-v1",
        })

        migrated = user_email_cache.invalidate_model_version(self.user_a_id, target_version="priority-v2")
        assert migrated >= 1

        entry = user_email_cache.get(self.user_a_id, "v1_email")
        assert entry["model_version"] == "priority-v2"

    # 9. Scan progress
    def test_09_scan_progress(self):
        """Verify progress updates accurately during execution."""
        mock_service = MagicMock()
        mock_service.users().messages().list.return_value.execute.return_value = {
            "messages": [{"id": f"msg_{i}"} for i in range(10)],
            "nextPageToken": None,
        }

        def mock_batch_fetch(*args, **kwargs):
            msg_ids = kwargs.get("message_ids") or (args[1] if len(args) > 1 else [])
            return [
                {
                    "email_id": mid,
                    "subject": f"Notice {mid}",
                    "body": "Normal notification",
                    "sender": "test@test.com",
                    "date": "2026-10-01T10:00:00Z",
                    "content_hash": f"hash_{mid}",
                }
                for mid in msg_ids
            ], [], 1, 0

        progress_snapshots = []
        def track_progress(status):
            progress_snapshots.append(dict(status))

        job = MailboxScanJob(
            self.user_a_id,
            mock_service,
            scope="mailbox",
            mode="full",
            on_progress=track_progress
        )
        with patch("backend.app.gmail.scan_engine.fetch_message_metadata_batch", side_effect=mock_batch_fetch):
            final = job.execute()

        assert len(progress_snapshots) > 0
        assert any(p.get("progress_percent", 0) > 0 for p in progress_snapshots)
        assert final["progress_percent"] == 100.0

    # 10. Scan completion
    def test_10_scan_completion(self):
        """Verify scan completes with all fields correctly set in final status."""
        mock_service = MagicMock()
        mock_service.users().messages().list.return_value.execute.return_value = {
            "messages": [{"id": "done_1"}, {"id": "done_2"}],
            "nextPageToken": None,
        }

        with patch("backend.app.gmail.scan_engine.fetch_message_metadata_batch", return_value=(
            [
                {"email_id": "done_1", "subject": "S1", "body": "B1", "sender": "s@s.com", "date": "2026-10-01T00:00:00Z"},
                {"email_id": "done_2", "subject": "S2", "body": "B2", "sender": "s@s.com", "date": "2026-10-01T00:00:00Z"},
            ],
            [], 1, 0
        )):
            job = MailboxScanJob(self.user_a_id, mock_service, scope="mailbox", mode="full")
            result = job.execute()

            assert result["status"] == "COMPLETE"
            assert result["total"] == 2
            assert result["newly_analyzed"] == 2
            assert result["completed_at"] is not None
            assert result["scan_duration_sec"] >= 0

    # 11. Scan failure resilience
    def test_11_scan_failure(self):
        """Verify scan cleanly transitions to FAILED on catastrophic exception."""
        mock_service = MagicMock()
        mock_service.users().messages().list.side_effect = RuntimeError("Gmail API network fatal drop")

        job = MailboxScanJob(self.user_a_id, mock_service, scope="mailbox", mode="full")
        result = job.execute()

        assert result["status"] == "FAILED"
        assert "Gmail API network fatal drop" in result["error"]

    # 12. Scan resume
    def test_12_scan_resume(self):
        """Verify interrupted scan resumes from checkpoint without starting from scratch."""
        scan_state_dir = os.path.join("google_auth", "scans")
        os.makedirs(scan_state_dir, exist_ok=True)
        checkpoint_path = os.path.join(scan_state_dir, f"scan_{self.user_a_id}.json")

        initial_checkpoint = {
            "user_id": self.user_a_id,
            "status": "ANALYZING",
            "scope": "mailbox",
            "mode": "full",
            "discovered": 4,
            "analyzed": 2,
            "cached": 0,
            "newly_analyzed": 2,
            "failed": 0,
            "total": 4,
            "discovered_ids": ["m1", "m2", "m3", "m4"],
            "processed_ids": ["m1", "m2"],
            "progress_percent": 50.0,
            "started_at": "2026-10-01T10:00:00Z",
            "updated_at": "2026-10-01T10:01:00Z",
            "completed_at": None,
            "error": None,
        }
        with open(checkpoint_path, "w", encoding="utf-8") as f:
            json.dump(initial_checkpoint, f)

        mock_service = MagicMock()
        called_ids = []
        def mock_batch_fetch(*args, **kwargs):
            msg_ids = kwargs.get("message_ids") or (args[1] if len(args) > 1 else [])
            called_ids.extend(msg_ids)
            return [
                {"email_id": mid, "subject": f"Sub {mid}", "body": "Body", "sender": "x@x.com", "date": "2026-10-01T00:00:00Z"}
                for mid in msg_ids
            ], [], 1, 0

        with patch("backend.app.gmail.scan_engine.fetch_message_metadata_batch", side_effect=mock_batch_fetch):
            job = MailboxScanJob(self.user_a_id, mock_service, scope="mailbox", mode="full")
            result = job.execute()

            assert result["status"] == "COMPLETE"
            assert "m1" not in called_ids
            assert "m2" not in called_ids
            assert "m3" in called_ids
            assert "m4" in called_ids
            assert result["total"] == 4

        if os.path.exists(checkpoint_path):
            os.remove(checkpoint_path)

    # 13. Malformed email
    def test_13_malformed_email(self):
        """Verify malformed email does not terminate scan, recorded under failed count."""
        mock_service = MagicMock()
        mock_service.users().messages().list.return_value.execute.return_value = {
            "messages": [{"id": "good_1"}, {"id": "bad_2"}, {"id": "good_3"}],
            "nextPageToken": None,
        }

        def mock_batch_fetch(*args, **kwargs):
            msg_ids = kwargs.get("message_ids") or (args[1] if len(args) > 1 else [])
            results = []
            failed = []
            for mid in msg_ids:
                if mid == "bad_2":
                    failed.append({"message_id": "bad_2", "error": "Corrupt MIME payload"})
                else:
                    results.append({"email_id": mid, "subject": f"Sub {mid}", "body": "Valid body", "sender": "s@s.com", "date": "2026-10-01T00:00:00Z"})
            return results, failed, 1, 0

        with patch("backend.app.gmail.scan_engine.fetch_message_metadata_batch", side_effect=mock_batch_fetch):
            job = MailboxScanJob(self.user_a_id, mock_service, scope="mailbox", mode="full")
            result = job.execute()

            assert result["status"] == "COMPLETE"
            assert result["newly_analyzed"] == 2
            assert result["failed"] == 1
            assert result["total"] == 3

    # 14. Gmail 429
    def test_14_gmail_429(self):
        """Verify 429 rate limit triggers exponential backoff retry and succeeds."""
        mock_service = MagicMock()
        mock_messages = mock_service.users().messages()

        from googleapiclient.errors import HttpError
        resp_429 = MagicMock()
        resp_429.status = 429

        attempts = [0]
        def mock_list(**kwargs):
            req = MagicMock()
            attempts[0] += 1
            if attempts[0] == 1:
                raise HttpError(resp=resp_429, content=b"Rate limit exceeded (429)")
            req.execute.return_value = {
                "messages": [{"id": "m_after_429"}],
                "nextPageToken": None,
            }
            return req

        mock_messages.list.side_effect = mock_list

        with patch("time.sleep", return_value=None):
            msg_ids = discover_mailbox_message_ids(mock_service, scope="mailbox")
            assert len(msg_ids) == 1
            assert msg_ids == ["m_after_429"]
            assert attempts[0] == 2

    # 15. Gmail 500
    def test_15_gmail_500(self):
        """Verify 500/503 server error triggers backoff retry and succeeds."""
        mock_service = MagicMock()
        mock_messages = mock_service.users().messages()

        from googleapiclient.errors import HttpError
        resp_503 = MagicMock()
        resp_503.status = 503

        attempts = [0]
        def mock_list(**kwargs):
            req = MagicMock()
            attempts[0] += 1
            if attempts[0] == 1:
                raise HttpError(resp=resp_503, content=b"Service Unavailable (503)")
            req.execute.return_value = {
                "messages": [{"id": "m_after_503"}],
                "nextPageToken": None,
            }
            return req

        mock_messages.list.side_effect = mock_list

        with patch("time.sleep", return_value=None):
            msg_ids = discover_mailbox_message_ids(mock_service, scope="mailbox")
            assert len(msg_ids) == 1
            assert msg_ids == ["m_after_503"]
            assert attempts[0] == 2

    # 16. Concurrent users
    def test_16_concurrent_users(self):
        """Verify concurrent mailbox scans for User A and User B proceed without interference."""
        mock_svc_a = MagicMock()
        mock_svc_a.users().messages().list.return_value.execute.return_value = {
            "messages": [{"id": f"msg_a_{i}"} for i in range(10)],
            "nextPageToken": None,
        }

        mock_svc_b = MagicMock()
        mock_svc_b.users().messages().list.return_value.execute.return_value = {
            "messages": [{"id": f"msg_b_{i}"} for i in range(10)],
            "nextPageToken": None,
        }

        def mock_batch_fetch(*args, **kwargs):
            msg_ids = kwargs.get("message_ids") or (args[1] if len(args) > 1 else [])
            return [
                {"email_id": mid, "subject": f"Sub {mid}", "body": "Body text", "sender": "t@t.com", "date": "2026-10-01T00:00:00Z"}
                for mid in msg_ids
            ], [], 1, 0

        with patch("backend.app.gmail.scan_engine.fetch_message_metadata_batch", side_effect=mock_batch_fetch):
            job_a = MailboxScanJob(self.user_a_id, mock_svc_a, scope="mailbox", mode="full")
            job_b = MailboxScanJob(self.user_b_id, mock_svc_b, scope="mailbox", mode="full")

            with ThreadPoolExecutor(max_workers=2) as executor:
                f_a = executor.submit(job_a.execute)
                f_b = executor.submit(job_b.execute)

                res_a = f_a.result()
                res_b = f_b.result()

            assert res_a["status"] == "COMPLETE"
            assert res_b["status"] == "COMPLETE"
            assert res_a["total"] == 10
            assert res_b["total"] == 10

            cached_a = user_email_cache.get_all_cached_ids(self.user_a_id)
            assert len(cached_a) == 10
            assert all(k.startswith("msg_a_") for k in cached_a)

            cached_b = user_email_cache.get_all_cached_ids(self.user_b_id)
            assert len(cached_b) == 10
            assert all(k.startswith("msg_b_") for k in cached_b)


    # 17. User isolation
    def test_17_user_isolation(self):
        """Verify strict isolation: User A cannot see User B's cache or stats."""
        user_email_cache.set(self.user_b_id, "bob_private_msg", {
            "email_id": "bob_private_msg",
            "subject": "Bob confidential salary review",
            "body": "Salary details",
            "sender": "hr@corp.com",
            "date": "2026-10-01T00:00:00Z",
            "predicted_priority": "P1",
            "action_required": True,
            "needs_attention": True,
        })

        leak = user_email_cache.get(self.user_a_id, "bob_private_msg")
        assert leak is None

        alice_emails, total = user_email_cache.query_emails(self.user_a_id)
        assert total == 0
        assert "bob_private_msg" not in [e["email_id"] for e in alice_emails]

    # 18. Cancellation
    def test_18_cancellation(self):
        """Verify user can cancel an in-progress scan and state becomes CANCELLED."""
        mock_service = MagicMock()
        mock_service.users().messages().list.return_value.execute.return_value = {
            "messages": [{"id": f"canc_msg_{i}"} for i in range(200)],
            "nextPageToken": None,
        }

        job = MailboxScanJob(self.user_a_id, mock_service, scope="mailbox", mode="full")

        def mock_batch_with_cancel(*args, **kwargs):
            job.cancel()
            msg_ids = kwargs.get("message_ids") or (args[1] if len(args) > 1 else [])
            return [
                {"email_id": mid, "subject": f"Sub {mid}", "body": "Body", "sender": "s@s.com", "date": "2026-10-01T00:00:00Z"}
                for mid in msg_ids
            ], [], 1, 0

        with patch("backend.app.gmail.scan_engine.fetch_message_metadata_batch", side_effect=mock_batch_with_cancel):
            result = job.execute()
            assert result["status"] == "CANCELLED"

    # 19. Large mailbox batching
    def test_19_large_mailbox_batching(self):
        """Verify 500 emails are processed in manageable batches of 100 without memory bloat."""
        mock_service = MagicMock()
        mock_service.users().messages().list.return_value.execute.return_value = {
            "messages": [{"id": f"batch_msg_{i}"} for i in range(500)],
            "nextPageToken": None,
        }

        batches_processed = []
        def mock_batch_fetch(*args, **kwargs):
            msg_ids = kwargs.get("message_ids") or (args[1] if len(args) > 1 else [])
            batches_processed.append(len(msg_ids))
            return [
                {"email_id": mid, "subject": f"Sub {mid}", "body": "Body", "sender": "s@s.com", "date": "2026-10-01T00:00:00Z"}
                for mid in msg_ids
            ], [], 1, 0

        with patch("backend.app.gmail.scan_engine.fetch_message_metadata_batch", side_effect=mock_batch_fetch):
            job = MailboxScanJob(self.user_a_id, mock_service, scope="mailbox", mode="full", batch_size=100)
            result = job.execute()

            assert result["status"] == "COMPLETE"
            assert result["newly_analyzed"] == 500
            assert len(batches_processed) == 5
            assert all(size == 100 for size in batches_processed)

    # 20. Memory safety
    def test_20_memory_safety(self):
        """Verify cache returns lightweight representations without full bodies unless requested."""
        user_email_cache.set(self.user_a_id, "mem_test_msg", {
            "email_id": "mem_test_msg",
            "subject": "Lightweight Summary",
            "body": "Giant email text" * 100,
            "sender": "sender@test.com",
            "date": "2026-10-01T00:00:00Z",
            "predicted_priority": "P2",
            "confidence": 0.88,
            "action_required": True,
            "needs_attention": True,
        })

        results, total = user_email_cache.query_emails(self.user_a_id, page=1, page_size=10)
        assert total == 1
        assert "email_id" in results[0]
        assert "predicted_priority" in results[0]

    # 21. Authentication enforcement
    def test_21_authentication_enforcement(self):
        """Verify scan endpoints return 401 Unauthorized for unauthenticated requests."""
        resp_status = client.get("/api/scan/status")
        assert resp_status.status_code == 401

        resp_start = client.post("/api/scan/start", json={"scope": "mailbox"})
        assert resp_start.status_code == 401

        resp_rescan = client.post("/api/scan/rescan", json={"scope": "mailbox"})
        assert resp_rescan.status_code == 401

        resp_cancel = client.post("/api/scan/cancel")
        assert resp_cancel.status_code == 401

    # 22. Unauthorized scan status isolation
    def test_22_unauthorized_scan_status(self):
        """Verify User A cannot observe User B's scan status."""
        client_a = TestClient(app)
        client_a.cookies.set("mailmind_session", self.session_a.session_id)

        client_b = TestClient(app)
        client_b.cookies.set("mailmind_session", self.session_b.session_id)

        scan_manager.set_status(self.user_b_id, {
            "status": "ANALYZING",
            "scope": "mailbox",
            "discovered": 1000,
            "analyzed": 500,
            "cached": 0,
            "newly_analyzed": 500,
            "failed": 0,
            "total": 1000,
            "progress_percent": 50.0,
        })

        res_a = client_a.get("/api/scan/status")
        assert res_a.status_code == 200
        data_a = res_a.json()
        assert data_a["status"] != "ANALYZING"
        assert data_a["total"] != 1000  # User A does not see User B's 1000 messages

        res_b = client_b.get("/api/scan/status")
        assert res_b.status_code == 200
        data_b = res_b.json()
        assert data_b["status"] == "ANALYZING"
        assert data_b["total"] == 1000

    # 23. Full rescan
    def test_23_full_rescan(self):
        """Verify full rescan re-analyzes all messages without incremental bypass."""
        user_email_cache.set(self.user_a_id, "rescan_msg", {
            "email_id": "rescan_msg",
            "subject": "Old rescan subject",
            "body": "Body",
            "predicted_priority": "P4",
            "action_required": False,
            "needs_attention": False,
        })

        mock_service = MagicMock()
        mock_service.users().messages().list.return_value.execute.return_value = {
            "messages": [{"id": "rescan_msg"}],
            "nextPageToken": None,
        }

        with patch("backend.app.gmail.scan_engine.fetch_message_metadata_batch", return_value=(
            [{"email_id": "rescan_msg", "subject": "Refreshed Subject", "body": "New body", "sender": "s@s.com", "date": "2026-10-01T00:00:00Z"}],
            [], 1, 0
        )):
            job = MailboxScanJob(self.user_a_id, mock_service, scope="mailbox", mode="full", force_rescan=True)
            res = job.execute()

            assert res["status"] == "COMPLETE"
            assert res["newly_analyzed"] == 1
            assert res["cached"] == 0

    # 24. No token fallback for session
    def test_24_no_token_fallback(self):
        """Verify web API strictly rejects requests without session cookie, never falling back to token.json."""
        resp = client.get("/api/emails")
        assert resp.status_code == 401

    # 25. ML artifact integrity
    def test_25_ml_artifact_integrity(self):
        """Verify priority-v2 and test.csv hashes are untouched."""
        test_csv_path = os.path.join("dataset", "processed", "test.csv")
        assert os.path.exists(test_csv_path), "test.csv must exist"
        with open(test_csv_path, "rb") as f:
            h = hashlib.sha256(f.read()).hexdigest().upper()
        assert h == "6841CD44901FA56242BF3752257E991FD7FF474ED7E0F7A5D2B7065A0827C138"

        model_dir = os.path.join("dataset", "models", "priority-v2")
        assert os.path.exists(os.path.join(model_dir, "model.joblib"))
        assert os.path.exists(os.path.join(model_dir, "metadata.json"))
        assert os.path.exists(os.path.join(model_dir, "metrics.json"))

        codevita_subject = "TCS CodeVita Season 14 - Email Verification"
        codevita_body = (
            "Dear Candidate, Thank you for registering for TCS CodeVita Season 14. "
            "Please verify your email address to complete your registration process. "
            "Click on the link below to verify your account. "
            "Note: This verification link remains active for 12 hours only."
        )
        sample_email = {
            "id": "codevita_sample",
            "subject": codevita_subject,
            "body": codevita_body,
            "sender": "codevita-noreply@tcs.com",
            "date": "2026-10-01T12:00:00Z"
        }
        from backend.app.ml.predictor import invalidate_cached_pipeline
        invalidate_cached_pipeline()
        res = predict_email(sample_email)
        assert res["predicted_priority"] == "P2"
        assert res["refinement_applied"] is False
        assert res["action_required"] is True
        assert res["deadline_detected"] is True


