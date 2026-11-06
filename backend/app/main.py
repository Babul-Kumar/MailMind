import os
import warnings

# Filter harmless sklearn patch-version unpickling warnings for the frozen model
try:
    from sklearn.exceptions import InconsistentVersionWarning
    warnings.filterwarnings("ignore", category=InconsistentVersionWarning)
except ImportError:
    pass

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from backend.app.core.config import BASE_DIR
from backend.app.core.security import setup_security
from backend.app.ml.predictor import load_model
from backend.app.api.routes_health import router as health_router
from backend.app.api.routes_auth import router as auth_router
from backend.app.api.routes_gmail import router as gmail_router
from backend.app.api.routes_model import router as model_router
from backend.app.api.routes_emails import router as emails_router
from backend.app.api.routes_monitoring import router as monitoring_router
from backend.app.api.routes_phase51 import router as phase51_router
from backend.app.api.routes_adjudication import router as adjudication_router
from backend.app.api.routes_actions import router as actions_router
from backend.app.api.routes_analysis import router as analysis_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        model = load_model()
        vocab_len = len(model.named_steps['tfidf'].vocabulary_)
        print(f"[FastAPI Startup] Pre-warmed frozen model with {vocab_len:,} vocabulary features.")
    except Exception as e:
        print(f"[FastAPI Startup Error] Could not pre-warm model: {e}")
    yield
    try:
        from backend.app.core.cache import user_email_cache
        user_email_cache.close()
    except Exception:
        pass
    print("[FastAPI Shutdown] Clean shutdown completed.")


app = FastAPI(
    title="MailMind | AI Email Priority Intelligence",
    description="Real-Time Gmail Priority Classification with Version-Controlled ML (CSE472)",
    version="2.1.0",
    lifespan=lifespan
)

# Setup security, CORS and exception handlers
setup_security(app)

# Include API route controllers
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(gmail_router)
app.include_router(model_router)
app.include_router(emails_router)
app.include_router(monitoring_router)
app.include_router(phase51_router)
app.include_router(adjudication_router)
app.include_router(actions_router)
app.include_router(analysis_router)

# Mount React static build if available
frontend_dist = os.path.join(BASE_DIR, "frontend", "dist")
if os.path.exists(frontend_dist):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")

    @app.get("/{full_path:path}", response_class=HTMLResponse, include_in_schema=False)
    async def serve_spa(full_path: str):
        # Exclude API endpoints from SPA fallback
        if full_path.startswith("api/") or full_path == "api":
            raise HTTPException(status_code=404, detail="API endpoint not found")
        index_file = os.path.join(frontend_dist, "index.html")
        if os.path.exists(index_file):
            with open(index_file, "r", encoding="utf-8") as f:
                return f.read()
        return "<h1>Frontend build available, but index.html is missing.</h1>"
