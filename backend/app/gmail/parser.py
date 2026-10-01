import re
import base64
from email.header import decode_header
from typing import Dict, Any
from bs4 import BeautifulSoup


def decode_mime_header(header_value: str) -> str:
    """
    Decodes MIME-encoded header strings (RFC 2047) into clean Unicode strings.
    """
    if not header_value:
        return ""
    try:
        decoded_parts = decode_header(header_value)
        result = []
        for part, enc in decoded_parts:
            if isinstance(part, bytes):
                encoding = enc or "utf-8"
                try:
                    result.append(part.decode(encoding, errors="replace"))
                except (LookupError, UnicodeDecodeError):
                    result.append(part.decode("latin-1", errors="replace"))
            else:
                result.append(str(part))
        return "".join(result).strip()
    except Exception:
        return str(header_value).strip()


def clean_html_to_text(html_content: str) -> str:
    """
    Converts raw HTML email markup into clean, readable plain text.
    Strips scripts, styles, metadata tags, and normalizes consecutive whitespace.
    """
    if not html_content:
        return ""
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        for tag in soup(["script", "style", "head", "meta", "noscript", "svg"]):
            tag.decompose()
        text = soup.get_text(separator=" ")
        return re.sub(r"\s+", " ", text).strip()
    except Exception:
        clean = re.sub(r"<[^>]+>", " ", html_content)
        return re.sub(r"\s+", " ", clean).strip()


def decode_payload_data(data_b64: str) -> str:
    """
    Safely decodes base64url-encoded Gmail payload body strings into text.
    """
    if not data_b64:
        return ""
    try:
        padded = data_b64 + "=" * (-len(data_b64) % 4)
        raw_bytes = base64.urlsafe_b64decode(padded.encode("ascii"))
        try:
            return raw_bytes.decode("utf-8", errors="replace")
        except UnicodeDecodeError:
            return raw_bytes.decode("latin-1", errors="replace")
    except Exception:
        return ""


def extract_body_from_payload(payload: Dict[str, Any]) -> str:
    """
    Recursively extracts and prioritizes text/plain body content over text/html.
    Handles multipart/alternative, multipart/mixed, and nested message structures.
    """
    if not payload:
        return ""

    mime_type = payload.get("mimeType", "")
    body_data = payload.get("body", {}).get("data", "")
    parts = payload.get("parts", [])

    plain_candidates = []
    html_candidates = []

    # Single-part message
    if body_data and not parts:
        decoded = decode_payload_data(body_data)
        if "html" in mime_type.lower():
            return clean_html_to_text(decoded)
        return decoded.strip()

    # Recursive walker for multipart messages
    def _walk_parts(part_list):
        for part in part_list:
            p_mime = part.get("mimeType", "").lower()
            p_body = part.get("body", {})
            p_data = p_body.get("data", "")
            sub_parts = part.get("parts", [])

            if sub_parts:
                _walk_parts(sub_parts)
            elif p_data:
                decoded = decode_payload_data(p_data)
                if p_mime == "text/plain":
                    plain_candidates.append(decoded.strip())
                elif p_mime == "text/html":
                    html_candidates.append(clean_html_to_text(decoded))

    _walk_parts(parts)

    if plain_candidates:
        return " ".join([p for p in plain_candidates if p]).strip()
    elif html_candidates:
        return " ".join([h for h in html_candidates if h]).strip()

    return ""


def parse_message(msg_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parses a raw Gmail API message JSON resource into a clean structured dictionary.
    Guarantees consistent schema, header decoding, and robust MIME body extraction.
    """
    msg_id = msg_data.get("id", "")
    thread_id = msg_data.get("threadId", "")
    snippet = msg_data.get("snippet", "")
    label_ids = msg_data.get("labelIds", [])

    payload = msg_data.get("payload", {})
    headers = payload.get("headers", [])

    header_dict = {}
    for h in headers:
        name = h.get("name", "").lower()
        val = h.get("value", "")
        header_dict[name] = val

    subject_raw = header_dict.get("subject", "")
    subject = decode_mime_header(subject_raw) if subject_raw else "(No Subject)"

    sender_raw = header_dict.get("from", "")
    sender = decode_mime_header(sender_raw) if sender_raw else "(Unknown Sender)"

    to_raw = header_dict.get("to", "")
    recipients = decode_mime_header(to_raw) if to_raw else ""

    date_str = header_dict.get("date", "")
    body_text = extract_body_from_payload(payload)

    if not body_text and snippet:
        body_text = snippet

    return {
        "id": msg_id,
        "thread_id": thread_id,
        "subject": subject,
        "sender": sender,
        "recipients": recipients,
        "date": date_str,
        "body": body_text,
        "snippet": snippet,
        "labels": label_ids,
    }
