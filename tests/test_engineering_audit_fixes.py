import os
import sys
import tempfile
import time
import unittest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.app.main import app
from backend.app.core.config import MODEL_PATH, DATA_DIR
from backend.app.core.cache import UserEmailCache
from backend.app.gmail.scan_engine import SCANS_DIR
from backend.app.ml.shadow_engine import SHADOW_DB_DIR
from backend.app.ml.predictor import load_model, predict_batch
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

    def test_07_mailbox_stats_and_unread_recent_parity(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_file = os.path.join(tmpdir, "test_stats_parity.db")
            cache = UserEmailCache(db_path=db_file)
            try:
                uid = f"stats_user_{int(time.time() * 1000)}"
                now = time.time()
                items = [
                    {
                        "id": "s1",
                        "email_id": "s1",
                        "subject": "URGENT server cluster outage",
                        "body": "Immediate failover required.",
                        "sender": "alerts@ops.io",
                        "predicted_priority": "P1",
                        "final_priority": "P1",
                        "action_required": True,
                        "needs_attention": True,
                        "is_unread": True,
                        "labels": ["INBOX", "UNREAD"],
                        "internal_date": int((now - 2 * 86400) * 1000),
                        "date": datetime.fromtimestamp(now - 2 * 86400, timezone.utc).isoformat(),
                    },
                    {
                        "id": "s2",
                        "email_id": "s2",
                        "subject": "Quarterly security review",
                        "body": "Please sign off on access audit.",
                        "sender": "sec@ops.io",
                        "predicted_priority": "P2",
                        "final_priority": "P2",
                        "action_required": True,
                        "needs_attention": True,
                        "is_unread": False,
                        "labels": ["INBOX"],
                        "internal_date": int((now - 10 * 86400) * 1000),
                        "date": datetime.fromtimestamp(now - 10 * 86400, timezone.utc).isoformat(),
                    },
                    {
                        "id": "s3",
                        "email_id": "s3",
                        "subject": "Sprint update & notes",
                        "body": "Action needed: confirm sprint backlog.",
                        "sender": "pm@ops.io",
                        "predicted_priority": "P3",
                        "final_priority": "P3",
                        "action_required": True,
                        "needs_attention": True,
                        "is_unread": True,
                        "labels": ["INBOX", "UNREAD"],
                        "internal_date": int((now - 45 * 86400) * 1000),
                        "date": datetime.fromtimestamp(now - 45 * 86400, timezone.utc).isoformat(),
                    },
                    {
                        "id": "s4",
                        "email_id": "s4",
                        "subject": "Newsletter promo offer",
                        "body": "Save 20% today only.",
                        "sender": "promo@shop.io",
                        "predicted_priority": "P4",
                        "final_priority": "P4",
                        "action_required": False,
                        "needs_attention": False,
                        "is_unread": False,
                        "labels": ["INBOX"],
                        "internal_date": int((now - 60 * 86400) * 1000),
                        "date": datetime.fromtimestamp(now - 60 * 86400, timezone.utc).isoformat(),
                    },
                ]
                cache.store_batch(uid, items, model_version="priority-v5.1")

                stats = cache.get_mailbox_stats(uid, model_version="priority-v5.1")
                self.assertEqual(stats["total_analyzed"], 4)
                self.assertEqual(stats["counts"], {"P1": 1, "P2": 1, "P3": 1, "P4": 1})
                self.assertEqual(stats["recent_count"], 2)
                self.assertEqual(stats["unread_count"], 2)

                _, na_total = cache.query_emails(uid, priority="NEEDS_ATTENTION", model_version="priority-v5.1")
                self.assertEqual(stats["needs_attention_count"], na_total)
                self.assertEqual(stats["needs_attention_count"], 3)

                unread_rows, unread_total = cache.query_emails(uid, unread_only=True, model_version="priority-v5.1")
                self.assertEqual(unread_total, 2)
                self.assertEqual({r["email_id"] for r in unread_rows}, {"s1", "s3"})

                # Predictor preserves UNREAD label metadata during classification
                preds = predict_batch([{
                    "id": "pred_unread",
                    "subject": "Verification needed",
                    "body": "Confirm account access.",
                    "sender": "sec@example.com",
                    "labels": ["INBOX", "UNREAD"],
                }])
                self.assertTrue(preds[0]["is_unread"])
                self.assertIn("UNREAD", preds[0]["labels"])
            finally:
                cache.close()


if __name__ == "__main__":
    unittest.main()
