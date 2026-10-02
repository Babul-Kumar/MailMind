import os
import json
import hashlib
import pandas as pd
import pytest
import joblib
from backend.app.core.config import BASE_DIR
from backend.app.ml.registry import ModelRegistry, compute_sha256
from backend.app.ml.predictor import predict_email

HISTORICAL_HOLDOUT_SHA256 = "6841CD44901FA56242BF3752257E991FD7FF474ED7E0F7A5D2B7065A0827C138"
V3_ARTIFACT_SHA256 = "fa69e6a5cfafb8b24c5941dbb8fb08a208addfc4f39e38fa47df0a7cd7040b56"
V4_ARTIFACT_SHA256 = "cf814f01534910aac67d2db2b72b8a410c876d37d29bf56da8422205807307fc"


class TestDatasetV41Integrity:
    """Verifies dataset-v4.1 files, structure, and absence of data leakage across holdouts."""

    def test_dataset_v4_1_files_exist(self):
        v4_1_dir = os.path.join(BASE_DIR, "dataset-v4.1")
        assert os.path.exists(os.path.join(v4_1_dir, "train.csv")), "train.csv missing in dataset-v4.1"
        assert os.path.exists(os.path.join(v4_1_dir, "validation.csv")), "validation.csv missing in dataset-v4.1"
        assert os.path.exists(os.path.join(v4_1_dir, "test.csv")), "test.csv missing in dataset-v4.1"
        assert os.path.exists(os.path.join(v4_1_dir, "metadata.json")), "metadata.json missing in dataset-v4.1"
        assert os.path.exists(os.path.join(v4_1_dir, "boundary_review.csv")), "boundary_review.csv missing in dataset-v4.1"
        assert os.path.exists(os.path.join(BASE_DIR, "dataset-v4", "boundary_review.csv")), "boundary_review.csv missing in dataset-v4"

    def test_historical_holdout_invariant(self):
        hist_path = os.path.join(BASE_DIR, "dataset", "processed", "test.csv")
        current_sha = compute_sha256(hist_path).upper()
        assert current_sha == HISTORICAL_HOLDOUT_SHA256, "Historical holdout test.csv hash must never be modified!"

    def test_zero_leakage_between_splits_and_holdouts(self):
        v4_1_dir = os.path.join(BASE_DIR, "dataset-v4.1")
        df_train = pd.read_csv(os.path.join(v4_1_dir, "train.csv"))
        df_val = pd.read_csv(os.path.join(v4_1_dir, "validation.csv"))
        df_test = pd.read_csv(os.path.join(v4_1_dir, "test.csv"))
        df_hist = pd.read_csv(os.path.join(BASE_DIR, "dataset", "processed", "test.csv"))
        df_modern = pd.read_csv(os.path.join(BASE_DIR, "dataset-v3", "modern_holdout.csv"))
        df_nl = pd.read_csv(os.path.join(BASE_DIR, "dataset-v4", "newsletter_holdout.csv"))
        df_soc = pd.read_csv(os.path.join(BASE_DIR, "dataset-v4", "social_holdout.csv"))

        def get_hashes(df):
            return set(
                hashlib.sha256(f"{str(s).strip().lower()}|{str(b).strip().lower()}".encode()).hexdigest()
                for s, b in zip(df["subject"].fillna(""), df["body"].fillna(""))
            )

        h_train = get_hashes(df_train)
        h_val = get_hashes(df_val)
        h_test = get_hashes(df_test)
        h_hist = get_hashes(df_hist)
        h_modern = get_hashes(df_modern)
        h_nl = get_hashes(df_nl)
        h_soc = get_hashes(df_soc)

        assert len(h_train.intersection(h_val)) == 0, "Leakage detected between train and val"
        assert len(h_train.intersection(h_test)) == 0, "Leakage detected between train and test"
        assert len(h_train.intersection(h_hist)) == 0, "Leakage detected into Historical holdout"
        assert len(h_train.intersection(h_modern)) == 0, "Leakage detected into Modern holdout"
        assert len(h_train.intersection(h_nl)) == 0, "Leakage detected into Newsletter holdout"
        assert len(h_train.intersection(h_soc)) == 0, "Leakage detected into Social holdout"


class TestModelRegistryV41Coexistence:
    """Verifies registry configuration, coexistence of v3, v4, v4.1, and rollback contract."""

    def test_registry_active_and_candidate_versions(self):
        reg = ModelRegistry()
        data = reg.get_registry()

        assert data["active_model"] in ("priority-v3", "priority-v4.1"), "active model must be priority-v3 or priority-v4.1"
        assert "priority-v4" in data["versions"], "priority-v4 must be registered"
        assert "priority-v4.1" in data["versions"], "priority-v4.1 must be registered"
        assert data["versions"]["priority-v3"]["status"] in ("production", "retired")
        assert data["versions"]["priority-v4"]["status"] == "candidate"
        assert data["versions"]["priority-v4.1"]["status"] in ("candidate", "production")

    def test_artifact_hashes_and_coexistence(self):
        v3_path = os.path.join(BASE_DIR, "dataset", "models", "priority-v3", "model.joblib")
        v4_path = os.path.join(BASE_DIR, "dataset", "models", "priority-v4", "model.joblib")
        v4_1_path = os.path.join(BASE_DIR, "dataset", "models", "priority-v4.1", "model.joblib")

        assert compute_sha256(v3_path).lower() == V3_ARTIFACT_SHA256, "priority-v3 artifact altered!"
        assert compute_sha256(v4_path).lower() == V4_ARTIFACT_SHA256, "priority-v4 artifact altered!"
        assert os.path.exists(v4_1_path), "priority-v4.1 artifact missing!"

        pipe_v3 = joblib.load(v3_path)
        pipe_v4 = joblib.load(v4_path)
        pipe_v4_1 = joblib.load(v4_1_path)

        assert hasattr(pipe_v3, "predict")
        assert hasattr(pipe_v4, "predict")
        assert hasattr(pipe_v4_1, "predict")

        # Test on shared authentication sample
        text = ["Your Google verification code is 492019. Valid for 10 minutes."]
        assert pipe_v3.predict(text)[0] == "P1"
        assert pipe_v4.predict(text)[0] == "P1"
        assert pipe_v4_1.predict(text)[0] == "P1"


class TestV41BehavioralRegressions:
    """Verifies exact behavioral regression fixtures across key communication types on v4.1."""

    @pytest.fixture(autouse=True)
    def setup_model(self):
        v4_1_path = os.path.join(BASE_DIR, "dataset", "models", "priority-v4.1", "model.joblib")
        self.model = joblib.load(v4_1_path)

    def test_tcs_otp_classification(self):
        email_text = "TCS iON: Your OTP for login is 948102. Valid for 10 minutes. Do not share your one-time verification password with anyone."
        pred = self.model.predict([email_text])[0]
        assert pred == "P1"

    def test_security_alert(self):
        email_text = "Google Security Alert: Unrecognized login detected from Linux device in Amsterdam, Netherlands. Review account activity."
        pred = self.model.predict([email_text])[0]
        assert pred == "P1"

    def test_account_activation(self):
        email_text = "Supabase: Confirm your email address to activate your developer account. Click the verification link to proceed."
        pred = self.model.predict([email_text])[0]
        assert pred == "P2"

    def test_payment_failure(self):
        email_text = "Stripe Billing: Payment failed for monthly cloud database cluster. Update credit card immediately to prevent suspension."
        pred = self.model.predict([email_text])[0]
        assert pred == "P2"

    def test_application_deadline(self):
        email_text = "NeurIPS 2026: Paper camera-ready submission deadline is October 22 at 23:59 UTC. Late submissions cannot be published."
        pred = self.model.predict([email_text])[0]
        assert pred == "P2"

    def test_academic_homework(self):
        email_text = "CS182: Homework 4 due Friday at 11:59 PM. Please submit your completed Python notebook to Gradescope."
        pred = self.model.predict([email_text])[0]
        assert pred == "P2"

    def test_routine_newsletter(self):
        email_text = "The Batch: Weekly AI insights by Andrew Ng. New papers in sparse autoencoders and deep learning frameworks."
        pred = self.model.predict([email_text])[0]
        assert pred in ("P3", "P4")

    def test_routine_social(self):
        email_text = "LinkedIn: Alice Smith and 4 others viewed your profile this week. Connect with colleagues in your network."
        pred = self.model.predict([email_text])[0]
        assert pred in ("P3", "P4")


class TestHoldoutRecoveryAndBenchmarking:
    """Verifies that v4.1 recovers modern P2 recall while maintaining holdout accuracy and newsletter de-escalation."""

    @pytest.fixture(autouse=True)
    def setup_model(self):
        v4_1_path = os.path.join(BASE_DIR, "dataset", "models", "priority-v4.1", "model.joblib")
        self.model = joblib.load(v4_1_path)

    def test_modern_holdout_p2_recall_recovery(self):
        df_modern = pd.read_csv(os.path.join(BASE_DIR, "dataset-v3", "modern_holdout.csv"))
        modern_p2 = df_modern[df_modern['final_label'] == 'P2']
        texts = (modern_p2['subject'].fillna('') + ' ' + modern_p2['body'].fillna('')).tolist()
        preds = self.model.predict(texts)
        p2_recall = (preds == 'P2').mean()
        assert p2_recall >= 0.90, f"Expected modern P2 recall >= 90%, got {p2_recall:.2%}"

    def test_newsletter_routine_p2_error_low(self):
        df_nl = pd.read_csv(os.path.join(BASE_DIR, "dataset-v4", "newsletter_holdout.csv"))
        routine_nl = df_nl[df_nl['final_label'].isin(['P3', 'P4'])]
        texts = (routine_nl['subject'].fillna('') + ' ' + routine_nl['body'].fillna('')).tolist()
        preds = self.model.predict(texts)
        p2_error_rate = (preds == 'P2').mean()
        assert p2_error_rate <= 0.05, f"Expected newsletter P2 error rate <= 5%, got {p2_error_rate:.2%}"

    def test_social_routine_p2_error_zero(self):
        df_soc = pd.read_csv(os.path.join(BASE_DIR, "dataset-v4", "social_holdout.csv"))
        routine_soc = df_soc[df_soc['final_label'].isin(['P3', 'P4'])]
        texts = (routine_soc['subject'].fillna('') + ' ' + routine_soc['body'].fillna('')).tolist()
        preds = self.model.predict(texts)
        p2_error_rate = (preds == 'P2').mean()
        assert p2_error_rate <= 0.05, f"Expected social P2 error rate <= 5%, got {p2_error_rate:.2%}"

    def test_historical_holdout_accuracy(self):
        df_hist = pd.read_csv(os.path.join(BASE_DIR, "dataset", "processed", "test.csv"))
        texts = (df_hist['subject'].fillna('') + ' ' + df_hist['body'].fillna('')).tolist()
        preds = self.model.predict(texts)
        acc = (preds == df_hist['final_label']).mean()
        assert acc >= 0.80, f"Expected historical holdout accuracy >= 80%, got {acc:.2%}"
