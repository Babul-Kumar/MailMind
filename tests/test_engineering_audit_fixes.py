import os
import sys
import tempfile
import unittest
from fastapi.testclient import TestClient

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.app.main import app
from backend.app.core.config import MODEL_PATH, DATA_DIR
from backend.app.core.cache import UserEmailCache
from backend.app.gmail.scan_engine import SCANS_DIR
from backend.app.ml.shadow_engine import SHADOW_DB_DIR
from backend.app.ml.predictor import load_model
from backend.app.ml.explanations import extract_feature_signals


class TestEngineeringAuditFixes(unittest.TestCase):
    """Regression coverage for cloud, backend, ML, and cache isolation audit fixes."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_01_model_path_points_to_v51(self):
        self.assertIn("priority-v5.1", MODEL_PATH)
        self.assertTrue(os.path.exists(MODEL_PATH))

    def test_02_persistent_paths_anchored_to_data_dir(self):
        self.assertEqual(SCANS_DIR, os.path.join(DATA_DIR, "scans"))
        self.assertEqual(SHADOW_DB_DIR, os.path.join(DATA_DIR, "cache"))

    def test_03_render_yaml_matches_disk_mount(self):
        render_path = os.path.join(BASE_DIR, "render.yaml")
        with open(render_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("mountPath: /var/data", content)
        self.assertIn("value: /var/data", content)
        self.assertNotIn("value: /tmp/mailmind-data", content)

    def test_04_health_reports_model_and_db(self):
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data.get("status"), "healthy")
        self.assertTrue(data.get("model_loaded"))
        self.assertTrue(data.get("db_connected"))
        self.assertEqual(data.get("model_version"), "priority-v5.1")

    def test_05_explanations_include_normalized_contribution_pct(self):
        pipeline = load_model()
        signals = extract_feature_signals(
            pipeline,
            "URGENT: Production outage on server cluster immediate action required",
            "P1",
            max_terms=4,
        )
        self.assertGreater(len(signals), 0)
        total_pct = 0.0
        for sig in signals:
            self.assertIn("contribution_pct", sig)
            self.assertGreater(sig["contribution_pct"], 0.0)
            self.assertLessEqual(sig["contribution_pct"], 100.0)
            total_pct += sig["contribution_pct"]
        self.assertLessEqual(total_pct, 100.5)

    def test_06_consolidate_legacy_history_ids_preserves_isolation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_file = os.path.join(tmpdir, "test_consolidate.db")
            cache = UserEmailCache(db_path=db_file)
            try:
                user_email = "alice@example.com"
                other_email = "bob@example.com"
                cache.set_analysis_preference("hist_100", user_email, "last_3_months")
                cache.set_analysis_preference("hist_200", user_email, "last_3_months")
                cache.set_analysis_preference("hist_999", other_email, "all_time")

                cache.store_batch("hist_100", [{
                    "id": "m1", "message_id": "m1", "subject": "Older email",
                    "sender": "a@b.com", "predicted_priority": "P2", "date": "2026-09-01T10:00:00Z",
                    "internal_date": 1788256800000,
                }], model_version="priority-v5.1")
                cache.store_batch("hist_200", [{
                    "id": "m2", "message_id": "m2", "subject": "Newer email",
                    "sender": "a@b.com", "predicted_priority": "P1", "date": "2026-11-01T10:00:00Z",
                    "internal_date": 1793527200000,
                }], model_version="priority-v5.1")
                cache.store_batch("hist_999", [{
                    "id": "m3", "message_id": "m3", "subject": "Bob email",
                    "sender": "c@d.com", "predicted_priority": "P3", "date": "2026-11-01T10:00:00Z",
                    "internal_date": 1793527200000,
                }], model_version="priority-v5.1")

                migrated = cache.consolidate_legacy_user_data(user_email, user_email)
                self.assertEqual(migrated, 2)

                alice_rows, alice_total = cache.query_emails(user_email)
                self.assertEqual(alice_total, 2)
                alice_ids = {item["email_id"] for item in alice_rows}
                self.assertEqual(alice_ids, {"m1", "m2"})

                # Bob's partition remains completely untouched
                bob_rows, bob_total = cache.query_emails("hist_999")
                self.assertEqual(bob_total, 1)
                bob_ids = {item["email_id"] for item in bob_rows}
                self.assertEqual(bob_ids, {"m3"})

                # Idempotent second run
                self.assertEqual(cache.consolidate_legacy_user_data(user_email, user_email), 0)
            finally:
                cache.close()


if __name__ == "__main__":
    unittest.main()
