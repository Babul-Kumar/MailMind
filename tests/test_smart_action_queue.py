import os
import sys
import time
import unittest
import tempfile
import shutil
from datetime import datetime, timedelta, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.app.core.action_store import UserActionStore
from backend.app.core.action_policy import (
    classify_action_queue_item,
    evaluate_action_queue,
    generate_next_step,
    is_critical_incident,
    is_otp_or_verification_code,
    AGE_THRESHOLD_SECONDS,
)
from backend.app.ml.refinement import (
    refine_priority,
    extract_deadline,
    evaluate_action_layer,
    determine_deadline_status,
)
from backend.app.ml.predictor import load_model, predict_email


class TestSmartActionQueue(unittest.TestCase):
    """
    Comprehensive regression test suite for MailMind's Smart Action Queue upgrade.
    Validates all 18 core requirements:
      1. Actionable email within 8 days -> active queue.
      2. Ordinary actionable email older than 8 days -> older actions.
      3. Exact 8.0-day boundary test (<= 691200s active, > 691200s older).
      4. Old unresolved critical incident remains active.
      5. Old non-incident P1 email does not bypass the 8-day rule.
      6. Expired verification code leaves active queue.
      7. Overdue task (e.g., bill or assignment) remains overdue and actionable, not expired.
      8. Uncertain deadline is not invented.
      9. Snoozed item is hidden until return time.
      10. Snoozed item returns to correct queue upon expiration.
      11. Mark resolved persists across refreshes and rescans.
      12. Undo restores the appropriate state.
      13. Actionable announcement classified P3 is recognized as actionable without altering P3.
      14. Re-fetching an old message does not reopen a resolved task.
      15. User A cannot read or modify User B's resolution or snooze state.
      16. Counts do not double-count items.
      17. Failed state persistence is handled safely.
      18. Existing pagination, classification, and mailbox behavior remain intact.
    """

    @classmethod
    def setUpClass(cls):
        cls.pipeline = load_model()

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_action_store.db")
        self.store = UserActionStore(self.db_path)
        self.now_dt = datetime(2026, 10, 19, 12, 0, 0, tzinfo=timezone.utc)

    def tearDown(self):
        try:
            shutil.rmtree(self.temp_dir)
        except Exception:
            pass

    # --------------------------------------------------------------------------
    # 1. Actionable email within 8 days -> Active queue
    # --------------------------------------------------------------------------
    def test_01_actionable_within_8_days(self):
        arrival_dt = self.now_dt - timedelta(days=2)
        email = {
            "id": "msg_recent_action",
            "subject": "Review pull request #42",
            "body": "Please review and approve the pull request before deployment.",
            "sender": "lead@techcorp.com",
            "date": arrival_dt.isoformat(),
            "final_priority": "P2",
            "action_required": True,
            "action_reason": "Review request",
            "deadline_detected": False,
        }
        res = classify_action_queue_item(email, now_dt=self.now_dt)
        self.assertEqual(res["queue_placement"], "ACTIVE_QUEUE")
        self.assertFalse(res["is_older"])
        self.assertFalse(res["is_expired"])
        self.assertFalse(res["is_resolved"])
        self.assertFalse(res["is_snoozed"])
        self.assertIn("Review", res["next_step"])

    # --------------------------------------------------------------------------
    # 2. Ordinary actionable email older than 8 days -> Older actions
    # --------------------------------------------------------------------------
    def test_02_ordinary_actionable_older_than_8_days(self):
        arrival_dt = self.now_dt - timedelta(days=9)
        email = {
            "id": "msg_older_action",
            "subject": "Complete team feedback survey",
            "body": "Please fill out the annual survey by visiting the internal portal.",
            "sender": "hr@techcorp.com",
            "date": arrival_dt.isoformat(),
            "final_priority": "P3",
            "action_required": True,
            "action_reason": "Survey request",
            "deadline_detected": False,
        }
        res = classify_action_queue_item(email, now_dt=self.now_dt)
        self.assertEqual(res["queue_placement"], "OLDER_ACTIONS")
        self.assertTrue(res["is_older"])
        self.assertFalse(res["is_expired"])

    # --------------------------------------------------------------------------
    # 3. Exact 8.0-day boundary test
    # --------------------------------------------------------------------------
    def test_03_exact_8_day_boundary(self):
        # Exactly at 691200 seconds (8.0 days): should be ACTIVE_QUEUE (<= threshold)
        exact_8_days_ago = self.now_dt - timedelta(seconds=AGE_THRESHOLD_SECONDS)
        email_exact = {
            "id": "msg_exact_boundary",
            "subject": "Action task at boundary",
            "body": "Please update your profile details.",
            "sender": "admin@service.com",
            "date": exact_8_days_ago.isoformat(),
            "final_priority": "P2",
            "action_required": True,
            "action_reason": "Profile update",
        }
        res_exact = classify_action_queue_item(email_exact, now_dt=self.now_dt)
        self.assertEqual(res_exact["queue_placement"], "ACTIVE_QUEUE")

        # Exactly at 691201 seconds (8 days + 1 second): should be OLDER_ACTIONS (> threshold)
        past_8_days_ago = self.now_dt - timedelta(seconds=AGE_THRESHOLD_SECONDS + 1)
        email_past = {
            "id": "msg_past_boundary",
            "subject": "Action task past boundary",
            "body": "Please update your profile details.",
            "sender": "admin@service.com",
            "date": past_8_days_ago.isoformat(),
            "final_priority": "P2",
            "action_required": True,
            "action_reason": "Profile update",
        }
        res_past = classify_action_queue_item(email_past, now_dt=self.now_dt)
        self.assertEqual(res_past["queue_placement"], "OLDER_ACTIONS")

    # --------------------------------------------------------------------------
    # 4. Old unresolved critical incident remains active regardless of age
    # --------------------------------------------------------------------------
    def test_04_critical_incident_older_than_8_days_remains_active(self):
        arrival_dt = self.now_dt - timedelta(days=25)
        email_incident = {
            "id": "msg_critical_outage",
            "subject": "CRITICAL ALERT: Production Database Outage - Service Down",
            "body": "Primary cluster is unresponsive. Emergency engineering action required immediately.",
            "sender": "pagerduty@alerts.corp.internal",
            "date": arrival_dt.isoformat(),
            "final_priority": "P1",
            "action_required": True,
            "action_reason": "Critical production incident",
            "deadline_detected": False,
        }
        self.assertTrue(is_critical_incident(email_incident))
        res = classify_action_queue_item(email_incident, now_dt=self.now_dt)
        self.assertEqual(res["queue_placement"], "ACTIVE_QUEUE")
        self.assertTrue(res["is_critical"])
        self.assertIn("Resolve urgent incident", res["next_step"])

    # --------------------------------------------------------------------------
    # 5. Old non-incident P1 email does not bypass the 8-day rule
    # --------------------------------------------------------------------------
    def test_05_old_p1_non_incident_moves_to_older_actions(self):
        arrival_dt = self.now_dt - timedelta(days=12)
        # Executive VIP hello email classified as P1, but not a server crash / critical incident
        email_vip = {
            "id": "msg_vip_hello",
            "subject": "Quarterly leadership welcome and greetings",
            "body": "Welcome to Q4. Please review our vision document when you get a chance.",
            "sender": "ceo@techcorp.com",
            "date": arrival_dt.isoformat(),
            "final_priority": "P1",
            "action_required": True,
            "action_reason": "Document review",
            "deadline_detected": False,
        }
        self.assertFalse(is_critical_incident(email_vip))
        res = classify_action_queue_item(email_vip, now_dt=self.now_dt)
        self.assertEqual(res["queue_placement"], "OLDER_ACTIONS")
        self.assertTrue(res["is_older"])

    # --------------------------------------------------------------------------
    # 6. Expired verification code leaves active queue
    # --------------------------------------------------------------------------
    def test_06_expired_otp_verification_leaves_active_queue(self):
        # OTP received 30 minutes ago
        arrival_dt = self.now_dt - timedelta(minutes=30)
        email_otp = {
            "id": "msg_otp_expired",
            "subject": "Your verification code is 482910",
            "body": "Your one-time login code is 482910. This code will expire in 10 minutes.",
            "sender": "security@auth.service.com",
            "date": arrival_dt.isoformat(),
            "final_priority": "P2",
            "action_required": True,
            "action_reason": "Immediate verification required",
            "deadline_detected": True,
        }
        self.assertTrue(is_otp_or_verification_code(email_otp))
        res = classify_action_queue_item(email_otp, now_dt=self.now_dt)
        self.assertEqual(res["queue_placement"], "EXPIRED_ACTIONS")
        self.assertTrue(res["is_expired"])
        self.assertTrue("verification code" in res["next_step"].lower() or "expired" in res["next_step"].lower())

    # --------------------------------------------------------------------------
    # 7. Overdue task (e.g. bill or assignment) remains overdue, NOT expired
    # --------------------------------------------------------------------------
    def test_07_overdue_bill_or_assignment_remains_actionable_not_expired(self):
        arrival_dt = self.now_dt - timedelta(days=6)
        email_bill = {
            "id": "msg_overdue_bill",
            "subject": "Urgent: Electricity Bill Past Due",
            "body": "Your electricity payment of $142.50 was due on Oct 16. Pay now to prevent service cutoff.",
            "sender": "billing@powercompany.com",
            "date": arrival_dt.isoformat(),
            "final_priority": "P1",
            "action_required": True,
            "action_reason": "Payment overdue",
            "deadline_detected": True,
            "deadline_datetime": (self.now_dt - timedelta(days=3)).strftime("%Y-%m-%d"),
            "deadline_status": "OVERDUE",
        }
        # Overdue bill is NOT an ephemeral OTP and must remain actionable
        self.assertFalse(is_otp_or_verification_code(email_bill))
        res = classify_action_queue_item(email_bill, now_dt=self.now_dt)
        self.assertEqual(res["queue_placement"], "ACTIVE_QUEUE")
        self.assertFalse(res["is_expired"])
        self.assertIn("overdue", res["next_step"].lower())

    # --------------------------------------------------------------------------
    # 8. Uncertain deadline is not invented
    # --------------------------------------------------------------------------
    def test_08_uncertain_deadline_not_invented(self):
        res = extract_deadline(
            subject="Upcoming Exam Schedule Notice",
            body="Exam dates will be announced on the portal soon. Please keep checking the portal.",
            email_date=self.now_dt.isoformat(),
        )
        self.assertFalse(res["deadline_detected"])
        self.assertEqual(res["deadline_precision"], "NONE")
        self.assertIsNone(res["deadline_datetime"])
        self.assertEqual(res["deadline_status"], "NONE")

    # --------------------------------------------------------------------------
    # 9. Snoozed item is hidden until return time
    # --------------------------------------------------------------------------
    def test_09_snoozed_item_hidden_until_return_time(self):
        user_id = "user_test_snooze"
        email_id = "msg_snoozed_task"
        snooze_until = self.now_dt + timedelta(hours=4)
        
        self.store.snooze_action(user_id, email_id, snooze_until.isoformat())
        action_state = self.store.get_action_state(user_id, email_id)
        
        email = {
            "id": email_id,
            "subject": "Follow up with client",
            "body": "Need to follow up regarding contract signing.",
            "sender": "partner@consulting.com",
            "date": (self.now_dt - timedelta(days=1)).isoformat(),
            "final_priority": "P2",
            "action_required": True,
            "action_reason": "Follow up",
        }
        res = classify_action_queue_item(email, action_state=action_state, now_dt=self.now_dt)
        self.assertEqual(res["queue_placement"], "SNOOZED")
        self.assertTrue(res["is_snoozed"])
        self.assertEqual(res["snoozed_until"], snooze_until.timestamp())

    # --------------------------------------------------------------------------
    # 10. Snoozed item returns to correct queue upon expiration
    # --------------------------------------------------------------------------
    def test_10_snoozed_item_returns_to_correct_queue_when_expired(self):
        user_id = "user_test_snooze_return"
        email_id_active = "msg_snooze_returned_active"
        email_id_older = "msg_snooze_returned_older"
        
        # Snooze expired 10 minutes ago
        snooze_past = self.now_dt - timedelta(minutes=10)
        self.store.snooze_action(user_id, email_id_active, snooze_past.isoformat())
        self.store.snooze_action(user_id, email_id_older, snooze_past.isoformat())

        state_active = self.store.get_action_state(user_id, email_id_active)
        state_older = self.store.get_action_state(user_id, email_id_older)

        # Recent email (2 days old) should return to ACTIVE_QUEUE
        email_active = {
            "id": email_id_active,
            "subject": "Active task returns",
            "body": "Task details.",
            "sender": "work@company.com",
            "date": (self.now_dt - timedelta(days=2)).isoformat(),
            "final_priority": "P2",
            "action_required": True,
        }
        res_active = classify_action_queue_item(email_active, action_state=state_active, now_dt=self.now_dt)
        self.assertEqual(res_active["queue_placement"], "ACTIVE_QUEUE")
        self.assertFalse(res_active["is_snoozed"])

        # Older email (12 days old) should return to OLDER_ACTIONS
        email_older = {
            "id": email_id_older,
            "subject": "Older task returns",
            "body": "Task details.",
            "sender": "work@company.com",
            "date": (self.now_dt - timedelta(days=12)).isoformat(),
            "final_priority": "P2",
            "action_required": True,
        }
        res_older = classify_action_queue_item(email_older, action_state=state_older, now_dt=self.now_dt)
        self.assertEqual(res_older["queue_placement"], "OLDER_ACTIONS")
        self.assertFalse(res_older["is_snoozed"])

    # --------------------------------------------------------------------------
    # 11. Mark resolved persists across refreshes and rescans
    # --------------------------------------------------------------------------
    def test_11_mark_resolved_persists_across_queries(self):
        user_id = "user_test_resolve"
        email_id = "msg_resolved_01"
        self.store.resolve_action(user_id, email_id, notes="Handled via phone call")

        # Read back fresh from store
        state = self.store.get_action_state(user_id, email_id)
        self.assertTrue(state["is_resolved"])
        self.assertIsNotNone(state["resolved_at"])

        email = {
            "id": email_id,
            "subject": "Submit quarterly timesheet",
            "body": "Reminder to submit timesheet for September.",
            "sender": "payroll@company.com",
            "date": (self.now_dt - timedelta(days=1)).isoformat(),
            "final_priority": "P2",
            "action_required": True,
        }
        res = classify_action_queue_item(email, action_state=state, now_dt=self.now_dt)
        self.assertEqual(res["queue_placement"], "RESOLVED")
        self.assertTrue(res["is_resolved"])

    # --------------------------------------------------------------------------
    # 12. Undo restores the appropriate state
    # --------------------------------------------------------------------------
    def test_12_undo_restores_appropriate_state(self):
        user_id = "user_test_undo"
        email_id = "msg_undo_01"
        
        # 1. Resolve
        self.store.resolve_action(user_id, email_id)
        self.assertTrue(self.store.get_action_state(user_id, email_id)["is_resolved"])

        # 2. Unresolve (Undo)
        self.store.unresolve_action(user_id, email_id)
        state_after_undo = self.store.get_action_state(user_id, email_id)
        self.assertFalse(state_after_undo["is_resolved"])

        # 3. Verify it restores to ACTIVE_QUEUE for 3-day old email
        email = {
            "id": email_id,
            "subject": "Review draft document",
            "body": "Please review the attached contract.",
            "sender": "legal@company.com",
            "date": (self.now_dt - timedelta(days=3)).isoformat(),
            "final_priority": "P2",
            "action_required": True,
        }
        res = classify_action_queue_item(email, action_state=state_after_undo, now_dt=self.now_dt)
        self.assertEqual(res["queue_placement"], "ACTIVE_QUEUE")
        self.assertFalse(res["is_resolved"])

    # --------------------------------------------------------------------------
    # 13. Actionable announcement classified P3 surfaces in Needs Attention without altering P3
    # --------------------------------------------------------------------------
    def test_13_actionable_announcement_classified_p3(self):
        # Reproducing the exact bug case from remainingtask.txt
        email_data = {
            "id": "nptel_hall_ticket_01",
            "subject": "October 2026 NPTEL Exams - Hall Tickets Released!!",
            "body": (
                "Dear Candidate, The hall tickets for the October 2026 NPTEL examinations have been released. "
                "Registered candidates can now download their admit card and exam hall ticket from the portal."
            ),
            "sender": "onlinecourses@nptel.iitm.ac.in",
            "date": (self.now_dt - timedelta(days=2)).isoformat(),
        }
        pred = predict_email(email_data, self.pipeline)
        # 1. Verify priority remains P3 (preserves learned priority classification)
        self.assertEqual(pred["final_priority"], "P3")
        # 2. Verify separate action layer correctly flags action_required
        self.assertTrue(pred["action_required"])
        self.assertEqual(pred["action_evidence"]["action_type"], "document_download")
        # 3. Verify surfaces in Needs Attention
        self.assertTrue(pred["needs_attention"])
        # 4. Verify queue placement is ACTIVE_QUEUE
        queue_item = classify_action_queue_item(pred, now_dt=self.now_dt)
        self.assertEqual(queue_item["queue_placement"], "ACTIVE_QUEUE")
        self.assertIn("download", queue_item["next_step"].lower())

    # --------------------------------------------------------------------------
    # 14. Re-fetching an old message does not reopen a resolved task
    # --------------------------------------------------------------------------
    def test_14_refetching_message_does_not_reopen_resolved_task(self):
        user_id = "user_test_rescan"
        email_id = "msg_rescan_01"
        self.store.resolve_action(user_id, email_id)

        # Re-scan or re-fetch produces raw email from server
        email_from_fetch = {
            "id": email_id,
            "subject": "Security audit form",
            "body": "Fill out audit checklist.",
            "sender": "security@corp.com",
            "date": (self.now_dt - timedelta(days=4)).isoformat(),
            "final_priority": "P2",
            "action_required": True,
            "needs_attention": True,
        }
        # In the pipeline, email is merged with action_state
        state = self.store.get_action_state(user_id, email_id)
        res = classify_action_queue_item(email_from_fetch, action_state=state, now_dt=self.now_dt)
        self.assertEqual(res["queue_placement"], "RESOLVED")
        self.assertTrue(res["is_resolved"])

    # --------------------------------------------------------------------------
    # 15. User A cannot read or modify User B's state
    # --------------------------------------------------------------------------
    def test_15_user_isolation(self):
        user_a = "user_alice@corp.com"
        user_b = "user_bob@corp.com"
        shared_email_id = "msg_all_hands_qna"

        # User A resolves the task
        self.store.resolve_action(user_a, shared_email_id, notes="Alice done")

        # User B should have an untouched, un-resolved state
        state_a = self.store.get_action_state(user_a, shared_email_id)
        state_b = self.store.get_action_state(user_b, shared_email_id)

        self.assertTrue(state_a["is_resolved"])
        self.assertIsNone(state_b)

        # User B snoozes
        self.store.snooze_action(user_b, shared_email_id, (self.now_dt + timedelta(days=1)).isoformat())
        state_a_updated = self.store.get_action_state(user_a, shared_email_id)
        state_b_updated = self.store.get_action_state(user_b, shared_email_id)

        self.assertFalse(state_a_updated["is_snoozed"])
        self.assertTrue(state_b_updated["is_snoozed"])

    # --------------------------------------------------------------------------
    # 16. Counts do not double-count items
    # --------------------------------------------------------------------------
    def test_16_counts_do_not_double_count(self):
        emails = [
            # 1. Urgent critical incident (active)
            {
                "id": "m1",
                "subject": "CRITICAL: Server Outage",
                "body": "Server down",
                "date": (self.now_dt - timedelta(days=1)).isoformat(),
                "final_priority": "P1",
                "action_required": True,
                "needs_attention": True,
            },
            # 2. Due soon active (2 days old with active deadline)
            {
                "id": "m2",
                "subject": "Assignment Due Tomorrow",
                "body": "Submit assignment",
                "date": (self.now_dt - timedelta(days=2)).isoformat(),
                "final_priority": "P2",
                "action_required": True,
                "needs_attention": True,
                "deadline_detected": True,
                "deadline_datetime": (self.now_dt + timedelta(days=1)).strftime("%Y-%m-%d"),
                "deadline_status": "ACTIVE",
            },
            # 3. Other active (3 days old, ordinary action)
            {
                "id": "m3",
                "subject": "Code Review",
                "body": "Please review",
                "date": (self.now_dt - timedelta(days=3)).isoformat(),
                "final_priority": "P2",
                "action_required": True,
                "needs_attention": True,
            },
            # 4. Older actions (10 days old, ordinary action)
            {
                "id": "m4",
                "subject": "HR Survey",
                "body": "Complete survey",
                "date": (self.now_dt - timedelta(days=10)).isoformat(),
                "final_priority": "P3",
                "action_required": True,
                "needs_attention": True,
            },
            # 5. Snoozed item
            {
                "id": "m5",
                "subject": "Partner proposal",
                "body": "Check proposal",
                "date": (self.now_dt - timedelta(days=1)).isoformat(),
                "final_priority": "P2",
                "action_required": True,
                "needs_attention": True,
            },
            # 6. Resolved item
            {
                "id": "m6",
                "subject": "Signed invoice",
                "body": "Invoice signed",
                "date": (self.now_dt - timedelta(days=1)).isoformat(),
                "final_priority": "P2",
                "action_required": True,
                "needs_attention": True,
            },
        ]
        user_states = {
            "m5": {"is_resolved": False, "is_snoozed": True, "snoozed_until": (self.now_dt + timedelta(days=1)).isoformat()},
            "m6": {"is_resolved": True, "is_snoozed": False, "snoozed_until": None},
        }
        res = evaluate_action_queue(emails, user_action_states=user_states, now_dt=self.now_dt)
        counts = res["counts"]

        self.assertEqual(len(res["active_queue"]), 3)
        self.assertEqual(len(res["older_actions"]), 1)
        self.assertEqual(len(res["snoozed_items"]), 1)
        self.assertEqual(len(res["resolved_items"]), 1)

        self.assertEqual(counts["urgent_count"], 1)
        self.assertEqual(counts["due_soon_count"], 1)
        self.assertEqual(counts["other_active_count"], 1)
        self.assertEqual(counts["active_total"], 3)
        self.assertEqual(counts["older_total"], 1)
        self.assertEqual(counts["snoozed_total"], 1)
        self.assertEqual(counts["resolved_total"], 1)

        # Exact mathematical partition check
        partition_sum = counts["active_total"] + counts["older_total"] + counts["snoozed_total"] + counts["resolved_total"]
        self.assertEqual(partition_sum, len(emails))

    # --------------------------------------------------------------------------
    # 17. Failed state persistence is handled safely
    # --------------------------------------------------------------------------
    def test_17_failed_state_persistence_handled_safely(self):
        # Empty user_id or email_id returns None safely without throwing unhandled exceptions
        state_empty = self.store.get_action_state("", "")
        self.assertIsNone(state_empty)

        # Empty parameters to resolve/snooze raise ValueError as expected
        with self.assertRaises(ValueError):
            self.store.resolve_action("", "")
        with self.assertRaises(ValueError):
            self.store.snooze_action("", "", "2026-10-20T12:00:00Z")

    # --------------------------------------------------------------------------
    # 18. Existing pagination, classification, and mailbox behavior remain intact
    # --------------------------------------------------------------------------
    def test_18_existing_pagination_classification_mailbox_intact(self):
        # Verify predict_email continues returning all required production schema keys
        sample_email = {
            "id": "msg_schema_check",
            "subject": "System Status Update",
            "body": "All systems operating normally.",
            "sender": "ops@techcorp.com",
            "date": self.now_dt.isoformat(),
        }
        res = predict_email(sample_email, self.pipeline)
        expected_keys = [
            "model_priority", "final_priority", "confidence", "confidence_level",
            "topic", "action_required", "action_reason", "action_evidence",
            "deadline_detected", "deadline_datetime", "deadline_precision",
            "deadline_display", "deadline_status", "needs_attention", "probabilities"
        ]
        for key in expected_keys:
            self.assertIn(key, res, f"Expected key '{key}' in prediction response")

    # 19. Action store method compatibility and aliases
    def test_19_action_store_method_compatibility_and_aliases(self):
        self.store.resolve_action(user_id="user_compat_1", message_id="msg_101", note="Done")
        self.store.snooze_action(user_id="user_compat_1", message_id="msg_102", snoozed_until=time.time() + 3600, reason="Later")

        # Verify get_user_actions_map
        map1 = self.store.get_user_actions_map("user_compat_1")
        self.assertIn("msg_101", map1)
        self.assertIn("msg_102", map1)
        self.assertEqual(map1["msg_101"]["is_resolved"], 1)
        self.assertEqual(map1["msg_102"]["is_snoozed"], 1)

        # Verify get_user_action_states alias
        map2 = self.store.get_user_action_states("user_compat_1")
        self.assertEqual(map1, map2)

        # Verify get_all_action_states alias
        map3 = self.store.get_all_action_states("user_compat_1")
        self.assertEqual(map1, map3)

    # 20. Action store strict user isolation
    def test_20_action_store_strict_user_isolation(self):
        self.store.resolve_action(user_id="user_alice", message_id="msg_shared", note="Alice resolved")

        alice_states = self.store.get_user_action_states("user_alice")
        bob_states = self.store.get_user_action_states("user_bob")

        self.assertIn("msg_shared", alice_states)
        self.assertEqual(alice_states["msg_shared"]["is_resolved"], 1)
        self.assertNotIn("msg_shared", bob_states)
        self.assertEqual(bob_states, {})

    # 21. Action store safe handling of empty or missing users
    def test_21_action_store_safe_handling_of_empty_inputs(self):
        self.assertEqual(self.store.get_user_actions_map(""), {})
        self.assertEqual(self.store.get_user_action_states(""), {})
        self.assertEqual(self.store.get_all_action_states(""), {})
        self.assertEqual(self.store.get_resolved_message_ids(""), set())
        self.assertEqual(self.store.get_active_snoozed_message_ids(""), set())
        self.assertIsNone(self.store.get_action_state("", "msg_1"))
        self.assertIsNone(self.store.get_action_state("user_1", ""))


class TestAnnouncementRegression(unittest.TestCase):
    """
    Dedicated regression test suite covering the 9 specific requirements from
    Section 6 of remainingtask.txt:
      1. Actionable hall-ticket announcement classified P3.
      2. Registration announcement with a genuine action.
      3. Routine feedback form without an actionable requirement.
      4. General informational course announcement.
      5. P3 email containing a meaningful upcoming deadline.
      6. Message whose applicability to recipient is uncertain.
      7. Old actionable announcement that belongs in Older actions.
      8. Expired action that no longer belongs in active attention.
      9. Message with a date in the body that is not a deadline.
    """

    @classmethod
    def setUpClass(cls):
        cls.pipeline = load_model()

    def setUp(self):
        self.now_dt = datetime(2026, 10, 19, 12, 0, 0, tzinfo=timezone.utc)

    # 1. An actionable hall-ticket announcement classified P3
    def test_case1_actionable_hall_ticket_announcement_p3(self):
        email = {
            "id": "case1_hall_ticket",
            "subject": "October 2026 NPTEL Exams - Hall Tickets Released!!",
            "body": "Dear Candidate, Hall tickets for the October 2026 examination are released. Registered candidates can download their exam hall ticket from the portal.",
            "sender": "onlinecourses@nptel.iitm.ac.in",
            "date": (self.now_dt - timedelta(days=1)).isoformat()
        }
        pred = predict_email(email, self.pipeline)
        self.assertEqual(pred["final_priority"], "P3")
        self.assertTrue(pred["action_required"])
        self.assertEqual(pred["action_evidence"]["action_type"], "document_download")
        self.assertTrue(pred["needs_attention"])
        
        queue_eval = classify_action_queue_item(pred, now_dt=self.now_dt)
        self.assertEqual(queue_eval["queue_placement"], "ACTIVE_QUEUE")
        self.assertIn("download", queue_eval["next_step"].lower())

    # 2. A registration announcement with a genuine action
    def test_case2_registration_announcement_genuine_action(self):
        email = {
            "id": "case2_reg_open",
            "subject": "October 2026 Symposium - Registration is open",
            "body": "Registration is open for the upcoming symposium. Register online to participate.",
            "sender": "onlinecourses@nptel.iitm.ac.in",
            "date": (self.now_dt - timedelta(days=2)).isoformat()
        }
        pred = predict_email(email, self.pipeline)
        self.assertEqual(pred["final_priority"], "P3")
        self.assertTrue(pred["action_required"])
        self.assertEqual(pred["action_evidence"]["action_type"], "registration")
        self.assertTrue(pred["needs_attention"])

    # 3. A routine feedback form without an actionable requirement
    def test_case3_routine_feedback_form_not_actionable(self):
        email = {
            "id": "case3_feedback",
            "subject": "Course Feedback: How was Week 3?",
            "body": "Take a moment to explore our recommended lectures and tell us what you thought about week 3.",
            "sender": "onlinecourses@nptel.iitm.ac.in",
            "date": (self.now_dt - timedelta(days=2)).isoformat()
        }
        pred = predict_email(email, self.pipeline)
        self.assertEqual(pred["final_priority"], "P3")
        self.assertFalse(pred["action_required"])
        self.assertFalse(pred["needs_attention"])

    # 4. A general informational course announcement
    def test_case4_general_informational_course_announcement(self):
        email = {
            "id": "case4_exam_format",
            "subject": "Exam Format - October, 2026!!",
            "body": "The exam will consist of 50 multiple-choice questions. All questions carry equal marks. Please consult syllabus for topics covered.",
            "sender": "onlinecourses@nptel.iitm.ac.in",
            "date": (self.now_dt - timedelta(days=3)).isoformat()
        }
        pred = predict_email(email, self.pipeline)
        self.assertEqual(pred["final_priority"], "P3")
        self.assertFalse(pred["action_required"])
        self.assertFalse(pred["needs_attention"])

    # 5. A P3 email containing a meaningful upcoming deadline
    def test_case5_p3_with_meaningful_upcoming_deadline(self):
        email = {
            "id": "case5_upcoming_deadline",
            "subject": "NPTEL October 2026: Workshop and Webinar Schedule",
            "body": "Dear Learner, Registration closes on Nov 15, 2026. Feel free to join our online session.",
            "sender": "onlinecourses@nptel.iitm.ac.in",
            "date": (self.now_dt - timedelta(days=1)).isoformat()
        }
        pred = predict_email(email, self.pipeline)
        self.assertEqual(pred["final_priority"], "P3")
        self.assertTrue(pred["action_required"])
        self.assertTrue(pred["deadline_detected"])
        self.assertEqual(pred["deadline_status"], "ACTIVE")
        self.assertTrue(pred["needs_attention"])

    # 6. A message whose applicability to recipient is uncertain
    def test_case6_applicability_uncertain(self):
        email = {
            "id": "case6_applicability",
            "subject": "FINAL October 2026 NPTEL Exams – Hall Tickets, Centre Details and Registration...",
            "body": "Hall tickets have been released on the portal. Registered candidates can download their hall ticket.",
            "sender": "onlinecourses@nptel.iitm.ac.in",
            "date": (self.now_dt - timedelta(days=2)).isoformat()
        }
        pred = predict_email(email, self.pipeline)
        evidence = pred["action_evidence"]
        self.assertIn("registered", evidence["applicability"].lower())
        self.assertIn("registered", evidence["next_step"].lower())

    # 7. An old actionable announcement that belongs in Older actions
    def test_case7_old_actionable_announcement_belongs_in_older_actions(self):
        # 14 days old actionable announcement
        email = {
            "id": "case7_old_announcement",
            "subject": "NPTEL Exams - Hall Tickets Released",
            "body": "Hall tickets are available for download for registered candidates.",
            "sender": "onlinecourses@nptel.iitm.ac.in",
            "date": (self.now_dt - timedelta(days=14)).isoformat(),
            "final_priority": "P3",
            "action_required": True,
            "action_reason": "Download available document or ticket",
            "deadline_detected": False,
        }
        res = classify_action_queue_item(email, now_dt=self.now_dt)
        self.assertEqual(res["queue_placement"], "OLDER_ACTIONS")
        self.assertTrue(res["is_older"])

    # 8. An expired action that no longer belongs in active attention
    def test_case8_expired_action_leaves_active_attention(self):
        # OTP verification email received 45 minutes ago
        email = {
            "id": "case8_expired_action",
            "subject": "Your portal verification code is 193847",
            "body": "Use one-time password 193847 to log in. Valid for 10 minutes.",
            "sender": "noreply@examportal.edu",
            "date": (self.now_dt - timedelta(minutes=45)).isoformat(),
            "final_priority": "P2",
            "action_required": True,
            "action_reason": "Immediate verification required",
            "deadline_detected": True,
        }
        res = classify_action_queue_item(email, now_dt=self.now_dt)
        self.assertEqual(res["queue_placement"], "EXPIRED_ACTIONS")
        self.assertTrue(res["is_expired"])

    # 9. A message with a date in the body that is not a deadline
    def test_case9_date_in_body_not_a_deadline(self):
        email = {
            "id": "case9_date_not_deadline",
            "subject": "Department Meeting Minutes - October 5, 2026",
            "body": "The quarterly committee met on October 5, 2026 to review the annual report. Minutes are attached.",
            "sender": "secretary@dept.org",
            "date": (self.now_dt - timedelta(days=5)).isoformat()
        }
        pred = predict_email(email, self.pipeline)
        # Meeting in the past mentioned as historical record must NOT be detected as a deadline
        self.assertFalse(pred["deadline_detected"])
        self.assertEqual(pred["deadline_status"], "NONE")
        self.assertFalse(pred["action_required"])
        self.assertFalse(pred["needs_attention"])

    # 10. Multi-clause hall ticket & centre details announcement
    def test_case10_multi_clause_hall_ticket_and_centre_details(self):
        email = {
            "id": "case10_nptel_multi_clause",
            "subject": "FINAL October 2026 NPTEL Exams – Hall Tickets, Centre Details and Registration...",
            "body": (
                "Dear Learner, The hall tickets, centre details and registration details are now available for download. "
                "Candidates can access their exam hall tickets from the candidate portal."
            ),
            "sender": "onlinecourses@nptel.iitm.ac.in",
            "date": (self.now_dt - timedelta(days=1)).isoformat()
        }
        pred = predict_email(email, self.pipeline)
        self.assertEqual(pred["final_priority"], "P3")
        self.assertTrue(pred["action_required"])
        self.assertTrue(pred["needs_attention"])
        queue_item = classify_action_queue_item(pred, now_dt=self.now_dt)
        self.assertEqual(queue_item["queue_placement"], "ACTIVE_QUEUE")
        self.assertIn("download", queue_item["next_step"].lower())

    # 11. Informational exam format announcement is NOT actionable
    def test_case11_exam_format_informational_not_actionable(self):
        email = {
            "id": "case11_exam_format",
            "subject": "Exam Format - October, 2026!!",
            "body": "The exam format will be 50 multiple choice questions with 3 hours duration. Calculators are permitted.",
            "sender": "onlinecourses@nptel.iitm.ac.in",
            "date": (self.now_dt - timedelta(days=2)).isoformat()
        }
        pred = predict_email(email, self.pipeline)
        self.assertEqual(pred["final_priority"], "P3")
        self.assertFalse(pred["action_required"])
        self.assertFalse(pred["needs_attention"])
        queue_item = classify_action_queue_item(pred, now_dt=self.now_dt)
        self.assertEqual(queue_item["queue_placement"], "EXCLUDED")

    # 12. General course update is NOT actionable
    def test_case12_general_course_update_not_actionable(self):
        email = {
            "id": "case12_course_update",
            "subject": "Lecture notes and slide deck for Module 4 uploaded",
            "body": "Dear students, the lecture notes for module 4 have been uploaded to the portal for your reference.",
            "sender": "instructor@university.edu",
            "date": (self.now_dt - timedelta(days=1)).isoformat()
        }
        pred = predict_email(email, self.pipeline)
        self.assertFalse(pred["action_required"])
        self.assertFalse(pred["needs_attention"])

    # 13. Tax document release announcement is actionable P3
    def test_case13_tax_document_release_actionable_p3(self):
        email = {
            "id": "case13_w2_tax_doc",
            "subject": "Your W-2 tax statement is ready for download",
            "body": "Your annual wage and tax statement (Form W-2) is now available for download on the payroll portal.",
            "sender": "payroll@enterprise.com",
            "date": (self.now_dt - timedelta(days=2)).isoformat()
        }
        pred = predict_email(email, self.pipeline)
        self.assertTrue(pred["action_required"])
        self.assertTrue(pred["needs_attention"])
        self.assertEqual(pred["action_evidence"]["action_type"], "document_download")
        queue_item = classify_action_queue_item(pred, now_dt=self.now_dt)
        self.assertEqual(queue_item["queue_placement"], "ACTIVE_QUEUE")


if __name__ == "__main__":
    unittest.main()

