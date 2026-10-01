import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from backend.app.core.config import FRONTEND_DIST_DIR
from backend.app.core.security import setup_security
from backend.app.ml.predictor import load_model
from backend.app.api.routes_health import router as health_router
from backend.app.api.routes_auth import router as auth_router
from backend.app.api.routes_gmail import router as gmail_router
from backend.app.api.routes_model import router as model_router
from backend.app.api.routes_emails import router as emails_router


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

# Serve built React frontend from frontend/dist
assets_dir = os.path.join(FRONTEND_DIST_DIR, "assets")
if os.path.exists(assets_dir):
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

# Also mount /static if frontend/dist/static or legacy static exists
static_dir = os.path.join(FRONTEND_DIST_DIR, "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/favicon.ico", include_in_schema=False)
def serve_favicon_ico():
    fav_ico = os.path.join(FRONTEND_DIST_DIR, "favicon.ico")
    if os.path.exists(fav_ico):
        return FileResponse(fav_ico, media_type="image/x-icon")
    fav_svg = os.path.join(FRONTEND_DIST_DIR, "favicon.svg")
    if os.path.exists(fav_svg):
        return FileResponse(fav_svg, media_type="image/svg+xml")
    from fastapi import Response
    return Response(status_code=204)


@app.get("/favicon.svg", include_in_schema=False)
def serve_favicon_svg():
    fav_svg = os.path.join(FRONTEND_DIST_DIR, "favicon.svg")
    if os.path.exists(fav_svg):
        return FileResponse(fav_svg, media_type="image/svg+xml")
    from fastapi import Response
    return Response(status_code=204)


@app.get("/index.html", include_in_schema=False)
@app.get("/")
def serve_index():
    index_html = os.path.join(FRONTEND_DIST_DIR, "index.html")
    if os.path.exists(index_html):
        return FileResponse(index_html)
    return HTMLResponse(
        """<!DOCTYPE html>
        <html>
        <head><title>MailMind | Email Priority Intelligence</title></head>
        <body style="font-family:sans-serif;text-align:center;padding:50px;background:#0f172a;color:#fff;">
          <h1>✦ MailMind</h1>
          <p>AI Email Priority Intelligence API is active.</p>
          <p>Frontend is currently building or run via <code>npm run dev</code> in <code>frontend/</code>.</p>
        </body></html>"""
    )


@app.get("/{full_path:path}", include_in_schema=False)
def serve_spa_fallback(full_path: str):
    # Do not intercept API routes; let standard 404 handler return proper JSON error
    if full_path.startswith("api/") or full_path == "api":
        raise HTTPException(status_code=404, detail="API endpoint not found")

    # If physical static asset exists in dist (e.g. assets, favicon, etc.), serve it
    file_path = os.path.join(FRONTEND_DIST_DIR, full_path)
    if os.path.exists(file_path) and os.path.isfile(file_path):
        return FileResponse(file_path)

    # Fallback to index.html for client-side SPA routing
    return serve_index()


if __name__ == "__main__":
    import uvicorn
    print("Starting MailMind Backend on http://127.0.0.1:8000...")
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=8000, reload=True)
