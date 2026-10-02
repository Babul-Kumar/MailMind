import os
import json
import hashlib
import pandas as pd
import pytest
import joblib
from backend.app.core.config import BASE_DIR
from backend.app.ml.registry import ModelRegistry, compute_sha256
from backend.app.ml.predictor import load_model, predict_email, invalidate_cached_pipeline

HISTORICAL_HOLDOUT_SHA256 = "6841CD44901FA56242BF3752257E991FD7FF474ED7E0F7A5D2B7065A0827C138"
V3_ARTIFACT_SHA256 = "fa69e6a5cfafb8b24c5941dbb8fb08a208addfc4f39e38fa47df0a7cd7040b56"


class TestDatasetV4Integrity:
    """Verifies dataset-v4 files, structure, and absence of data leakage."""

    def test_dataset_v4_files_exist(self):
        v4_dir = os.path.join(BASE_DIR, "dataset-v4")
        assert os.path.exists(os.path.join(v4_dir, "train.csv")), "train.csv missing in dataset-v4"
        assert os.path.exists(os.path.join(v4_dir, "validation.csv")), "validation.csv missing in dataset-v4"
        assert os.path.exists(os.path.join(v4_dir, "test.csv")), "test.csv missing in dataset-v4"
        assert os.path.exists(os.path.join(v4_dir, "newsletter_holdout.csv")), "newsletter_holdout.csv missing in dataset-v4"
        assert os.path.exists(os.path.join(v4_dir, "social_holdout.csv")), "social_holdout.csv missing in dataset-v4"
        assert os.path.exists(os.path.join(v4_dir, "metadata.json")), "metadata.json missing in dataset-v4"
        assert os.path.exists(os.path.join(v4_dir, "review_candidates.csv")), "review_candidates.csv missing in dataset-v4"

    def test_historical_holdout_invariant(self):
        hist_path = os.path.join(BASE_DIR, "dataset", "processed", "test.csv")
        current_sha = compute_sha256(hist_path).upper()
        assert current_sha == HISTORICAL_HOLDOUT_SHA256, "Historical holdout test.csv hash must never be modified!"

    def test_zero_leakage_between_splits(self):
        v4_dir = os.path.join(BASE_DIR, "dataset-v4")
        df_train = pd.read_csv(os.path.join(v4_dir, "train.csv"))
        df_val = pd.read_csv(os.path.join(v4_dir, "validation.csv"))
        df_test = pd.read_csv(os.path.join(v4_dir, "test.csv"))
        df_nl = pd.read_csv(os.path.join(v4_dir, "newsletter_holdout.csv"))
        df_soc = pd.read_csv(os.path.join(v4_dir, "social_holdout.csv"))
        df_hist = pd.read_csv(os.path.join(BASE_DIR, "dataset", "processed", "test.csv"))

        def get_hashes(df):
            return set(
                hashlib.sha256(f"{str(s).strip().lower()}|{str(b).strip().lower()}".encode()).hexdigest()
                for s, b in zip(df["subject"].fillna(""), df["body"].fillna(""))
            )

        h_train = get_hashes(df_train)
        h_val = get_hashes(df_val)
        h_test = get_hashes(df_test)
        h_nl = get_hashes(df_nl)
        h_soc = get_hashes(df_soc)
        h_hist = get_hashes(df_hist)

        assert len(h_train.intersection(h_val)) == 0, "Leakage detected between train and val"
        assert len(h_train.intersection(h_test)) == 0, "Leakage detected between train and v4 test"
        assert len(h_train.intersection(h_nl)) == 0, "Leakage detected between train and newsletter holdout"
        assert len(h_train.intersection(h_soc)) == 0, "Leakage detected between train and social holdout"
        assert len(h_train.intersection(h_hist)) == 0, "Leakage detected between train and historical test.csv"


class TestModelRegistryV4Candidate:
    """Verifies registry configuration, candidate status, and active model preservation."""

    def test_registry_active_and_candidate_versions(self):
        reg = ModelRegistry()
        data = reg.get_registry()

        assert data["active_model"] in ("priority-v3", "priority-v4.1"), "active model must be priority-v3 or priority-v4.1"
        assert "priority-v4" in data["versions"], "priority-v4 must be versioned in registry"
        assert data["versions"]["priority-v4"]["status"] == "candidate", "priority-v4 must have status 'candidate'"
        assert data["versions"]["priority-v3"]["status"] in ("production", "retired")

    def test_priority_v3_artifact_integrity(self):
        v3_path = os.path.join(BASE_DIR, "dataset", "models", "priority-v3", "model.joblib")
        assert os.path.exists(v3_path), "priority-v3 artifact missing"
        assert compute_sha256(v3_path).lower() == V3_ARTIFACT_SHA256, "priority-v3 weights altered!"

    def test_v3_and_v4_coexistence(self):
        v3_path = os.path.join(BASE_DIR, "dataset", "models", "priority-v3", "model.joblib")
        v4_path = os.path.join(BASE_DIR, "dataset", "models", "priority-v4", "model.joblib")

        pipe_v3 = joblib.load(v3_path)
        pipe_v4 = joblib.load(v4_path)

        assert hasattr(pipe_v3, "predict"), "v3 pipeline must have predict method"
        assert hasattr(pipe_v4, "predict"), "v4 pipeline must have predict method"

        # Test prediction on a sample
        sample_text = ["Your GitHub security verification code is 123456. Valid for 5 minutes."]
        pred_v3 = pipe_v3.predict(sample_text)[0]
        pred_v4 = pipe_v4.predict(sample_text)[0]

        assert pred_v3 == "P1", "v3 must predict P1 for verification code"
        assert pred_v4 == "P1", "v4 must predict P1 for verification code"

    def test_model_rollback_contract(self):
        reg = ModelRegistry()
        data = reg.get_registry()
        # Verify rollback capability without permanently mutating active model
        prev_model = data.get("previous_model")
        assert prev_model in ("priority-v1", "priority-v2", "priority-v3"), "Valid previous model must be stored for rollback"


class TestHoldoutBenchmarksV4:
    """Verifies that candidate priority-v4 satisfies core quality objectives on unseen holdouts."""

    def test_v4_reduces_routine_newsletter_p2_errors(self):
        nl_path = os.path.join(BASE_DIR, "dataset-v4", "newsletter_holdout.csv")
        df_nl = pd.read_csv(nl_path)

        v3_path = os.path.join(BASE_DIR, "dataset", "models", "priority-v3", "model.joblib")
        v4_path = os.path.join(BASE_DIR, "dataset", "models", "priority-v4", "model.joblib")
        pipe_v3 = joblib.load(v3_path)
        pipe_v4 = joblib.load(v4_path)

        X = (df_nl["subject"].fillna("") + " " + df_nl["body"].fillna("")).tolist()
        y = df_nl["final_label"].tolist()

        preds_v3 = pipe_v3.predict(X)
        preds_v4 = pipe_v4.predict(X)

        routine_mask = [label in ("P3", "P4") for label in y]
        v3_p2_errors = sum(1 for p, r in zip(preds_v3, routine_mask) if r and p == "P2")
        v4_p2_errors = sum(1 for p, r in zip(preds_v4, routine_mask) if r and p == "P2")
        total_routine = sum(1 for r in routine_mask if r)

        v3_err_pct = v3_p2_errors / total_routine
        v4_err_pct = v4_p2_errors / total_routine

        assert v4_err_pct < 0.10, f"v4 routine newsletter P2 error rate ({v4_err_pct:.2%}) must be < 10%"
        assert v4_err_pct < v3_err_pct, "v4 must significantly reduce newsletter P2 error rate compared to v3"

    def test_v4_preserves_social_security_recall(self):
        soc_path = os.path.join(BASE_DIR, "dataset-v4", "social_holdout.csv")
        df_soc = pd.read_csv(soc_path)

        v4_path = os.path.join(BASE_DIR, "dataset", "models", "priority-v4", "model.joblib")
        pipe_v4 = joblib.load(v4_path)

        X = (df_soc["subject"].fillna("") + " " + df_soc["body"].fillna("")).tolist()
        y = df_soc["final_label"].tolist()
        preds_v4 = pipe_v4.predict(X)

        sec_mask = [label in ("P1", "P2") for label in y]
        total_sec = sum(1 for s in sec_mask if s)
        if total_sec > 0:
            sec_correct = sum(1 for p, s in zip(preds_v4, sec_mask) if s and p in ("P1", "P2"))
            recall = sec_correct / total_sec
            assert recall >= 0.85, f"v4 security event recall on social ({recall:.2%}) must be >= 85%"


class TestProductionAPIBehavioralRegressions:
    """Verifies that production inference API with active priority-v3 maintains 100% regression fidelity."""

    def test_tcs_otp_verification_regression(self):
        tcs_email = {
            "email_id": "test_tcs_otp_phase39",
            "subject": "TCS NextStep: Login Email ID Verification",
            "snippet": "Dear Candidate Your One Time Password (OTP) for login: 6329871. OTP is valid only for 05:00 mins.",
            "body": "Dear Candidate Your One Time Password (OTP) for login: 6329871. OTP is valid only for 05:00 mins. Do not share this OTP with anyone.",
            "sender": "careers@tcs.com",
            "date": "Fri, 02 Oct 2026 12:00:00 +0000"
        }
        res = predict_email(tcs_email)
        assert res["predicted_priority"] == "P1"
        assert res["action_required"] is True
        assert res["deadline_detected"] is True
        assert res["needs_attention"] is True
        assert "login" in res["action_reason"].lower() or "verification" in res["action_reason"].lower()

    def test_account_activation_elevation_regression(self):
        act_email = {
            "email_id": "test_activation_phase39",
            "subject": "Activate your account - Supabase",
            "snippet": "Confirm your email address to activate your account and start building.",
            "body": "Welcome to Supabase! Please confirm your email address by clicking the link below. Your token expires soon.",
            "sender": "no-reply@supabase.io",
            "date": "Fri, 02 Oct 2026 12:00:00 +0000"
        }
        res = predict_email(act_email)
        assert res["predicted_priority"] == "P2"
        assert res["action_required"] is True
        assert "activation" in (res["action_reason"] or "").lower()

    def test_security_alert_regression(self):
        sec_email = {
            "email_id": "test_sec_alert_phase39",
            "subject": "Security Alert: Unauthorized sign-in attempt detected",
            "snippet": "We blocked an unrecognized sign-in attempt from Russia.",
            "body": "Security alert: suspicious login detected on your account. Review your recent security activity immediately.",
            "sender": "security@google.com",
            "date": "Fri, 02 Oct 2026 12:00:00 +0000"
        }
        res = predict_email(sec_email)
        assert res["predicted_priority"] == "P1"

    def test_historical_deadline_safety_regression(self):
        hist_dl_email = {
            "email_id": "test_hist_dl_phase39",
            "subject": "Save 50% on annual subscription - sale ended May 2024",
            "snippet": "Our spring offer expired on May 15, 2024.",
            "body": "This promotion was valid until May 15, 2024. Thank you for subscribing.",
            "sender": "marketing@coursera.org",
            "date": "Mon, 10 May 2024 12:00:00 +0000"
        }
        res = predict_email(hist_dl_email)
        assert res.get("deadline_status") == "HISTORICAL"
        assert res["needs_attention"] is False
