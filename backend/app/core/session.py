import os
import re
import time
import json
import secrets
import threading
import base64
import hashlib
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from fastapi import Request
from google.oauth2.credentials import Credentials
from cryptography.fernet import Fernet, InvalidToken
from backend.app.core.config import BASE_DIR, DATA_DIR, GMAIL_SCOPES

logger = logging.getLogger("mailmind.session")

SESSION_COOKIE_NAME = "mailmind_session"
SESSION_DURATION_SECONDS = 7 * 24 * 3600  # 7 days
SESSIONS_DIR = os.path.join(DATA_DIR, "sessions")
_handoff_lock = threading.Lock()

# Derive deterministic 32-byte Fernet key from SESSION_SECRET for at-rest token encryption
_session_secret_raw = os.getenv("SESSION_SECRET", "mailmind-default-secure-dev-secret-key-32b").encode("utf-8")
_fernet_key = base64.urlsafe_b64encode(hashlib.sha256(_session_secret_raw).digest())
_cipher = Fernet(_fernet_key)


def encrypt_session_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Encrypts session payload at rest on disk to protect OAuth refresh tokens."""
    raw_json = json.dumps(data).encode("utf-8")
    token = _cipher.encrypt(raw_json).decode("utf-8")
    return {"version": "enc_v1", "encrypted": token}


def decrypt_session_data(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Decrypts session payload, supporting envelope enc_v1 and legacy plaintext JSON."""
    if not isinstance(data, dict):
        return None
    if data.get("version") == "enc_v1" and "encrypted" in data:
        try:
            decrypted_bytes = _cipher.decrypt(data["encrypted"].encode("utf-8"))
            return json.loads(decrypted_bytes.decode("utf-8"))
        except (InvalidToken, Exception):
            return None
    # Backward compatibility: legacy plaintext session files
    if "session_id" in data and "user_id" in data:
        return data
    return None


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
        try:
            os.chmod(SESSIONS_DIR, 0o700)
        except Exception:
            pass
        self._load_persisted_sessions()

    def _load_persisted_sessions(self):
        """Restores unexpired sessions across server restarts, renewing valid credentialed sessions."""
        try:
            now = time.time()
            for fname in os.listdir(SESSIONS_DIR):
                if fname.endswith(".json") and not fname.startswith("_"):
                    fpath = os.path.join(SESSIONS_DIR, fname)
                    try:
                        with open(fpath, "r", encoding="utf-8") as f:
                            raw = json.load(f)
                            data = decrypt_session_data(raw)
                            if data:
                                session = SessionData(**data)
                                has_creds = bool(session.credentials and (session.credentials.get("refresh_token") or session.credentials.get("token")))
                                if not session.is_expired():
                                    self._sessions[session.session_id] = session
                                elif has_creds:
                                    # Sliding renewal for active users with valid credentials
                                    session.expires_at = now + SESSION_DURATION_SECONDS
                                    self._sessions[session.session_id] = session
                                    self._persist_session(session)
                                else:
                                    try:
                                        os.remove(fpath)
                                    except Exception:
                                        pass
                    except Exception:
                        pass
        except Exception as e:
            print(f"[SessionManager Warning] Could not load persisted sessions: {e}")

    def _persist_session(self, session: SessionData):
        """Persists session to disk encrypted at rest so active users aren't logged out on restart."""
        if not self._is_safe_session_id(session.session_id):
            print(f"[SessionManager Warning] Refusing to persist invalid session ID: {session.session_id}")
            return
        try:
            fpath = os.path.join(SESSIONS_DIR, f"{session.session_id}.json")
            envelope = encrypt_session_data(session.to_dict())
            flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
            fd = os.open(fpath, flags, 0o600)
            with open(fd, "w", encoding="utf-8") as f:
                json.dump(envelope, f, indent=2)
            try:
                os.chmod(fpath, 0o600)
            except Exception:
                pass
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
            expiry = getattr(credentials, "expiry", None)
            expiry_str = None
            if expiry is not None:
                if hasattr(expiry, "isoformat"):
                    try:
                        expiry_str = expiry.isoformat()
                    except Exception:
                        expiry_str = str(expiry)
                elif isinstance(expiry, str):
                    expiry_str = expiry

            creds_dict = {
                "token": getattr(credentials, "token", None),
                "refresh_token": getattr(credentials, "refresh_token", None),
                "token_uri": getattr(credentials, "token_uri", None),
                "client_id": getattr(credentials, "client_id", None),
                "client_secret": getattr(credentials, "client_secret", None),
                "scopes": getattr(credentials, "scopes", None),
                "expiry": expiry_str,
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
        """Retrieves an active session by ID, implementing sliding expiration for active users."""
        if not self._is_safe_session_id(session_id):
            return None
        now = time.time()
        session = self._sessions.get(session_id)
        if not session:
            # Check disk in case another worker saved it
            fpath = os.path.join(SESSIONS_DIR, f"{session_id}.json")
            if os.path.exists(fpath):
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        raw = json.load(f)
                        data = decrypt_session_data(raw)
                        if data:
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

        # Sliding expiration: extend session if it has passed at least 1 hour of its lifespan
        if session.expires_at - now < (SESSION_DURATION_SECONDS - 3600):
            session.expires_at = now + SESSION_DURATION_SECONDS
            self._persist_session(session)

        return session

    def get_or_create_dev_session(self) -> Optional[SessionData]:
        """
        In non-production development environments, retrieves an existing active session
        or seeds a persistent developer session from local token.json if available and valid.
        """
        is_production = os.getenv("ENVIRONMENT", "development").lower() == "production"
        if is_production:
            return None

        # Check existing active sessions for dev user
        for s in list(self._sessions.values()):
            if s.email and "babulkumar" in s.email:
                if not s.credentials:
                    return s
                creds = self.get_credentials(s)
                if creds and creds.valid:
                    return s
                if creds and creds.expired and creds.refresh_token:
                    try:
                        from google.auth.transport.requests import Request
                        creds.refresh(Request())
                        s.credentials["token"] = creds.token
                        if creds.expiry:
                            s.credentials["expiry"] = creds.expiry.isoformat()
                        self._persist_session(s)
                        return s
                    except Exception as ref_err:
                        if "invalid_grant" in str(ref_err).lower():
                            logger.warning(
                                "Dev session credentials revoked or expired for %s: %s. Clearing credentials.",
                                s.email, ref_err
                            )
                            s.credentials = None
                            self._persist_session(s)
                            return s

        from backend.app.core.config import TOKEN_FILE
        if os.path.exists(TOKEN_FILE):
            try:
                from google.auth.transport.requests import Request
                creds = Credentials.from_authorized_user_file(TOKEN_FILE, GMAIL_SCOPES)
                if creds and creds.expired and creds.refresh_token:
                    try:
                        creds.refresh(Request())
                        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
                            f.write(creds.to_json())
                    except Exception as ref_err:
                        err_msg = str(ref_err)
                        if "invalid_grant" in err_msg.lower():
                            logger.warning(
                                "Local token in %s has been revoked or expired by Google (%s). "
                                "Quarantining invalid token. Please sign in via Google OAuth.",
                                TOKEN_FILE, err_msg
                            )
                            try:
                                os.rename(TOKEN_FILE, TOKEN_FILE + ".revoked")
                            except Exception:
                                pass
                            return None

                with open(TOKEN_FILE, "r", encoding="utf-8") as f:
                    creds_dict = json.load(f)
                return self.create_session(
                    user_id="1795488",
                    email="babulkumar0220@gmail.com",
                    credentials=creds_dict
                )
            except Exception as e:
                logger.warning("Could not seed dev session from token.json: %s", e)
        return None

    def invalidate_credentials(self, session_id: Optional[str]) -> bool:
        """Clears OAuth credentials on a session when revoked by Google without destroying the user session."""
        if not self._is_safe_session_id(session_id):
            return False
        session = self._sessions.get(session_id)
        if session:
            session.credentials = None
            self._persist_session(session)
            return True
        return False

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
        with _handoff_lock:
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
        with _handoff_lock:
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
            raw_expiry = session.credentials.get("expiry")
            parsed_expiry = None
            if raw_expiry:
                if isinstance(raw_expiry, str):
                    try:
                        clean_exp = raw_expiry.replace("Z", "+00:00")
                        parsed_expiry = datetime.fromisoformat(clean_exp)
                        if parsed_expiry.tzinfo is not None:
                            parsed_expiry = parsed_expiry.astimezone(timezone.utc).replace(tzinfo=None)
                    except Exception:
                        pass
                elif isinstance(raw_expiry, (int, float)):
                    parsed_expiry = datetime.fromtimestamp(raw_expiry, tz=timezone.utc).replace(tzinfo=None)

            return Credentials(
                token=session.credentials.get("token"),
                refresh_token=session.credentials.get("refresh_token"),
                token_uri=session.credentials.get("token_uri", "https://oauth2.googleapis.com/token"),
                client_id=session.credentials.get("client_id"),
                client_secret=session.credentials.get("client_secret"),
                scopes=session.credentials.get("scopes", GMAIL_SCOPES),
                expiry=parsed_expiry,
            )
        except Exception as e:
            logger.error("Failed to reconstruct credentials: %s", e)
            return None


# Global singleton instance
session_manager = SessionManager()


def get_session_from_request(request: Request) -> Optional[SessionData]:
    """
    Extracts session token from cookie or Authorization header.
    Returns SessionData if valid, or None if unauthenticated.
    """
    # 1. Bearer Header (for programmatic / mobile clients)
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        session = session_manager.get_session(token)
        if session:
            return session

    # 2. Cookie (for browser / SameSite sessions)
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if session_id:
        session = session_manager.get_session(session_id)
        if session:
            return session

    # 3. Explicit dev header
    dev_header = request.headers.get("X-MailMind-Dev-Session")
    if dev_header:
        session = session_manager.get_session(dev_header.strip())
        if session:
            return session

    # 4. Explicit session_id query param
    try:
        query_session = request.query_params.get("session_id")
        if query_session:
            session = session_manager.get_session(query_session.strip())
            if session:
                return session
    except Exception:
        pass

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


def is_admin_user(session: Optional[SessionData], request: Optional[Request] = None) -> bool:
    """
    Checks if the authenticated user has administrative / developer privileges.
    In production: user's email or user_id must be in ADMIN_USERS or DEV_EMAILS env vars.
    In development: allowed if explicitly enabled or if local dev mode.
    """
    if not session:
        return False
    admin_env = os.getenv("ADMIN_USERS", os.getenv("DEV_EMAILS", "")).strip()
    if admin_env:
        allowed = {e.strip().lower() for e in admin_env.split(",") if e.strip()}
        user_email = (session.email or "").strip().lower()
        user_id = (session.user_id or "").strip().lower()
        return user_email in allowed or user_id in allowed

    is_production = os.getenv("ENVIRONMENT", "development").lower() == "production"
    if is_production:
        return False
    return os.getenv("ENABLE_DEV_MODE", "true").lower() in ("true", "1", "yes")
