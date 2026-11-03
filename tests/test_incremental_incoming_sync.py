import pytest
import time
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.session import SessionData
from backend.app.core.cache import user_email_cache
from backend.app.api.routes_emails import (
    sync_incoming_emails,
    _last_user_sync_time,
    _user_sync_lock
)


@pytest.fixture
def test_user_id():
    uid = f"test_sync_{time.time()}@example.com"
    user_email_cache.clear_user(uid)
    yield uid
    user_email_cache.clear_user(uid)


@pytest.fixture
def mock_session(test_user_id):
    session = SessionData(
        session_id="test_sess_123",
        user_id=test_user_id,
        email=test_user_id,
        credentials={"token": "mock_token"},
        created_at=time.time(),
        expires_at=time.time() + 3600
    )
    return session


def test_sync_incoming_emails_discovers_and_persists_new_message(test_user_id):
    """
    Verifies that when Gmail returns a message ID not currently in cache,
    sync_incoming_emails fetches, predicts, and saves it into user_email_cache.
    """
    mock_service = MagicMock()
    mock_pipeline = MagicMock()
    mock_pipeline.predict.return_value = ["P1"]

    new_msg_id = f"msg_brand_new_{int(time.time() * 1000)}"
    existing_msg_id = f"msg_already_cached_{int(time.time() * 1000)}"

    # Pre-cache existing_msg_id
    user_email_cache.store_batch(
        user_id=test_user_id,
        items=[{
            "id": existing_msg_id,
            "subject": "Old Email",
            "snippet": "Already cached",
            "final_priority": "P3",
            "predicted_priority": "P3",
            "confidence": 0.95
        }],
        model_version="priority-v5.1"
    )

    with _user_sync_lock:
        _last_user_sync_time.pop(test_user_id, None)

    with patch("backend.app.api.routes_emails.list_message_ids") as mock_list, \
         patch("backend.app.api.routes_emails._fetch_single_message_safe") as mock_fetch, \
         patch("backend.app.api.routes_emails.predict_batch") as mock_predict:

        mock_list.return_value = {
            "messages": [
                {"id": new_msg_id},
                {"id": existing_msg_id}
            ]
        }

        mock_fetch.return_value = {
            "id": new_msg_id,
            "subject": "Urgent Server Outage",
            "snippet": "Production service is down",
            "sender": "alerts@infra.org",
            "recipients": test_user_id,
            "date": "Wed, 04 Nov 2026 03:00:00 +0000",
            "body": "Critical failure detected on server cluster alpha.",
            "labels": ["INBOX", "UNREAD"],
            "internal_date": int(time.time() * 1000)
        }

        mock_predict.return_value = [{
            "id": new_msg_id,
            "email_id": new_msg_id,
            "subject": "Urgent Server Outage",
            "snippet": "Production service is down",
            "sender": "alerts@infra.org",
            "predicted_priority": "P1",
            "final_priority": "P1",
            "confidence": 0.99,
            "action_required": True,
            "internal_date": int(time.time() * 1000)
        }]

        new_count = sync_incoming_emails(
            user_id=test_user_id,
            service=mock_service,
            pipeline=mock_pipeline,
            model_version="priority-v5.1",
            limit=25,
            force=True
        )

        assert new_count == 1
        mock_fetch.assert_called_once_with(mock_service, new_msg_id)
        mock_predict.assert_called_once()

        # Verify that the new email is now in user_email_cache
        cached_map, missing = user_email_cache.get_batch(
            user_id=test_user_id,
            message_ids=[new_msg_id],
            active_model_version="priority-v5.1"
        )
        assert new_msg_id in cached_map
        assert cached_map[new_msg_id]["final_priority"] == "P1"
        assert len(missing) == 0


def test_sync_incoming_emails_throttling(test_user_id):
    """
    Verifies that calling sync_incoming_emails in rapid succession
    is safely throttled to avoid hitting Gmail API quota unless force=True.
    """
    mock_service = MagicMock()
    with _user_sync_lock:
        _last_user_sync_time[test_user_id] = time.time()  # set right now

    with patch("backend.app.api.routes_emails.list_message_ids") as mock_list:
        # Non-forced call should immediately return 0 without listing Gmail
        count = sync_incoming_emails(
            user_id=test_user_id,
            service=mock_service,
            model_version="priority-v5.1",
            force=False
        )
        assert count == 0
        mock_list.assert_not_called()

        # Forced call bypasses throttle
        mock_list.return_value = {"messages": []}
        count_forced = sync_incoming_emails(
            user_id=test_user_id,
            service=mock_service,
            model_version="priority-v5.1",
            force=True
        )
        assert count_forced == 0
        mock_list.assert_called_once()


def test_sync_incoming_emails_network_resilience(test_user_id):
    """
    Verifies that if Gmail API throws a connection or rate limit error,
    sync_incoming_emails catches it gracefully, logs, and returns 0 without crashing.
    """
    mock_service = MagicMock()
    with _user_sync_lock:
        _last_user_sync_time.pop(test_user_id, None)

    with patch("backend.app.api.routes_emails.list_message_ids") as mock_list:
        mock_list.side_effect = RuntimeError("Gmail API rate limit exceeded")

        count = sync_incoming_emails(
            user_id=test_user_id,
            service=mock_service,
            model_version="priority-v5.1",
            force=True
        )
        assert count == 0


def test_api_emails_sync_endpoint(test_user_id, mock_session):
    """
    Verifies the dedicated POST /api/emails/sync endpoint executes forced sync
    and returns correct structured response with new email count and stats.
    """
    client = TestClient(app)

    with patch("backend.app.api.routes_emails.get_session_from_request", return_value=mock_session), \
         patch("backend.app.api.routes_emails.get_user_gmail_service") as mock_get_svc, \
         patch("backend.app.api.routes_emails.sync_incoming_emails", return_value=3) as mock_sync:

        mock_get_svc.return_value = MagicMock()

        response = client.post("/api/emails/sync?period=last_1_month")
        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "success"
        assert data["new_emails_count"] == 3
        assert "Discovered and classified 3 new email(s)" in data["message"]
        assert "stats" in data
        mock_sync.assert_called_once()
        assert mock_sync.call_args[1]["force"] is True


def test_rescan_mailbox_respects_period_boundaries(test_user_id, mock_session):
    """
    Verifies that POST /api/scan/rescan does NOT scan 18,000+ emails across all time,
    but restricts to the requested or preferred analysis period boundaries.
    """
    client = TestClient(app)

    with patch("backend.app.api.routes_emails.get_session_from_request", return_value=mock_session), \
         patch("backend.app.api.routes_emails.get_user_gmail_service", return_value=MagicMock()), \
         patch("backend.app.api.routes_emails.scan_manager.start_scan") as mock_start_scan:

        mock_start_scan.return_value = {"status": "SCANNING", "total": 100}

        response = client.post("/api/scan/rescan?period=last_1_month")
        assert response.status_code == 200

        mock_start_scan.assert_called_once()
        call_kwargs = mock_start_scan.call_args[1]
        assert call_kwargs["period"] == "last_1_month"
        assert call_kwargs["force_rescan"] is True
        assert call_kwargs["query"] is not None
        assert "after:" in call_kwargs["query"]
