"""
Tests for HTML body extraction, plain text newline formatting, and period aliasing.
"""

from backend.app.gmail.parser import parse_message, clean_html_to_text, extract_html_from_payload
from backend.app.core.date_utils import calculate_period_boundaries, SUPPORTED_PERIODS


def test_clean_html_to_text_preserves_paragraphs():
    html = "<p>First paragraph.</p><p>Second paragraph with <a href='https://example.com'>link</a>.</p>"
    text = clean_html_to_text(html)
    assert "First paragraph." in text
    assert "Second paragraph" in text
    assert "\n" in text


def test_parse_message_extracts_html_and_text():
    sample_msg = {
        "id": "msg_html_1",
        "threadId": "thread_1",
        "snippet": "Snippet preview",
        "internalDate": "1700000000000",
        "payload": {
            "mimeType": "multipart/alternative",
            "headers": [
                {"name": "Subject", "value": "Coursera Weekly Digest"},
                {"name": "From", "value": "Coursera <no-reply@coursera.org>"}
            ],
            "parts": [
                {
                    "mimeType": "text/plain",
                    "body": {"data": "SGkgaGVyZSwgdGhpcyBpcyBwbGFpbiB0ZXh0Lg=="} # Hi here, this is plain text.
                },
                {
                    "mimeType": "text/html",
                    "body": {"data": "PGRpdj48aDE+Q291cnNlcmE8L2gxPjxwPkFkdmFuY2VkIERlZXAgTGVhcm5pbmc8L3A+PC9kaXY+"} # <div><h1>Coursera</h1><p>Advanced Deep Learning</p></div>
                }
            ]
        }
    }
    parsed = parse_message(sample_msg)
    assert parsed["id"] == "msg_html_1"
    assert parsed["body"] == "Hi here, this is plain text."
    assert "<h1>Coursera</h1>" in parsed["body_html"]
    assert "<p>Advanced Deep Learning</p>" in parsed["body_html"]


def test_last_year_alias_supported():
    assert "last_year" in SUPPORTED_PERIODS
    assert "all_time" in SUPPORTED_PERIODS
    b_ly = calculate_period_boundaries(period="last_year")
    b_1y = calculate_period_boundaries(period="last_1_year")
    assert abs(b_ly["start_ts_sec"] - b_1y["start_ts_sec"]) < 5  # within 5 seconds
    b_all = calculate_period_boundaries(period="all_time")
    assert b_all["start_ts_sec"] == 0.0
