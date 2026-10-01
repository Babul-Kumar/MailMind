import unittest
import base64
import os
import sys
import pandas as pd
from unittest.mock import MagicMock, patch

# Ensure repo root is on sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.app.gmail.service import get_gmail_service
from backend.app.gmail.client import (
    get_profile,
    list_message_ids,
    get_message,
)
from backend.app.gmail.parser import (
    parse_message,
    decode_mime_header,
    clean_html_to_text,
    decode_payload_data,
    extract_body_from_payload,
)
from backend.app.ml.predictor import (
    load_model,
    predict_email,
    predict_batch,
    format_email_text,
)
from backend.app.ml.explanations import explain_prediction
from backend.app.ml.priority import PRIORITY_MAPPING


class TestGmailPipeline(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.model = load_model()

    # 1 & 2. Gmail Authentication and Profile Retrieval
    def test_01_gmail_auth_and_profile(self):
        try:
            service = get_gmail_service()
            profile = get_profile(service)
        except PermissionError as e:
            self.skipTest(f"Developer Gmail token revoked or expired: {e}")
        except Exception as e:
            if "invalid_grant" in str(e):
                self.skipTest(f"Developer Gmail token revoked by Google: {e}")
            raise
        self.assertIsNotNone(service, "Gmail service instance should not be None")
        self.assertIn("emailAddress", profile)
        self.assertIn("messagesTotal", profile)
        self.assertGreater(int(profile["messagesTotal"]), 0)

    # 3 & 4. Message Listing and Pagination
    def test_02_message_listing_and_pagination(self):
        try:
            service = get_gmail_service()
            res_page1 = list_message_ids(service, max_results=3)
        except PermissionError as e:
            self.skipTest(f"Developer Gmail token revoked or expired: {e}")
        except Exception as e:
            if "invalid_grant" in str(e):
                self.skipTest(f"Developer Gmail token revoked by Google: {e}")
            raise
        self.assertIn("messages", res_page1)
        self.assertLessEqual(len(res_page1["messages"]), 3)

        next_token = res_page1.get("nextPageToken")
        if next_token:
            res_page2 = list_message_ids(service, max_results=3, page_token=next_token)
            self.assertIn("messages", res_page2)
            # Ensure different messages retrieved
            id1 = [m["id"] for m in res_page1["messages"]]
            id2 = [m["id"] for m in res_page2["messages"]]
            self.assertTrue(set(id1).isdisjoint(set(id2)), "Paginated message IDs should be disjoint")

    # 5 & 8. MIME Parsing: Plain Text Email
    def test_03_mime_parsing_plain(self):
        sample_text = "Please submit the quarterly financial report by 5 PM today."
        encoded_data = base64.urlsafe_b64encode(sample_text.encode("utf-8")).decode("ascii")

        raw_msg = {
            "id": "msg_plain_1",
            "threadId": "th_1",
            "snippet": "Quarterly report...",
            "labelIds": ["INBOX"],
            "payload": {
                "mimeType": "text/plain",
                "headers": [
                    {"name": "Subject", "value": "Urgent: Quarterly Report Due"},
                    {"name": "From", "value": "Alice Manager <alice@company.com>"},
                    {"name": "To", "value": "bob@company.com"},
                    {"name": "Date", "value": "Thu, 25 Sep 2026 10:00:00 +0000"}
                ],
                "body": {"data": encoded_data}
            }
        }

        parsed = parse_message(raw_msg)
        self.assertEqual(parsed["id"], "msg_plain_1")
        self.assertEqual(parsed["subject"], "Urgent: Quarterly Report Due")
        self.assertEqual(parsed["sender"], "Alice Manager <alice@company.com>")
        self.assertEqual(parsed["body"], sample_text)

    # 9. MIME Parsing: Multipart / Alternative with HTML fallback
    def test_04_mime_parsing_multipart(self):
        plain_text = "Plain text version of meeting details."
        html_markup = "<html><body><h1>Meeting Details</h1><p>Join link below.</p></body></html>"

        plain_b64 = base64.urlsafe_b64encode(plain_text.encode("utf-8")).decode("ascii")
        html_b64 = base64.urlsafe_b64encode(html_markup.encode("utf-8")).decode("ascii")

        raw_msg = {
            "id": "msg_multi_1",
            "threadId": "th_multi_1",
            "snippet": "Meeting details...",
            "labelIds": ["INBOX"],
            "payload": {
                "mimeType": "multipart/alternative",
                "headers": [
                    {"name": "Subject", "value": "Sprint Planning Sync"},
                    {"name": "From", "value": "lead@company.com"}
                ],
                "parts": [
                    {
                        "mimeType": "text/plain",
                        "body": {"data": plain_b64}
                    },
                    {
                        "mimeType": "text/html",
                        "body": {"data": html_b64}
                    }
                ]
            }
        }

        parsed = parse_message(raw_msg)
        # Should prefer text/plain
        self.assertIn("Plain text version", parsed["body"])

    # 6. Missing Subject Handling
    def test_05_missing_subject(self):
        raw_msg = {
            "id": "msg_no_subj",
            "payload": {
                "headers": [{"name": "From", "value": "unknown@domain.com"}],
                "body": {"data": ""}
            }
        }
        parsed = parse_message(raw_msg)
        self.assertEqual(parsed["subject"], "(No Subject)")

    # 7. Missing Body Handling
    def test_06_missing_body(self):
        raw_msg = {
            "id": "msg_no_body",
            "snippet": "This is a fallback snippet",
            "payload": {
                "headers": [{"name": "Subject", "value": "Quick question"}],
                "body": {"data": ""}
            }
        }
        parsed = parse_message(raw_msg)
        self.assertEqual(parsed["body"], "This is a fallback snippet")

    # 10. Model Loading and Architecture Inspection
    def test_07_model_loading_and_attributes(self):
        pipeline = load_model()
        self.assertIn('tfidf', pipeline.named_steps)
        self.assertIn('clf', pipeline.named_steps)
        self.assertEqual(list(pipeline.classes_), ['P1', 'P2', 'P3', 'P4'])
        vocab = pipeline.named_steps['tfidf'].vocabulary_
        self.assertGreater(len(vocab), 50000)

    # 11 & 12. Prediction and Probability Output
    def test_08_prediction_and_probability_output(self):
        email_sample = {
            "id": "msg_pred_test",
            "date": "Today",
            "sender": "noreply@deals.com",
            "subject": "Flash 70% discount sale ending soon!",
            "body": "Buy now and save huge discount today only."
        }
        result = predict_email(email_sample, self.model)
        self.assertIn("predicted_priority", result)
        self.assertIn(result["predicted_priority"], ['P1', 'P2', 'P3', 'P4'])
        self.assertIn("priority_name", result)
        self.assertIn("confidence", result)
        self.assertIn("probabilities", result)
        self.assertIn("explanation", result)

        probs = result["probabilities"]
        self.assertAlmostEqual(sum(probs.values()), 1.0, places=2)
        self.assertEqual(result["predicted_priority"], "P4")

    # 13. Malformed / Empty Email Handling
    def test_09_malformed_and_empty_email(self):
        empty_email = {"id": "empty_1", "subject": "", "body": ""}
        result = predict_email(empty_email, self.model)
        self.assertEqual(result["predicted_priority"], "P4")
        self.assertGreater(result["confidence"], 0.0)

    # Critical Safeguard: Verify model.fit is NEVER called during inference
    def test_10_no_fit_called_in_inference_path(self):
        pipeline = load_model()
        with patch.object(pipeline, 'fit') as mock_fit, \
             patch.object(pipeline.named_steps['tfidf'], 'fit') as mock_tfidf_fit, \
             patch.object(pipeline.named_steps['tfidf'], 'fit_transform') as mock_tfidf_fit_transform, \
             patch.object(pipeline.named_steps['clf'], 'fit') as mock_clf_fit:

            sample_batch = [
                {"id": "m1", "subject": "Meeting", "body": "Discussion at 2pm"},
                {"id": "m2", "subject": "Promo", "body": "Buy discount items"}
            ]
            predict_batch(sample_batch, pipeline=pipeline)

            mock_fit.assert_not_called()
            mock_tfidf_fit.assert_not_called()
            mock_tfidf_fit_transform.assert_not_called()
            mock_clf_fit.assert_not_called()

    # Critical Safeguard: Verify Frozen Datasets and Artifacts Remain Intact
    def test_11_frozen_artifacts_integrity(self):
        test_csv_path = os.path.join(BASE_DIR, "dataset", "processed", "test.csv")
        self.assertTrue(os.path.exists(test_csv_path), "test.csv must exist")
        df_test = pd.read_csv(test_csv_path)
        self.assertEqual(len(df_test), 300, "Held-out test set must contain exactly 300 rows")
        self.assertEqual(df_test['final_label'].isnull().sum(), 0, "No missing labels in test.csv")

        model_path = os.path.join(BASE_DIR, "dataset", "models", "tfidf_logistic_baseline.joblib")
        self.assertTrue(os.path.exists(model_path), "Model artifact must exist")


if __name__ == "__main__":
    unittest.main(verbosity=2)
