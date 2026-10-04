from datetime import datetime, timezone
from fastapi import APIRouter
from backend.app.ml.predictor import load_model

router = APIRouter(tags=["Health"])


@router.get("/health")
@router.get("/api/health")
def health_check():
    """Health status check."""
    try:
        model = load_model()
        model_loaded = model is not None
    except Exception:
        model_loaded = False

    return {
        "status": "healthy",
        "service": "AI Email Priority Dashboard",
        "model_loaded": model_loaded,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
