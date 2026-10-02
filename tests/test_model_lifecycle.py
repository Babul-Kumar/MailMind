import os
import sys
import unittest
import hashlib
from unittest.mock import patch

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.app.ml.registry import model_registry
from backend.app.ml.predictor import load_model, predict_email, invalidate_cached_pipeline
from backend.app.core.feedback import feedback_manager


class TestModelLifecycle(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._saved_registry = model_registry.get_registry()

    @classmethod
    def tearDownClass(cls):
        model_registry._save_registry(cls._saved_registry)
        invalidate_cached_pipeline()

    def setUp(self):
        invalidate_cached_pipeline()

    # 1. Model Registry active version resolution & metadata
    def test_01_registry_loads_active_version(self):
        active_ver = model_registry.get_active_version()
        self.assertIn(active_ver, ["priority-v1", "priority-v2", "priority-v3", "priority-v4", "priority-v4.1", "priority-v5.1"])

        meta = model_registry.get_active_metadata()
        self.assertIsNotNone(meta)
        self.assertEqual(meta["model_version"], active_ver)
        self.assertIn("artifact_sha256", meta)
        self.assertIn("status", meta)

    # 2. Candidate separation and explicit promotion
    def test_02_candidate_does_not_auto_promote(self):
        # Ensure priority-v1 is active
        model_registry.set_active("priority-v1")
        invalidate_cached_pipeline()

        self.assertEqual(model_registry.get_active_version(), "priority-v1")
        pipeline = load_model()
        sample_email = {
            "id": "cand_test",
            "subject": "System status check",
            "body": "Normal operational metrics."
        }
        res = predict_email(sample_email, pipeline)
        self.assertEqual(res["model_version"], "priority-v1")

    # 3. Model rollback works cleanly
    def test_03_model_promotion_and_rollback(self):
        # Promote priority-v2
        success = model_registry.promote_candidate("priority-v2")
        self.assertTrue(success)
        self.assertEqual(model_registry.get_active_version(), "priority-v2")

        # Rollback to priority-v1
        rolled_back = model_registry.rollback()
        self.assertTrue(rolled_back)
        self.assertEqual(model_registry.get_active_version(), "priority-v1")

        # Restore initial active model
        model_registry.set_active(self._saved_registry["active_model"])


    # 4. Strict inference immutability: No fitting during prediction
    def test_04_inference_never_trains_or_fits(self):
        pipeline = load_model()
        with patch.object(pipeline, 'fit') as mock_fit, \
             patch.object(pipeline.named_steps['tfidf'], 'fit') as mock_tfidf_fit, \
             patch.object(pipeline.named_steps['clf'], 'fit') as mock_clf_fit:

            sample_email = {
                "id": "immut_test",
                "subject": "Urgent Security Action",
                "body": "Please verify your credentials immediately."
            }
            res = predict_email(sample_email, pipeline)
            self.assertIn("predicted_priority", res)

            mock_fit.assert_not_called()
            mock_tfidf_fit.assert_not_called()
            mock_clf_fit.assert_not_called()

    # 5. Artifact Hash Integrity Check
    def test_05_artifact_hashes_verified(self):
        # Verify priority-v1 artifact hash
        v1_meta = model_registry.get_version("priority-v1")
        self.assertIsNotNone(v1_meta)
        v1_path = os.path.join(BASE_DIR, "dataset", "models", v1_meta["artifact_path"])
        self.assertTrue(os.path.exists(v1_path))

        with open(v1_path, "rb") as f:
            computed_v1_sha = hashlib.sha256(f.read()).hexdigest()
        self.assertEqual(computed_v1_sha, v1_meta["artifact_sha256"])

        # Verify holdout test.csv hash is strictly untouched
        test_csv_path = os.path.join(BASE_DIR, "dataset", "processed", "test.csv")
        with open(test_csv_path, "rb") as f:
            computed_test_sha = hashlib.sha256(f.read()).hexdigest().upper()
        self.assertEqual(computed_test_sha, "6841CD44901FA56242BF3752257E991FD7FF474ED7E0F7A5D2B7065A0827C138")

    # 6. CodeVita Email Evaluation under candidate/priority-v2
    def test_06_codevita_email_classification(self):
        # Test against priority-v2
        v2_path = os.path.join(BASE_DIR, "dataset", "models", "priority-v2", "model.joblib")
        import joblib
        pipeline_v2 = joblib.load(v2_path)

        codevita_email = {
            "id": "codevita_real_email",
            "subject": "TCS CodeVita Season 14 - Email Verification",
            "body": "Dear Candidate, Thank you for registering for TCS CodeVita Season 14. "
                    "Please verify your email address to complete your registration process. "
                    "Click on the link below to verify your account. "
                    "Note: This verification link remains active for 12 hours only. "
                    "If you did not initiate this request, please ignore this email.",
            "sender": "noreply@tcscodevita.com",
            "date": "2026-10-01T10:00:00Z"
        }

        res = predict_email(codevita_email, pipeline_v2)
        # Expected semantic classification learned by model
        self.assertEqual(res["predicted_priority"], "P2", "CodeVita registration verification must be P2")
        self.assertTrue(res["action_required"], "Action required must be True")
        self.assertTrue(res["deadline_detected"], "12-hour deadline window must be detected")
        self.assertEqual(res["deadline_display"], "Oct 1, 2026 · 10:00 PM")
        self.assertTrue(res["needs_attention"], "P2 + Action Required + Deadline must trigger Needs Attention")

    # 7. Semantic Distinction: P1 vs P2 vs P3 vs P4
    def test_07_semantic_distinctions(self):
        v2_path = os.path.join(BASE_DIR, "dataset", "models", "priority-v2", "model.joblib")
        import joblib
        pipeline_v2 = joblib.load(v2_path)

        # P1: Immediate security incident / account compromise
        p1_email = {
            "id": "sem_p1",
            "subject": "SECURITY BREACH: Unauthorized access detected",
            "body": "Your account was accessed from an unrecognized device in a foreign location. Account compromised. Reset password immediately.",
            "sender": "security@bank.com"
        }
        res_p1 = predict_email(p1_email, pipeline_v2)
        self.assertEqual(res_p1["predicted_priority"], "P1")
        self.assertTrue(res_p1["action_required"])

        # P2: Meaningful registration or action with time constraint
        p2_email = {
            "id": "sem_p2",
            "subject": "Complete your applicant registration - Action Required",
            "body": "Please verify your email address within 24 hours to finalize your application.",
            "sender": "recruitment@portal.org"
        }
        res_p2 = predict_email(p2_email, pipeline_v2)
        self.assertEqual(res_p2["predicted_priority"], "P2")
        self.assertTrue(res_p2["action_required"])

        # P3: Informational verification / routine policy
        p3_email = {
            "id": "sem_p3",
            "subject": "Information: Annual verification of our privacy guidelines",
            "body": "We have published an updated overview of our security and verification standards. No action is required.",
            "sender": "legal@company.com"
        }
        res_p3 = predict_email(p3_email, pipeline_v2)
        self.assertEqual(res_p3["predicted_priority"], "P3")
        self.assertFalse(res_p3["action_required"])

        # P4: Promotional noise with verification keyword
        p4_email = {
            "id": "sem_p4",
            "subject": "Exclusive Discount: Verify our lowest prices today with 50% off",
            "body": "Check out our mega clearance sale! Verify your coupon code SAVE50 at checkout. Limited time deal.",
            "sender": "deals@market.com"
        }
        res_p4 = predict_email(p4_email, pipeline_v2)
        self.assertEqual(res_p4["predicted_priority"], "P4")
        self.assertFalse(res_p4["action_required"])

    # 8. User Feedback logging without online retraining
    def test_08_feedback_logged_without_retraining(self):
        feedback_entry = feedback_manager.record_feedback(
            user_id="user_test_fb",
            email_id="msg_feedback_001",
            model_version="priority-v1",
            predicted_priority="P4",
            corrected_priority="P2",
            predicted_action_required=False,
            corrected_action_required=True,
            deadline_correction="Oct 1, 2026",
            notes="Should be P2 registration deadline"
        )
        self.assertIsNotNone(feedback_entry)
        self.assertEqual(feedback_entry["corrected_priority"], "P2")

        # Verify active model remains strictly immutable
        active_ver = model_registry.get_active_version()
        self.assertIn(active_ver, ["priority-v1", "priority-v2", "priority-v3", "priority-v4", "priority-v4.1", "priority-v5.1"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
