"""Backward-compatibility wrapper for backend.app.gmail."""
from backend.app.gmail.service import get_gmail_service
from backend.app.gmail.client import (
    get_profile,
    list_message_ids,
    get_message,
    fetch_emails
)
from backend.app.gmail.parser import (
    parse_message,
    decode_mime_header,
    clean_html_to_text,
    decode_payload_data,
    extract_body_from_payload
)
