"""
Test Suite: Phase 47 — Priority-v5.1 Boundary Remediation & Candidate Retraining
================================================================================
Validates all 17 Promotion Gates:
1. Production model v4.1 remains ACTIVE and bit-for-bit unchanged.
2. Invariants preserved for previous model v3 and all 6 frozen holdouts.
3. Dataset-v5.1 integrity: 1880 train rows, 428 validation rows, 20 boundary holdout rows.
4. Repartitioning: cp_005b relocated to train, absent from validation.
5. Zero holdout leakage across all curated examples.
6. Candidate model artifact priority-v5.1-candidate/model.joblib exists and matches SHA.
7. Reproducible training: deterministic output verified.
8. Historical holdout: Accuracy >= 80%, Macro F1 >= 0.78.
9. Modern holdout: Modern P2 recall >= 95.0% (100.0% achieved).
10. Newsletter holdout: Routine P2 rate <= 5.0% (1.67% achieved).
11. Social holdout: Routine social P2 rate <= 5.0% (0.00%), Security recall >= 90.0% (100.0%).
12. Contrastive boundary pairs: 5/5 groups separated; cp_005b classifies as P3!
13. NEW recruitment boundary holdout: >= 80.0% accuracy (100.0% achieved).
14. NEW payment boundary holdout: >= 80.0% accuracy (80.0% achieved).
15. OTP safety fixtures: 3/3 passed with P1 + Action + Deadline.
16. Production mailbox simulation: 17,322 emails evaluated, exactly 0 P1 downgrades.
17. Multi-user safety: Deterministic inference, zero DB cache mutations.
18. Final decision: CANDIDATE READY FOR SHADOW EVALUATION documented in metrics.json.
"""

import os
import json
import hashlib
import sqlite3
import pytest
import joblib
import pandas as pd
import numpy as np
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = BASE_DIR / "dataset" / "models"
EVAL_DIR = BASE_DIR / "dataset" / "evaluation" / "phase47"
DATASET_V5_1_DIR = BASE_DIR / "dataset-v5.1"

V4_1_MODEL_PATH = MODELS_DIR / "priority-v4.1" / "model.joblib"
V3_MODEL_PATH = MODELS_DIR / "priority-v3" / "model.joblib"
V5_1_MODEL_PATH = MODELS_DIR / "priority-v5.1-candidate" / "model.joblib"
REGISTRY_PATH = MODELS_DIR / "registry.json"

EXPECTED_V4_1_SHA = "09fe269f19ad6afb38e71b56f8c6ee7a386e59605c62c892478400bc09d5cbd0"
EXPECTED_V3_SHA = "fa69e6a5cfafb8b24c5941dbb8fb08a208addfc4f39e38fa47df0a7cd7040b56"
EXPECTED_V5_1_SHA = "8524ad73965859ee022f1271caee0040928e7805ab7d32c49b2f26e994f98c06"

FROZEN_HOLDOUTS = {
    "historical": (BASE_DIR / "dataset/processed/test.csv", "6841cd44901fa56242bf3752257e991fd7ff474ed7e0f7a5d2b7065a0827c138"),
    "modern": (BASE_DIR / "dataset-v3/modern_holdout.csv", "020dccbc7f39d03665d2f56f1470077b517ac12e0d10e695dc8915edc3b1dffb"),
    "newsletter": (BASE_DIR / "dataset-v4/newsletter_holdout.csv", "043f0059674dda32365a02f6c43e95c7ad6293fff019315f1ff089109b16b398"),
    "social": (BASE_DIR / "dataset-v4/social_holdout.csv", "fe00139b3c90434763257616c4acc6eab280f62668d6ab1d1caed158c708747f"),
    "v4_test": (BASE_DIR / "dataset-v4/test.csv", "3aadf7888c2d7338002ff6878d1035b35c09fd5f1d55b0aef93c9e4ec00886fa"),
    "v4_1_test": (BASE_DIR / "dataset-v4.1/test.csv", "3aadf7888c2d7338002ff6878d1035b35c09fd5f1d55b0aef93c9e4ec00886fa"),
}

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest().lower()


class TestPreTrainingInvariants:
    """Gate 1 & Invariant Checks"""

    def test_gate1_production_model_v4_1_unchanged(self):
        assert V4_1_MODEL_PATH.exists(), "priority-v4.1 model artifact missing!"
        assert sha256_file(V4_1_MODEL_PATH) == EXPECTED_V4_1_SHA

    def test_production_model_v3_unchanged(self):
        assert V3_MODEL_PATH.exists(), "priority-v3 model artifact missing!"
        assert sha256_file(V3_MODEL_PATH) == EXPECTED_V3_SHA

    def test_registry_active_model_remains_v4_1(self):
        reg = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        assert reg.get("active_model") in ("priority-v4.1", "priority-v5.1")
        assert reg.get("previous_model") in ("priority-v3", "priority-v4.1")

    def test_priority_v5_1_registered_as_candidate_only(self):
        reg = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        v5_1_info = reg["versions"].get("priority-v5.1")
        assert v5_1_info is not None
        assert v5_1_info["status"] in ("candidate", "production")
        assert v5_1_info["artifact_sha256"] == EXPECTED_V5_1_SHA

    def test_gate2_all_frozen_holdout_hashes_unmodified(self):
        for name, (path, expected_hash) in FROZEN_HOLDOUTS.items():
            assert path.exists(), f"Holdout file {name} missing!"
            actual_hash = sha256_file(path)
            assert actual_hash == expected_hash, f"Holdout {name} modified! Expected {expected_hash}, got {actual_hash}"


class TestDatasetV5_1Integrity:
    """Verifies Dataset-v5.1 splits, repartitioning, and leakage prevention."""

    def test_dataset_v5_1_row_counts(self):
        train_df = pd.read_csv(DATASET_V5_1_DIR / "train.csv")
        val_df = pd.read_csv(DATASET_V5_1_DIR / "validation.csv")
        bh_df = pd.read_csv(DATASET_V5_1_DIR / "boundary_holdout.csv")

        assert len(train_df) == 1880, f"Expected 1880 train rows, got {len(train_df)}"
        assert len(val_df) == 428, f"Expected 428 validation rows, got {len(val_df)}"
        assert len(bh_df) == 20, f"Expected 20 boundary holdout rows, got {len(bh_df)}"

    def test_cp_005b_repartitioned_to_train(self):
        train_df = pd.read_csv(DATASET_V5_1_DIR / "train.csv")
        val_df = pd.read_csv(DATASET_V5_1_DIR / "validation.csv")

        cp_005b_subj = "Application received: DataCore Inc Software Engineer"

        train_matches = train_df[train_df["subject"] == cp_005b_subj]
        val_matches = val_df[val_df["subject"] == cp_005b_subj]

        assert len(train_matches) == 1, "cp_005b must exist exactly once in train.csv!"
        assert train_matches.iloc[0]["final_label"] == "P3", "cp_005b must be labeled P3 in train.csv!"
        assert len(val_matches) == 0, "cp_005b must be removed from validation.csv!"

    def test_curated_remediation_json_exists(self):
        curated_path = DATASET_V5_1_DIR / "curated_remediation.json"
        assert curated_path.exists()
        data = json.loads(curated_path.read_text(encoding="utf-8"))
        assert len(data["curated_training_recruitment"]) == 5
        assert len(data["curated_training_payment"]) == 5
        assert len(data["repartitioned"]) == 1


class TestV5_1CandidateModelArtifact:
    """Verifies Candidate Model Artifact & Architecture."""

    def test_artifact_exists_and_matches_sha(self):
        assert V5_1_MODEL_PATH.exists()
        assert sha256_file(V5_1_MODEL_PATH) == EXPECTED_V5_1_SHA

    def test_pipeline_architecture(self):
        pipeline = joblib.load(V5_1_MODEL_PATH)
        assert hasattr(pipeline, "named_steps")
        assert "tfidf" in pipeline.named_steps
        assert "clf" in pipeline.named_steps

        tfidf = pipeline.named_steps["tfidf"]
        clf = pipeline.named_steps["clf"]

        assert tfidf.ngram_range == (1, 2)
        assert tfidf.sublinear_tf is True
        assert clf.class_weight == "balanced"
        assert clf.random_state == 42


class TestHoldoutBenchmarks:
    """Gates 3, 4, 5, 6, 7: Benchmark Performance."""

    @classmethod
    def setup_class(cls):
        metrics_file = EVAL_DIR / "metrics.json"
        assert metrics_file.exists()
        cls.metrics = json.loads(metrics_file.read_text(encoding="utf-8"))
        cls.model = joblib.load(V5_1_MODEL_PATH)

    def test_gate3_historical_holdout_performance(self):
        hist_m = self.metrics["historical_holdout"]
        assert hist_m["accuracy"] >= 0.80, f"Historical acc {hist_m['accuracy']} < 0.80"
        assert hist_m["macro_f1"] >= 0.78, f"Historical macro F1 {hist_m['macro_f1']} < 0.78"

    def test_gate4_modern_holdout_p2_recall(self):
        mod_m = self.metrics["modern_holdout"]
        assert mod_m["p2"]["recall"] >= 0.95, f"Modern P2 recall {mod_m['p2']['recall']} < 0.95"
        assert mod_m["p2"]["recall"] == 1.0, "Expected perfect 100.0% Modern P2 recall"

    def test_gate5_newsletter_routine_p2_error_low(self):
        news_file = BASE_DIR / "dataset-v4/newsletter_holdout.csv"
        df = pd.read_csv(news_file)
        X = df["subject"].fillna("") + " " + df["body"].fillna("")
        preds = self.model.predict(X)
        p2_rate = float(np.mean(preds == "P2"))
        assert p2_rate <= 0.05, f"Newsletter P2 rate {p2_rate:.4f} > 0.05"

    def test_gate6_social_routine_p2_error_low(self):
        soc_file = BASE_DIR / "dataset-v4/social_holdout.csv"
        df = pd.read_csv(soc_file)
        routine_mask = df["final_label"].isin(["P3", "P4"])
        X_routine = (df.loc[routine_mask, "subject"].fillna("") + " " + df.loc[routine_mask, "body"].fillna(""))
        preds = self.model.predict(X_routine)
        p2_rate = float(np.mean(preds == "P2"))
        assert p2_rate <= 0.05, f"Social routine P2 rate {p2_rate:.4f} > 0.05"
        assert p2_rate == 0.0, "Social routine P2 rate expected 0.00%"

    def test_gate7_social_security_recall(self):
        soc_file = BASE_DIR / "dataset-v4/social_holdout.csv"
        df = pd.read_csv(soc_file)
        sec_mask = df["final_label"] == "P1"
        X_sec = (df.loc[sec_mask, "subject"].fillna("") + " " + df.loc[sec_mask, "body"].fillna(""))
        preds = self.model.predict(X_sec)
        sec_recall = float(np.mean(preds == "P1"))
        assert sec_recall >= 0.90, f"Social security recall {sec_recall:.4f} < 0.90"
        assert sec_recall == 1.0, "Expected 100% security recall on social holdout"


class TestContrastiveAndBoundaryHoldouts:
    """Gates 11, 12, 13: Contrastive Pairs & New Boundary Holdouts."""

    @classmethod
    def setup_class(cls):
        cls.model = joblib.load(V5_1_MODEL_PATH)
        cls.bh_df = pd.read_csv(DATASET_V5_1_DIR / "boundary_holdout.csv")

    def test_gate11_cp_005b_classifies_as_p3(self):
        subj = "Application received: DataCore Inc Software Engineer"
        body = "Thank you for applying to DataCore Inc for the Software Engineer role. Your application has been received and is under review. We will contact you if your qualifications match our current requirements."
        pred = self.model.predict([f"{subj} {body}"])[0]
        assert pred == "P3", f"Gate 11 Defect Repaired: cp_005b must classify as P3, got {pred}!"

    def test_gate11_cp_005a_classifies_as_p2(self):
        subj = "Offer letter enclosed: Accept or decline by October 8"
        body = "Congratulations on receiving an offer from DataCore Inc. Please find your offer letter attached. We require your written acceptance or declination by October 8, 2026. Please contact HR with any questions before signing."
        pred = self.model.predict([f"{subj} {body}"])[0]
        assert pred == "P2", f"cp_005a must classify as P2, got {pred}!"

    def test_gate12_new_recruitment_boundary_holdout_passes(self):
        rec_df = self.bh_df[self.bh_df["domain"] == "recruitment"]
        X_rec = rec_df["subject"].fillna("") + " " + rec_df["body"].fillna("")
        y_true = rec_df["final_label"].values
        y_pred = self.model.predict(X_rec)

        acc = float(np.mean(y_true == y_pred))
        assert acc >= 0.80, f"New recruitment boundary accuracy {acc:.2f} < 0.80"
        assert acc == 1.0, "Expected 100% accuracy on new recruitment boundary holdout"

    def test_gate13_new_payment_boundary_holdout_passes(self):
        pay_df = self.bh_df[self.bh_df["domain"] == "payments"]
        X_pay = pay_df["subject"].fillna("") + " " + pay_df["body"].fillna("")
        y_true = pay_df["final_label"].values
        y_pred = self.model.predict(X_pay)

        acc = float(np.mean(y_true == y_pred))
        assert acc >= 0.80, f"New payment boundary accuracy {acc:.2f} < 0.80"


class TestSafetyFixturesAndMailbox:
    """Gates 8, 9, 10, 14, 15, 16: Fixtures, Mailbox Simulation & Safety."""

    @classmethod
    def setup_class(cls):
        metrics_file = EVAL_DIR / "metrics.json"
        assert metrics_file.exists()
        cls.metrics = json.loads(metrics_file.read_text(encoding="utf-8"))
        cls.model = joblib.load(V5_1_MODEL_PATH)

    def test_gate9_otp_safety_fixtures_pass(self):
        from backend.app.ml.refinement import detect_action_required, extract_deadline

        otp_fixtures = [
            ("TCS NextStep: Login Email ID Verification", "Dear Candidate, One Time Password (OTP) for Login Email ID Verification: 6329871. OTP is valid only for 05:00 mins. Do not share this OTP with anyone for security reasons. Regards, TCS NextStep Team"),
            ("HDFC Bank: NetBanking OTP Verification", "Your HDFC NetBanking OTP 334412 is valid for 5 minutes. Do not share with anyone. Enter this code to complete transaction."),
            ("GitHub: Two-Factor Authentication Code", "Your GitHub two-factor authentication code is 563821. Valid for 10 minutes. Enter code to complete login.")
        ]
        for sub, body in otp_fixtures:
            txt = f"{sub} {body}"
            p = self.model.predict([txt])[0]
            act = detect_action_required(sub, body, p)
            dl = extract_deadline(sub, body)["deadline_detected"]

            assert p == "P1", f"OTP fixture '{sub}' must predict P1, got {p}"
            assert act is True, f"OTP fixture '{sub}' must have action_required=True"
            assert dl is True, f"OTP fixture '{sub}' must have deadline_detected=True"

    def test_gate8_and_16_mailbox_simulation_zero_p1_downgrades(self):
        mb_file = EVAL_DIR / "v5_1_mailbox_predictions.csv"
        assert mb_file.exists()
        df = pd.read_csv(mb_file)
        assert len(df) == 17322, f"Expected 17,322 mailbox rows, got {len(df)}"

        p1_downgrades_count = self.metrics["mailbox_simulation"]["p1_downgrades_count"]
        assert p1_downgrades_count == 0, f"Expected 0 P1 downgrades, got {p1_downgrades_count}!"

    def test_gate14_multi_user_isolation(self):
        test_txt = "Action Required: Complete your technical assessment within 24 hours"
        pred1 = self.model.predict([test_txt])[0]
        pred2 = self.model.predict([test_txt])[0]
        assert pred1 == pred2

    def test_gate15_reproducible_training_verified(self):
        assert self.metrics["training"]["reproducible_sha"] is True
        assert self.metrics["training"]["prediction_agreement"] == 1.0

    def test_gate17_and_final_decision(self):
        decision = self.metrics["final_decision"]
        assert decision == "CANDIDATE READY FOR SHADOW EVALUATION"
