import unittest
import os
import sys
import pandas as pd
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# Ensure repo root is on sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.app.main import app
from backend.app.ml.predictor import load_model, predict_email


from backend.app.core.config import TOKEN_FILE, GMAIL_SCOPES
from backend.app.core.session import session_manager
from google.oauth2.credentials import Credentials


class TestDashboardAPI(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        if os.path.exists(TOKEN_FILE):
            try:
                creds = Credentials.from_authorized_user_file(TOKEN_FILE, GMAIL_SCOPES)
                session = session_manager.create_session(
                    user_id="test_dashboard_user",
                    email="dev@mailmind.local",
                    credentials=creds
                )
                cls.client.cookies.set("mailmind_session", session.session_id)
            except Exception as e:
                print(f"Warning: Could not create test session in test_dashboard_api: {e}")

    # 1. Dashboard Backend Health Check
    def test_01_health_endpoint(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("status"), "healthy")

    # 2. Frozen Model Metadata Endpoint
    def test_02_model_info_endpoint(self):
        response = self.client.get("/api/model-info")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("model_name"), "TF-IDF + Logistic Regression")
        self.assertEqual(data.get("model_state"), "Strictly Frozen")
        self.assertGreater(data.get("vocabulary_features", 0), 50000)
        self.assertEqual(data.get("classes"), ["P1", "P2", "P3", "P4"])

    # 3. Gmail Profile Endpoint
    @patch("backend.app.api.routes_gmail.get_user_gmail_service")
    def test_03_gmail_profile_endpoint(self, mock_get_svc):
        mock_svc = MagicMock()
        mock_svc.users().getProfile().execute.return_value = {
            "emailAddress": "dev@mailmind.local",
            "messagesTotal": "150",
            "threadsTotal": "80"
        }
        mock_get_svc.return_value = mock_svc

        response = self.client.get("/api/profile")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("email_address", data)
        self.assertIn("messages_total", data)
        self.assertGreater(data["messages_total"], 0)
        self.assertIn("READ-ONLY", data.get("access_scope", ""))

    # 4. Email Ingestion & Live Priority Inference Endpoint
    @patch("backend.app.api.routes_emails.get_user_gmail_service")
    @patch("backend.app.api.routes_emails.list_message_ids")
    @patch("backend.app.api.routes_emails._fetch_single_message_safe")
    def test_04_emails_endpoint_live_inference(self, mock_fetch, mock_list, mock_get_svc):
        mock_svc = MagicMock()
        mock_svc.users().getProfile().execute.return_value = {
            "emailAddress": "dev@mailmind.local",
            "messagesTotal": "150",
            "threadsTotal": "80"
        }
        mock_get_svc.return_value = mock_svc
        mock_list.return_value = {
            "messages": [{"id": f"msg_test_{i}"} for i in range(5)],
            "nextPageToken": None
        }
        mock_fetch.side_effect = lambda svc, mid: {
            "id": mid,
            "subject": f"Test email {mid}",
            "sender": "sender@test.com",
            "body": "Here is the body content for testing live priority inference.",
            "date": "2026-10-01T12:00:00Z"
        }

        response = self.client.get("/api/emails?max_emails=5")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("status"), "success")
        self.assertIn("emails", data)
        self.assertIn("stats", data)
        self.assertIn("profile", data)

        emails = data["emails"]
        self.assertLessEqual(len(emails), 5)
        if emails:
            sample = emails[0]
            self.assertIn("email_id", sample)
            self.assertIn("subject", sample)
            self.assertIn("sender", sample)
            self.assertIn("predicted_priority", sample)
            self.assertIn(sample["predicted_priority"], ["P1", "P2", "P3", "P4"])
            self.assertIn("confidence", sample)
            self.assertIn("probabilities", sample)
            self.assertIn("explanation", sample)
            self.assertIn("action_required", sample)
            self.assertIn("topic", sample)

        stats = data["stats"]
        self.assertEqual(stats["total_analyzed"], len(emails))
        self.assertIn("counts", stats)
        self.assertIn("percentages", stats)
        self.assertIn("average_confidence", stats)
        self.assertIn("refined_count", stats)
        self.assertIn("refinement_rate", stats)

    # 5. Parameter Validation (max_emails boundaries)
    def test_05_emails_endpoint_parameter_validation(self):
        # max_emails > 100 should return 422 Unprocessable Entity
        res_high = self.client.get("/api/emails?max_emails=150")
        self.assertEqual(res_high.status_code, 422)

        # max_emails < 1 should return 422
        res_low = self.client.get("/api/emails?max_emails=0")
        self.assertEqual(res_low.status_code, 422)

    # 6. Static Asset Delivery (HTML, CSS, JS)
    def test_06_static_dashboard_files_served(self):
        # Main Dashboard Page
        res_html = self.client.get("/")
        self.assertEqual(res_html.status_code, 200)
        self.assertIn("text/html", res_html.headers.get("content-type", ""))
        self.assertIn("Email Priority Intelligence", res_html.text)

        # Built Frontend Assets Delivery
        assets_dir = os.path.join(BASE_DIR, "frontend", "dist", "assets")
        self.assertTrue(os.path.exists(assets_dir), "Built frontend assets must exist")
        css_files = [f for f in os.listdir(assets_dir) if f.endswith(".css")]
        js_files = [f for f in os.listdir(assets_dir) if f.endswith(".js")]
        self.assertGreater(len(css_files), 0, "Built CSS bundle must exist")
        self.assertGreater(len(js_files), 0, "Built JS bundle must exist")

        res_css = self.client.get(f"/assets/{css_files[0]}")
        self.assertEqual(res_css.status_code, 200)
        self.assertIn("text/css", res_css.headers.get("content-type", ""))

        res_js = self.client.get(f"/assets/{js_files[0]}")
        self.assertEqual(res_js.status_code, 200)
        self.assertIn("javascript", res_js.headers.get("content-type", ""))

    # 7. Model-Grounded Explanation Verification
    def test_07_model_explanation_logic(self):
        pipeline = load_model()
        sample_email = {
            "id": "exp_test_1",
            "subject": "Urgent deadline approaching for report",
            "body": "Please submit your review immediately."
        }
        pred = predict_email(sample_email, pipeline)
        self.assertIn("explanation", pred)
        self.assertIn("Model classified this email as", pred["explanation"])

    # 8. Critical Safeguard: Verify NO .fit() or .fit_transform() is Called During Inference
    @patch("backend.app.api.routes_emails.get_user_gmail_service")
    @patch("backend.app.api.routes_emails.list_message_ids")
    @patch("backend.app.api.routes_emails._fetch_single_message_safe")
    def test_08_no_fit_called_in_dashboard(self, mock_fetch, mock_list, mock_get_svc):
        mock_svc = MagicMock()
        mock_svc.users().getProfile().execute.return_value = {
            "emailAddress": "dev@mailmind.local",
            "messagesTotal": "150"
        }
        mock_get_svc.return_value = mock_svc
        mock_list.return_value = {
            "messages": [{"id": f"msg_fit_{i}"} for i in range(3)],
            "nextPageToken": None
        }
        mock_fetch.side_effect = lambda svc, mid: {
            "id": mid,
            "subject": f"Test email {mid}",
            "sender": "sender@test.com",
            "body": "Here is the body content for testing immutability.",
            "date": "2026-10-01T12:00:00Z"
        }

        pipeline = load_model()
        with patch.object(pipeline, 'fit') as mock_fit, \
             patch.object(pipeline.named_steps['tfidf'], 'fit') as mock_tfidf_fit, \
             patch.object(pipeline.named_steps['tfidf'], 'fit_transform') as mock_tfidf_fit_transform, \
             patch.object(pipeline.named_steps['clf'], 'fit') as mock_clf_fit:

            # Make request to /api/emails
            response = self.client.get("/api/emails?max_emails=3")
            self.assertEqual(response.status_code, 200)

            mock_fit.assert_not_called()
            mock_tfidf_fit.assert_not_called()
            mock_tfidf_fit_transform.assert_not_called()
            mock_clf_fit.assert_not_called()

    # 9. Graceful Error Handling When Gmail Service Fails
    @patch("backend.app.api.routes_emails.get_user_gmail_service")
    def test_09_gmail_error_handling(self, mock_get_svc):
        mock_get_svc.side_effect = RuntimeError("Simulated Gmail API Timeout")
        response = self.client.get("/api/emails?max_emails=5")
        self.assertEqual(response.status_code, 502)
        data = response.json()
        self.assertIn("detail", data)
        self.assertIn("Simulated Gmail API Timeout", data["detail"])

    # 10. Frozen Datasets & Baseline Model Integrity
    def test_10_frozen_artifacts_integrity(self):
        test_csv_path = os.path.join(BASE_DIR, "dataset", "processed", "test.csv")
        self.assertTrue(os.path.exists(test_csv_path), "test.csv must exist")
        df_test = pd.read_csv(test_csv_path)
        self.assertEqual(len(df_test), 300, "Held-out test set must remain 300 rows")
        self.assertEqual(df_test['final_label'].isnull().sum(), 0, "No missing labels in test.csv")

        model_path = os.path.join(BASE_DIR, "dataset", "models", "tfidf_logistic_baseline.joblib")
        self.assertTrue(os.path.exists(model_path), "Model artifact must exist")


if __name__ == "__main__":
    unittest.main(verbosity=2)
