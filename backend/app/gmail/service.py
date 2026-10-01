import os
from typing import Optional
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from backend.app.core.config import CREDENTIALS_FILE, TOKEN_FILE, GMAIL_SCOPES
from backend.app.core.session import SessionData, session_manager


def get_user_gmail_service(
    session: Optional[SessionData] = None,
    credentials: Optional[Credentials] = None,
):
    """
    Returns an isolated Google Gmail API client for a specific user session or credentials.
    STRICTLY USER-SCOPED: Raises PermissionError if no authenticated session or valid credentials exist.
    DOES NOT FALL BACK TO ANY GLOBAL OR DEVELOPER TOKEN.
    """
    creds = credentials

    if creds is None and session is not None:
        creds = session_manager.get_credentials(session)
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                # Update session with refreshed token
                session.credentials["token"] = creds.token
                session_manager._persist_session(session)
            except Exception as e:
                print(f"[OAuth Warning] Token refresh failed for user {session.email}: {e}")

    # Enforce strict session requirement for web requests: NO dev token fallback
    if not creds or not creds.valid:
        raise PermissionError("Valid Google OAuth session required. Unauthenticated access denied.")

    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def get_dev_cli_gmail_service():
    """
    Developer CLI-only utility to obtain a Gmail service from google_auth/token.json.
    STRICTLY FOR OFFLINE CLI SCRIPTS AND INTEGRATION TESTS.
    NEVER ACCESSIBLE OR INVOKED FROM LIVE WEB REQUESTS.
    """
    if not os.path.exists(TOKEN_FILE):
        raise PermissionError(f"Developer token file missing at {TOKEN_FILE}.")
    creds = Credentials.from_authorized_user_file(TOKEN_FILE, GMAIL_SCOPES)
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            with open(TOKEN_FILE, "w", encoding="utf-8") as f:
                f.write(creds.to_json())
        except Exception as e:
            print(f"[OAuth Warning] Dev token refresh failed: {e}")

    if not creds or not creds.valid:
        raise PermissionError("Valid Google OAuth credentials not found in developer token.")

    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def get_gmail_service(session_id: Optional[str] = None):
    """
    Convenience wrapper returning user-scoped Gmail service if session_id is provided,
    otherwise falling back to dev mode via get_dev_cli_gmail_service() ONLY for offline CLI scripts/tests.
    """
    if session_id:
        session = session_manager.get_session(session_id)
        return get_user_gmail_service(session=session)
    return get_dev_cli_gmail_service()
