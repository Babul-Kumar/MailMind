import os
import json
import secrets
import time
from typing import Optional
from fastapi import APIRouter, Request, Response, HTTPException, Query
from fastapi.responses import RedirectResponse, JSONResponse
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from backend.app.core.config import CREDENTIALS_FILE, GMAIL_SCOPES
from backend.app.core.session import (
    session_manager,
    get_session_from_request,
    SESSION_COOKIE_NAME,
    SESSION_DURATION_SECONDS,
    SESSIONS_DIR,
    mask_email,
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

# Pending OAuth states: state -> dict with timestamp and PKCE code_verifier
_PENDING_STATES: dict[str, dict] = {}
STATE_FILE = os.path.join(SESSIONS_DIR, "_pending_oauth_states.json")


def _load_pending_states() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_pending_states(states: dict):
    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(states, f)
    except Exception as e:
        print(f"[Warning] Failed to persist pending OAuth states: {e}")


def _store_pending_state(state: str, code_verifier: Optional[str]):
    now = time.time()
    states = _load_pending_states()
    # Prune states older than 10 minutes
    pruned = {s: data for s, data in states.items() if now - data.get("timestamp", 0) <= 600}
    pruned[state] = {
        "timestamp": now,
        "code_verifier": code_verifier
    }
    _save_pending_states(pruned)
    _PENDING_STATES[state] = {"timestamp": now, "code_verifier": code_verifier}


def _retrieve_and_consume_state(state: str, request: Request) -> Optional[str]:
    """
    Retrieves and consumes the PKCE code_verifier for the given OAuth state.
    Returns code_verifier string (or empty string) if state is valid, or None if state is invalid/expired.
    """
    now = time.time()
    code_verifier = None
    state_valid = False

    # 1. Check in-memory state
    mem_data = _PENDING_STATES.pop(state, None)
    if mem_data and now - mem_data.get("timestamp", 0) <= 600:
        state_valid = True
        code_verifier = mem_data.get("code_verifier")

    # 2. Check persisted file (survives uvicorn reload)
    states = _load_pending_states()
    if state in states:
        file_data = states.pop(state)
        _save_pending_states(states)
        if now - file_data.get("timestamp", 0) <= 600:
            state_valid = True
            if not code_verifier:
                code_verifier = file_data.get("code_verifier")

    # 3. Fallback to HttpOnly cookie
    cookie_val = request.cookies.get("mailmind_oauth_verifier", "")
    if cookie_val:
        if ":" in cookie_val:
            c_state, c_verifier = cookie_val.split(":", 1)
            if c_state == state:
                state_valid = True
                if not code_verifier:
                    code_verifier = c_verifier
        elif not code_verifier:
            code_verifier = cookie_val

    if not state_valid:
        return None

    return code_verifier or ""


def get_base_url(request: Request) -> str:
    """
    Resolves canonical base URL for the application.
    Prioritizes:
      1. Explicit BASE_URL environment variable (e.g. https://mailmind.onrender.com)
      2. Reverse proxy headers (X-Forwarded-Proto, X-Forwarded-Host) injected by Render / Nginx
      3. Incoming request URL (upgrading scheme to https if ENVIRONMENT=production)
    """
    env_base = os.getenv("BASE_URL", "").strip().rstrip("/")
    if env_base:
        return env_base

    proto = request.headers.get("x-forwarded-proto")
    host = request.headers.get("x-forwarded-host")
    if proto and host:
        return f"{proto}://{host}".rstrip("/")

    url = request.base_url
    scheme = url.scheme
    if os.getenv("ENVIRONMENT", "development").lower() == "production" and not scheme.startswith("https"):
        scheme = "https"
    netloc = url.netloc
    return f"{scheme}://{netloc}".rstrip("/")


def get_redirect_uri(request: Request) -> str:
    """Returns the canonical OAuth 2.0 callback redirect URI."""
    base = get_base_url(request)
    return f"{base}/api/auth/callback"


def create_oauth_flow(
    redirect_uri: str,
    state: Optional[str] = None,
    code_verifier: Optional[str] = None
) -> Flow:
    """
    Builds a Google OAuth 2.0 Flow instance.
    Supports:
      1. GOOGLE_OAUTH_CLIENT_JSON: Raw credentials JSON string in environment variable
      2. GOOGLE_CLIENT_ID + GOOGLE_CLIENT_SECRET: Standard cloud environment variables
      3. CREDENTIALS_FILE: Physical credentials.json file (supporting both 'web' and 'installed' schemas)
    """
    # 1. Environment variable with full client JSON
    oauth_json_env = os.getenv("GOOGLE_OAUTH_CLIENT_JSON", "").strip()
    if oauth_json_env:
        try:
            client_config = json.loads(oauth_json_env)
            return Flow.from_client_config(
                client_config,
                scopes=GMAIL_SCOPES,
                redirect_uri=redirect_uri,
                state=state,
                code_verifier=code_verifier
            )
        except Exception as err:
            print(f"[OAuth Config Error] Failed parsing GOOGLE_OAUTH_CLIENT_JSON: {err}")

    # 2. Environment variables with Client ID & Client Secret
    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
    if client_id and client_secret:
        client_config = {
            "web": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [redirect_uri],
            }
        }
        return Flow.from_client_config(
            client_config,
            scopes=GMAIL_SCOPES,
            redirect_uri=redirect_uri,
            state=state,
            code_verifier=code_verifier
        )

    # 3. File-based credentials
    if os.path.exists(CREDENTIALS_FILE):
        try:
            with open(CREDENTIALS_FILE, "r", encoding="utf-8") as f:
                raw_config = json.load(f)
            return Flow.from_client_config(
                raw_config,
                scopes=GMAIL_SCOPES,
                redirect_uri=redirect_uri,
                state=state,
                code_verifier=code_verifier
            )
        except Exception:
            return Flow.from_client_secrets_file(
                CREDENTIALS_FILE,
                scopes=GMAIL_SCOPES,
                redirect_uri=redirect_uri,
                state=state,
                code_verifier=code_verifier
            )

    raise HTTPException(
        status_code=500,
        detail=(
            f"Google OAuth client secrets not configured. Please provide GOOGLE_CLIENT_ID and "
            f"GOOGLE_CLIENT_SECRET environment variables, or mount credentials.json at {CREDENTIALS_FILE}."
        )
    )


@router.get("/login")
def auth_login(
    request: Request,
    prompt: Optional[str] = Query(default="select_account", description="Consent/Account selection prompt"),
    redirect_to: Optional[str] = Query(default="/", description="Frontend return path")
):
    """
    Initiates Google OAuth 2.0 flow with account selection.
    Returns the Google authorization URL or redirects if requested by a browser.
    Preserves PKCE code_verifier across redirects.
    """
    state = secrets.token_urlsafe(16)
    redirect_uri = get_redirect_uri(request)

    try:
        flow = create_oauth_flow(redirect_uri=redirect_uri)
        auth_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt=prompt or "select_account",
            state=state
        )
        code_verifier = getattr(flow, "code_verifier", None)
        _store_pending_state(state, code_verifier)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate OAuth flow: {str(e)}")

    accept_header = request.headers.get("accept", "")
    if "text/html" in accept_header:
        res = RedirectResponse(auth_url)
    else:
        res = JSONResponse(content={
            "status": "success",
            "auth_url": auth_url,
            "authorization_url": auth_url,
            "state": state
        })

    if code_verifier:
        is_production = os.getenv("ENVIRONMENT", "development").lower() == "production"
        is_secure = is_production or request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"
        res.set_cookie(
            key="mailmind_oauth_verifier",
            value=f"{state}:{code_verifier}",
            max_age=600,
            httponly=True,
            samesite="lax",
            secure=is_secure,
            path="/"
        )
    return res


@router.get("/callback")
def auth_callback(
    request: Request,
    code: Optional[str] = Query(default=None),
    state: Optional[str] = Query(default=None),
    error: Optional[str] = Query(default=None),
):
    """
    Handles Google OAuth redirect, exchanges auth code for user credentials with PKCE verifier,
    extracts user identity, creates an isolated session, and sets the secure HttpOnly cookie.
    """
    if error:
        return RedirectResponse(f"/?auth_error={error}")

    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing OAuth code or state parameter.")

    code_verifier = _retrieve_and_consume_state(state, request)
    if code_verifier is None:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state parameter.")

    redirect_uri = get_redirect_uri(request)

    try:
        flow = create_oauth_flow(
            redirect_uri=redirect_uri,
            state=state,
            code_verifier=code_verifier if code_verifier else None
        )
        if code_verifier:
            flow.code_verifier = code_verifier
            flow.fetch_token(code=code, code_verifier=code_verifier)
        else:
            flow.fetch_token(code=code)
        credentials = flow.credentials

        # Verify credentials by fetching user profile from Gmail API
        service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
        profile = service.users().getProfile(userId="me").execute()
        email_address = profile.get("emailAddress", "unknown@gmail.com")
        user_id = profile.get("historyId", email_address)

        # Invalidate previous session if any was attached
        old_session = get_session_from_request(request)
        if old_session:
            session_manager.delete_session(old_session.session_id)

        # Create new isolated session
        new_session = session_manager.create_session(
            user_id=user_id,
            email=email_address,
            credentials=credentials
        )

        response = RedirectResponse(url="/", status_code=302)
        is_production = os.getenv("ENVIRONMENT", "development").lower() == "production"
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=new_session.session_id,
            max_age=SESSION_DURATION_SECONDS,
            httponly=True,
            samesite="lax",
            secure=is_production,
            path="/"
        )
        response.delete_cookie(key="mailmind_oauth_verifier", path="/")
        return response
    except Exception as e:
        print(f"[OAuth Callback Error] {e}")
        return RedirectResponse(f"/?auth_error={str(e)}")


@router.get("/status")
def auth_status(request: Request):
    """
    Returns current authentication status and user metadata.
    NEVER leaks tokens or secrets to the client.
    """
    session = get_session_from_request(request)
    if session:
        return {
            "authenticated": True,
            "mode": "session",
            "user": {
                "email": session.email,
                "masked_email": mask_email(session.email),
                "user_id": session.user_id,
            }
        }

    return {
        "authenticated": False,
        "mode": "unauthenticated",
        "user": None
    }


@router.post("/logout")
def auth_logout(request: Request, response: Response):
    """
    Disconnects the active account, destroys the session, and clears the session cookie.
    """
    session = get_session_from_request(request)
    if session:
        session_manager.delete_session(session.session_id)

    res = JSONResponse(content={"status": "logged_out", "message": "Disconnected successfully"})
    res.delete_cookie(key=SESSION_COOKIE_NAME, path="/")
    return res


@router.post("/test-session")
def create_test_session(
    email: str = Query(..., description="Test user email"),
    response: Response = None
):
    """
    Helper endpoint for automated tests and multi-user concurrency testing.
    Creates a simulated isolated session for testing without hitting Google OAuth servers.
    Disabled in production unless ALLOW_TEST_ENDPOINTS=true.
    """
    is_production = os.getenv("ENVIRONMENT", "development").lower() == "production"
    allow_test = os.getenv("ALLOW_TEST_ENDPOINTS", "false" if is_production else "true").lower() in ("true", "1", "yes")
    if is_production and not allow_test:
        raise HTTPException(
            status_code=403,
            detail="Test session creation endpoint is disabled in production environment."
        )
    simulated_creds = {
        "token": f"mock_token_{email}",
        "refresh_token": f"mock_refresh_{email}",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "mock_client_id",
        "client_secret": "mock_client_secret",
        "scopes": GMAIL_SCOPES,
    }
    session = session_manager.create_session(
        user_id=f"uid_{email}",
        email=email,
        credentials=simulated_creds
    )

    res = JSONResponse(content={
        "status": "success",
        "session_id": session.session_id,
        "email": email,
        "masked_email": mask_email(email),
        "user_id": session.user_id
    })
    res.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session.session_id,
        max_age=SESSION_DURATION_SECONDS,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/"
    )
    return res
