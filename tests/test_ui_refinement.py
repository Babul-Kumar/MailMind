import os
import sys
import json
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.session import session_manager
from backend.app.core.cache import user_email_cache
from backend.app.gmail.scan_engine import (
    scan_manager,
    discover_mailbox_message_ids,
    fetch_message_metadata_batch,
    MailboxScanJob,
)
from backend.app.ml.predictor import predict_batch, predict_email

client = TestClient(app)


class TestUIRefinementAndCompleteScan:
    """
    Test suite for MailMind User-Facing Refinement:
    1. Complete mailbox discovery without 20-message ceilings.
    2. Incremental caching preserving past predictions.
    3. Pagination resilience over large analyzed datasets.
    4. Local inference verification (0 external generative AI / Gemini calls).
    5. Multi-user session isolation.
    """

    @pytest.fixture(autouse=True)
    def setup_user(self):
        self.user_id = "test_ui_refine_user"
        self.user_email = "refine.test@domain.com"
        self.session = session_manager.create_session(
            email=self.user_email,
            user_id=self.user_id,
            credentials={"token": "mock_tok", "refresh_token": "mock_rf"}
        )
        user_email_cache.clear_user(self.user_id)
        yield
        user_email_cache.clear_user(self.user_id)

    # 1. Complete mailbox discovery exhausts nextPageToken
    def test_01_discovery_exhausts_next_page_token(self):
        mock_svc = MagicMock()
        mock_msgs = mock_svc.users().messages()

        p1 = {"messages": [{"id": f"msg_{i}"} for i in range(500)], "nextPageToken": "tok_2"}
        p2 = {"messages": [{"id": f"msg_{i}"} for i in range(500, 1000)], "nextPageToken": "tok_3"}
        p3 = {"messages": [{"id": f"msg_{i}"} for i in range(1000, 1250)], "nextPageToken": None}

        def mock_list(userId, maxResults, pageToken=None, **kwargs):
            req = MagicMock()
            if pageToken is None:
                req.execute.return_value = p1
            elif pageToken == "tok_2":
                req.execute.return_value = p2
            else:
                req.execute.return_value = p3
            return req

        mock_msgs.list.side_effect = mock_list

        discovered, stats = discover_mailbox_message_ids(mock_svc, scope="mailbox", return_stats=True)
        assert len(discovered) == 1250
        assert stats["pages_scanned"] == 3
        assert stats["duplicates_removed"] == 0

    # 2. Complete discovery does not stop at 20 emails
    def test_02_discovery_exceeds_arbitrary_20_limit(self):
        mock_svc = MagicMock()
        mock_msgs = mock_svc.users().messages()

        p1 = {"messages": [{"id": f"msg_{i}"} for i in range(150)], "nextPageToken": None}
        mock_msgs.list.return_value.execute.return_value = p1

        discovered = discover_mailbox_message_ids(mock_svc, scope="mailbox")
        assert len(discovered) == 150
        assert len(discovered) > 20

    # 3. Incremental scan reuses cache and only analyzes missing messages
    def test_03_incremental_scan_reuses_cache(self):
        # Pre-cache 100 emails
        for i in range(100):
            user_email_cache.set(self.user_id, f"precached_{i}", {
                "email_id": f"precached_{i}",
                "subject": f"Precached Subject {i}",
                "body": f"Precached body {i}",
                "sender": "sender@test.com",
                "date": "2026-10-01T00:00:00Z",
                "predicted_priority": "P2" if i % 2 == 0 else "P4",
                "confidence": 0.90,
                "action_required": (i % 2 == 0),
                "needs_attention": (i % 2 == 0),
            })

        # Gmail discovery finds the 100 precached + 5 new emails
        all_ids = [f"precached_{i}" for i in range(100)] + [f"new_email_{i}" for i in range(5)]
        mock_svc = MagicMock()
        mock_svc.users().messages().list.return_value.execute.return_value = {
            "messages": [{"id": mid} for mid in all_ids],
            "nextPageToken": None
        }

        analyzed_new_ids = []
        def mock_batch_fetch(service, message_ids, **kwargs):
            analyzed_new_ids.extend(message_ids)
            return [
                {
                    "email_id": mid,
                    "subject": f"New email {mid}",
                    "body": "Important server update required immediately.",
                    "sender": "ops@corp.com",
                    "date": "2026-10-02T12:00:00Z",
                    "content_hash": f"hash_{mid}"
                }
                for mid in message_ids
            ], [], 1, 0

        with patch("backend.app.gmail.scan_engine.fetch_message_metadata_batch", side_effect=mock_batch_fetch):
            job = MailboxScanJob(self.user_id, mock_svc, scope="mailbox", mode="incremental")
            status = job.execute()

            assert status["status"] == "COMPLETE"
            assert status["total"] == 105
            assert status["cached"] == 100
            assert status["newly_analyzed"] == 5
            assert len(analyzed_new_ids) == 5
            assert all(mid.startswith("new_email_") for mid in analyzed_new_ids)

    # 4. Display pagination over large analyzed mailbox without memory bloat
    def test_04_display_pagination_on_large_cache(self):
        for i in range(250):
            user_email_cache.set(self.user_id, f"mail_{i:04d}", {
                "email_id": f"mail_{i:04d}",
                "subject": f"Notice {i:04d}",
                "body": "Detailed content" * 20,
                "sender": "sender@test.com",
                "date": f"2026-10-01T{i % 24:02d}:00:00Z",
                "predicted_priority": "P1" if i == 0 else "P2" if i < 50 else "P3" if i < 150 else "P4",
                "action_required": (i < 50),
                "needs_attention": (i < 50),
            })

        # Test querying page 2 with page_size=50 (descending order by date/id)
        page2_items, total = user_email_cache.query_emails(self.user_id, page=2, page_size=50)
        assert total == 250
        assert len(page2_items) == 50
        assert page2_items[0]["email_id"] == "mail_0199"

        # Verify mailbox stats reflect total analyzed
        stats = user_email_cache.get_mailbox_stats(self.user_id)
        assert stats["total_analyzed"] == 250
        assert stats["counts"]["P1"] == 1
        assert stats["counts"]["P2"] == 49
        assert stats["counts"]["P3"] == 100
        assert stats["counts"]["P4"] == 100

    # 5. Production inference is strictly local, zero external generative AI
    def test_05_production_inference_is_local_no_external_ai(self):
        email = {
            "id": "local_inference_test",
            "subject": "Action Required: Complete Security Compliance by Friday",
            "body": "Please complete your quarterly security training by this Friday at 5 PM.",
            "sender": "security@enterprise.com",
            "date": "2026-10-01T10:00:00Z"
        }

        # Predict using production prediction path
        pred = predict_email(email)
        assert pred["predicted_priority"] in ("P1", "P2")
        assert pred["action_required"] is True
        assert "confidence" in pred
        assert "probabilities" in pred

        # Inspect imported modules to guarantee zero google.generativeai, openai, anthropic
        forbidden = ["google.generativeai", "google.genai", "openai", "anthropic"]
        for mod in forbidden:
            assert mod not in sys.modules, f"Forbidden external AI module '{mod}' must not be loaded!"

    # 6. Multi-user isolation during scan status & cache
    def test_06_multiuser_scan_isolation(self):
        user_b_id = "test_ui_refine_user_b"
        session_b = session_manager.create_session(
            email="userb@domain.com",
            user_id=user_b_id,
            credentials={"token": "tok_b"}
        )

        scan_manager.set_status(self.user_id, {
            "status": "ANALYZING",
            "discovered": 2000,
            "analyzed": 1500,
            "total": 2000
        })

        client_b = TestClient(app)
        client_b.cookies.set("mailmind_session", session_b.session_id)
        resp_b = client_b.get("/api/scan/status")
        assert resp_b.status_code == 200
        data_b = resp_b.json()
        assert data_b.get("total") != 2000

        user_email_cache.clear_user(user_b_id)
