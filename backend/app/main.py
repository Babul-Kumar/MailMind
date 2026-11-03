import os
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

# Mount frontend static assets if built dist exists
_frontend_assets_dir = os.path.join(BASE_DIR, "frontend", "dist", "assets")
if os.path.exists(_frontend_assets_dir):
    app.mount("/assets", StaticFiles(directory=_frontend_assets_dir), name="assets")


@app.get("/", include_in_schema=False)
def serve_root():
    return HTMLResponse(
        """<!DOCTYPE html>
        <html>
        <head><title>MailMind | AI Email Priority Intelligence</title></head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; text-align: center; padding: 60px 20px; background: #0b0f19; color: #f8fafc;">
          <h1 style="font-size: 2.2rem; margin-bottom: 0.5rem; background: linear-gradient(135deg, #6366f1 0%, #a855f7 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">✦ MailMind</h1>
          <p style="font-size: 1.1rem; color: #94a3b8; margin-bottom: 2rem;">AI Email Priority Intelligence & Action Lifecycle API</p>
          <div style="display: inline-block; background: #131b2e; border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; padding: 1.5rem 2rem; text-align: left; max-width: 500px;">
            <p style="margin: 0.5rem 0;">🚀 <strong>React App:</strong> <a href="https://mail-mind-ten-chi.vercel.app" style="color: #818cf8; text-decoration: none;">https://mail-mind-ten-chi.vercel.app</a></p>
            <p style="margin: 0.5rem 0;">📖 <strong>API Documentation:</strong> <a href="/docs" style="color: #38bdf8; text-decoration: none;">/docs</a></p>
            <p style="margin: 0.5rem 0;">🔍 <strong>Health Status:</strong> <a href="/health" style="color: #34d399; text-decoration: none;">/health</a></p>
          </div>
        </body></html>"""
    )


if __name__ == "__main__":
    import uvicorn
    print("Starting MailMind Backend on http://127.0.0.1:8000...")
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=8000, reload=True)
