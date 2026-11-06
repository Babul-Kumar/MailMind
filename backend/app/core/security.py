from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from backend.app.core.config import ALLOWED_ORIGINS


def setup_security(app: FastAPI) -> None:
    """Configures CORS, defensive security headers, CSRF protection, and standard exception handlers."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def security_headers_and_csrf_middleware(request: Request, call_next):
        # 1. CSRF Protection for state-mutating methods when session cookie is attached
        if request.method in ("POST", "PUT", "DELETE", "PATCH"):
            path = request.url.path
            exempt_prefixes = (
                "/api/auth/callback",
                "/api/auth/exchange",
                "/api/auth/test-session",
                "/api/auth/login",
            )
            cookie_present = "mailmind_session" in request.cookies
            if cookie_present and not any(path.startswith(p) for p in exempt_prefixes):
                custom_hdr = request.headers.get("x-requested-with") or request.headers.get("x-csrf-token")
                sec_fetch_site = request.headers.get("sec-fetch-site")
                # Allow same-origin or non-browser API client requests (where sec-fetch-site is none or same-origin)
                # But require custom header if cross-site or standard browser request
                if not custom_hdr and sec_fetch_site == "cross-site":
                    return JSONResponse(
                        status_code=403,
                        content={"status": "error", "message": "CSRF protection: Missing X-Requested-With header on cross-site mutating request."}
                    )

        response = await call_next(request)
        # 2. Defensive HTTP Security Headers (Clickjacking, MIME Sniffing, Referrer Policy)
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "frame-ancestors 'none';"
        return response

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"status": "error", "message": exc.detail, "detail": exc.detail}
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        errors = []
        for err in exc.errors():
            err_dict = dict(err)
            if "ctx" in err_dict and isinstance(err_dict["ctx"], dict):
                err_dict["ctx"] = {k: str(v) for k, v in err_dict["ctx"].items()}
            errors.append(err_dict)
        first_msg = errors[0].get("msg", "Invalid request parameters") if errors else "Validation error"
        return JSONResponse(
            status_code=422,
            content={"status": "error", "message": f"Parameter validation error: {first_msg}", "detail": errors}
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        # Log internally without leaking stack trace to user
        print(f"[Internal Server Error] {exc}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "An internal server error occurred while processing the request."}
        )
