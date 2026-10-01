import unittest
import os
import sys
import pandas as pd
from unittest.mock import patch

# Ensure repo root is on sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.app.ml.predictor import load_model, predict_email
from backend.app.ml.refinement import refine_priority


class TestPriorityRefinement(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        v1_path = os.path.join(BASE_DIR, "dataset", "models", "priority-v1", "model.joblib")
        if os.path.exists(v1_path):
            cls.pipeline = load_model(v1_path)
        else:
            cls.pipeline = load_model()

    # 1. Security alert with action requirement -> P2, action_required: True, topic: security
    def test_01_security_alert_with_action(self):
        email_data = {
            "id": "sec_test_01",
            "subject": "Security alert",
            "body": "You allowed Google Drive for desktop access to some of your Google Account data. "
                    "If you didn't allow this, someone else may be trying to access your account. "
                    "Take a moment now to check your account activity and secure your account. "
                    "Visit google.com or contact support via email. View image here.",
            "sender": "no-reply@accounts.google.com"
        }
        res = predict_email(email_data, self.pipeline)
        self.assertEqual(res["model_priority"], "P4")
        self.assertEqual(res["final_priority"], "P2")
        self.assertEqual(res["predicted_priority"], "P2")
        self.assertEqual(res["topic"], "security")
        self.assertTrue(res["action_required"])
        self.assertTrue(res["refinement_applied"])
        self.assertIn("Security verification", res["refinement_reason"])
        self.assertGreater(len(res["refinement_signals"]), 0)

    # 2. Urgent account compromise / lockout -> P1, action_required: True, topic: security
    def test_02_security_critical_compromise(self):
        email_data = {
            "id": "sec_test_02",
            "subject": "Critical Security Alert: Suspicious sign-in detected",
            "body": "We detected unauthorized access to your account from an unknown device. "
                    "Your account has been compromised. Please immediately reset your password now "
                    "and secure your account.",
            "sender": "security@service.com"
        }
        res = predict_email(email_data, self.pipeline)
        self.assertEqual(res["final_priority"], "P1")
        self.assertEqual(res["predicted_priority"], "P1")
        self.assertEqual(res["topic"], "security")
        self.assertTrue(res["action_required"])
        self.assertTrue(res["refinement_applied"])
        self.assertIn("Critical security alert", res["refinement_reason"])

    # 3. Informational security update / policy -> P3, action_required: False, topic: security
    def test_03_security_informational_notice(self):
        email_data = {
            "id": "sec_test_03",
            "subject": "Notice: Privacy policy update",
            "body": "We are updating our privacy policy and terms of service update for all active accounts. "
                    "These updates provide greater transparency. No action is required on your part.",
            "sender": "privacy@company.com"
        }
        res = predict_email(email_data, self.pipeline)
        self.assertEqual(res["final_priority"], "P3")
        self.assertEqual(res["predicted_priority"], "P3")
        self.assertEqual(res["topic"], "security")
        self.assertFalse(res["action_required"])
        self.assertTrue(res["refinement_applied"])
        self.assertIn("Routine security update", res["refinement_reason"])

    # 4. Security promotional / marketing -> P4 (Not elevated), action_required: False
    def test_04_security_promotional_not_elevated(self):
        email_data = {
            "id": "sec_test_04",
            "subject": "Exclusive Deal: Antivirus Security Suite 50% off",
            "body": "Protect your digital security today! Get a flat discount of 50% off all security tools. "
                    "Limited time offer. Buy now and save $40.",
            "sender": "sales@antivirusdeals.com"
        }
        res = predict_email(email_data, self.pipeline)
        self.assertEqual(res["final_priority"], "P4")
        self.assertEqual(res["predicted_priority"], "P4")
        self.assertFalse(res["action_required"])
        self.assertFalse(res["refinement_applied"])

    # 5. Academic assignment with submission deadline -> P2, action_required: True, topic: academic
    def test_05_academic_assignment_with_deadline(self):
        email_data = {
            "id": "acad_test_05",
            "subject": "Deep Learning for NLP - Week 11 content is live now!!",
            "body": "Dear Candidates, Assignment 11 for Week 11 is also released and can be accessed from the portal. "
                    "The deadline for submitting Assignment 11 is Wednesday at 23:59 IST. "
                    "Please submit before the deadline. Late submissions will not be accepted.",
            "sender": "onlinecourses@nptel.iitm.ac.in"
        }
        res = predict_email(email_data, self.pipeline)
        self.assertEqual(res["final_priority"], "P2")
        self.assertEqual(res["predicted_priority"], "P2")
        self.assertEqual(res["topic"], "academic")
        self.assertTrue(res["action_required"])

    # 6. Academic assignment solution released (no deadline) -> P3, action_required: False, topic: academic
    def test_06_academic_solution_released(self):
        email_data = {
            "id": "acad_test_06",
            "subject": "Deep Learning for NLP - Assignment 10 Solution Released",
            "body": "Dear Candidates, Assignment 10 Solution has been released in the course portal. "
                    "The solution is available in the course outline tab under Week 10. "
                    "You are receiving this email because you subscribed. To unsubscribe click here.",
            "sender": "onlinecourses@nptel.iitm.ac.in"
        }
        res = predict_email(email_data, self.pipeline)
        self.assertEqual(res["final_priority"], "P3")
        self.assertEqual(res["predicted_priority"], "P3")
        self.assertEqual(res["topic"], "academic")
        self.assertFalse(res["action_required"])
        self.assertTrue(res["refinement_applied"])
        self.assertIn("Academic informational update", res["refinement_reason"])

    # 7. Generic course promotion / marketing -> P4 (Not elevated), action_required: False
    def test_07_course_promotion_not_elevated(self):
        email_data = {
            "id": "acad_test_07",
            "subject": "Explore 50+ New Computer Science Courses",
            "body": "Upskill with our top rated faculty. Flat discount of 40% on all professional certifications. "
                    "Browse courses and enroll today. Limited time offer!",
            "sender": "offers@onlinecoursehub.com"
        }
        res = predict_email(email_data, self.pipeline)
        self.assertEqual(res["final_priority"], "P4")
        self.assertEqual(res["predicted_priority"], "P4")
        self.assertFalse(res["action_required"])
        self.assertFalse(res["refinement_applied"])

    # 8. Marketing email with keyword "security" -> P4 (Not elevated), action_required: False
    def test_08_marketing_with_keyword_security(self):
        email_data = {
            "id": "mkt_test_08",
            "subject": "Secure your dream vacation home with special rates",
            "body": "Enjoy total financial security and convenience with our summer travel financing. "
                    "Limited time offer: get 20% off all booking fees. Shop now!",
            "sender": "travel@promotions.com"
        }
        res = predict_email(email_data, self.pipeline)
        self.assertEqual(res["final_priority"], "P4")
        self.assertEqual(res["predicted_priority"], "P4")
        self.assertFalse(res["action_required"])
        self.assertFalse(res["refinement_applied"])

    # 9. Empty email handling
    def test_09_empty_email_resilience(self):
        email_data = {
            "id": "empty_test_09",
            "subject": "",
            "body": "",
            "sender": ""
        }
        res = predict_email(email_data, self.pipeline)
        self.assertEqual(res["final_priority"], "P4")
        self.assertEqual(res["predicted_priority"], "P4")
        self.assertEqual(res["model_priority"], "P4")
        self.assertEqual(res["topic"], "other")
        self.assertFalse(res["action_required"])
        self.assertFalse(res["refinement_applied"])
        self.assertIsNone(res["refinement_reason"])
        self.assertEqual(res["refinement_signals"], [])

    # 10. Verification that model weights are strictly unmodified
    def test_10_model_weights_unmodified(self):
        clf = self.pipeline.named_steps["clf"]
        tfidf = self.pipeline.named_steps["tfidf"]

        self.assertEqual(list(clf.classes_), ["P1", "P2", "P3", "P4"])
        self.assertGreater(len(tfidf.vocabulary_), 50000)
        self.assertEqual(clf.coef_.shape[0], 4)
        self.assertEqual(clf.coef_.shape[1], len(tfidf.vocabulary_))

        test_csv_path = os.path.join(BASE_DIR, "dataset", "processed", "test.csv")
        df_test = pd.read_csv(test_csv_path)
        self.assertEqual(len(df_test), 300)


if __name__ == "__main__":
    unittest.main(verbosity=2)
