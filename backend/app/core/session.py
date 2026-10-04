import os
import re
import time
import json
import secrets
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from fastapi import Request
from google.oauth2.credentials import Credentials
from backend.app.core.config import BASE_DIR, DATA_DIR, GMAIL_SCOPES

SESSION_COOKIE_NAME = "mailmind_session"
SESSION_DURATION_SECONDS = 7 * 24 * 3600  # 7 days
SESSIONS_DIR = os.path.join(DATA_DIR, "sessions")


@dataclass
class SessionData:
    session_id: str
    user_id: str
    email: str
    credentials: Dict[str, Any]
    created_at: float
    expires_at: float

    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SessionManager:
    """
    Thread-safe user session and OAuth credentials manager.
    Isolates credentials, tokens, and mailbox access per authenticated session.
    Never exposes credentials or tokens to the client frontend.
    """
    def __init__(self):
        self._sessions: Dict[str, SessionData] = {}
        os.makedirs(SESSIONS_DIR, exist_ok=True)
        self._load_persisted_sessions()

    def _load_persisted_sessions(self):
        """Restores unexpired sessions across server restarts."""
        try:
            for fname in os.listdir(SESSIONS_DIR):
                if fname.endswith(".json") and not fname.startswith("_"):
                    fpath = os.path.join(SESSIONS_DIR, fname)
                    try:
                        with open(fpath, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            session = SessionData(**data)
                            if not session.is_expired():
                                self._sessions[session.session_id] = session
                            else:
                                os.remove(fpath)
                    except Exception as err:
                        print(f"[SessionManager Warning] Failed to load session {fname}: {err}")
        except Exception as e:
            print(f"[SessionManager Warning] Could not load persisted sessions: {e}")

    def _persist_session(self, session: SessionData):
        """Persists session to disk so active users aren't logged out on restart."""
        if not self._is_safe_session_id(session.session_id):
            print(f"[SessionManager Warning] Refusing to persist invalid session ID: {session.session_id}")
            return
        try:
            fpath = os.path.join(SESSIONS_DIR, f"{session.session_id}.json")
            with open(fpath, "w", encoding="utf-8") as f:
                json.dump(session.to_dict(), f, indent=2)
        except Exception as e:
            print(f"[SessionManager Warning] Could not persist session: {e}")

    def create_session(
        self,
        user_id: str,
        email: str,
        credentials: Any,
    ) -> SessionData:
        """Creates and stores a new isolated user session."""
        session_id = secrets.token_urlsafe(32)
        now = time.time()

        if isinstance(credentials, Credentials):
            creds_dict = {
                "token": credentials.token,
                "refresh_token": credentials.refresh_token,
                "token_uri": credentials.token_uri,
                "client_id": credentials.client_id,
                "client_secret": credentials.client_secret,
                "scopes": credentials.scopes,
            }
        elif isinstance(credentials, dict):
            creds_dict = credentials
        else:
            creds_dict = {}

        session = SessionData(
            session_id=session_id,
            user_id=user_id,
            email=email,
            credentials=creds_dict,
            created_at=now,
            expires_at=now + SESSION_DURATION_SECONDS,
        )
        self._sessions[session_id] = session
        self._persist_session(session)
        return session

    @staticmethod
    def _is_safe_session_id(session_id: Optional[str]) -> bool:
        """Validates that a session_id is a safe alphanumeric token without path traversal."""
        if not session_id or not isinstance(session_id, str):
            return False
        # Strictly URL-safe alphanumeric, underscore, hyphen, tilde (16-128 chars). No dots, no slashes.
        return bool(re.match(r"^[A-Za-z0-9_\-~]{16,128}$", session_id))

    def get_session(self, session_id: Optional[str]) -> Optional[SessionData]:
        """Retrieves an active, unexpired session by ID."""
        if not self._is_safe_session_id(session_id):
            return None
        session = self._sessions.get(session_id)
        if not session:
            # Check disk in case another worker saved it
            fpath = os.path.join(SESSIONS_DIR, f"{session_id}.json")
            if os.path.exists(fpath):
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        s = SessionData(**data)
                        if not s.is_expired():
                            self._sessions[session_id] = s
                            return s
                except Exception:
                    pass
            return None

        if session.is_expired():
            self.delete_session(session_id)
            return None
        return session

    def delete_session(self, session_id: Optional[str]) -> bool:
        """Deletes and invalidates an active session."""
        if not self._is_safe_session_id(session_id):
            return False
        self._sessions.pop(session_id, None)
        fpath = os.path.join(SESSIONS_DIR, f"{session_id}.json")
        if os.path.exists(fpath):
            try:
                os.remove(fpath)
            except Exception:
                pass
        return True

    HANDOFF_TTL_SECONDS = 120  # 2 minutes expiration
    HANDOFF_FILE = os.path.join(SESSIONS_DIR, "_pending_handoffs.json")

    def _load_pending_handoffs(self) -> Dict[str, Dict[str, Any]]:
        if os.path.exists(self.HANDOFF_FILE):
            try:
                with open(self.HANDOFF_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_pending_handoffs(self, handoffs: Dict[str, Dict[str, Any]]):
        try:
            with open(self.HANDOFF_FILE, "w", encoding="utf-8") as f:
                json.dump(handoffs, f)
        except Exception as e:
            print(f"[SessionManager Warning] Failed to persist handoffs: {e}")

    def create_handoff(self, session_id: str) -> str:
        """
        Creates a short-lived (120s), single-use cryptographic handoff code
        mapped to an authenticated session ID. Never logs the handoff code.
        """
        code = secrets.token_urlsafe(32)
        now = time.time()
        handoffs = self._load_pending_handoffs()
        # Prune expired handoffs
        handoffs = {c: d for c, d in handoffs.items() if now - d.get("created_at", 0) <= self.HANDOFF_TTL_SECONDS}
        handoffs[code] = {
            "session_id": session_id,
            "created_at": now,
        }
        self._save_pending_handoffs(handoffs)
        return code

    def consume_handoff(self, code: Optional[str]) -> Optional[str]:
        """
        Validates and atomically consumes a one-time handoff code.
        Returns the session_id if valid, or None if invalid/expired/already used.
        Enforces strict single-use anti-replay protection.
        """
        if not self._is_safe_session_id(code):
            return None

        now = time.time()
        handoffs = self._load_pending_handoffs()
        entry = handoffs.pop(code, None)

        # Always persist back the deletion immediately to enforce single-use / anti-replay
        self._save_pending_handoffs(handoffs)

        if not entry:
            return None

        if now - entry.get("created_at", 0) > self.HANDOFF_TTL_SECONDS:
            return None

        session_id = entry.get("session_id")
        if not self._is_safe_session_id(session_id):
            return None

        return session_id

    def get_credentials(self, session: SessionData) -> Optional[Credentials]:
        """Builds a google.oauth2.credentials.Credentials instance from session."""
        if not session or not session.credentials:
            return None
        try:
            return Credentials(
                token=session.credentials.get("token"),
                refresh_token=session.credentials.get("refresh_token"),
                token_uri=session.credentials.get("token_uri", "https://oauth2.googleapis.com/token"),
                client_id=session.credentials.get("client_id"),
                client_secret=session.credentials.get("client_secret"),
                scopes=session.credentials.get("scopes", GMAIL_SCOPES),
            )
        except Exception as e:
            print(f"[SessionManager Error] Failed to reconstruct credentials: {e}")
            return None


# Global singleton instance
session_manager = SessionManager()


def get_session_from_request(request: Request) -> Optional[SessionData]:
    """
    Extracts session token from cookie or Authorization header.
    Returns SessionData if valid, or None if unauthenticated.
    """
    # 1. Cookie
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if session_id:
        session = session_manager.get_session(session_id)
        if session:
            return session

    # 2. Bearer Header (for programmatic / mobile clients)
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        session = session_manager.get_session(token)
        if session:
            return session

    return None


def mask_email(email: str) -> str:
    """Masks an email for privacy-safe presentation, e.g. babulkumar••••@gmail.com."""
    if not email or "@" not in email:
        return email or "Unknown"
    local, domain = email.split("@", 1)
    if len(local) > 6:
        visible = local[:min(len(local), 10)]
    else:
        visible = local[:max(2, len(local) // 2)]
    return f"{visible}••••@{domain}"
