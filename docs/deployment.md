# MAILMIND — PRODUCTION DEPLOYMENT GUIDE

**Author:** Senior Cloud Infrastructure & DevOps Team  
**Date:** November 4, 2026  
**Target Architecture:** FastAPI Backend (Render Web Service) & React Frontend (Vercel SPA)

---

## 1. System Overview

MailMind operates on a high-performance decoupled architecture:
- **FastAPI Backend:** Asynchronous REST API providing Google OAuth 2.0 authentication, Gmail sync pipelines, incremental ML inference, SQLite caching, priority aging, and smart action queue endpoints. Hosted on Render.
- **React Frontend:** Fast, responsive React single-page application built with Vite and modern CSS design tokens. Features real-time period-scoped Recent Mail, unbounded All History browsing, interactive period selection, and an active Needs Attention queue. Hosted on Vercel.
- **Machine Learning Core:** Frozen Scikit-Learn pipeline (`priority-v5.1`) loaded into memory once during FastAPI startup.

---

## 2. Environment Variables Specification

### 2.1 Backend Environment Variables (FastAPI on Render)

| Variable | Required | Default | Description |
| :--- | :---: | :--- | :--- |
| `PORT` | Yes | `10000` | Port assigned by Render for incoming HTTP traffic |
| `ENVIRONMENT` | Yes | `production` | Deployment tier (`production`, `staging`, `development`) |
| `SECRET_KEY` | Yes | — | 64-character hex key for HMAC signing and token encryption |
| `SESSION_SECRET` | Yes | — | 64-character secret for cookie signing |
| `GOOGLE_CLIENT_ID` | Yes | — | Google Cloud OAuth 2.0 Web Client ID |
| `GOOGLE_CLIENT_SECRET` | Yes | — | Google Cloud OAuth 2.0 Web Client Secret |
| `GOOGLE_REDIRECT_URI` | Yes | `https://<backend-host>/api/auth/google/callback` | OAuth redirect endpoint registered in Google Cloud Console |
| `FRONTEND_URL` | Yes | `https://mail-mind-ten-chi.vercel.app` | Permitted CORS origin and OAuth redirect target |
| `MODEL_PATH` | No | `dataset/models/priority-v5.1-candidate/model.joblib` | Path to frozen ML model artifact |
| `CACHE_DB_PATH` | No | `mailmind_cache.db` | Path to persistent SQLite cache database |

### 2.2 Frontend Environment Variables (React on Vercel)

| Variable | Required | Default | Description |
| :--- | :---: | :--- | :--- |
| `VITE_API_BASE_URL` | Optional | `https://mailmind-api-xzu8.onrender.com` | Target backend URL (when direct API is used) |
| `VITE_USE_DIRECT_API` | Optional | `false` | When false, uses same-origin Vercel reverse proxy for cookies |

---

## 3. Google Cloud OAuth Configuration

In the [Google Cloud Console](https://console.cloud.google.com/apis/credentials):

1. **Authorized JavaScript Origins:**
   - `https://mailmind-api-xzu8.onrender.com`
   - `https://mail-mind-ten-chi.vercel.app`
   - `http://localhost:5173` (for local Vite development)
   - `http://localhost:8000` (for local backend development)

2. **Authorized Redirect URIs:**
   - `https://mailmind-api-xzu8.onrender.com/api/auth/google/callback`
   - `http://localhost:8000/api/auth/google/callback`

3. **Scopes Required:**
   - `https://www.googleapis.com/auth/gmail.readonly`
   - `https://www.googleapis.com/auth/userinfo.email`
   - `https://www.googleapis.com/auth/userinfo.profile`

---

## 4. Backend Deployment (Render)

MailMind backend is configured for automated Git deployments via `render.yaml`.

### 4.1 Render Service Settings
- **Environment:** `Python 3`
- **Build Command:** `pip install -r backend/requirements.txt`
- **Start Command:** `uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT --workers 1`
- **Plan:** Free or Starter tier (512MB - 1GB RAM)

### 4.2 Low-Memory & Root Cause Protection
Render's free tier has a 512MB RAM cap. To prevent Out-Of-Memory (OOM) crashes:
1. **Single Worker:** Always run with `--workers 1`. The frozen ML model requires ~70MB; multiple workers multiply memory overhead.
2. **Batch Processing:** Mail sync processes emails in chunks of 25 rather than buffering entire inboxes into memory.
3. **Database Indexing:** SQLite indexes (`idx_cache_user_date_stale`, `idx_analysis_pref_user`) execute fast range scans without full-table memory copies.

---

## 5. Frontend Deployment (Vercel)

1. Connect your GitHub repository to Vercel.
2. Root Directory: `frontend`
3. Framework Preset: `Vite`
4. Build Command: `npm run build`
5. Output Directory: `dist`
6. Reverse Proxy Configuration: `frontend/vercel.json` routes `/api/(.*)` directly to the Render backend, ensuring seamless HttpOnly first-party cookies without cross-origin browser blocking.

---

## 6. Pre-Flight Verification Checklist

Before opening the service to traffic:
- [ ] **Health Check:** `curl -f https://<backend>/api/health` returns `{"status": "healthy", "model_loaded": true}`.
- [ ] **Model Artifact Hash:** Verify SHA-256 equals `8524ad73965859ee022f1271caee0040928e7805ab7d32c49b2f26e994f98c06`.
- [ ] **Config Endpoint:** Verify `GET /api/analysis/config` returns default period `last_3_months`.
- [ ] **Google OAuth Flow:** Initiate login, confirm consent screen, verify seamless redirect to React frontend with valid session cookie and handoff token.
- [ ] **Incremental Analysis:** Perform analysis on `last_3_months`, change period to `this_month`, and confirm instant 100% cache hit without full mailbox re-scan.
- [ ] **History & Actions Check:** Open *All History* to verify unanalyzed emails are visible; open *Needs Attention* to verify unresolved actions are visible across all dates.
