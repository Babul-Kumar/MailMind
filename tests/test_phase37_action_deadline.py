import os
import json
import pytest
from datetime import datetime
from backend.app.ml.refinement import (
    refine_priority,
    evaluate_action_layer,
    determine_deadline_status,
    extract_deadline
)
from backend.app.ml.predictor import predict_email
from backend.app.core.cache import user_email_cache

class TestPhase37ActionAndDeadlines:
    """
    Tests for Phase 37: Action-Layer Hardening, Account Activation Elevation,
    Multi-State Deadline Presentation, and Needs Attention Safety.
    """

    # =========================================================================
    # 1. ACTION LAYER: ACCOUNT ACTIVATION ELEVATION (P4 -> P2 + Action)
    # =========================================================================
    @pytest.mark.parametrize("subject,body,sender", [
        ("Confirm Your Signup", "Click here to confirm your email and complete your account setup.", "support@supabase.io"),
        ("Please verify your email address", "Welcome to Hugging Face! Please verify your email to activate your account.", "no-reply@huggingface.co"),
        ("Activate your Zoom account", "You've been invited to Zoom. Click below to activate your account.", "no-reply@zoom.us"),
        ("Verify your student status", "Confirm your UNiDAYS account by clicking the verification link.", "help@myunidays.com"),
        ("Complete your registration", "Click the activation link to confirm your admission portal registration.", "admissions@manipal.edu"),
        ("Activate your Writerly subscription", "Confirm your email address to begin using Writerly.", "team@writerly.ai"),
    ])
    def test_account_activation_elevated_to_p2_action(self, subject, body, sender):
        """Account activation emails must elevate to P2 + Action Required with reason 'Account activation required'."""
        email = {
            "email_id": "activation_001",
            "subject": subject,
            "body": body,
            "sender": sender,
            "date": "2026-10-01T12:00:00Z"
        }
        res = predict_email(email)
        assert res["final_priority"] == "P2"
        assert res["action_required"] is True
        assert res["action_reason"] == "Account activation required"
        assert "action_evidence" in res
        assert res["action_evidence"]["imperative"] is True
        assert res["action_evidence"]["action_type"] == "activation"
        assert res["needs_attention"] is True

    # =========================================================================
    # 2. ACTION LAYER: PASSWORD RESET ELEVATION (P2 + Action)
    # =========================================================================
    def test_password_reset_elevated_to_p2_action(self):
        """User-requested password resets must be P2 + Action Required."""
        email = {
            "email_id": "pwd_001",
            "subject": "Reset your Superset password",
            "body": "We received a request to reset your password. Click the link below to set a new password.",
            "sender": "no-reply@superset.apache.org",
            "date": "2026-10-01T14:00:00Z"
        }
        res = predict_email(email)
        assert res["final_priority"] in ("P1", "P2")
        assert res["action_required"] is True
        assert res["action_reason"] == "Account security action"
        assert res["action_evidence"]["action_type"] == "security"
        assert res["needs_attention"] is True

    # =========================================================================
    # 3. ACTION LAYER: SERVICE ACTIONS (P2 + Action)
    # =========================================================================
    @pytest.mark.parametrize("subject,body,sender", [
        ("Your Jira Cloud trial has expired", "Your trial has ended. Action required to prevent workspace deactivation.", "notifications@atlassian.net"),
        ("Inactive project scheduled for deletion", "Your project will be deleted on 2026-10-05 unless you take action.", "support@neon.tech"),
    ])
    def test_service_action_elevated_to_p2_action(self, subject, body, sender):
        """Service action and project deactivation warnings must be P2 + Action Required."""
        email = {
            "email_id": "svc_001",
            "subject": subject,
            "body": body,
            "sender": sender,
            "date": "2026-10-01T08:00:00Z"
        }
        res = predict_email(email)
        assert res["final_priority"] == "P2"
        assert res["action_required"] is True
        assert res["action_reason"] == "Service action required"
        assert res["action_evidence"]["action_type"] == "service"
        assert res["needs_attention"] is True

    # =========================================================================
    # 4. ACTION LAYER: SUBMISSION DEADLINE INDEPENDENCE (P4 stays P4)
    # =========================================================================
    def test_kaggle_submission_stays_p4_action(self):
        """Kaggle competitions have actionable submission deadlines while priority is not elevated by rule."""
        ref = refine_priority(
            subject="Reminder: Google Fast or Slow? AI Speed Up Challenge deadline approaching",
            body="Submissions close on Oct 15, 2026 at 11:59 PM UTC. Make sure your notebook is submitted.",
            sender="noreply@kaggle.com",
            model_priority="P4",
            confidence=0.7,
            email_date="2026-10-01T09:00:00Z"
        )
        assert ref["final_priority"] == "P4"
        assert ref["action_required"] is True
        assert ref["action_reason"] == "Submission deadline"
        assert ref["action_evidence"]["action_type"] == "submission"

    # =========================================================================
    # 5. ACTION LAYER: OPTIONAL ENGAGEMENT FILTERING
    # =========================================================================
    @pytest.mark.parametrize("subject,body,sender", [
        ("Review your monthly summary", "See how you performed this month with personalized stats and insights.", "updates@service.com"),
        ("Explore recommended jobs for you", "Based on your search history, check out these open roles.", "jobs-listings@linkedin.com"),
        ("Discover new courses this week", "Top trending courses on machine learning and cloud architecture.", "recommendations@coursera.org"),
        ("Read our weekly developer digest", "Here are the top trending open-source projects this week.", "digest@github.com"),
        ("Stay connected to Postman", "Catch up on the latest API platform updates and features.", "news@postman.com"),
        ("Check out what you missed", "Highlights from your network this week.", "notifications@twitter.com"),
    ])
    def test_optional_engagement_not_action_required(self, subject, body, sender):
        """Marketing, digests, and soft recommendation CTAs must NOT trigger action_required."""
        email = {
            "email_id": "opt_001",
            "subject": subject,
            "body": body,
            "sender": sender,
            "date": "2026-10-01T12:00:00Z"
        }
        res = predict_email(email)
        assert res["action_required"] is False
        assert res["action_reason"] is None
        assert res["action_evidence"]["operational_consequence"] is False
        assert res["action_evidence"]["action_type"] == "none"

    # =========================================================================
    # 6. MULTI-STATE DEADLINE PRESENTATION (ACTIVE, OVERDUE, EXPIRED, HISTORICAL)
    # =========================================================================
    def test_deadline_status_active(self):
        """Future deadline must be classified as ACTIVE."""
        status = determine_deadline_status(
            "2026-10-15T23:59:00",
            now_dt=datetime(2026, 10, 1, 12, 0, 0),
            is_otp=False
        )
        assert status == "ACTIVE"

    def test_deadline_status_overdue(self):
        """Recent past deadline (<= 30 days) must be classified as OVERDUE."""
        status = determine_deadline_status(
            "2026-09-28T23:59:00",
            now_dt=datetime(2026, 10, 1, 12, 0, 0),
            is_otp=False
        )
        assert status == "OVERDUE"

    def test_deadline_status_expired_otp(self):
        """Short-lived OTP / verification code must be classified as EXPIRED."""
        status = determine_deadline_status(
            "2026-10-01T11:50:00",
            now_dt=datetime(2026, 10, 1, 12, 0, 0),
            is_otp=True
        )
        assert status == "EXPIRED"

    def test_deadline_status_historical(self):
        """Old deadline (> 30 days past) must be classified as HISTORICAL."""
        status = determine_deadline_status(
            "2024-05-15T18:00:00",
            now_dt=datetime(2026, 10, 1, 12, 0, 0),
            is_otp=False
        )
        assert status == "HISTORICAL"

    def test_deadline_status_none(self):
        """No deadline detected must be NONE."""
        status = determine_deadline_status(None)
        assert status == "NONE"

    # =========================================================================
    # 7. NEEDS ATTENTION FORMULA SAFETY
    # =========================================================================
    def test_needs_attention_p1(self):
        """All P1 emails require attention."""
        email = {
            "email_id": "att_p1",
            "subject": "CRITICAL: Production Outage Incident 1042",
            "body": "Database servers are down. Immediate intervention required.",
            "sender": "alerts@pagerduty.com",
            "date": "2026-10-01T12:00:00Z"
        }
        res = predict_email(email)
        assert res["final_priority"] == "P1"
        assert res["needs_attention"] is True

    def test_needs_attention_p2_action(self):
        """P2 emails with action_required require attention."""
        email = {
            "email_id": "att_p2_act",
            "subject": "Confirm your registration",
            "body": "Click here to activate your account and verify your email.",
            "sender": "no-reply@service.com",
            "date": "2026-10-01T12:00:00Z"
        }
        res = predict_email(email)
        assert res["final_priority"] == "P2"
        assert res["action_required"] is True
        assert res["needs_attention"] is True

    def test_needs_attention_action_with_active_deadline(self):
        """Emails with action_required and ACTIVE deadline require attention."""
        email = {
            "email_id": "att_act_dl",
            "subject": "Assignment 3: Submission Deadline",
            "body": "Submit assignment 3 before Oct 10, 2026 at 11:59 PM.",
            "sender": "instructor@university.edu",
            "date": "2026-10-01T12:00:00Z"
        }
        res = predict_email(email)
        assert res["action_required"] is True
        assert res["deadline_status"] == "ACTIVE"
        assert res["needs_attention"] is True

    def test_needs_attention_historical_deadline_alone_does_not_trigger(self):
        """A P4 email with an old historical deadline must NOT trigger Needs Attention."""
        ref = refine_priority(
            subject="Past Kaggle Competition 2023",
            body="Submissions close on Oct 15, 2023 at 11:59 PM.",
            sender="noreply@kaggle.com",
            model_priority="P4",
            confidence=0.6,
            email_date="2023-10-01T12:00:00Z"
        )
        assert ref["final_priority"] == "P4"
        assert ref["deadline_status"] == "HISTORICAL"
        # Needs attention formula check
        needs_att = (
            (ref["final_priority"] == "P1") or
            (ref["final_priority"] == "P2" and ref["action_required"]) or
            (ref["action_required"] and ref["deadline_status"] in ("ACTIVE", "OVERDUE"))
        )
        assert needs_att is False

    # =========================================================================
    # 8. MULTI-USER ISOLATION SAFETY (USER A, USER B, USER C)
    # =========================================================================
    def test_multi_user_isolation_actions_and_deadlines(self):
        """Verify strict isolation across User A, B, and C for action and deadline caching."""
        user_a = "user_iso_a"
        user_b = "user_iso_b"
        user_c = "user_iso_c"

        conn = user_email_cache._get_connection()
        with user_email_cache._lock:
            cur = conn.cursor()
            cur.execute("DELETE FROM user_email_cache WHERE user_id IN (?, ?, ?)", (user_a, user_b, user_c))
            conn.commit()

        try:
            # User A has active deadline
            email_a = {
                "email_id": "same_id_100",
                "thread_id": "th_a",
                "subject": "User A Activation",
                "predicted_priority": "P2",
                "action_required": True,
                "action_reason": "Account activation required",
                "deadline_status": "ACTIVE",
                "needs_attention": True,
                "model_version": "priority-v3"
            }
            # User B has historical deadline
            email_b = {
                "email_id": "same_id_100",
                "thread_id": "th_b",
                "subject": "User B Newsletter",
                "predicted_priority": "P4",
                "action_required": False,
                "action_reason": None,
                "deadline_status": "HISTORICAL",
                "needs_attention": False,
                "model_version": "priority-v3"
            }
            # User C has P1 incident
            email_c = {
                "email_id": "same_id_100",
                "thread_id": "th_c",
                "subject": "User C Security Alert",
                "predicted_priority": "P1",
                "action_required": True,
                "action_reason": "Account security action",
                "deadline_status": "NONE",
                "needs_attention": True,
                "model_version": "priority-v3"
            }

            user_email_cache.store_batch(user_a, [email_a])
            user_email_cache.store_batch(user_b, [email_b])
            user_email_cache.store_batch(user_c, [email_c])

            # Invalidate memory cache to test persistent storage isolation
            with user_email_cache._lock:
                user_email_cache._mem_cache.pop(user_a, None)
                user_email_cache._mem_cache.pop(user_b, None)
                user_email_cache._mem_cache.pop(user_c, None)

            rec_a = user_email_cache.get(user_a, "same_id_100")
            rec_b = user_email_cache.get(user_b, "same_id_100")
            rec_c = user_email_cache.get(user_c, "same_id_100")

            assert rec_a["subject"] == "User A Activation"
            assert rec_a["predicted_priority"] == "P2"
            assert rec_a["action_required"] is True
            assert rec_a["deadline_status"] == "ACTIVE"
            assert rec_a["needs_attention"] is True

            assert rec_b["subject"] == "User B Newsletter"
            assert rec_b["predicted_priority"] == "P4"
            assert rec_b["action_required"] is False
            assert rec_b["deadline_status"] == "HISTORICAL"
            assert rec_b["needs_attention"] is False

            assert rec_c["subject"] == "User C Security Alert"
            assert rec_c["predicted_priority"] == "P1"
            assert rec_c["action_required"] is True
            assert rec_c["deadline_status"] == "NONE"
            assert rec_c["needs_attention"] is True

        finally:
            with user_email_cache._lock:
                cur = conn.cursor()
                cur.execute("DELETE FROM user_email_cache WHERE user_id IN (?, ?, ?)", (user_a, user_b, user_c))
                conn.commit()
                user_email_cache._mem_cache.pop(user_a, None)
                user_email_cache._mem_cache.pop(user_b, None)
                user_email_cache._mem_cache.pop(user_c, None)
