import os
import sys
import unittest
import tempfile
import time
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.core.session import session_manager, SessionData
from backend.app.core.cache import user_email_cache
from backend.app.core.action_store import user_action_store, UserActionStore


class TestPriorityFilteringRegression(unittest.TestCase):
    """
    Comprehensive regression test suite for strict priority filtering,
    action state enrichment, count correctness, and user isolation.
    """

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.user_a_id = "test_user_filter_a"
        cls.user_b_id = "test_user_filter_b"

        # Create authenticated sessions
        cls.session_a = session_manager.create_session(
            user_id=cls.user_a_id,
            email="alice@test.com",
            credentials={"access_token": "mock_token_a", "refresh_token": "mock_refresh_a"}
        )
        cls.session_b = session_manager.create_session(
            user_id=cls.user_b_id,
            email="bob@test.com",
            credentials={"access_token": "mock_token_b", "refresh_token": "mock_refresh_b"}
        )

        # Clear existing caches for test users
        user_email_cache.clear_user(cls.user_a_id)
        user_email_cache.clear_user(cls.user_b_id)
        user_action_store.clear_user_actions(cls.user_a_id)
        user_action_store.clear_user_actions(cls.user_b_id)

        # Populate User A's cache with diverse priority fixture
        now = time.time()
        cls.emails_fixture = [
            # P1 items
            {
                "email_id": "msg_p1_01",
                "subject": "CRITICAL: Database primary outage alert",
                "sender": "pagerduty@enterprise.com",
                "body": "Production database cluster primary node down. Immediate incident triage required.",
                "predicted_priority": "P1",
                "final_priority": "P1",
                "action_required": True,
                "needs_attention": True,
                "confidence": 0.98,
                "internal_date": int((now - 100) * 1000),
                "date": datetime.fromtimestamp(now - 100, timezone.utc).isoformat(),
            },
            {
                "email_id": "msg_p1_02",
                "subject": "Security Alert: Unauthorized SSH key added to root",
                "sender": "security@enterprise.com",
                "body": "An unauthorized SSH public key was added to root on bastion-01.",
                "predicted_priority": "P1",
                "final_priority": "P1",
                "action_required": True,
                "needs_attention": True,
                "confidence": 0.95,
                "internal_date": int((now - 200) * 1000),
                "date": datetime.fromtimestamp(now - 200, timezone.utc).isoformat(),
            },
            # P2 items
            {
                "email_id": "msg_p2_01",
                "subject": "Project Sprint Review Agenda and Deliverables",
                "sender": "lead@enterprise.com",
                "body": "Please review deliverables before tomorrow's 10 AM sprint demo meeting.",
                "predicted_priority": "P2",
                "final_priority": "P2",
                "action_required": True,
                "needs_attention": True,
                "confidence": 0.88,
                "internal_date": int((now - 300) * 1000),
                "date": datetime.fromtimestamp(now - 300, timezone.utc).isoformat(),
            },
            {
                "email_id": "msg_p2_02",
                "subject": "Quarterly Budget Sign-off Required",
                "sender": "finance@enterprise.com",
                "body": "Q4 IT infrastructure allocation budget sheet needs manager sign-off.",
                "predicted_priority": "P2",
                "final_priority": "P2",
                "action_required": True,
                "needs_attention": True,
                "confidence": 0.85,
                "internal_date": int((now - 400) * 1000),
                "date": datetime.fromtimestamp(now - 400, timezone.utc).isoformat(),
            },
            # P3 items (including an actionable announcement)
            {
                "email_id": "msg_p3_01",
                "subject": "Exam Hall Tickets Released for October 2026",
                "sender": "onlinecourses@nptel.iitm.ac.in",
                "body": "Exam hall tickets have been generated. Candidates can access their candidate portal to download tickets.",
                "predicted_priority": "P3",
                "final_priority": "P3",
                "action_required": True,
                "needs_attention": True,
                "action_reason": "Download exam hall ticket",
                "confidence": 0.78,
                "internal_date": int((now - 500) * 1000),
                "date": datetime.fromtimestamp(now - 500, timezone.utc).isoformat(),
            },
            {
                "email_id": "msg_p3_02",
                "subject": "Engineering Team Weekly Lunch & Learn Schedule",
                "sender": "hr@enterprise.com",
                "body": "This week topic is Distributed Tracing with OpenTelemetry.",
                "predicted_priority": "P3",
                "final_priority": "P3",
                "action_required": False,
                "needs_attention": False,
                "confidence": 0.72,
                "internal_date": int((now - 600) * 1000),
                "date": datetime.fromtimestamp(now - 600, timezone.utc).isoformat(),
            },
            # P4 items
            {
                "email_id": "msg_p4_01",
                "subject": "Cloud Platform Weekly Product Newsletter",
                "sender": "news@cloudnewsletter.com",
                "body": "Explore our monthly product release notes and webinar recordings.",
                "predicted_priority": "P4",
                "final_priority": "P4",
                "action_required": False,
                "needs_attention": False,
                "confidence": 0.92,
                "internal_date": int((now - 700) * 1000),
                "date": datetime.fromtimestamp(now - 700, timezone.utc).isoformat(),
            },
            {
                "email_id": "msg_p4_02",
                "subject": "Exclusive 50% discount on dev conference tickets",
                "sender": "promotions@techconf.org",
                "body": "Register now to claim your early bird promotion before it ends.",
                "predicted_priority": "P4",
                "final_priority": "P4",
                "action_required": False,
                "needs_attention": False,
                "confidence": 0.94,
                "internal_date": int((now - 800) * 1000),
                "date": datetime.fromtimestamp(now - 800, timezone.utc).isoformat(),
            },
        ]
        # Mock Gmail service and profile fetching so cached emails are served smoothly
        cls.patch_service = patch("backend.app.api.routes_emails.get_user_gmail_service", return_value=MagicMock())
        cls.patch_profile = patch("backend.app.api.routes_emails.get_profile", return_value={"emailAddress": "alice@test.com", "messagesTotal": 8, "threadsTotal": 8})
        cls.patch_scan = patch("backend.app.api.routes_emails.scan_manager.start_scan", return_value="mock_job_id")
        cls.patch_list = patch("backend.app.api.routes_emails.list_message_ids", return_value=[])
        cls.patch_service.start()
        cls.patch_profile.start()
        cls.patch_scan.start()
        cls.patch_list.start()

        user_email_cache.store_batch(cls.user_a_id, cls.emails_fixture)

    @classmethod
    def tearDownClass(cls):
        cls.patch_service.stop()
        cls.patch_profile.stop()
        cls.patch_scan.stop()
        cls.patch_list.stop()
        user_email_cache.clear_user(cls.user_a_id)
        user_email_cache.clear_user(cls.user_b_id)
        user_action_store.clear_user_actions(cls.user_a_id)
        user_action_store.clear_user_actions(cls.user_b_id)
        session_manager.delete_session(cls.session_a.session_id)
        session_manager.delete_session(cls.session_b.session_id)

    def test_01_p1_filter_strict_isolation(self):
        """P1 filter returns only P1 emails, zero P2, P3, or P4 emails."""
        res = self.client.get(
            "/api/emails?priority=P1&page=1&page_size=50",
            cookies={"mailmind_session": self.session_a.session_id}
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        emails = data["emails"]
        self.assertGreater(len(emails), 0)
        for e in emails:
            effective_p = e.get("final_priority") or e.get("predicted_priority")
            self.assertEqual(effective_p, "P1", f"Expected P1 email but got {effective_p}: {e['subject']}")

    def test_02_p2_filter_strict_isolation(self):
        """P2 filter returns only P2 emails, zero P1, P3, or P4 emails."""
        res = self.client.get(
            "/api/emails?priority=P2&page=1&page_size=50",
            cookies={"mailmind_session": self.session_a.session_id}
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        emails = data["emails"]
        self.assertGreater(len(emails), 0)
        for e in emails:
            effective_p = e.get("final_priority") or e.get("predicted_priority")
            self.assertEqual(effective_p, "P2", f"Expected P2 email but got {effective_p}: {e['subject']}")

    def test_03_p3_filter_strict_isolation(self):
        """P3 filter returns only P3 emails, zero P1, P2, or P4 emails."""
        res = self.client.get(
            "/api/emails?priority=P3&page=1&page_size=50",
            cookies={"mailmind_session": self.session_a.session_id}
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        emails = data["emails"]
        self.assertGreater(len(emails), 0)
        for e in emails:
            effective_p = e.get("final_priority") or e.get("predicted_priority")
            self.assertEqual(effective_p, "P3", f"Expected P3 email but got {effective_p}: {e['subject']}")

    def test_04_p4_filter_strict_isolation(self):
        """P4 filter returns only P4 emails, zero P1, P2, or P3 emails."""
        res = self.client.get(
            "/api/emails?priority=P4&page=1&page_size=50",
            cookies={"mailmind_session": self.session_a.session_id}
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        emails = data["emails"]
        self.assertGreater(len(emails), 0)
        for e in emails:
            effective_p = e.get("final_priority") or e.get("predicted_priority")
            self.assertEqual(effective_p, "P4", f"Expected P4 email but got {effective_p}: {e['subject']}")

    def test_05_all_mail_returns_all_records(self):
        """All Mail (priority=ALL or omitted) returns all emails."""
        res = self.client.get(
            "/api/emails?priority=ALL&page=1&page_size=50",
            cookies={"mailmind_session": self.session_a.session_id}
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        emails = data["emails"]
        self.assertEqual(len(emails), 8)
        priorities_present = {e.get("final_priority") or e.get("predicted_priority") for e in emails}
        self.assertEqual(priorities_present, {"P1", "P2", "P3", "P4"})

    def test_06_needs_attention_preserves_p3_priority(self):
        """Needs Attention includes actionable P3 without modifying its priority to P1."""
        res = self.client.get(
            "/api/emails?priority=NEEDS_ATTENTION&page=1&page_size=50",
            cookies={"mailmind_session": self.session_a.session_id}
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        emails = data["emails"]
        p3_in_attention = [e for e in emails if (e.get("final_priority") or e.get("predicted_priority")) == "P3"]
        self.assertGreater(len(p3_in_attention), 0, "Actionable P3 should be in Needs Attention")
        self.assertEqual(p3_in_attention[0]["email_id"], "msg_p3_01")
        # Ensure priority is still P3, not promoted to P1
        self.assertEqual(p3_in_attention[0]["final_priority"], "P3")

    def test_07_action_state_enrichment_and_isolation(self):
        """Action states are attached to User A's emails and isolated from User B."""
        # Resolve an email for User A
        user_action_store.resolve_action(
            user_id=self.user_a_id,
            message_id="msg_p1_01",
            note="Resolved by Alice"
        )

        res_a = self.client.get(
            "/api/emails?page=1&page_size=50",
            cookies={"mailmind_session": self.session_a.session_id}
        )
        self.assertEqual(res_a.status_code, 200)
        emails_a = {e["email_id"]: e for e in res_a.json()["emails"]}
        self.assertTrue(emails_a["msg_p1_01"]["is_resolved"])

        # User B should NOT see User A's resolved state
        res_b = self.client.get(
            "/api/emails?page=1&page_size=50",
            cookies={"mailmind_session": self.session_b.session_id}
        )
        self.assertEqual(res_b.status_code, 200)
        emails_b = {e["email_id"]: e for e in res_b.json()["emails"]}
        if "msg_p1_01" in emails_b:
            self.assertFalse(emails_b["msg_p1_01"]["is_resolved"])

    def test_08_search_and_priority_composition(self):
        """Search composed with priority filter returns exact intersection."""
        # Search for 'database' under P1
        res = self.client.get(
            "/api/emails?priority=P1&query=database&page=1&page_size=50",
            cookies={"mailmind_session": self.session_a.session_id}
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(len(data["emails"]), 1)
        self.assertEqual(data["emails"][0]["email_id"], "msg_p1_01")

        # Search for 'agenda' under P1 (which is P2) -> should return 0 results
        res_empty = self.client.get(
            "/api/emails?priority=P1&query=agenda&page=1&page_size=50",
            cookies={"mailmind_session": self.session_a.session_id}
        )
        self.assertEqual(res_empty.status_code, 200)
        self.assertEqual(len(res_empty.json()["emails"]), 0)

    def test_09_pagination_consistency(self):
        """Pagination returns accurate total_emails, total_pages, and slice boundaries."""
        res = self.client.get(
            "/api/emails?page=1&page_size=3",
            cookies={"mailmind_session": self.session_a.session_id}
        )
        self.assertEqual(res.status_code, 200)
        pag = res.json()["pagination"]
        self.assertEqual(pag["page"], 1)
        self.assertEqual(pag["page_size"], 3)
        self.assertEqual(pag["total_emails"], 8)
        self.assertEqual(pag["total_pages"], 3)
        self.assertTrue(pag["has_next"])
        self.assertFalse(pag["has_prev"])


if __name__ == "__main__":
    unittest.main()
