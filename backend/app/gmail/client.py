import threading
import httplib2
import google_auth_httplib2
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List, Optional
from googleapiclient.errors import HttpError
from backend.app.gmail.parser import parse_message

_tls = threading.local()


def _get_thread_http(service):
    """Provides an isolated, thread-safe AuthorizedHttp instance per worker thread."""
    if not hasattr(_tls, "http"):
        creds = getattr(service._http, "credentials", None) if hasattr(service, "_http") else None
        if creds:
            _tls.http = google_auth_httplib2.AuthorizedHttp(creds, http=httplib2.Http())
        else:
            _tls.http = httplib2.Http()
    return _tls.http


def get_profile(service) -> Dict[str, Any]:
    """Retrieves the authenticated Gmail user profile metadata."""
    if service is None:
        raise ValueError("An authenticated Gmail service instance must be provided.")
    return service.users().getProfile(userId="me").execute()


def list_message_ids(
    service,
    max_results: int = 50,
    query: Optional[str] = None,
    page_token: Optional[str] = None,
) -> Dict[str, Any]:
    """Lists message IDs from Gmail with optional search query and pagination."""
    kwargs = {
        "userId": "me",
        "maxResults": min(max_results, 500),
    }
    if query:
        kwargs["q"] = query
    if page_token:
        kwargs["pageToken"] = page_token

    return service.users().messages().list(**kwargs).execute()


def get_message(service, message_id: str, format_type: str = "full", http=None) -> Dict[str, Any]:
    """Fetches a single Gmail message resource by ID."""
    req = service.users().messages().get(
        userId="me",
        id=message_id,
        format=format_type
    )
    if http is not None:
        return req.execute(http=http)
    return req.execute()


def get_single_email(service, message_id: str) -> Optional[Dict[str, Any]]:
    """Fetches and parses a single email with full body content."""
    try:
        raw_msg = get_message(service, message_id, format_type="full")
        return parse_message(raw_msg)
    except Exception as e:
        print(f"[Warning] Failed to fetch full message {message_id}: {e}")
        return None


def _fetch_single_message_safe(service, msg_id: str) -> Optional[Dict[str, Any]]:
    """Helper to fetch and parse a single message safely in a concurrent thread."""
    try:
        thread_http = _get_thread_http(service)
        raw_msg = get_message(service, msg_id, format_type="full", http=thread_http)
        return parse_message(raw_msg)
    except HttpError as http_err:
        print(f"[Warning] Failed to fetch message {msg_id}: {http_err}")
        return None
    except Exception as err:
        print(f"[Warning] Error parsing message {msg_id}: {err}")
        return None


def fetch_emails(
    service,
    max_emails: int = 20,
    query: Optional[str] = None,
    page_size: int = 50,
) -> List[Dict[str, Any]]:
    """
    Fetches up to max_emails parsed emails concurrently from Gmail.
    Preserves exact chronological mailbox order while speeding up fetch by 5-10x.
    """
    if service is None:
        raise ValueError("An authenticated Gmail service instance must be provided.")

    target_ids: List[str] = []
    page_token = None

    while len(target_ids) < max_emails:
        batch_limit = min(page_size, max_emails - len(target_ids))
        res = list_message_ids(
            service=service,
            max_results=batch_limit,
            query=query,
            page_token=page_token,
        )
        messages = res.get("messages", [])
        if not messages:
            break
        for m in messages:
            if len(target_ids) >= max_emails:
                break
            target_ids.append(m.get("id"))

        page_token = res.get("nextPageToken")
        if not page_token:
            break

    if not target_ids:
        return []

    # Fetch concurrently using ThreadPoolExecutor while maintaining ID order
    results_map: Dict[str, Dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=min(10, len(target_ids))) as executor:
        future_to_id = {
            executor.submit(_fetch_single_message_safe, service, mid): mid
            for mid in target_ids
        }
        for future in as_completed(future_to_id):
            mid = future_to_id[future]
            parsed = future.result()
            if parsed:
                results_map[mid] = parsed

    # Return in original list order
    ordered_emails = [results_map[mid] for mid in target_ids if mid in results_map]
    return ordered_emails
