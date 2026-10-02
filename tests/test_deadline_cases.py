import unittest
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.app.ml.refinement import extract_deadline, determine_action_reason, refine_priority
from backend.app.ml.predictor import load_model, predict_email

class TestDeadlineCases(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pipeline = load_model()

    # Section 29 Cases
    def test_29_october_5(self):
        res = extract_deadline("", "Submission closes on October 5.", "Wed, 30 Sep 2026 12:00:00 +0000")
        self.assertTrue(res["deadline_detected"])
        self.assertEqual(res["deadline_precision"], "DATE")
        self.assertIn("Oct 5", res["deadline_display"])

    def test_29_oct_5_with_time(self):
        res = extract_deadline("", "Submit before Oct 5 at 11:59 PM.", "Wed, 30 Sep 2026 12:00:00 +0000")
        self.assertTrue(res["deadline_detected"])
        self.assertEqual(res["deadline_precision"], "DATETIME")
        self.assertIn("11:59 PM", res["deadline_display"])

    def test_29_relative_days(self):
        res = extract_deadline("", "Your inactive projects will be deleted in 5 days.", "Wed, 30 Sep 2026 12:00:00 +0000")
        self.assertTrue(res["deadline_detected"])
        self.assertEqual(res["deadline_precision"], "DATE")
        self.assertIn("Due in 5 days", res["deadline_display"])

    def test_29_closes_tomorrow(self):
        res = extract_deadline("", "Registration closes tomorrow.", "Wed, 30 Sep 2026 12:00:00 +0000")
        self.assertTrue(res["deadline_detected"])
        self.assertEqual(res["deadline_precision"], "DATE")
        self.assertIn("Due tomorrow", res["deadline_display"])

    def test_29_iso_format(self):
        res = extract_deadline("", "Kaggriculture ends in 24 hours (2026-09-30 23:59PM UTC)", "Wed, 30 Sep 2026 12:00:00 +0000")
        self.assertTrue(res["deadline_detected"])
        self.assertEqual(res["deadline_precision"], "DATETIME")
        self.assertIn("Sep 30, 2026", res["deadline_display"])

    # Section 30 Cases
    def test_30_case1_neon(self):
        email_data = {
            "id": "neon_01",
            "subject": "Action Required: Your inactive Neon Azure projects will be deleted in 5 days",
            "body": "Migrate or reconnect before October 5, 2026 to prevent permanent deletion.",
            "sender": "Neon Team <azure-deprecation@neon.tech>",
            "date": "Wed, 30 Sep 2026 18:32:54 +0000"
        }
        res = predict_email(email_data, self.pipeline)
        self.assertEqual(res["final_priority"], "P2")
        self.assertTrue(res["action_required"])
        self.assertEqual(res["action_reason"], "Service action")
        self.assertTrue(res["deadline_detected"])
        self.assertIn("Oct 5", res["deadline_display"])

    def test_30_case2_google_security(self):
        email_data = {
            "id": "google_01",
            "subject": "Security alert",
            "body": "Take a moment now to check your account activity and secure your account.",
            "sender": "Google <no-reply@accounts.google.com>",
            "date": "Thu, 01 Oct 2026 11:30:11 GMT"
        }
        res = predict_email(email_data, self.pipeline)
        self.assertEqual(res["final_priority"], "P2")
        self.assertTrue(res["action_required"])
        self.assertEqual(res["action_reason"], "Account security action")
        self.assertFalse(res["deadline_detected"])

    def test_30_case3_nptel(self):
        email_data = {
            "id": "nptel_01",
            "subject": "Assignment 10 Solution Released",
            "body": "Dear Learner, The solution for Assignment 10 has been released on the portal.",
            "sender": "onlinecourses@nptel.iitm.ac.in",
            "date": "Thu, 01 Oct 2026 10:00:00 GMT"
        }
        res = predict_email(email_data, self.pipeline)
        self.assertEqual(res["final_priority"], "P3")
        self.assertFalse(res["action_required"])
        self.assertFalse(res["deadline_detected"])

    def test_30_case4_kaggle_priority_separation(self):
        # Deadline must NOT change priority to P2! Kaggle remains P4!
        email_data = {
            "id": "kaggle_01",
            "subject": "Competition deadline approaching",
            "body": "Kaggriculture ends in 24 hours (2026-09-30 23:59PM UTC). Competition submissions close September 30. You received this email because you entered this competition. Unsubscribe from this notification.",
            "sender": "Kaggle <kaggle-noreply@google.com>",
            "date": "Tue, 29 Sep 2026 15:20:19 -0700"
        }
        res = predict_email(email_data, self.pipeline)
        self.assertIn(res["model_priority"], ["P3", "P4"])
        self.assertIn(res["final_priority"], ["P3", "P4"])
        self.assertTrue(res["action_required"])
        self.assertEqual(res["action_reason"], "Submission deadline")
        self.assertTrue(res["deadline_detected"])
        self.assertIn("Sep 30", res["deadline_display"])

    def test_30_case5_promo_no_deadline(self):
        email_data = {
            "id": "promo_01",
            "subject": "Register now! 50% discount available today.",
            "body": "Click here to learn more about our summer discounts.",
            "sender": "deals@shopping.com",
            "date": "Thu, 01 Oct 2026 09:00:00 GMT"
        }
        res = predict_email(email_data, self.pipeline)
        self.assertEqual(res["final_priority"], "P4")
        self.assertFalse(res["action_required"])
        self.assertFalse(res["deadline_detected"])

    def test_email_date_never_used_as_deadline(self):
        res = extract_deadline("Weekly Newsletter", "Here are your top articles for this week.", "Thu, 01 Oct 2026 11:30:11 GMT")
        self.assertFalse(res["deadline_detected"])
        self.assertIsNone(res["deadline_datetime"])

    # Section 4: False-Positive Regression Tests
    def test_false_positive_due_to(self):
        res = extract_deadline("", "Due to technical issues, the service was unavailable.", "Thu, 01 Oct 2026 12:00:00 GMT")
        self.assertFalse(res["deadline_detected"])
        self.assertIsNone(res["deadline_datetime"])

    def test_false_positive_low_end(self):
        res = extract_deadline("", "Works well on low-end Android devices.", "Thu, 01 Oct 2026 12:00:00 GMT")
        self.assertFalse(res["deadline_detected"])
        self.assertIsNone(res["deadline_datetime"])

    def test_false_positive_close_associates(self):
        res = extract_deadline("", "Stay connected with close associates.", "Thu, 01 Oct 2026 12:00:00 GMT")
        self.assertFalse(res["deadline_detected"])
        self.assertIsNone(res["deadline_datetime"])

    def test_false_positive_todays_newsletter(self):
        res = extract_deadline("", "Today's newsletter includes our latest updates.", "Thu, 01 Oct 2026 12:00:00 GMT")
        self.assertFalse(res["deadline_detected"])
        self.assertIsNone(res["deadline_datetime"])

    def test_false_positive_available_today(self):
        res = extract_deadline("", "Available today.", "Thu, 01 Oct 2026 12:00:00 GMT")
        self.assertFalse(res["deadline_detected"])
        self.assertIsNone(res["deadline_datetime"])

    def test_false_positive_check_now(self):
        res = extract_deadline("", "Check this out now.", "Thu, 01 Oct 2026 12:00:00 GMT")
        self.assertFalse(res["deadline_detected"])
        self.assertIsNone(res["deadline_datetime"])

    def test_false_positive_register_now(self):
        res = extract_deadline("", "Register now!", "Thu, 01 Oct 2026 12:00:00 GMT")
        self.assertFalse(res["deadline_detected"])
        self.assertIsNone(res["deadline_datetime"])

    def test_false_positive_latest_update(self):
        res = extract_deadline("", "Latest update available.", "Thu, 01 Oct 2026 12:00:00 GMT")
        self.assertFalse(res["deadline_detected"])
        self.assertIsNone(res["deadline_datetime"])

    # Section 5: Real Deadline Positive Verification
    def test_real_deadline_applications_close(self):
        res = extract_deadline("", "Applications close at 5 PM on October 10.", "Wed, 30 Sep 2026 12:00:00 +0000")
        self.assertTrue(res["deadline_detected"])
        self.assertEqual(res["deadline_precision"], "DATETIME")
        self.assertEqual(res["deadline_display"], "Oct 10, 2026 · 5:00 PM")

    def test_real_deadline_deleted_after(self):
        res = extract_deadline("", "Your project will be deleted after October 5.", "Wed, 30 Sep 2026 12:00:00 +0000")
        self.assertTrue(res["deadline_detected"])
        self.assertEqual(res["deadline_precision"], "DATE")
        self.assertEqual(res["deadline_display"], "Oct 5, 2026")

    def test_real_deadline_respond_by_friday(self):
        res = extract_deadline("", "Respond by Friday.", "Wed, 30 Sep 2026 12:00:00 +0000")
        self.assertTrue(res["deadline_detected"])
        self.assertEqual(res["deadline_precision"], "DATE")
        self.assertIn("Friday", res["deadline_display"])

    def test_time_formatting_consistency_no_mixed_pm(self):
        res = extract_deadline("", "Kaggriculture ends in 24 hours (2026-09-30 23:59PM UTC)", "Wed, 30 Sep 2026 12:00:00 +0000")
        self.assertTrue(res["deadline_detected"])
        self.assertEqual(res["deadline_precision"], "DATETIME")
        self.assertEqual(res["deadline_display"], "Sep 30, 2026 · 11:59 PM")
        self.assertNotIn("23:59PM", res["deadline_display"])

if __name__ == '__main__':
    unittest.main()
