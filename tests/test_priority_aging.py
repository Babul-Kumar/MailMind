import os
import sys
import unittest
import time
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.core.session import session_manager
from backend.app.core.cache import user_email_cache
from backend.app.core.action_store import user_action_store
from backend.app.core.action_policy import (
    evaluate_priority_aging,
    calculate_effective_priority,
    get_otp_expiry_seconds,
    is_security_notification,
    SEVEN_DAYS_SECONDS,
    DEFAULT_OTP_EXPIRY_SECONDS,
)


class TestPriorityAging(unittest.TestCase):
    """
    Comprehensive tests for Dynamic Priority-Aging and Expiration Rules.
    Verifies:
      1. Explicit passed deadlines demote P1 to P2 (if actionable/overdue) or P4 (if expired).
      2. Expired OTPs immediately demote to P4 and leave the active queue.
      3. Active OTPs (< 10 mins or within validity window) remain P1.
      4. P1 without an explicit deadline ages from P1 to P2 after 7 days from received timestamp.
      5. Security alerts without a deadline age from P1 to P2 after 7 days.
      6. Unresolved security incidents remain accessible in Needs Attention even after demoting to P2.
      7. Three separate fields: original_priority, effective_priority, action_status.
      8. Original received timestamp is preserved across scans/refreshes.
      9. Dynamic recalculation on mailbox query and stats reflecting effective priorities.
    """

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.user_id = "test_user_aging"
        cls.session = session_manager.create_session(
            user_id=cls.user_id,
            email="aging_tester@example.com",
            credentials={"access_token": "mock_token", "refresh_token": "mock_refresh"}
        )
        cls.patch_service = patch("backend.app.api.routes_emails.get_user_gmail_service", return_value=MagicMock())
        cls.patch_profile = patch("backend.app.api.routes_emails.get_profile", return_value={"emailAddress": "aging_tester@example.com", "messagesTotal": 1, "threadsTotal": 1})
        cls.patch_scan = patch("backend.app.api.routes_emails.scan_manager.start_scan", return_value="mock_job_id")
        cls.patch_list = patch("backend.app.api.routes_emails.list_message_ids", return_value=[])
        cls.patch_service.start()
        cls.patch_profile.start()
        cls.patch_scan.start()
        cls.patch_list.start()

    @classmethod
    def tearDownClass(cls):
        cls.patch_service.stop()
        cls.patch_profile.stop()
        cls.patch_scan.stop()
        cls.patch_list.stop()

    def setUp(self):
        user_email_cache.clear_user(self.user_id)
        user_action_store.clear_user_actions(self.user_id)

    def test_explicit_deadline_passed_demotes_p1(self):
        """Rule 1: If an explicit deadline has passed, immediately remove from active P1."""
        now = time.time()
        # Case A: Actionable overdue item (past deadline but action still required) -> demote P1 to P2
        overdue_email = {
            "subject": "Urgent: Complete quarterly self-evaluation",
            "body": "The deadline was yesterday at 5 PM. Action is required to avoid HR escalation.",
            "final_priority": "P1",
            "predicted_priority": "P1",
            "deadline_detected": True,
            "deadline_datetime": datetime.fromtimestamp(now - 3600, timezone.utc).isoformat(),
            "deadline_status": "OVERDUE",
            "action_required": True,
            "internal_date": int((now - 7200) * 1000),
        }
        aging_res = evaluate_priority_aging(overdue_email, now_ts=now)
        self.assertEqual(aging_res["original_priority"], "P1")
        self.assertEqual(aging_res["effective_priority"], "P2")
        self.assertTrue(aging_res["is_demoted"])
        self.assertEqual(aging_res["action_status"], "ACTIVE")
        self.assertIn("deadline has passed", aging_res["demotion_reason"].lower())

        # Case B: Expired non-actionable offer/event deadline -> demote to P4 / EXPIRED
        expired_offer = {
            "subject": "Early bird conference registration closes today!",
            "body": "Register before noon today. Once closed, tickets cannot be purchased.",
            "final_priority": "P1",
            "predicted_priority": "P1",
            "deadline_detected": True,
            "deadline_datetime": datetime.fromtimestamp(now - 7200, timezone.utc).isoformat(),
            "deadline_status": "EXPIRED",
            "action_required": False,
            "internal_date": int((now - 10000) * 1000),
        }
        aging_res2 = evaluate_priority_aging(expired_offer, now_ts=now)
        self.assertEqual(aging_res2["effective_priority"], "P4")
        self.assertTrue(aging_res2["is_demoted"])
        self.assertEqual(aging_res2["action_status"], "EXPIRED")
        self.assertEqual(aging_res2["queue_placement"], "HISTORICAL")

    def test_otp_and_verification_code_expiration(self):
        """Rule 2: OTP / verification code expiry rules."""
        now = time.time()

        # Case A: Fresh OTP (2 minutes old, 10 min window) -> remains P1 ACTIVE
        fresh_otp = {
            "subject": "Your Google Verification Code is 839201",
            "body": "Use code 839201 to verify your account. It is valid for 10 minutes.",
            "final_priority": "P1",
            "predicted_priority": "P1",
            "action_required": True,
            "internal_date": int((now - 120) * 1000),  # 2 mins old
        }
        aging_fresh = evaluate_priority_aging(fresh_otp, now_ts=now)
        self.assertEqual(aging_fresh["effective_priority"], "P1")
        self.assertFalse(aging_fresh["is_demoted"])
        self.assertEqual(aging_fresh["action_status"], "ACTIVE")
        self.assertFalse(aging_fresh["is_otp_expired"])

        # Case B: Expired OTP with explicit validity (e.g. 5 minutes, email is 10 mins old)
        expired_otp_explicit = {
            "subject": "One-Time Password (OTP) for Bank Login",
            "body": "Your OTP is 492011. This code expires in 5 minutes. Do not share.",
            "final_priority": "P1",
            "predicted_priority": "P1",
            "action_required": True,
            "internal_date": int((now - 600) * 1000),  # 10 mins old
        }
        aging_exp_explicit = evaluate_priority_aging(expired_otp_explicit, now_ts=now)
        self.assertEqual(aging_exp_explicit["effective_priority"], "P4")
        self.assertTrue(aging_exp_explicit["is_demoted"])
        self.assertTrue(aging_exp_explicit["is_otp_expired"])
        self.assertEqual(aging_exp_explicit["action_status"], "EXPIRED")
        self.assertEqual(aging_exp_explicit["queue_placement"], "HISTORICAL")

        # Case C: Expired OTP with default validity (10 mins default, email is 20 mins old)
        expired_otp_default = {
            "subject": "Your login code",
            "body": "Here is your security passcode: 882103",
            "final_priority": "P1",
            "predicted_priority": "P1",
            "action_required": True,
            "internal_date": int((now - 1200) * 1000),  # 20 mins old
        }
        aging_exp_default = evaluate_priority_aging(expired_otp_default, now_ts=now)
        self.assertEqual(aging_exp_default["effective_priority"], "P4")
        self.assertTrue(aging_exp_default["is_demoted"])
        self.assertTrue(aging_exp_default["is_otp_expired"])
        self.assertEqual(aging_exp_default["action_status"], "EXPIRED")

    def test_p1_without_deadline_seven_day_aging(self):
        """Rule 3: P1 without an explicit deadline keeps P1 for 7 days, then demotes to P2."""
        now = time.time()

        # Case A: 3 days old (<= 7 days) -> remains P1
        recent_p1 = {
            "subject": "Contract draft for review and approval",
            "body": "Please review the attached vendor agreement and confirm your approval.",
            "final_priority": "P1",
            "predicted_priority": "P1",
            "deadline_detected": False,
            "deadline_datetime": None,
            "action_required": True,
            "internal_date": int((now - (3 * 86400)) * 1000),  # 3 days old
        }
        aging_recent = evaluate_priority_aging(recent_p1, now_ts=now)
        self.assertEqual(aging_recent["original_priority"], "P1")
        self.assertEqual(aging_recent["effective_priority"], "P1")
        self.assertFalse(aging_recent["is_demoted"])

        # Case B: Exactly 8 days old (> 7 days) -> demotes to P2
        aged_p1 = {
            "subject": "Contract draft for review and approval",
            "body": "Please review the attached vendor agreement and confirm your approval.",
            "final_priority": "P1",
            "predicted_priority": "P1",
            "deadline_detected": False,
            "deadline_datetime": None,
            "action_required": True,
            "internal_date": int((now - (8 * 86400)) * 1000),  # 8 days old
        }
        aging_aged = evaluate_priority_aging(aged_p1, now_ts=now)
        self.assertEqual(aging_aged["original_priority"], "P1")
        self.assertEqual(aging_aged["effective_priority"], "P2")
        self.assertTrue(aging_aged["is_demoted"])
        self.assertIn("7 days", aging_aged["demotion_reason"])

    def test_security_alert_without_deadline_aging(self):
        """Rule 4: Security alert without a deadline keeps P1 for up to 7 days, then demotes."""
        now = time.time()

        # Case A: Security notification 2 days old -> remains P1
        sec_alert_recent = {
            "subject": "Security alert: New sign-in from Chrome on macOS",
            "body": "We noticed a new sign-in to your account from Chrome on macOS. If this was you, ignore.",
            "final_priority": "P1",
            "predicted_priority": "P1",
            "deadline_detected": False,
            "deadline_datetime": None,
            "action_required": False,
            "internal_date": int((now - (2 * 86400)) * 1000),
        }
        res_recent = evaluate_priority_aging(sec_alert_recent, now_ts=now)
        self.assertEqual(res_recent["effective_priority"], "P1")
        self.assertFalse(res_recent["is_demoted"])

        # Case B: Security notification 10 days old -> demotes to P2
        sec_alert_aged = {
            "subject": "Security alert: Password changed successfully",
            "body": "Your account password was changed 10 days ago. If you did not make this change, contact support.",
            "final_priority": "P1",
            "predicted_priority": "P1",
            "deadline_detected": False,
            "deadline_datetime": None,
            "action_required": False,
            "internal_date": int((now - (10 * 86400)) * 1000),
        }
        res_aged = evaluate_priority_aging(sec_alert_aged, now_ts=now)
        self.assertEqual(res_aged["original_priority"], "P1")
        self.assertEqual(res_aged["effective_priority"], "P2")
        self.assertTrue(res_aged["is_demoted"])

    def test_unresolved_security_incident_retained_in_needs_attention(self):
        """Rule 5: Unresolved security incident remains in Needs Attention even after P1 demotion to P2."""
        now = time.time()

        # Critical security incident older than 7 days
        incident = {
            "subject": "CRITICAL INCIDENT: Unauthorized privilege escalation detected in cluster",
            "body": "Immediate incident response required. Unrecognized root shell spawned on worker node.",
            "final_priority": "P1",
            "predicted_priority": "P1",
            "action_required": True,
            "needs_attention": True,
            "is_critical_incident": True,
            "internal_date": int((now - (12 * 86400)) * 1000),  # 12 days old
        }
        res = evaluate_priority_aging(incident, now_ts=now)
        # Demoted from P1 to P2
        self.assertEqual(res["original_priority"], "P1")
        self.assertEqual(res["effective_priority"], "P2")
        self.assertTrue(res["is_demoted"])
        # Retained in active Needs Attention queue!
        self.assertEqual(res["queue_placement"], "ACTIVE")
        self.assertEqual(res["action_status"], "ACTIVE")
        self.assertTrue(res["is_actionable"])

    def test_original_received_timestamp_preserved(self):
        """The 7-day clock must start from the original received timestamp, not scan time."""
        now = time.time()
        received_timestamp = now - (9 * 86400)  # Received 9 days ago

        email_data = {
            "email_id": "aging_clock_test_01",
            "subject": "High priority budget approval",
            "body": "Please approve the Q4 budget allocation.",
            "final_priority": "P1",
            "predicted_priority": "P1",
            "action_required": True,
            "internal_date": int(received_timestamp * 1000),
            "date": datetime.fromtimestamp(received_timestamp, timezone.utc).isoformat(),
        }

        # Store in cache at current time `now`
        user_email_cache.set(self.user_id, "aging_clock_test_01", email_data)

        # Retrieve and verify: even though cached right now, the age is based on internal_date (9 days)
        rows, total = user_email_cache.query_emails(self.user_id, now_ts=now)
        self.assertEqual(total, 1)
        retrieved = rows[0]
        self.assertEqual(retrieved["original_priority"], "P1")
        self.assertEqual(retrieved["effective_priority"], "P2")
        self.assertTrue(retrieved["is_demoted"])

        # Simulate a re-scan/refresh: storing again should NOT reset the 7-day clock
        email_data_rescan = dict(email_data)
        email_data_rescan["_rescan_ts"] = now + 100
        user_email_cache.store_batch(self.user_id, [email_data_rescan])

        rows_rescan, _ = user_email_cache.query_emails(self.user_id, now_ts=now + 200)
        self.assertEqual(rows_rescan[0]["effective_priority"], "P2")
        self.assertTrue(rows_rescan[0]["is_demoted"])

    def test_three_fields_separation_and_frozen_ml(self):
        """Separation of original_priority, effective_priority, and action_status."""
        now = time.time()
        item = {
            "subject": "Action item: Q3 review",
            "body": "Review the presentation.",
            "predicted_priority": "P1",  # Frozen ML prediction
            "internal_date": int((now - (14 * 86400)) * 1000),  # 14 days old
        }
        aging = evaluate_priority_aging(item, now_ts=now)
        self.assertEqual(aging["original_priority"], "P1")
        self.assertEqual(aging["effective_priority"], "P2")
        self.assertIn("action_status", aging)
        # Ensure input predicted_priority was untouched
        self.assertEqual(item["predicted_priority"], "P1")

    def test_query_filter_and_stats_use_effective_priority(self):
        """Querying by priority filter and stats must use effective_priority."""
        now = time.time()
        emails = [
            # 1. Fresh P1 (remains P1)
            {
                "email_id": "fresh_p1",
                "subject": "System Emergency: Cluster Down",
                "body": "Cluster down, urgent response needed.",
                "predicted_priority": "P1",
                "final_priority": "P1",
                "action_required": True,
                "internal_date": int((now - 3600) * 1000),
            },
            # 2. Aged P1 (received 10 days ago -> becomes P2)
            {
                "email_id": "aged_p1",
                "subject": "Important architecture discussion",
                "body": "Please review the doc when you can.",
                "predicted_priority": "P1",
                "final_priority": "P1",
                "action_required": True,
                "internal_date": int((now - (10 * 86400)) * 1000),
            },
            # 3. Expired OTP (was P1, 30 mins old -> becomes P4 / EXPIRED)
            {
                "email_id": "expired_otp",
                "subject": "Your OTP code is 998877",
                "body": "Valid for 10 minutes.",
                "predicted_priority": "P1",
                "final_priority": "P1",
                "action_required": True,
                "internal_date": int((now - 1800) * 1000),
            },
            # 4. Standard P3
            {
                "email_id": "standard_p3",
                "subject": "Weekly Tech Digest",
                "body": "Here are this week's articles.",
                "predicted_priority": "P3",
                "final_priority": "P3",
                "action_required": False,
                "internal_date": int((now - 7200) * 1000),
            },
        ]
        user_email_cache.store_batch(self.user_id, emails)

        # A. Filter by P1 with effective priority aging: only fresh_p1 should match
        p1_rows, p1_total = user_email_cache.query_emails(self.user_id, priority="P1", now_ts=now, use_effective_priority=True)
        self.assertEqual(p1_total, 1)
        self.assertEqual(p1_rows[0]["email_id"], "fresh_p1")
        self.assertEqual(p1_rows[0]["effective_priority"], "P1")

        # A2. Standard mailbox filter by original model priority: all 3 P1 emails returned
        p1_orig_rows, p1_orig_total = user_email_cache.query_emails(self.user_id, priority="P1", now_ts=now, use_effective_priority=False)
        self.assertEqual(p1_orig_total, 3)

        # B. Filter by P2: aged_p1 should match because it demoted to P2
        p2_rows, p2_total = user_email_cache.query_emails(self.user_id, priority="P2", now_ts=now, use_effective_priority=True)
        self.assertEqual(p2_total, 1)
        self.assertEqual(p2_rows[0]["email_id"], "aged_p1")
        self.assertEqual(p2_rows[0]["effective_priority"], "P2")
        self.assertEqual(p2_rows[0]["original_priority"], "P1")
        self.assertTrue(p2_rows[0]["is_demoted"])

        # C. Filter by P4: expired_otp should be counted in P4 under effective priority
        p4_rows, p4_total = user_email_cache.query_emails(self.user_id, priority="P4", now_ts=now, use_effective_priority=True)
        p4_ids = [r["email_id"] for r in p4_rows]
        self.assertIn("expired_otp", p4_ids)

        # D. Mailbox stats: dynamic counts must reflect effective priorities when use_effective_priority=True
        stats = user_email_cache.get_mailbox_stats(self.user_id, use_effective_priority=True)
        self.assertEqual(stats["total_analyzed"], 4)
        self.assertEqual(stats["counts"]["P1"], 1)  # Only fresh_p1
        self.assertEqual(stats["counts"]["P2"], 1)  # aged_p1
        self.assertEqual(stats["counts"]["P3"], 1)  # standard_p3
        self.assertEqual(stats["counts"]["P4"], 1)  # expired_otp
        self.assertEqual(stats["highest_priority_count"], 1)

        # D2. Standard mailbox stats reflects total baseline priorities
        stats_std = user_email_cache.get_mailbox_stats(self.user_id, use_effective_priority=False)
        self.assertEqual(stats_std["counts"]["P1"], 3)

    def test_api_routes_display_aging_enrichment(self):
        """API /api/emails route returns effective_priority, original_priority, is_demoted."""
        now = time.time()
        aged_email = {
            "email_id": "api_aged_msg_01",
            "subject": "Action needed on partner contract",
            "body": "Please review this urgently.",
            "predicted_priority": "P1",
            "final_priority": "P1",
            "action_required": True,
            "internal_date": int((now - (9 * 86400)) * 1000),
            "date": datetime.fromtimestamp(now - (9 * 86400), timezone.utc).isoformat(),
        }
        user_email_cache.store_batch(self.user_id, [aged_email])

        response = self.client.get(
            "/api/emails",
            cookies={"mailmind_session": self.session.session_id}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        emails = data["emails"]
        self.assertEqual(len(emails), 1)
        item = emails[0]
        self.assertEqual(item["original_priority"], "P1")
        self.assertEqual(item["effective_priority"], "P2")
        self.assertTrue(item["is_demoted"])
        self.assertIn("7 days", item["demotion_reason"])


if __name__ == "__main__":
    unittest.main()
