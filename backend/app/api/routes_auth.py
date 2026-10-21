import os
import json
import secrets
import time
import urllib.parse
from typing import Optional
from fastapi import APIRouter, Request, Response, HTTPException, Query
from fastapi.responses import RedirectResponse, JSONResponse
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from backend.app.core.config import CREDENTIALS_FILE, GMAIL_SCOPES, ALLOWED_ORIGINS
from backend.app.core.session import (
    session_manager,
    get_session_from_request,
    SESSION_COOKIE_NAME,
    SESSION_DURATION_SECONDS,
    SESSIONS_DIR,
    mask_email,
    is_admin_user,
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


def _store_pending_state(state: str, code_verifier: Optional[str], frontend_origin: Optional[str] = None):
    now = time.time()
    states = _load_pending_states()
    # Prune states older than 10 minutes
    pruned = {s: data for s, data in states.items() if now - data.get("timestamp", 0) <= 600}
    pruned[state] = {
        "timestamp": now,
        "code_verifier": code_verifier,
        "frontend_origin": frontend_origin
    }
    _save_pending_states(pruned)
    _PENDING_STATES[state] = {
        "timestamp": now,
        "code_verifier": code_verifier,
        "frontend_origin": frontend_origin
    }


def _retrieve_and_consume_state(state: str, request: Request) -> tuple[bool, Optional[str], Optional[str]]:
    """
    Retrieves and consumes the PKCE code_verifier and frontend_origin for the given OAuth state.
    Returns (state_valid, code_verifier, frontend_origin).
    """
    now = time.time()
    code_verifier = None
    frontend_origin = None
    state_valid = False

    # 1. Check in-memory state
    mem_data = _PENDING_STATES.pop(state, None)
    if mem_data and now - mem_data.get("timestamp", 0) <= 600:
        state_valid = True
        code_verifier = mem_data.get("code_verifier")
        frontend_origin = mem_data.get("frontend_origin")

    # 2. Check persisted file (survives uvicorn reload)
    states = _load_pending_states()
    if state in states:
        file_data = states.pop(state)
        _save_pending_states(states)
        if now - file_data.get("timestamp", 0) <= 600:
            state_valid = True
            if not code_verifier:
                code_verifier = file_data.get("code_verifier")
            if not frontend_origin:
                frontend_origin = file_data.get("frontend_origin")

    # 3. Fallback to HttpOnly cookie
    cookie_val = request.cookies.get("mailmind_oauth_verifier", "")
    if cookie_val:
        if ":" in cookie_val:
            parts = cookie_val.split(":", 2)
            c_state = parts[0]
            if c_state == state:
                state_valid = True
                if not code_verifier and len(parts) > 1:
                    code_verifier = parts[1]
                if not frontend_origin and len(parts) > 2:
                    frontend_origin = parts[2]
        elif not code_verifier:
            code_verifier = cookie_val

    return state_valid, code_verifier or "", frontend_origin


def _is_allowed_frontend_origin(origin: Optional[str]) -> bool:
    """Validates that a frontend origin is authorized to prevent open redirect vulnerabilities."""
    if not origin or not isinstance(origin, str):
        return False
    clean = origin.strip().rstrip("/")
    if not clean:
        return False
    allowed_lower = [o.lower() for o in ALLOWED_ORIGINS]
    if clean.lower() in allowed_lower:
        return True
    try:
        parsed = urllib.parse.urlparse(clean)
        hostname = (parsed.hostname or "").lower()
        if not hostname:
            return False
        if hostname in ("localhost", "127.0.0.1"):
            return True
        if hostname == "mail-mind-ten-chi.vercel.app" or hostname.endswith(".vercel.app"):
            return True
        if hostname == "mailmind-api-xzu8.onrender.com" or hostname.endswith(".onrender.com"):
            return True
    except Exception:
        return False
    return False


def resolve_frontend_url(request: Request, stored_origin: Optional[str] = None) -> str:
    """
    Resolves the canonical target frontend URL for redirecting authenticated users.
    Prioritizes:
      1. Validated frontend origin stored during /api/auth/login
      2. Validated origin or referer in incoming request
      3. Explicit FRONTEND_URL environment variable override (if set to "" in monolithic mode, returns "")
      4. Localhost dev fallback (http://localhost:5173 if request is local)
      5. Default cloud deployment fallback (https://mail-mind-ten-chi.vercel.app)
    """
    if stored_origin and _is_allowed_frontend_origin(stored_origin):
        return stored_origin.strip().rstrip("/")

    req_origin = request.headers.get("origin")
    if req_origin and _is_allowed_frontend_origin(req_origin):
        return req_origin.strip().rstrip("/")

    req_referer = request.headers.get("referer")
    if req_referer:
        try:
            parsed = urllib.parse.urlparse(req_referer)
            ref_origin = f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
            if _is_allowed_frontend_origin(ref_origin):
                return ref_origin
        except Exception:
            pass

    # Check explicit FRONTEND_URL environment variable override
    env_frontend = os.environ.get("FRONTEND_URL")
    if env_frontend is not None:
        env_frontend = env_frontend.strip().rstrip("/")
        if not env_frontend:
            return ""
        if _is_allowed_frontend_origin(env_frontend):
            return env_frontend

    # If incoming request host is localhost or 127.0.0.1, keep user on local frontend
    host = request.headers.get("host", "").lower()
    if "localhost" in host or "127.0.0.1" in host:
        return "http://localhost:5173"

    if "testserver" in host:
        return ""

    return "https://mail-mind-ten-chi.vercel.app"


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
    explicit_uri = os.getenv("GMAIL_REDIRECT_URI", "").strip()
    if explicit_uri:
        return explicit_uri

    render_external = os.getenv("RENDER_EXTERNAL_URL", "").strip().rstrip("/")
    if render_external:
        return f"{render_external}/api/auth/callback"

    backend_url = os.getenv("BACKEND_URL", "").strip().rstrip("/")
    if backend_url:
        return f"{backend_url}/api/auth/callback"

    # Avoid using frontend host (e.g. Vercel) if request was proxied
    forwarded_host = request.headers.get("x-forwarded-host", "")
    if forwarded_host and "vercel.app" in forwarded_host:
        host = request.headers.get("host") or "mailmind-api-xzu8.onrender.com"
        proto = request.headers.get("x-forwarded-proto") or "https"
        return f"{proto}://{host}/api/auth/callback"

    base = get_base_url(request)
    return f"{base}/api/auth/callback"


def get_cookie_security_flags(request: Request) -> tuple[str, bool]:
    """
    Determines SameSite and Secure cookie flags for session management.
    For Vercel (frontend) + Render (backend) cross-origin deployment:
      - SameSite MUST be 'none'
      - Secure MUST be True
      - HttpOnly MUST be True
      - Path MUST be '/'
    This allows the browser to include the session cookie in cross-site fetch
    requests from Vercel with credentials: 'include'.
    """
    # 1. Explicit override via COOKIE_SAMESITE environment variable
    explicit_samesite = os.getenv("COOKIE_SAMESITE", "").strip().lower()
    if explicit_samesite in ("none", "lax", "strict"):
        is_secure = (explicit_samesite == "none") or (request.url.scheme == "https") or (request.headers.get("x-forwarded-proto") == "https")
        return explicit_samesite, is_secure

    # 2. Production or Render or HTTPS or Cross-Origin Frontend Detection
    is_prod_env = os.getenv("ENVIRONMENT", "development").lower() == "production"
    is_render = bool(os.getenv("RENDER") == "true" or "onrender.com" in request.headers.get("host", "") or "onrender.com" in os.getenv("BASE_URL", ""))
    is_https = bool(
        request.url.scheme == "https"
        or request.headers.get("x-forwarded-proto") == "https"
        or os.getenv("BASE_URL", "").startswith("https://")
        or os.getenv("FRONTEND_URL", "").startswith("https://")
    )
    frontend_url = os.getenv("FRONTEND_URL", "").strip().lower()
    is_cross_site = bool(frontend_url and not any(loc in frontend_url for loc in ("localhost", "127.0.0.1")))

    if is_prod_env or is_render or is_https or is_cross_site:
        return "none", True

    # 3. Local HTTP development fallback
    return "lax", False


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
    redirect_to: Optional[str] = Query(default="/", description="Frontend return path"),
    origin: Optional[str] = Query(default=None, description="Frontend origin")
):
    """
    Initiates Google OAuth 2.0 flow with account selection.
    Returns the Google authorization URL or redirects if requested by a browser.
    Preserves PKCE code_verifier and frontend origin across redirects.
    """
    # Detect frontend origin from query param, Origin header, or Referer header
    detected_origin = None
    for cand in [origin, request.headers.get("origin"), request.headers.get("referer")]:
        if cand:
            try:
                parsed = urllib.parse.urlparse(cand)
                base_cand = f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
                if _is_allowed_frontend_origin(base_cand):
                    detected_origin = base_cand
                    break
            except Exception:
                continue

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
        _store_pending_state(state, code_verifier, frontend_origin=detected_origin)
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
        cookie_samesite, cookie_secure = get_cookie_security_flags(request)
        cookie_val = f"{state}:{code_verifier}:{detected_origin or ''}" if detected_origin else f"{state}:{code_verifier}"
        res.set_cookie(
            key="mailmind_oauth_verifier",
            value=cookie_val,
            max_age=600,
            httponly=True,
            samesite=cookie_samesite,
            secure=cookie_secure,
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
    frontend_url = resolve_frontend_url(request)
    if error:
        err_url = f"{frontend_url}/?auth_error={error}" if frontend_url else f"/?auth_error={error}"
        return RedirectResponse(err_url, status_code=302)

    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing OAuth code or state parameter.")

    state_valid, code_verifier, stored_origin = _retrieve_and_consume_state(state, request)
    if not state_valid:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state parameter.")

    frontend_url = resolve_frontend_url(request, stored_origin=stored_origin)
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

        # Generate short-lived (120s), single-use cryptographic handoff code
        handoff_code = session_manager.create_handoff(new_session.session_id)

        target_url = f"{frontend_url}/auth/callback?handoff={handoff_code}" if frontend_url else f"/auth/callback?handoff={handoff_code}"
        response = RedirectResponse(url=target_url, status_code=302)
        cookie_samesite, cookie_secure = get_cookie_security_flags(request)

        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=new_session.session_id,
            max_age=SESSION_DURATION_SECONDS,
            httponly=True,
            samesite=cookie_samesite,
            secure=cookie_secure,
            path="/"
        )
        response.delete_cookie(
            key="mailmind_oauth_verifier",
            path="/",
            samesite=cookie_samesite,
            secure=cookie_secure
        )
        print(f"[OAuth Callback] Successfully authenticated {mask_email(email_address)}. Session created. Redirecting to frontend handoff at {frontend_url}.")
        return response
    except Exception as e:
        print(f"[OAuth Callback Error] {e}")
        err_url = f"{frontend_url}/?auth_error={str(e)}" if frontend_url else f"/?auth_error={str(e)}"
        return RedirectResponse(err_url, status_code=302)


@router.post("/exchange")
@router.get("/exchange")
async def auth_exchange(
    request: Request,
    handoff: Optional[str] = Query(default=None),
):
    """
    Consumes a one-time OAuth handoff token and sets the same-origin session cookie.
    Enforces strict single-use anti-replay protection.
    Never exposes OAuth tokens to the client.
    """
    handoff_token = handoff
    if not handoff_token and request.method == "POST":
        try:
            payload = await request.json()
            if isinstance(payload, dict):
                handoff_token = payload.get("handoff")
        except Exception:
            pass

    if not handoff_token:
        try:
            handoff_token = request.query_params.get("handoff")
        except Exception:
            pass

    if not handoff_token:
        raise HTTPException(status_code=400, detail="Missing required handoff code.")

    session_id = session_manager.consume_handoff(handoff_token)
    if not session_id:
        raise HTTPException(
            status_code=400,
            detail="Invalid, expired, or already-consumed handoff code. Please sign in again."
        )

    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=401, detail="Session expired or invalid.")

    cookie_samesite, cookie_secure = get_cookie_security_flags(request)

    res = JSONResponse(content={
        "status": "success",
        "authenticated": True,
        "user": {
            "email": session.email,
            "masked_email": mask_email(session.email),
            "user_id": session.user_id,
            "is_admin": is_admin_user(session, request),
        }
    })
    res.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session.session_id,
        max_age=SESSION_DURATION_SECONDS,
        httponly=True,
        samesite=cookie_samesite,
        secure=cookie_secure,
        path="/"
    )
    print(f"[Auth Exchange] Successfully exchanged handoff for {mask_email(session.email)}. Session cookie set.")
    return res


@router.get("/status")
def auth_status(request: Request):
    """
    Returns current authentication status and user metadata.
    NEVER leaks tokens or secrets to the client.
    """
    cookie_present = SESSION_COOKIE_NAME in request.cookies
    session = get_session_from_request(request)
    if session:
        return {
            "authenticated": True,
            "mode": "session",
            "user": {
                "email": session.email,
                "masked_email": mask_email(session.email),
                "user_id": session.user_id,
                "is_admin": is_admin_user(session, request),
            }
        }

    print(f"[Auth Status] Request unauthenticated. Cookie present: {cookie_present}, Origin: {request.headers.get('origin')}")
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

    cookie_samesite, cookie_secure = get_cookie_security_flags(request)

    res = JSONResponse(content={"status": "logged_out", "message": "Disconnected successfully"})
    res.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        samesite=cookie_samesite,
        secure=cookie_secure
    )
    return res


@router.post("/test-session")
def create_test_session(
    request: Request,
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

    cookie_samesite, cookie_secure = get_cookie_security_flags(request)

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
        samesite=cookie_samesite,
        secure=cookie_secure,
        path="/"
    )
    return res
