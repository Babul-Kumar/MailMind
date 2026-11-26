from datetime import datetime, timezone
from fastapi import APIRouter
from backend.app.ml.predictor import load_model
from backend.app.ml.registry import model_registry
from backend.app.core.cache import user_email_cache

router = APIRouter(tags=["Health"])


@router.get("/health", operation_id="health_check_root")
@router.get("/api/health", operation_id="health_check_api")
@router.get("/api/v1/health", operation_id="health_check_api_v1")
def health_check():
    """Health status check covering ML model readiness and SQLite connectivity."""
    try:
        model = load_model()
        model_loaded = model is not None
    except Exception:
        model_loaded = False

    try:
        active_version = model_registry.get_active_version()
    except Exception:
        active_version = "unknown"

    try:
        conn = user_email_cache._get_connection()
        conn.execute("SELECT 1;").fetchone()
        db_connected = True
    except Exception:
        db_connected = False

    return {
        "status": "healthy" if (model_loaded and db_connected) else "degraded",
        "service": "AI Email Priority Dashboard",
        "model_loaded": model_loaded,
        "model_version": active_version,
        "db_connected": db_connected,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
