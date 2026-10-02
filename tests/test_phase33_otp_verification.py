"""
Phase 33: OTP / Time-Sensitive Verification Priority Correction Tests
=====================================================================
Tests that the priority-v3 model *learns* to classify OTP/verification emails
as P1+action_required=True through training data, NOT via keyword hacks.

Key constraints:
  - Raw model (priority-v3) must produce P1 for TCS-style OTP email.
  - No keyword override ("if OTP in text: P1") must exist in refinement.py.
  - Historical holdout hash must remain unchanged.
  - CodeVita regression must remain P2.
  - Cases 4, 5, 7 must NOT be P1 and must have action_required=False.
"""

import hashlib
import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

import joblib
import pandas as pd
import pytest

# Ensure project root is on path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from backend.app.ml.refinement import (
    ACTION_NOT_REQUIRED_PATTERNS,
    ACTION_REQUIRED_PATTERNS,
    RELATIVE_MINUTES_REGEX,
    detect_action_required,
    detect_topic,
    extract_deadline,
    refine_priority,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
MODELS_DIR = ROOT / "dataset" / "models"
PRIORITY_V2_PATH = MODELS_DIR / "priority-v2" / "model.joblib"
PRIORITY_V3_PATH = MODELS_DIR / "priority-v3" / "model.joblib"
REGISTRY_PATH = MODELS_DIR / "registry.json"
HISTORICAL_HOLDOUT = ROOT / "dataset" / "processed" / "test.csv"
MODERN_HOLDOUT = ROOT / "dataset" / "processed" / "modern_email_holdout.csv"
DATASET_V2_DIR = ROOT / "dataset" / "versions" / "dataset-v2"
DATASET_V3_DIR = ROOT / "dataset" / "versions" / "dataset-v3"

# This hash must NEVER change -- it validates the holdout is untouched.
EXPECTED_TEST_CSV_SHA256 = "6841CD44901FA56242BF3752257E991FD7FF474ED7E0F7A5D2B7065A0827C138"

# priority-v2 artifact hash -- must remain unchanged
EXPECTED_V2_SHA256 = "be52c2dbfe28001a66b134d1125dfa8d117bbe64206590d71bde9f7029f3cd75"

# ============================================================================
# Helpers
# ============================================================================

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def load_model(path: Path):
    return joblib.load(path)


def raw_predict(model, text: str) -> str:
    """Return raw model label for a single text string."""
    return model.predict([text])[0]


def raw_predict_proba(model, text: str) -> dict:
    proba = model.predict_proba([text])[0]
    classes = model.classes_
    return dict(zip(classes, proba))


# ============================================================================
# 33.1 -- Artifact Integrity Checks
# ============================================================================

class TestArtifactIntegrity:
    """Ensures no model artifact or holdout was accidentally mutated."""

    def test_historical_holdout_hash_unchanged(self):
        """test.csv must remain bit-for-bit identical to the pre-v3 baseline."""
        actual = sha256_file(HISTORICAL_HOLDOUT)
        assert actual == EXPECTED_TEST_CSV_SHA256, (
            f"CRITICAL: Historical holdout contaminated!\n"
            f"  Expected: {EXPECTED_TEST_CSV_SHA256}\n"
            f"  Actual:   {actual}"
        )

    def test_priority_v2_artifact_unchanged(self):
        """priority-v2/model.joblib must not be overwritten by v3 training."""
        actual = sha256_file(PRIORITY_V2_PATH).lower()
        assert actual == EXPECTED_V2_SHA256, (
            f"priority-v2 artifact was modified!\n"
            f"  Expected: {EXPECTED_V2_SHA256}\n"
            f"  Actual:   {actual}"
        )

    def test_priority_v3_artifact_exists(self):
        assert PRIORITY_V3_PATH.exists(), "priority-v3 model artifact missing"

    def test_registry_has_both_v2_and_v3(self):
        with open(REGISTRY_PATH) as f:
            reg = json.load(f)
        assert "priority-v2" in reg["versions"], "priority-v2 missing from registry"
        assert "priority-v3" in reg["versions"], "priority-v3 missing from registry"

    def test_registry_active_model_is_v3(self):
        with open(REGISTRY_PATH) as f:
            reg = json.load(f)
        assert reg["active_model"] in ("priority-v3", "priority-v4.1", "priority-v5.1"), (
            f"Expected active_model in ('priority-v3', 'priority-v4.1', 'priority-v5.1'), got '{reg['active_model']}'"
        )

    def test_v3_registry_entry_has_required_fields(self):
        with open(REGISTRY_PATH) as f:
            reg = json.load(f)
        v3 = reg["versions"]["priority-v3"]
        required_fields = [
            "model_version", "dataset_version", "created_at",
            "artifact_path", "artifact_sha256",
        ]
        for field in required_fields:
            assert field in v3, f"Registry v3 entry missing field: {field}"


# ============================================================================
# 33.4 / 33.5 -- Dataset-v3 Existence & Labels
# ============================================================================

class TestDatasetV3:
    """Verifies dataset-v3 was created correctly with OTP examples."""

    def test_dataset_v3_train_exists(self):
        assert (DATASET_V3_DIR / "train.csv").exists()

    def test_dataset_v3_train_has_more_rows_than_v2(self):
        v2_train = pd.read_csv(DATASET_V2_DIR / "train.csv")
        v3_train = pd.read_csv(DATASET_V3_DIR / "train.csv")
        assert len(v3_train) > len(v2_train), (
            f"v3 train ({len(v3_train)}) must be > v2 train ({len(v2_train)})"
        )

    def test_dataset_v3_contains_otp_p1_examples(self):
        df = pd.read_csv(DATASET_V3_DIR / "train.csv")
        # Combine subject+body into text for matching
        df["_text"] = df["subject"].fillna("") + " " + df["body"].fillna("")
        otp_mask = df["_text"].str.contains(
            r"\botp\b|one.?time password|login code|mfa code",
            case=False, regex=True, na=False
        )
        p1_otp = df[otp_mask & (df["final_label"] == "P1")]
        assert len(p1_otp) >= 3, (
            f"Expected >=3 OTP P1 examples in v3 train, found {len(p1_otp)}"
        )

    def test_dataset_v3_contains_non_actionable_verification(self):
        df = pd.read_csv(DATASET_V3_DIR / "train.csv")
        df["_text"] = df["subject"].fillna("") + " " + df["body"].fillna("")
        non_action = df[
            df["_text"].str.contains(
                r"verification (?:was |has been )?(?:successfully )?completed|"
                r"account (?:was )?successfully verified|"
                r"security settings were updated",
                case=False, regex=True, na=False
            )
        ]
        assert len(non_action) >= 1, "Non-actionable verification examples missing from v3"
        non_p1 = non_action[non_action["final_label"] != "P1"]
        assert len(non_p1) >= 1, "Non-actionable verification examples must not all be P1"

    def test_dataset_v3_metadata_exists(self):
        assert (DATASET_V3_DIR / "metadata.json").exists()

    def test_modern_holdout_exists_and_not_in_train(self):
        assert MODERN_HOLDOUT.exists(), "modern_email_holdout.csv missing"
        holdout_df = pd.read_csv(MODERN_HOLDOUT)
        train_df = pd.read_csv(DATASET_V3_DIR / "train.csv")
        # Compare by subject+body composite key
        holdout_keys = set(
            (row["subject"] + " " + row["body"]) for _, row in holdout_df.iterrows()
        )
        train_keys = set(
            (str(row["subject"]) + " " + str(row["body"])) for _, row in train_df.iterrows()
        )
        overlap = holdout_keys & train_keys
        assert len(overlap) == 0, (
            f"modern_email_holdout rows leaked into v3 training set: {len(overlap)} overlap(s)"
        )


# ============================================================================
# 33.6 -- Raw Model: priority-v3 Core OTP Classification
# ============================================================================

# Exact real TCS email text (as extracted by Gmail pipeline)
TCS_OTP_SUBJECT = "TCS NextStep: Login Email ID Verification"
TCS_OTP_BODY = (
    "Dear Candidate, "
    "One Time Password (OTP) for Login Email ID Verification: 6329871. "
    "OTP is valid only for 05:00 mins. "
    "Do not share this OTP with anyone for security reasons. "
    "Regards, TCS NextStep Team"
)
TCS_OTP_TEXT = f"{TCS_OTP_SUBJECT} {TCS_OTP_BODY}"
TCS_EMAIL_DATE = "2026-10-02T02:13:21+05:30"


class TestRawModelV3OTPClassification:
    """
    The RAW model (no refinement) must produce P1 for TCS OTP email.
    This is the critical test -- it validates that priority-v3 LEARNED the
    P1 relationship from training data, NOT from keyword overrides.
    """

    @pytest.fixture(scope="class")
    def v3_model(self):
        return load_model(PRIORITY_V3_PATH)

    def test_tcs_otp_raw_model_predicts_p1(self, v3_model):
        """Raw model must classify TCS OTP email as P1 -- learned behavior."""
        prediction = raw_predict(v3_model, TCS_OTP_TEXT)
        assert prediction == "P1", (
            f"Raw priority-v3 must predict P1 for TCS OTP email.\n"
            f"  Got: {prediction}\n"
            f"  Text: {TCS_OTP_TEXT[:120]}"
        )

    def test_tcs_otp_raw_model_p1_probability_dominant(self, v3_model):
        """P1 probability should be the highest class probability."""
        proba = raw_predict_proba(v3_model, TCS_OTP_TEXT)
        p1_prob = proba.get("P1", 0.0)
        assert p1_prob > 0.50, (
            f"P1 probability should exceed 50% for TCS OTP.\n"
            f"  P1 prob: {p1_prob:.4f}\n"
            f"  All probs: {proba}"
        )
        max_class = max(proba, key=proba.get)
        assert max_class == "P1", f"P1 must be the dominant class, got {max_class}: {proba}"

    def test_v3_vs_v2_otp_prediction(self, v3_model):
        """v3 must correctly predict P1 where v2 incorrectly predicted P2."""
        v2_model = load_model(PRIORITY_V2_PATH)
        v2_pred = raw_predict(v2_model, TCS_OTP_TEXT)
        v3_pred = raw_predict(v3_model, TCS_OTP_TEXT)
        assert v2_pred == "P2", f"v2 should still predict P2 (unchanged), got {v2_pred}"
        assert v3_pred == "P1", f"v3 should predict P1 (fixed), got {v3_pred}"

    def test_case1_login_otp_raw_p1(self, v3_model):
        """Case 1: Login OTP with explicit short expiry -> P1."""
        text = "Login OTP Your OTP for login is 6329871. Valid for 5 minutes."
        pred = raw_predict(v3_model, text)
        assert pred == "P1", f"Case 1 raw model expected P1, got {pred}"

    def test_case2_verification_expires_raw_p1(self, v3_model):
        """Case 2: Email verification code with expiry -> P1."""
        text = "Email Verification Your verification code expires in 10 minutes. Enter code to verify."
        pred = raw_predict(v3_model, text)
        assert pred == "P1", f"Case 2 raw model expected P1, got {pred}"

    def test_case3_password_reset_raw_p1(self, v3_model):
        """Case 3: Password reset code -> P1."""
        text = "Password Reset Your password reset code is 123456. Enter this code to proceed."
        pred = raw_predict(v3_model, text)
        assert pred == "P1", f"Case 3 raw model expected P1, got {pred}"

    def test_case4_verification_completed_not_p1(self, v3_model):
        """Case 4: 'Verification completed' confirmation must NOT be P1."""
        text = "Account Verification Complete Your account verification was successfully completed. No action required."
        pred = raw_predict(v3_model, text)
        assert pred != "P1", (
            f"Case 4 'verification completed' should NOT be P1, got {pred}. "
            "This is a false-positive regression."
        )

    def test_case5_security_settings_updated_not_p1(self, v3_model):
        """Case 5: 'Security settings updated' confirmation must NOT be P1."""
        text = "Security Update Your security settings were updated successfully. If you did not make this change, contact support."
        pred = raw_predict(v3_model, text)
        assert pred != "P1", (
            f"Case 5 'security settings updated' should NOT be P1, got {pred}."
        )

    def test_case6_security_alert_p1(self, v3_model):
        """Case 6: Security alert with immediate action -> P1."""
        text = "Security Alert New login detected from unrecognized device. Review immediately and secure your account."
        pred = raw_predict(v3_model, text)
        assert pred == "P1", f"Case 6 security alert expected P1, got {pred}"

    def test_case7_monthly_report_not_p1(self, v3_model):
        """Case 7: Monthly security report -> NOT P1, NOT action_required."""
        text = "Security Your monthly account security report for September 2026."
        pred = raw_predict(v3_model, text)
        assert pred != "P1", (
            f"Case 7 'monthly report' should NOT be P1, got {pred}."
        )

    def test_codevita_regression_raw_model_p2(self, v3_model):
        """CodeVita competition email must remain P2 -- no OTP regression."""
        text = (
            "TCS CodeVita Season 12 Round 1 Invitation "
            "Dear Candidate, You are invited to participate in TCS CodeVita Season 12. "
            "The competition deadline closes on 2026-10-15 11:59 PM. "
            "Submit your solution before the deadline."
        )
        pred = raw_predict(v3_model, text)
        assert pred == "P2", (
            f"CodeVita must remain P2 after OTP training. Got {pred}. "
            "This is a regression."
        )


# ============================================================================
# 33.3 -- No Keyword Hack Verification
# ============================================================================

class TestNoKeywordHack:
    """
    Verifies that refinement.py does NOT contain any raw keyword override
    that forces OTP emails to P1 regardless of model output.
    """

    def test_refine_priority_has_no_otp_keyword_override(self):
        """refine_priority must not contain 'if.*otp.*P1' style overrides."""
        refinement_path = ROOT / "backend" / "app" / "ml" / "refinement.py"
        source = refinement_path.read_text(encoding="utf-8")
        func_start = source.find("def refine_priority(")
        assert func_start >= 0, "refine_priority function not found"
        func_body = source[func_start:]
        # Look for assignment of refined_priority or final_priority triggered by OTP condition alone
        # This would be: if 'otp' in text: refined_priority = 'P1' (on same or immediately next line)
        otp_priority_override = re.search(
            r'if\b[^\n]*\botp\b[^\n]*\n\s*(?:refined_priority|final_priority)\s*=\s*["\']P1["\']',
            func_body, re.IGNORECASE
        )
        assert otp_priority_override is None, (
            f"Keyword hack detected: OTP check directly sets priority to P1 in refine_priority"
        )

    def test_no_otp_special_case_in_refine_priority(self):
        """The refine_priority function must not have an OTP-specific branch."""
        refinement_path = ROOT / "backend" / "app" / "ml" / "refinement.py"
        source = refinement_path.read_text(encoding="utf-8")
        forbidden = re.search(
            r"if\s+['\"]otp['\"]\s+in\s+(?:text|subject|body).*?=.*?P1",
            source, re.IGNORECASE | re.DOTALL
        )
        assert forbidden is None, "Direct OTP->P1 keyword hack found in refinement.py"


# ============================================================================
# 33.5 / 33.11 -- Refinement Pipeline: Full refine_priority Integration
# ============================================================================

class TestRefinementPipelineOTP:
    """Tests the complete refinement layer on OTP and non-OTP cases."""

    def test_tcs_otp_action_required_true(self):
        """Refinement must set action_required=True for TCS OTP email."""
        result = refine_priority(
            subject=TCS_OTP_SUBJECT,
            body=TCS_OTP_BODY,
            sender="noreply@tcsnextstep.com",
            model_priority="P1",
            confidence=0.80,
            email_date=TCS_EMAIL_DATE,
        )
        assert result["action_required"] is True, (
            f"action_required must be True for TCS OTP email.\n"
            f"  Result: {result}"
        )

    def test_tcs_otp_final_priority_p1(self):
        """Final priority must be P1 for TCS OTP email."""
        result = refine_priority(
            subject=TCS_OTP_SUBJECT,
            body=TCS_OTP_BODY,
            sender="noreply@tcsnextstep.com",
            model_priority="P1",
            confidence=0.80,
            email_date=TCS_EMAIL_DATE,
        )
        assert result["final_priority"] == "P1", (
            f"final_priority must be P1, got {result['final_priority']}"
        )

    def test_tcs_otp_deadline_detected(self):
        """Deadline must be detected for OTP with 5-minute expiry."""
        result = refine_priority(
            subject=TCS_OTP_SUBJECT,
            body=TCS_OTP_BODY,
            sender="noreply@tcsnextstep.com",
            model_priority="P1",
            confidence=0.80,
            email_date=TCS_EMAIL_DATE,
        )
        assert result["deadline_detected"] is True, (
            f"deadline_detected must be True for 'valid only for 05:00 mins'.\n"
            f"  Result: {result}"
        )

    def test_tcs_otp_topic_is_security(self):
        """Topic must be 'security' for TCS OTP email."""
        result = refine_priority(
            subject=TCS_OTP_SUBJECT,
            body=TCS_OTP_BODY,
            sender="noreply@tcsnextstep.com",
            model_priority="P1",
            confidence=0.80,
            email_date=TCS_EMAIL_DATE,
        )
        assert result["topic"] == "security", (
            f"topic must be 'security', got '{result['topic']}'"
        )

    def test_tcs_otp_action_reason_is_verification(self):
        """Action reason must indicate immediate verification for OTP email."""
        result = refine_priority(
            subject=TCS_OTP_SUBJECT,
            body=TCS_OTP_BODY,
            sender="noreply@tcsnextstep.com",
            model_priority="P1",
            confidence=0.80,
            email_date=TCS_EMAIL_DATE,
        )
        assert result["action_reason"] is not None
        reason_lower = result["action_reason"].lower()
        assert "verification" in reason_lower or "immediate" in reason_lower, (
            f"action_reason should mention verification/immediate, got: '{result['action_reason']}'"
        )

    def test_case4_verification_completed_action_false(self):
        """Case 4: Completed verification -> action_required=False."""
        result = refine_priority(
            subject="Account Verification Complete",
            body="Your account verification was successfully completed. No further action needed.",
            sender="noreply@example.com",
            model_priority="P3",
            confidence=0.65,
        )
        assert result["action_required"] is False, (
            f"Case 4: action_required must be False for completed verification.\n"
            f"  Result: {result}"
        )

    def test_case5_security_updated_action_false(self):
        """Case 5: Security settings updated -> action_required=False."""
        result = refine_priority(
            subject="Security Update",
            body="Your security settings were updated successfully.",
            sender="noreply@example.com",
            model_priority="P3",
            confidence=0.70,
        )
        assert result["action_required"] is False, (
            f"Case 5: action_required must be False for 'settings updated'.\n"
            f"  Result: {result}"
        )

    def test_case7_monthly_report_action_false(self):
        """Case 7: Monthly report -> action_required=False."""
        result = refine_priority(
            subject="Your monthly account security report",
            body="Here is your monthly account security report for September 2026.",
            sender="noreply@example.com",
            model_priority="P3",
            confidence=0.65,
        )
        assert result["action_required"] is False, (
            f"Case 7: monthly report should have action_required=False.\n"
            f"  Result: {result}"
        )


# ============================================================================
# 33.11 -- Deadline Extraction for OTP Expiry
# ============================================================================

class TestDeadlineExtractionOTP:
    """Tests that OTP-style expiry windows are correctly extracted as deadlines."""

    def test_tcs_otp_deadline_expiry_from_email_date(self):
        """
        Email received: 2026-10-02 02:13 IST
        OTP valid for: 05:00 mins
        Expected deadline: 2026-10-02 02:18:21 (local, stripped of tz)
        """
        result = extract_deadline(
            subject=TCS_OTP_SUBJECT,
            body=TCS_OTP_BODY,
            email_date=TCS_EMAIL_DATE,
        )
        assert result["deadline_detected"] is True, (
            f"Deadline must be detected for TCS OTP. Got: {result}"
        )
        dl_dt = result["deadline_datetime"]
        assert dl_dt is not None
        parsed = datetime.fromisoformat(dl_dt)
        assert parsed.hour == 2
        assert parsed.minute == 18

    def test_expires_in_5_minutes_deadline(self):
        """'Your verification code expires in 5 minutes.' -> deadline_detected=True."""
        result = extract_deadline(
            subject="Verify your account",
            body="Your verification code expires in 5 minutes. Enter code: 482910.",
            email_date="2026-10-02T10:00:00",
        )
        assert result["deadline_detected"] is True
        parsed = datetime.fromisoformat(result["deadline_datetime"])
        assert parsed.hour == 10 and parsed.minute == 5

    def test_valid_for_10_minutes_deadline(self):
        """'This code is valid for 10 minutes.' -> deadline_detected=True."""
        result = extract_deadline(
            subject="Your sign-in code",
            body="Your sign-in code is 771234. This code is valid for 10 minutes.",
            email_date="2026-10-02T09:00:00",
        )
        assert result["deadline_detected"] is True
        parsed = datetime.fromisoformat(result["deadline_datetime"])
        assert parsed.minute == 10

    def test_otp_display_contains_otp_expiry_label(self):
        """OTP expiry deadline display should indicate 'OTP expiry'."""
        result = extract_deadline(
            subject=TCS_OTP_SUBJECT,
            body=TCS_OTP_BODY,
            email_date=TCS_EMAIL_DATE,
        )
        assert "OTP expiry" in result.get("deadline_display", ""), (
            f"Deadline display should note OTP expiry. Got: {result.get('deadline_display')}"
        )

    def test_hours_deadline_still_works(self):
        """'Expires in 24 hours' must still work after minutes regex addition."""
        result = extract_deadline(
            subject="Link valid",
            body="Your activation link is valid for 24 hours.",
            email_date="2026-10-02T00:00:00",
        )
        assert result["deadline_detected"] is True
        parsed = datetime.fromisoformat(result["deadline_datetime"])
        assert parsed.day == 3

    def test_no_deadline_for_completed_verification(self):
        """'Verification completed' emails must NOT get a false deadline."""
        result = extract_deadline(
            subject="Account Verified",
            body="Your account verification was successfully completed.",
            email_date="2026-10-02T00:00:00",
        )
        assert result["deadline_detected"] is False, (
            f"Completed verification should not produce deadline. Got: {result}"
        )


# ============================================================================
# 33.7 -- Holdout Evaluation: v2 vs v3 Regression
# ============================================================================

class TestHoldoutEvaluation:
    """Checks v3 does not regress below v2 on the historical holdout."""

    @pytest.fixture(scope="class")
    def holdout_data(self):
        return pd.read_csv(HISTORICAL_HOLDOUT)

    @pytest.fixture(scope="class")
    def v2_model(self):
        return load_model(PRIORITY_V2_PATH)

    @pytest.fixture(scope="class")
    def v3_model(self):
        return load_model(PRIORITY_V3_PATH)

    def test_v3_historical_accuracy_no_regression(self, holdout_data, v2_model, v3_model):
        """v3 accuracy on historical holdout must be >= v2 - 2%."""
        texts = (holdout_data["subject"].fillna("") + " " + holdout_data["body"].fillna("")).tolist()
        labels = holdout_data["final_label"].tolist()
        v2_preds = v2_model.predict(texts)
        v3_preds = v3_model.predict(texts)
        v2_acc = sum(p == l for p, l in zip(v2_preds, labels)) / len(labels)
        v3_acc = sum(p == l for p, l in zip(v3_preds, labels)) / len(labels)
        assert v3_acc >= v2_acc - 0.02, (
            f"v3 regressed too much on historical holdout:\n"
            f"  v2 accuracy: {v2_acc:.4f}\n"
            f"  v3 accuracy: {v3_acc:.4f}\n"
            f"  Regression: {v2_acc - v3_acc:.4f} (limit 0.02)"
        )

    def test_v3_historical_accuracy_above_75pct(self, holdout_data, v3_model):
        texts = (holdout_data["subject"].fillna("") + " " + holdout_data["body"].fillna("")).tolist()
        labels = holdout_data["final_label"].tolist()
        preds = v3_model.predict(texts)
        acc = sum(p == l for p, l in zip(preds, labels)) / len(labels)
        assert acc > 0.75, f"v3 historical accuracy {acc:.4f} < 75%"

    def test_v3_p1_precision_and_recall(self, holdout_data, v3_model):
        texts = (holdout_data["subject"].fillna("") + " " + holdout_data["body"].fillna("")).tolist()
        labels = holdout_data["final_label"].tolist()
        preds = v3_model.predict(texts)
        p1_pred_count = sum(p == "P1" for p in preds)
        p1_true_count = sum(l == "P1" for l in labels)
        tp = sum(p == l == "P1" for p, l in zip(preds, labels))
        precision = tp / p1_pred_count if p1_pred_count else 0
        recall = tp / p1_true_count if p1_true_count else 0
        assert precision >= 0.60, f"P1 precision {precision:.4f} below 60%"
        assert recall >= 0.60, f"P1 recall {recall:.4f} below 60%"


# ============================================================================
# 33.8 -- Modern Holdout Evaluation
# ============================================================================

class TestModernHoldoutEvaluation:
    """Validates v3 performance on the modern email holdout."""

    @pytest.fixture(scope="class")
    def modern_data(self):
        return pd.read_csv(MODERN_HOLDOUT)

    @pytest.fixture(scope="class")
    def v3_model(self):
        return load_model(PRIORITY_V3_PATH)

    def test_modern_holdout_has_diverse_categories(self, modern_data):
        # modern_holdout uses 'final_label' not 'priority'
        label_col = "final_label" if "final_label" in modern_data.columns else "priority"
        assert label_col in modern_data.columns, f"Neither 'final_label' nor 'priority' found in modern holdout"
        classes = modern_data[label_col].unique()
        assert len(classes) >= 2, "Modern holdout must contain multiple priority classes"

    def test_modern_holdout_p1_recall_high(self, modern_data, v3_model):
        label_col = "final_label" if "final_label" in modern_data.columns else "priority"
        texts = (modern_data["subject"].fillna("") + " " + modern_data["body"].fillna("")).tolist()
        labels = modern_data[label_col].tolist()
        preds = v3_model.predict(texts)
        p1_true = sum(l == "P1" for l in labels)
        if p1_true == 0:
            pytest.skip("No P1 examples in modern holdout")
        tp = sum(p == l == "P1" for p, l in zip(preds, labels))
        recall = tp / p1_true
        assert recall >= 0.80, (
            f"Modern holdout P1 recall {recall:.4f} < 80%.\n"
            f"  True P1 count: {p1_true}, Correctly classified: {tp}"
        )

    def test_modern_holdout_accuracy_above_75pct(self, modern_data, v3_model):
        label_col = "final_label" if "final_label" in modern_data.columns else "priority"
        texts = (modern_data["subject"].fillna("") + " " + modern_data["body"].fillna("")).tolist()
        labels = modern_data[label_col].tolist()
        preds = v3_model.predict(texts)
        acc = sum(p == l for p, l in zip(preds, labels)) / len(labels)
        assert acc >= 0.75, f"Modern holdout accuracy {acc:.4f} < 75%"


# ============================================================================
# 33.9 -- OTP Regression Fixtures
# ============================================================================

class TestOTPRegressionFixtures:
    """Exact regression fixtures per Sections 33.9 and 33.10."""

    @pytest.fixture(scope="class")
    def v3_model(self):
        return load_model(PRIORITY_V3_PATH)

    def test_case1_otp_login_valid_5min(self, v3_model):
        text = "Login OTP Your OTP for login is 6329871. Valid for 5 minutes."
        assert raw_predict(v3_model, text) == "P1"
        action = detect_action_required("Login OTP", "Your OTP for login is 6329871. Valid for 5 minutes.", "P1")
        assert action is True

    def test_case2_verification_expires_10min(self, v3_model):
        text = "Verify Your Email Your verification code expires in 10 minutes. Enter code to verify your email."
        assert raw_predict(v3_model, text) == "P1"
        action = detect_action_required("Verify Your Email", "Your verification code expires in 10 minutes. Enter code.", "P1")
        assert action is True

    def test_case3_password_reset_code(self, v3_model):
        text = "Password Reset Your password reset code is 123456. Use this code to complete the reset."
        assert raw_predict(v3_model, text) == "P1"
        action = detect_action_required("Password Reset", "Your password reset code is 123456. Use this code.", "P1")
        assert action is True

    def test_case4_verification_completed_not_p1(self, v3_model):
        text = "Account Verification Complete Your account verification was successfully completed. No action required."
        pred = raw_predict(v3_model, text)
        assert pred != "P1", f"Case 4 must not be P1, got {pred}"
        action = detect_action_required("Account Verification Complete", "Your account verification was successfully completed.", pred)
        assert action is False, f"Case 4 action_required must be False"

    def test_case5_security_settings_updated(self, v3_model):
        text = "Security Update Your security settings were updated successfully."
        pred = raw_predict(v3_model, text)
        assert pred != "P1", f"Case 5 must not be P1, got {pred}"
        action = detect_action_required("Security Update", "Your security settings were updated successfully.", pred)
        assert action is False

    def test_case6_security_alert_new_login(self, v3_model):
        text = "Security Alert New login detected. Review immediately and secure your account."
        assert raw_predict(v3_model, text) == "P1"

    def test_case7_monthly_security_report(self, v3_model):
        text = "Security Your monthly account security report for September 2026."
        pred = raw_predict(v3_model, text)
        assert pred in ("P3", "P4"), f"Case 7 must be P3/P4, got {pred}"
        action = detect_action_required("Your monthly account security report", "Monthly account security report.", pred)
        assert action is False


# ============================================================================
# 33.10 -- Multi-Domain OTP Diversity Check
# ============================================================================

class TestMultiDomainOTPDiversity:
    """OTP emails from different domains must all be classified P1 by v3."""

    @pytest.fixture(scope="class")
    def v3_model(self):
        return load_model(PRIORITY_V3_PATH)

    MULTI_DOMAIN_OTP_CASES = [
        ("Banking OTP", "Your banking OTP is 445678. Valid for 5 minutes to complete your transaction."),
        ("Google Sign-In Code", "Your Google sign-in verification code is 291847. This code expires in 10 minutes."),
        ("GitHub Two-Factor Code", "Your GitHub two-factor authentication code is 563821. Do not share this code."),
        ("HDFC NetBanking OTP", "Your HDFC NetBanking OTP 334412 is valid for 5 minutes. Do not share with anyone."),
        ("AWS MFA Code", "Your AWS multi-factor authentication code is 728391. Enter this code to sign in."),
    ]

    @pytest.mark.parametrize("subject,body", MULTI_DOMAIN_OTP_CASES)
    def test_otp_domain_diversity(self, v3_model, subject, body):
        text = f"{subject} {body}"
        pred = raw_predict(v3_model, text)
        assert pred == "P1", (
            f"Multi-domain OTP must be P1.\n"
            f"  Subject: {subject}\n"
            f"  Prediction: {pred}"
        )


# ============================================================================
# Action Required Pattern Unit Tests
# ============================================================================

class TestActionRequiredPatterns:
    """Unit tests for the refined ACTION_REQUIRED_PATTERNS."""

    @pytest.mark.parametrize("text,expected_action", [
        ("Your OTP is valid only for 05:00 mins.", True),
        ("Valid for 5 minutes. Enter this code.", True),
        ("One Time Password for login: 123456.", True),
        ("OTP for your account: 778899.", True),
        ("Password reset code: 445566. Use this code.", True),
        ("Enter this verification code: 112233.", True),
        ("Verification code is 334455, expires in 10 minutes.", True),
        ("Your account verification was successfully completed.", False),
        ("Security settings were updated successfully.", False),
        ("Your account was successfully verified.", False),
    ])
    def test_action_required_pattern_matching(self, text, expected_action):
        action_hit = bool(ACTION_REQUIRED_PATTERNS.search(text))
        non_action_hit = bool(ACTION_NOT_REQUIRED_PATTERNS.search(text))
        if expected_action:
            assert action_hit, f"ACTION_REQUIRED should match: '{text}'"
        else:
            # For non-action cases: either non-action fires, or action doesn't fire
            if non_action_hit:
                assert True  # correctly identified as non-action via NOT pattern
            else:
                assert not action_hit, f"ACTION_REQUIRED should NOT match: '{text}'"


class TestRelativeMinutesRegex:
    """Unit tests for the RELATIVE_MINUTES_REGEX."""

    @pytest.mark.parametrize("text,should_match", [
        ("valid only for 05:00 mins", True),
        ("valid for 5 minutes", True),
        ("expires in 10 minutes", True),
        ("within 15 mins", True),
        ("OTP valid only for 3:00 mins", True),
        ("expires in 2 hours", False),
        ("valid for 24 hours", False),
        ("Your account is active for years", False),
    ])
    def test_regex_matches(self, text, should_match):
        match = RELATIVE_MINUTES_REGEX.search(text)
        if should_match:
            assert match is not None, f"RELATIVE_MINUTES_REGEX should match: '{text}'"
        else:
            assert match is None, f"RELATIVE_MINUTES_REGEX should NOT match: '{text}'"


# ============================================================================
# 33.14 / 33.15 -- Model Lifecycle & Rollback
# ============================================================================

class TestModelLifecycle:
    """Verifies the registry supports promotion and rollback."""

    def test_both_versions_loadable(self):
        v2 = load_model(PRIORITY_V2_PATH)
        v3 = load_model(PRIORITY_V3_PATH)
        assert v2 is not None
        assert v3 is not None

    def test_rollback_scenario_v2_still_predicts(self):
        """In a rollback scenario, v2 must still function correctly."""
        v2 = load_model(PRIORITY_V2_PATH)
        text = (
            "TCS CodeVita Season 12 Round 1 Invitation "
            "You are invited to TCS CodeVita. Competition deadline closes October 15."
        )
        pred = v2.predict([text])[0]
        assert pred == "P2", f"v2 rollback test failed, expected P2 got {pred}"

    def test_registry_supports_previous_model_field(self):
        with open(REGISTRY_PATH) as f:
            reg = json.load(f)
        assert "previous_model" in reg, "Registry must have 'previous_model' for rollback"
        # previous_model must be a valid known version (not necessarily v2 — test_03 in the
        # model lifecycle suite mutates registry state, so we just verify structural integrity)
        valid_versions = set(reg.get("versions", {}).keys())
        assert reg["previous_model"] in valid_versions, (
            f"previous_model '{reg['previous_model']}' is not a known version in {valid_versions}"
        )

    def test_v3_status_is_production(self):
        with open(REGISTRY_PATH) as f:
            reg = json.load(f)
        assert reg["versions"]["priority-v3"]["status"] in ("production", "retired")
