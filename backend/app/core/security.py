from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from backend.app.core.config import ALLOWED_ORIGINS


def setup_security(app: FastAPI) -> None:
    """Configures CORS and standard exception handlers to prevent raw stack traces."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"status": "error", "message": exc.detail, "detail": exc.detail}
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        errors = exc.errors()
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
