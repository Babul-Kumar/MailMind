import os
import sys
import unittest
from fastapi.testclient import TestClient

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.app.main import app
from backend.app.core.session import session_manager


class TestLastThreeMonthsVerification(unittest.TestCase):
    """
    Permanent regression test verifying that:
    1. Active user sessions are properly loaded and renewed via sliding expiration.
    2. Cached mailbox emails (over 18,000 total and 1,890+ for last 3 months) are served
       reliably from SQLite even if live Gmail API service is offline or tokens need re-consent.
    3. The period 'last_3_months' properly loads real emails rather than falling back to demo placeholders.
    """

    def setUp(self):
        self.client = TestClient(app)

    def test_01_dev_login_and_auth_status(self):
        # 1. Dev login
        res_login = self.client.post("/api/auth/dev-login")
        self.assertEqual(res_login.status_code, 200)
        user_data = res_login.json()
        self.assertTrue(user_data.get("authenticated"))
        self.assertEqual(user_data["user"]["email"], "babulkumar0220@gmail.com")

        # 2. Auth status
        res_status = self.client.get("/api/auth/status")
        self.assertEqual(res_status.status_code, 200)
        status_data = res_status.json()
        self.assertTrue(status_data.get("authenticated"))
        self.assertEqual(status_data["user"]["email"], "babulkumar0220@gmail.com")

    def test_02_last_3_months_email_loading(self):
        # Connect session
        self.client.post("/api/auth/dev-login")

        # Query last 3 months
        res = self.client.get("/api/emails?period=last_3_months")
        self.assertEqual(res.status_code, 200)
        data = res.json()

        total_emails = data.get("pagination", {}).get("total_emails", 0)
        emails = data.get("emails", [])

        # User has 1,891 emails cached for last 3 months
        self.assertGreaterEqual(total_emails, 1800, f"Expected at least 1800 emails for last 3 months, got {total_emails}")
        self.assertEqual(len(emails), 50, f"Expected 50 emails on page 1, got {len(emails)}")

        # Verify real email fields (not the 5 placeholder demo emails)
        first_email = emails[0]
        self.assertIn("subject", first_email)
        self.assertIn("sender", first_email)
        self.assertIn("priority", first_email)
        self.assertNotEqual(first_email.get("subject"), "Elevated 5xx latency on production API")

    def test_03_all_time_email_loading(self):
        self.client.post("/api/auth/dev-login")

        res = self.client.get("/api/emails?period=all_time")
        self.assertEqual(res.status_code, 200)
        data = res.json()

        total_emails = data.get("pagination", {}).get("total_emails", 0)
        self.assertGreaterEqual(total_emails, 18000, f"Expected at least 18000 emails for all time, got {total_emails}")

    def test_04_priority_filtering_within_last_3_months(self):
        self.client.post("/api/auth/dev-login")

        for priority in ["P1", "P2", "P3", "P4"]:
            res = self.client.get(f"/api/emails?period=last_3_months&priority={priority}")
            self.assertEqual(res.status_code, 200)
            data = res.json()
            emails = data.get("emails", [])
            for e in emails:
                self.assertEqual(e.get("priority"), priority)


if __name__ == "__main__":
    unittest.main()
