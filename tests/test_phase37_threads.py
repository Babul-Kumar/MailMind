import os
import time
import pytest
from backend.app.core.cache import user_email_cache, compute_content_hash

class TestPhase37Threads:
    """
    Tests for Phase 37: Thread ID Ingestion, Persistence, and Multi-User Isolation.
    Tests 1 to 8 as specified in Phase 37 Section 37.3.
    """

    @pytest.fixture(autouse=True)
    def setup_cleanup(self):
        # Setup test user IDs
        self.user_a = "phase37_user_a"
        self.user_b = "phase37_user_b"

        # Clean any prior test data
        conn = user_email_cache._get_connection()
        with user_email_cache._lock:
            cur = conn.cursor()
            cur.execute("DELETE FROM user_email_cache WHERE user_id IN (?, ?)", (self.user_a, self.user_b))
            conn.commit()
            user_email_cache._mem_cache.pop(self.user_a, None)
            user_email_cache._mem_cache.pop(self.user_b, None)

        yield

        # Teardown
        with user_email_cache._lock:
            cur = conn.cursor()
            cur.execute("DELETE FROM user_email_cache WHERE user_id IN (?, ?)", (self.user_a, self.user_b))
            conn.commit()
            user_email_cache._mem_cache.pop(self.user_a, None)
            user_email_cache._mem_cache.pop(self.user_b, None)

    def test_1_thread_persistence(self):
        """Test 1: store_batch retains non-empty thread_id in DB & mem_cache."""
        email = {
            "email_id": "msg_001",
            "thread_id": "thread_abc_123",
            "subject": "Discussion on Architecture",
            "sender": "lead@company.com",
            "recipients": "dev@company.com",
            "body": "Here is the architectural overview.",
            "snippet": "Here is the architectural...",
            "date": "2026-10-01T10:00:00Z",
            "predicted_priority": "P2",
            "model_priority": "P2",
            "final_priority": "P2",
            "action_required": False,
            "action_reason": None,
            "topic": "work",
            "confidence": 0.85,
            "model_version": "priority-v3"
        }

        user_email_cache.store_batch(self.user_a, [email])

        # Verify from memory cache
        cached = user_email_cache.get(self.user_a, "msg_001")
        assert cached is not None
        assert cached.get("thread_id") == "thread_abc_123"

        # Invalidate mem cache and verify from persistent SQLite
        with user_email_cache._lock:
            user_email_cache._mem_cache.pop(self.user_a, None)

        persisted = user_email_cache.get(self.user_a, "msg_001")
        assert persisted is not None
        assert persisted.get("thread_id") == "thread_abc_123"

    def test_2_thread_non_empty_invariant(self):
        """Test 2: Valid email records must store non-empty thread_id."""
        emails = [
            {
                "email_id": f"msg_ne_{i}",
                "thread_id": f"th_ne_{i}",
                "subject": f"Notice {i}",
                "sender": "notifications@service.com",
                "body": "Your account has an update.",
                "predicted_priority": "P3",
                "action_required": False,
                "confidence": 0.75,
                "model_version": "priority-v3"
            }
            for i in range(5)
        ]

        user_email_cache.store_batch(self.user_a, emails)

        for i in range(5):
            res = user_email_cache.get(self.user_a, f"msg_ne_{i}")
            assert res is not None
            assert res.get("thread_id") == f"th_ne_{i}"
            assert len(res.get("thread_id")) > 0

    def test_3_shared_thread_id(self):
        """Test 3: Multiple messages in the same conversation thread share thread_id."""
        thread_id = "thread_conversation_999"
        msg1 = {
            "email_id": "thread_msg_1",
            "thread_id": thread_id,
            "subject": "Project Proposal",
            "sender": "client@partner.com",
            "body": "Can you review the proposal?",
            "predicted_priority": "P2",
            "action_required": True,
            "action_reason": "Review request",
            "confidence": 0.80,
            "model_version": "priority-v3"
        }
        msg2 = {
            "email_id": "thread_msg_2",
            "thread_id": thread_id,
            "subject": "Re: Project Proposal",
            "sender": "me@company.com",
            "body": "Looks good, I will send our feedback tomorrow.",
            "predicted_priority": "P2",
            "action_required": False,
            "confidence": 0.85,
            "model_version": "priority-v3"
        }

        user_email_cache.store_batch(self.user_a, [msg1, msg2])

        r1 = user_email_cache.get(self.user_a, "thread_msg_1")
        r2 = user_email_cache.get(self.user_a, "thread_msg_2")

        assert r1["thread_id"] == r2["thread_id"] == thread_id
        assert r1["email_id"] != r2["email_id"]

    def test_4_disjoint_threads(self):
        """Test 4: Messages in different conversations receive distinct thread_ids."""
        msg_a = {
            "email_id": "msg_th_a",
            "thread_id": "thread_alpha",
            "subject": "Alpha Topic",
            "body": "Content for alpha.",
            "predicted_priority": "P3",
            "confidence": 0.7,
            "model_version": "priority-v3"
        }
        msg_b = {
            "email_id": "msg_th_b",
            "thread_id": "thread_beta",
            "subject": "Beta Topic",
            "body": "Content for beta.",
            "predicted_priority": "P3",
            "confidence": 0.7,
            "model_version": "priority-v3"
        }

        user_email_cache.store_batch(self.user_a, [msg_a, msg_b])

        res_a = user_email_cache.get(self.user_a, "msg_th_a")
        res_b = user_email_cache.get(self.user_a, "msg_th_b")

        assert res_a["thread_id"] == "thread_alpha"
        assert res_b["thread_id"] == "thread_beta"
        assert res_a["thread_id"] != res_b["thread_id"]

    def test_5_subject_independence(self):
        """Test 5: Threads are grouped by Gmail threadId, not subject line similarity."""
        # Two completely separate emails that happen to share identical subject line "(No Subject)"
        msg_diff_1 = {
            "email_id": "no_subj_1",
            "thread_id": "tid_no_subj_1",
            "subject": "(No Subject)",
            "body": "First unrelated email with no subject.",
            "predicted_priority": "P4",
            "confidence": 0.5,
            "model_version": "priority-v3"
        }
        msg_diff_2 = {
            "email_id": "no_subj_2",
            "thread_id": "tid_no_subj_2",
            "subject": "(No Subject)",
            "body": "Second completely separate email.",
            "predicted_priority": "P4",
            "confidence": 0.5,
            "model_version": "priority-v3"
        }

        user_email_cache.store_batch(self.user_a, [msg_diff_1, msg_diff_2])

        r1 = user_email_cache.get(self.user_a, "no_subj_1")
        r2 = user_email_cache.get(self.user_a, "no_subj_2")

        assert r1["subject"] == r2["subject"]
        assert r1["thread_id"] != r2["thread_id"]

    def test_6_invariant_preservation(self):
        """Test 6: Thread ID persistence preserves priority, action, deadlines, and model metadata."""
        msg = {
            "email_id": "msg_preserve",
            "thread_id": "thread_preserve_123",
            "subject": "Action Deadline Required",
            "sender": "admin@org.com",
            "body": "Submit report by Oct 5, 2026.",
            "predicted_priority": "P2",
            "model_priority": "P2",
            "final_priority": "P2",
            "action_required": True,
            "action_reason": "Submission deadline",
            "action_evidence": {"imperative": True, "deadline_present": True},
            "deadline_detected": True,
            "deadline_datetime": "2026-10-05T23:59:00",
            "deadline_status": "ACTIVE",
            "needs_attention": True,
            "confidence": 0.88,
            "model_version": "priority-v3"
        }

        user_email_cache.store_batch(self.user_a, [msg])

        with user_email_cache._lock:
            user_email_cache._mem_cache.pop(self.user_a, None)

        fetched = user_email_cache.get(self.user_a, "msg_preserve")
        assert fetched["thread_id"] == "thread_preserve_123"
        assert fetched["predicted_priority"] == "P2"
        assert fetched["action_required"] is True
        assert fetched["deadline_detected"] is True
        assert fetched["deadline_status"] == "ACTIVE"
        assert fetched["needs_attention"] is True
        assert fetched["model_version"] == "priority-v3"

    def test_7_user_scoped_query_returns_thread_id(self):
        """Test 7: query_emails returns thread_id for all results."""
        emails = [
            {
                "email_id": f"query_msg_{i}",
                "thread_id": f"query_th_{i // 2}",
                "subject": f"Query Item {i}",
                "body": f"Body {i}",
                "predicted_priority": "P2",
                "confidence": 0.8,
                "model_version": "priority-v3"
            }
            for i in range(4)
        ]

        user_email_cache.store_batch(self.user_a, emails)

        items, total = user_email_cache.query_emails(self.user_a, page=1, page_size=10)
        assert total == 4
        assert len(items) == 4

        for item in items:
            assert "thread_id" in item
            assert item["thread_id"].startswith("query_th_")

    def test_8_user_isolation(self):
        """Test 8: User A cannot see or mutate User B's thread_ids."""
        msg_a = {
            "email_id": "shared_mid_1",
            "thread_id": "thread_user_a_secret",
            "subject": "Alice Thread",
            "body": "Alice body.",
            "predicted_priority": "P2",
            "confidence": 0.8,
            "model_version": "priority-v3"
        }
        msg_b = {
            "email_id": "shared_mid_1",
            "thread_id": "thread_user_b_isolated",
            "subject": "Bob Thread",
            "body": "Bob body.",
            "predicted_priority": "P3",
            "confidence": 0.7,
            "model_version": "priority-v3"
        }

        user_email_cache.store_batch(self.user_a, [msg_a])
        user_email_cache.store_batch(self.user_b, [msg_b])

        res_a = user_email_cache.get(self.user_a, "shared_mid_1")
        res_b = user_email_cache.get(self.user_b, "shared_mid_1")

        assert res_a["thread_id"] == "thread_user_a_secret"
        assert res_b["thread_id"] == "thread_user_b_isolated"
        assert res_a["subject"] == "Alice Thread"
        assert res_b["subject"] == "Bob Thread"

        # Query check
        items_a, _ = user_email_cache.query_emails(self.user_a)
        items_b, _ = user_email_cache.query_emails(self.user_b)
        assert items_a[0]["thread_id"] == "thread_user_a_secret"
        assert items_b[0]["thread_id"] == "thread_user_b_isolated"
