import unittest
import os
import sys
import hashlib
import pandas as pd
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# Ensure repo root is on sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.app.main import app
from backend.app.ml.predictor import (
    load_model,
    predict_email,
    predict_batch,
    format_email_text,
)
from backend.app.ml.explanations import explain_prediction
from backend.app.ml.priority import PRIORITY_MAPPING


class TestPhase28Hardening(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.pipeline = load_model()

    # 1. Security: Credentials and Tokens Ignored in Git
    def test_01_gitignore_security(self):
        gitignore_path = os.path.join(BASE_DIR, ".gitignore")
        self.assertTrue(os.path.exists(gitignore_path), ".gitignore must exist")
        with open(gitignore_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("google_auth/credentials.json", content)
        self.assertIn("google_auth/token.json", content)
        self.assertIn("google_auth/sessions/", content)
        self.assertIn(".env", content)

    # 2. Security: No Sensitive Tokens Leaked via API & Strict Auth
    def test_02_no_tokens_leaked_in_profile(self):
        # Unauthenticated request must return 401
        res_unauth = self.client.get("/api/profile")
        self.assertEqual(res_unauth.status_code, 401)

        # Authenticated request returns profile with zero leaked tokens
        from backend.app.core.session import session_manager
        session = session_manager.create_session(
            email="test_hardening@mailmind.local",
            user_id="user_harden_999",
            credentials={"access_token": "secret_token_123", "refresh_token": "secret_refresh_456"}
        )
        mock_service = MagicMock()
        mock_service.users().getProfile().execute.return_value = {
            "emailAddress": "test_hardening@mailmind.local",
            "messagesTotal": 100,
            "threadsTotal": 50,
        }
        with patch("backend.app.api.routes_gmail.get_user_gmail_service", return_value=mock_service):
            res = self.client.get("/api/profile", cookies={"mailmind_session": session.session_id})
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertNotIn("token", data)
            self.assertNotIn("refresh_token", data)
            self.assertNotIn("client_id", data)
            self.assertNotIn("client_secret", data)
            self.assertIn("email_address", data)
            self.assertIn("READ-ONLY", data.get("access_scope", ""))

    # 3. Security: CORS Not Unnecessarily Permissive
    def test_03_cors_hardening(self):
        # Origin from unauthorized domain
        res = self.client.options(
            "/api/health",
            headers={"Origin": "https://malicious-site.com", "Access-Control-Request-Method": "GET"}
        )
        allow_origin = res.headers.get("access-control-allow-origin", "")
        self.assertNotEqual(allow_origin, "*", "CORS should not allow arbitrary wildcard origins")

    # 4. Security & API Quality: Query Parameter Validation & Error Formatting
    def test_04_query_parameter_bounds(self):
        # max_emails > 100
        res = self.client.get("/api/emails?max_emails=101")
        self.assertEqual(res.status_code, 422)
        err = res.json()
        self.assertEqual(err.get("status"), "error")
        self.assertIn("Parameter validation error", err.get("message", ""))

        # max_emails < 1
        res_zero = self.client.get("/api/emails?max_emails=0")
        self.assertEqual(res_zero.status_code, 422)
        self.assertEqual(res_zero.json().get("status"), "error")

        # query string too long (> 200 chars)
        long_query = "x" * 250
        res_long = self.client.get(f"/api/emails?query={long_query}")
        self.assertEqual(res_long.status_code, 422)
        self.assertEqual(res_long.json().get("status"), "error")

    # 5. UX & Confidence: Model Confidence Terminology & Low Confidence Advisory
    def test_05_confidence_ux_and_advisory(self):
        # Normal email prediction
        sample = {
            "id": "conf_1",
            "subject": "Quick project review requested",
            "body": "Please review this document when you have a moment."
        }
        res = predict_email(sample, self.pipeline)
        self.assertIn("model confidence", res["explanation"])
        self.assertIn("confidence_level", res)
        self.assertIn(res["confidence_level"], ["High", "Moderate", "Low"])

        # Low confidence advisory check
        explanation, _ = explain_prediction(self.pipeline, "casual chit chat hello", "P2", 0.35)
        self.assertIn("Model confidence is relatively low", explanation)

    # 6. Explanation Quality: Strictly Model-Grounded Signals
    def test_06_model_grounded_feature_signals(self):
        sample = {
            "id": "sig_1",
            "subject": "Emergency outage: server system down immediately",
            "body": "Critical failure in database cluster."
        }
        res = predict_email(sample, self.pipeline)
        self.assertIn("top_signals", res)
        signals = res["top_signals"]
        self.assertIsInstance(signals, list)
        for s in signals:
            self.assertIn("term", s)
            self.assertIn("weight", s)
            self.assertGreater(s["weight"], 0)

    # 7. Performance: Model Pre-Warmed and Health Endpoint
    def test_07_health_pre_warmed_model(self):
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data.get("status"), "healthy")
        self.assertIn("timestamp", data)

    # 8. Resilience: Malformed or Missing Email Fields Handled Gracefully
    def test_08_malformed_email_resilience(self):
        test_cases = [
            {"id": "m1"},  # missing subject, body, sender
            {"id": "m2", "subject": None, "body": None},
            {"id": "m3", "subject": "", "body": ""},
            {"id": "m4", "subject": "   ", "body": "   "}
        ]
        for em in test_cases:
            res = predict_email(em, self.pipeline)
            self.assertIn(res["predicted_priority"], ["P1", "P2", "P3", "P4"])
            self.assertEqual(res["predicted_priority"], "P4")
            self.assertGreater(res["confidence"], 0)

    # 9. Critical Safeguard: Verify Zero Retraining During Dashboard Calls
    def test_09_no_fit_called_under_any_condition(self):
        with patch.object(self.pipeline, 'fit') as mock_fit,              patch.object(self.pipeline.named_steps['tfidf'], 'fit') as mock_tfidf_fit,              patch.object(self.pipeline.named_steps['tfidf'], 'fit_transform') as mock_tfidf_fit_transform,              patch.object(self.pipeline.named_steps['clf'], 'fit') as mock_clf_fit:

            predict_batch([{"subject": "Urgent", "body": "Respond"}], pipeline=self.pipeline)

            mock_fit.assert_not_called()
            mock_tfidf_fit.assert_not_called()
            mock_tfidf_fit_transform.assert_not_called()
            mock_clf_fit.assert_not_called()

    # 10. Frozen Datasets & Baseline Model Integrity
    def test_10_frozen_artifacts_integrity(self):
        test_csv_path = os.path.join(BASE_DIR, "dataset", "processed", "test.csv")
        self.assertTrue(os.path.exists(test_csv_path), "test.csv must exist")
        df_test = pd.read_csv(test_csv_path)
        self.assertEqual(len(df_test), 300, "Held-out test set must remain 300 rows")
        self.assertEqual(df_test['final_label'].isnull().sum(), 0, "No missing labels in test.csv")

        # Verify class distribution in test set
        counts = df_test['final_label'].value_counts()
        self.assertEqual(counts['P1'], 8)
        self.assertEqual(counts['P2'], 143)
        self.assertEqual(counts['P3'], 68)
        self.assertEqual(counts['P4'], 81)

        model_path = os.path.join(BASE_DIR, "dataset", "models", "tfidf_logistic_baseline.joblib")
        self.assertTrue(os.path.exists(model_path), "Model artifact must exist")


if __name__ == "__main__":
    unittest.main(verbosity=2)
