import os
import sys
import json
import hashlib
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.config import BASE_DIR
from backend.app.core.cache import user_email_cache, compute_content_hash
from backend.app.core.session import session_manager, SessionData
from backend.app.ml.predictor import load_model, predict_email
from backend.app.ml.registry import model_registry
from backend.app.gmail.scan_engine import (
    MailboxScanJob,
    ScanJobState,
    discover_mailbox_message_ids,
    fetch_message_metadata_batch
)
from googleapiclient.errors import HttpError


client = TestClient(app)


# =============================================================================
# 1. MODEL REGISTRY AUDIT (34.1, 34.25)
# =============================================================================
class TestModelRegistryAudit:
    def test_registry_contains_v2_and_v3(self):
        reg = model_registry.get_registry()
        assert "priority-v2" in reg["versions"]
        assert "priority-v3" in reg["versions"]
        assert reg["active_model"] == "priority-v3"
        assert reg["previous_model"] in ("priority-v2", "priority-v1")

    def test_v2_artifact_unchanged(self):
        v2_path = os.path.join(BASE_DIR, "dataset", "models", "priority-v2", "model.joblib")
        assert os.path.exists(v2_path)
        with open(v2_path, "rb") as f:
            v2_hash = hashlib.sha256(f.read()).hexdigest()
        assert v2_hash == "be52c2dbfe28001a66b134d1125dfa8d117bbe64206590d71bde9f7029f3cd75"

    def test_v3_artifact_versioned_and_matches_registry(self):
        v3_path = os.path.join(BASE_DIR, "dataset", "models", "priority-v3", "model.joblib")
        assert os.path.exists(v3_path)
        with open(v3_path, "rb") as f:
            v3_hash = hashlib.sha256(f.read()).hexdigest()
        assert v3_hash == "fa69e6a5cfafb8b24c5941dbb8fb08a208addfc4f39e38fa47df0a7cd7040b56"
        reg = model_registry.get_registry()
        assert reg["versions"]["priority-v3"]["artifact_sha256"] == v3_hash

    def test_historical_test_csv_unmodified(self):
        test_path = os.path.join(BASE_DIR, "dataset", "processed", "test.csv")
        with open(test_path, "rb") as f:
            test_sha = hashlib.sha256(f.read()).hexdigest().upper()
        assert test_sha == "6841CD44901FA56242BF3752257E991FD7FF474ED7E0F7A5D2B7065A0827C138"


# =============================================================================
# 2. MODERN EMAIL HOLDOUT INTEGRITY (34.2)
# =============================================================================
class TestModernHoldoutIntegrity:
    @pytest.fixture(autouse=True)
    def load_holdout(self):
        self.holdout_path = os.path.join(BASE_DIR, "dataset-v3", "modern_holdout.csv")
        import pandas as pd
        self.df = pd.read_csv(self.holdout_path)

    def test_holdout_size_and_categories(self):
        assert len(self.df) >= 100, f"Expected >= 100 holdout examples, got {len(self.df)}"
        categories = set(self.df["category"].unique())
        required_cats = {
            "otp_auth", "mfa_auth", "password_reset", "account_verification",
            "security_alerts", "payments", "recruitment", "deadlines",
            "saas", "newsletter_promo", "academic", "routine_informational"
        }
        assert required_cats.issubset(categories), f"Missing categories: {required_cats - categories}"

    def test_holdout_disjoint_from_train_and_historical(self):
        import pandas as pd
        df_tr = pd.read_csv(os.path.join(BASE_DIR, "dataset", "versions", "dataset-v3", "train.csv"))
        df_hist = pd.read_csv(os.path.join(BASE_DIR, "dataset", "processed", "test.csv"))

        mod_texts = set((self.df["subject"].fillna("") + " " + self.df["body"].fillna("")).str.lower().str.strip())
        tr_texts = set((df_tr["subject"].fillna("") + " " + df_tr["body"].fillna("")).str.lower().str.strip())
        hist_texts = set((df_hist["subject"].fillna("") + " " + df_hist["body"].fillna("")).str.lower().str.strip())

        assert len(mod_texts.intersection(tr_texts)) == 0, "Holdout overlaps with dataset-v3 train!"
        assert len(mod_texts.intersection(hist_texts)) == 0, "Holdout overlaps with historical test!"


# =============================================================================
# 3. OTP GENERALIZATION TEST (34.3)
# =============================================================================
class TestOTPGeneralization:
    @pytest.mark.parametrize("case_id,subject,body", [
        ("Case A", "Your Google sign-in code", "Your Google sign-in code is 482913. It expires in 10 minutes."),
        ("Case B", "Identity Verification", "Use 918274 to verify your identity. This code is valid for 5 minutes."),
        ("Case C", "Sign-in Verification", "Enter the verification code below to continue signing in."),
        ("Case D", "Figma One-Time Passcode", "Your one-time passcode will expire shortly."),
        ("Case E", "MFA Code", "Use this MFA code to complete your login."),
        ("Case F", "Password Reset", "Your password reset code is 391827."),
    ])
    def test_unseen_otp_produces_p1_and_action_true(self, case_id, subject, body):
        pipeline = load_model()
        email_data = {
            "email_id": f"unseen_otp_{case_id}",
            "sender": "auth@service.com",
            "subject": subject,
            "body": body,
            "date": "2026-10-01T10:00:00Z"
        }
        res = predict_email(email_data, pipeline=pipeline)
        assert res["final_priority"] == "P1", f"{case_id} failed: got {res['final_priority']}"
        assert res["action_required"] is True, f"{case_id} action_required must be True"


# =============================================================================
# 4. NEGATIVE GENERALIZATION TEST (34.4)
# =============================================================================
class TestNegativeGeneralization:
    @pytest.mark.parametrize("case_id,subject,body", [
        ("Neg 1", "Account Notice", "Your account verification was completed successfully."),
        ("Neg 2", "Security update", "Your security settings were updated."),
        ("Neg 3", "Monthly digest", "Your monthly security report is ready."),
        ("Neg 4", "Profile update", "Your account was verified yesterday."),
        ("Neg 5", "Login confirmation", "Your previous login verification was successful."),
    ])
    def test_informational_security_not_p1_and_no_action(self, case_id, subject, body):
        pipeline = load_model()
        email_data = {
            "email_id": f"neg_{case_id}",
            "sender": "no-reply@service.com",
            "subject": subject,
            "body": body,
            "date": "2026-10-01T10:00:00Z"
        }
        res = predict_email(email_data, pipeline=pipeline)
        assert res["final_priority"] != "P1", f"{case_id} should NOT be P1, got {res['final_priority']}"
        assert res["action_required"] is False, f"{case_id} should not require action"


# =============================================================================
# 5. EXACT OBSERVED TCS EMAIL REGRESSION (34.22)
# =============================================================================
class TestExactTCSOTPRegression:
    def test_exact_tcs_email_regression(self):
        tcs_email = {
            "email_id": "real_tcs_nextstep_01",
            "sender": "Tata Consultancy Services <careers@tcs.com>",
            "subject": "TCS NextStep: Login Email ID Verification",
            "body": "Dear Candidate Your One Time Password (OTP) for login: 6329871. OTP is valid only for 05:00 mins. Do not share this OTP with anyone. Please note that the OTP is valid for only one session. If you try",
            "date": "2026-10-01T10:00:00Z"
        }
        pipeline = load_model()
        res = predict_email(tcs_email, pipeline=pipeline)
        assert res["final_priority"] == "P1"
        assert res["action_required"] is True
        assert res["action_reason"] == "Immediate verification required"
        assert "OTP expiry" in str(res["deadline_display"])
        assert res["needs_attention"] is True
        assert res["confidence"] >= 0.75
        assert res["model_version"] == "priority-v3"


# =============================================================================
# 6. COMPLETE GMAIL MAILBOX DISCOVERY & SCOPE (34.9, 34.10)
# =============================================================================
class TestCompleteMailboxDiscovery:
    def test_mailbox_scope_does_not_restrict_to_inbox(self):
        mock_svc = MagicMock()
        mock_list = mock_svc.users().messages().list
        mock_list.return_value.execute.return_value = {
            "messages": [{"id": f"msg_{i}"} for i in range(10)],
            "nextPageToken": None
        }

        ids = discover_mailbox_message_ids(mock_svc, scope="mailbox")
        assert len(ids) == 10

        call_kwargs = mock_list.call_args[1]
        assert "labelIds" not in call_kwargs, "scope='mailbox' must NOT restrict to labelIds"
        assert call_kwargs["maxResults"] == 500

    def test_label_scope_includes_label_ids(self):
        mock_svc = MagicMock()
        mock_list = mock_svc.users().messages().list
        mock_list.return_value.execute.return_value = {
            "messages": [{"id": "inbox_msg_1"}],
            "nextPageToken": None
        }

        ids = discover_mailbox_message_ids(mock_svc, scope="label", label_ids=["INBOX"])
        assert len(ids) == 1
        call_kwargs = mock_list.call_args[1]
        assert call_kwargs["labelIds"] == ["INBOX"]

    def test_discovery_pagination_across_pages(self):
        mock_svc = MagicMock()
        mock_svc.users().messages().list.return_value.execute.side_effect = [
            {"messages": [{"id": "m1"}, {"id": "m2"}], "nextPageToken": "token_page_2"},
            {"messages": [{"id": "m3"}, {"id": "m4"}], "nextPageToken": None}
        ]

        ids, stats = discover_mailbox_message_ids(mock_svc, scope="mailbox", return_stats=True)
        assert len(ids) == 4
        assert stats["pages_scanned"] == 2
        assert stats["api_calls"] == 2


# =============================================================================
# 7. INCREMENTAL SYNC & CACHE INTEGRITY (34.15, 34.16, 34.17)
# =============================================================================
class TestIncrementalScanAndCache:
    def setup_method(self):
        self.user_id = "test_user_phase34_inc"
        user_email_cache.clear_user(self.user_id)

    def teardown_method(self):
        user_email_cache.clear_user(self.user_id)

    def test_incremental_scan_skips_cached_emails(self):
        # Pre-seed 3 emails in cache
        user_email_cache.store_batch(self.user_id, [
            {"email_id": "msg_01", "subject": "Existing 1", "body": "Body 1", "predicted_priority": "P4", "model_version": "priority-v3"},
            {"email_id": "msg_02", "subject": "Existing 2", "body": "Body 2", "predicted_priority": "P3", "model_version": "priority-v3"},
            {"email_id": "msg_03", "subject": "Existing 3", "body": "Body 3", "predicted_priority": "P2", "model_version": "priority-v3"}
        ])

        mock_svc = MagicMock()
        mock_svc.users().messages().list.return_value.execute.return_value = {
            "messages": [{"id": "msg_01"}, {"id": "msg_02"}, {"id": "msg_03"}, {"id": "msg_04"}],
            "nextPageToken": None
        }

        def mock_batch(*args, **kwargs):
            return [{
                "email_id": "msg_04",
                "subject": "New OTP",
                "body": "Your sign-in code is 581920. Expires in 5 minutes.",
                "date": "2026-10-01T12:00:00Z"
            }], [], 1, 0

        with patch("backend.app.gmail.scan_engine.fetch_message_metadata_batch", side_effect=mock_batch):
            job = MailboxScanJob(user_id=self.user_id, service=mock_svc, mode="incremental")
            state = job.execute()

            assert state["status"] == ScanJobState.COMPLETE
            assert state["discovered"] == 4
            assert state["cached"] == 3
            assert state["newly_analyzed"] == 1
            assert state["cache_hit_rate"] == 75.0

    def test_content_change_triggers_reanalysis(self):
        old_hash = compute_content_hash("Invoice", "Snippet", "Old body")
        user_email_cache.store_batch(self.user_id, [{
            "email_id": "msg_content_test",
            "subject": "Invoice",
            "body": "Old body",
            "content_hash": old_hash,
            "predicted_priority": "P3",
            "model_version": "priority-v3"
        }])

        mock_svc = MagicMock()
        mock_svc.users().messages().list.return_value.execute.return_value = {
            "messages": [{"id": "msg_content_test"}],
            "nextPageToken": None
        }

        new_hash = compute_content_hash("Invoice Overdue", "Snippet", "Payment overdue. Immediate action required.")
        def mock_batch(*args, **kwargs):
            return [{
                "email_id": "msg_content_test",
                "subject": "Invoice Overdue",
                "body": "Payment overdue. Immediate action required.",
                "content_hash": new_hash,
                "date": "2026-10-01T12:00:00Z"
            }], [], 1, 0

        with patch("backend.app.gmail.scan_engine.fetch_message_metadata_batch", side_effect=mock_batch):
            job = MailboxScanJob(user_id=self.user_id, service=mock_svc, force_rescan=True)
            state = job.execute()

            assert state["status"] == ScanJobState.COMPLETE
            assert state["newly_analyzed"] == 1
            updated = user_email_cache.get(self.user_id, "msg_content_test")
            assert updated["content_hash"] == new_hash
            assert updated["final_priority"] == "P1"

    def test_v2_cache_recognized_as_stale_when_v3_active(self):
        user_email_cache.store_batch(self.user_id, [{
            "email_id": "v2_classified_email",
            "subject": "Verification",
            "body": "Code is 123456",
            "predicted_priority": "P2",
            "model_version": "priority-v2"
        }])

        cached_map, missing = user_email_cache.get_batch(
            user_id=self.user_id,
            message_ids=["v2_classified_email"],
            active_model_version="priority-v3"
        )
        assert "v2_classified_email" not in cached_map
        assert "v2_classified_email" in missing


# =============================================================================
# 8. MULTI-USER ISOLATION (34.18)
# =============================================================================
class TestMultiUserFullScanIsolation:
    def setup_method(self):
        self.user_a = "user_iso_a"
        self.user_b = "user_iso_b"
        self.user_c = "user_iso_c"
        for u in [self.user_a, self.user_b, self.user_c]:
            user_email_cache.clear_user(u)

    def teardown_method(self):
        for u in [self.user_a, self.user_b, self.user_c]:
            user_email_cache.clear_user(u)

    def test_concurrent_scans_three_users_strict_isolation(self):
        svc_a = MagicMock()
        svc_a.users().messages().list.return_value.execute.return_value = {
            "messages": [{"id": f"a_{i}"} for i in range(10)], "nextPageToken": None
        }

        svc_b = MagicMock()
        svc_b.users().messages().list.return_value.execute.return_value = {
            "messages": [{"id": f"b_{i}"} for i in range(25)], "nextPageToken": None
        }

        svc_c = MagicMock()
        svc_c.users().messages().list.return_value.execute.return_value = {
            "messages": [{"id": f"c_{i}"} for i in range(50)], "nextPageToken": None
        }

        def fake_fetch(service, message_ids, **kwargs):
            return [
                {
                    "email_id": mid,
                    "subject": f"Subject for {mid}",
                    "body": f"Body for {mid}",
                    "date": "2026-10-01T10:00:00Z"
                } for mid in message_ids
            ], [], 1, 0

        with patch("backend.app.gmail.scan_engine.fetch_message_metadata_batch", side_effect=fake_fetch):
            job_a = MailboxScanJob(self.user_a, svc_a)
            job_b = MailboxScanJob(self.user_b, svc_b)
            job_c = MailboxScanJob(self.user_c, svc_c)

            res_a = job_a.execute()
            res_b = job_b.execute()
            res_c = job_c.execute()

            assert res_a["discovered"] == 10
            assert res_b["discovered"] == 25
            assert res_c["discovered"] == 50

            cached_a = user_email_cache.get_all_cached_ids(self.user_a)
            cached_b = user_email_cache.get_all_cached_ids(self.user_b)
            cached_c = user_email_cache.get_all_cached_ids(self.user_c)

            assert len(cached_a) == 10
            assert len(cached_b) == 25
            assert len(cached_c) == 50
            assert cached_a.isdisjoint(cached_b)
            assert cached_b.isdisjoint(cached_c)
            assert cached_a.isdisjoint(cached_c)


# =============================================================================
# 9. FAILURE RECOVERY & RESILIENCE (34.19, 34.20)
# =============================================================================
class TestScanFailureRecovery:
    def test_transient_http_429_retry_with_backoff(self):
        mock_svc = MagicMock()
        err_resp = MagicMock()
        err_resp.status = 429
        mock_http_err = HttpError(err_resp, b"Rate limit exceeded")

        mock_svc.users().messages().list.return_value.execute.side_effect = [
            mock_http_err,
            mock_http_err,
            {"messages": [{"id": "m1"}], "nextPageToken": None}
        ]

        with patch("time.sleep", return_value=None):
            ids, stats = discover_mailbox_message_ids(mock_svc, scope="mailbox", return_stats=True)
            assert len(ids) == 1
            assert stats["retry_count"] == 2

    def test_malformed_email_skipped_without_halting_batch(self):
        mock_svc = MagicMock()
        mock_svc.users().messages().list.return_value.execute.return_value = {
            "messages": [{"id": "corrupt_1"}, {"id": "valid_2"}],
            "nextPageToken": None
        }

        def mock_fetch(*args, **kwargs):
            return [
                {"email_id": "corrupt_1"},  # missing subject/body
                {"email_id": "valid_2", "subject": "Valid Subject", "body": "Valid Body", "date": "2026-10-01T10:00:00Z"}
            ], [], 1, 0

        user_id = "test_user_malformed"
        user_email_cache.clear_user(user_id)

        with patch("backend.app.gmail.scan_engine.fetch_message_metadata_batch", side_effect=mock_fetch):
            job = MailboxScanJob(user_id=user_id, service=mock_svc)
            state = job.execute()

            assert state["status"] == ScanJobState.COMPLETE
            assert state["failed"] == 1
            assert state["newly_analyzed"] == 1
            assert user_email_cache.get(user_id, "valid_2") is not None
            assert user_email_cache.get(user_id, "corrupt_1") is None
        user_email_cache.clear_user(user_id)


# =============================================================================
# 10. SECURITY REGRESSION (34.24)
# =============================================================================
class TestSecurityRegression:
    def test_unauthenticated_scan_status_returns_401(self):
        res = client.get("/api/scan/status")
        assert res.status_code == 401

    def test_unauthenticated_scan_start_returns_401(self):
        res = client.post("/api/scan/start")
        assert res.status_code == 401

    def test_unauthenticated_scan_rescan_returns_401(self):
        res = client.post("/api/scan/rescan")
        assert res.status_code == 401

    def test_unauthenticated_emails_endpoint_returns_401(self):
        res = client.get("/api/emails")
        assert res.status_code == 401
