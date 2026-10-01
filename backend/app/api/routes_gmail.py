from fastapi import APIRouter, Request, HTTPException
from backend.app.core.session import get_session_from_request
from backend.app.gmail.service import get_user_gmail_service
from backend.app.gmail.client import get_profile

router = APIRouter(tags=["Gmail"])


@router.get("/api/profile")
def gmail_profile(request: Request):
    """
    Retrieves authenticated Gmail user profile metadata for the current user session.
    Derived strictly from backend session, never from client-provided user IDs.
    """
    session = get_session_from_request(request)
    if not session:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please connect your Gmail account."
        )

    try:
        service = get_user_gmail_service(session=session)
        profile = get_profile(service)
        email_addr = profile.get("emailAddress", session.email)
        return {
            "status": "success",
            "email_address": email_addr,
            "messages_total": int(profile.get("messagesTotal", 0)),
            "threads_total": int(profile.get("threadsTotal", 0)),
            "access_scope": "https://www.googleapis.com/auth/gmail.readonly (READ-ONLY)"
        }
    except PermissionError:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please connect your Gmail account."
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Gmail API connection error: {str(e)}")
