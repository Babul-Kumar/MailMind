# MailMind — Render Production Deployment Guide

This document provides a comprehensive, production-grade guide for deploying MailMind (`v5.4.1-verified-production`) to Render.

---

## Architecture Summary

```
                      HTTPS / Port 443
[ Browser / Client ] ───────────────────> [ Render TLS Edge Proxy ]
                                                    │
                                           HTTP / Port $PORT
                                         (X-Forwarded-Proto, Host)
                                                    │
                                                    ▼
                                       [ Uvicorn + FastAPI Backend ]
                                       - Routes & Security Middleware
                                       - Static File Serving (Vite SPA)
                                       - Local ML (priority-v5.1 TF-IDF)
                                                    │
                                    ┌───────────────┴───────────────┐
                                    ▼                               ▼
                           [ Persistent Disk ]             [ Gmail API ]
                           /var/data/sessions/          OAuth 2.0 Web Client
                           /var/data/cache/             gmail.readonly
                           /var/data/feedback/
```

---

## 1. Google Cloud Console Setup

> [!IMPORTANT]
> **Web Application Client Required**  
> In local development, MailMind may have used an `"installed"` (Desktop) OAuth client. Desktop clients only allow loopback redirect URIs (`http://localhost`, `http://127.0.0.1:8000`).  
> Render deployments **require** an OAuth 2.0 **Web application** client ID to authorize public HTTPS redirect URIs.

### Step 1.1: Create Web Application OAuth Client ID
1. Navigate to [Google Cloud Console](https://console.cloud.google.com/).
2. Select your project (e.g., `AI Email Priority Classifier`).
3. Go to **APIs & Services** > **Credentials**.
4. Click **Create Credentials** > **OAuth client ID**.
5. Application type: Select **Web application**.
6. Name: `MailMind Web Production`.
7. **Authorized JavaScript origins**:
   - `https://<YOUR-RENDER-SERVICE-NAME>.onrender.com`
   - `http://127.0.0.1:8000` (for local dev parity)
8. **Authorized redirect URIs**:
   - `https://<YOUR-RENDER-SERVICE-NAME>.onrender.com/api/auth/callback`
   - `http://127.0.0.1:8000/api/auth/callback`
9. Click **Create**.
10. Copy your **Client ID** and **Client Secret**.

### Step 1.2: OAuth Consent Screen Configuration
1. Go to **APIs & Services** > **OAuth consent screen**.
2. Scopes: Verify that `https://www.googleapis.com/auth/gmail.readonly` is added.
3. Publishing status:
   - If **Testing**: Add your personal Gmail address under **Test users** (maximum 100 test users allowed).
   - If **Production**: Submit for verification if required, or keep in testing for private internal use.

---

## 2. Render Deployment Options

You can deploy MailMind using either **Render Blueprints (IaC)** or the **Render Dashboard UI**.

### Option A: Render Blueprint (`render.yaml`) — Recommended
1. Push your repository to GitHub / GitLab.
2. In the Render Dashboard, click **New** > **Blueprint**.
3. Select your repository.
4. Render will parse `render.yaml` automatically.
5. In the blueprint variables page, populate:
   - `BASE_URL`: `https://<YOUR-SERVICE-NAME>.onrender.com`
   - `GOOGLE_CLIENT_ID`: Your Web OAuth Client ID
   - `GOOGLE_CLIENT_SECRET`: Your Web OAuth Client Secret
6. Click **Apply**.

### Option B: Manual Web Service Setup
1. In the Render Dashboard, click **New** > **Web Service**.
2. Connect your Git repository.
3. Configure the following service settings:
   - **Name**: `mailmind` (or your chosen name)
   - **Region**: Oregon (or your preferred region)
   - **Branch**: `main`
   - **Runtime**: `Python`
   - **Build Command**:
     ```bash
     cd frontend && npm install && npm run build && cd .. && pip install -r requirements.txt
     ```
   - **Start Command**:
     ```bash
     uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips "*"
     ```
   - **Plan**: `Starter` ($7/mo recommended for persistent disk; `Free` works with ephemeral disk)
   - **Health Check Path**: `/api/health`

---

## 3. Environment Variables Specification

Set the following environment variables in the Render Dashboard (**Environment** tab):

| Variable Name | Classification | Required? | Example Value | Description |
|---|---|---|---|---|
| `ENVIRONMENT` | Core Config | **YES** | `production` | Enables production security (secure cookies, suppresses dev error traces, disables test sessions). |
| `BASE_URL` | Routing & OAuth | **YES** | `https://mailmind.onrender.com` | Public base URL used to construct the OAuth 2.0 redirect URI. |
| `GOOGLE_CLIENT_ID` | OAuth Secret | **YES** | `xxxx.apps.googleusercontent.com` | Google Cloud Web OAuth 2.0 Client ID. |
| `GOOGLE_CLIENT_SECRET` | OAuth Secret | **YES** | `GOCSPX-xxxxxxxxxxxx` | Google Cloud Web OAuth 2.0 Client Secret. |
| `SESSION_SECRET` | Cryptography | **YES** | `64-char-hex-string` | Secret key for signing session IDs (click "Generate" in Render). |
| `DATA_DIR` | Storage | **Optional** | `/var/data` | Path to persistent storage disk mount point. |
| `ALLOWED_ORIGINS` | Networking | Optional | `https://mailmind.onrender.com` | Extra CORS allowed origins if using custom domain. |
| `ALLOW_TEST_ENDPOINTS` | Testing | Optional | `false` | Must remain `false` in production. |

---

## 4. Persistent Disk Configuration (Recommended)

Render web services run in ephemeral containers. When a container restarts or deploys a new commit, local disk storage is reset to the git checkout state.

To persist user sessions and cached mailbox metadata (~17,355 analyzed messages) across deployments:
1. In your Web Service settings on Render, navigate to the **Disks** section.
2. Click **Add Disk**.
3. **Name**: `mailmind-data`
4. **Mount Path**: `/var/data`
5. **Size**: `1 GB` (or larger depending on mailbox size)
6. Set the environment variable: `DATA_DIR=/var/data`.

> [!NOTE]
> If deploying on Render's **Free Plan**, persistent disks are not supported. MailMind will store sessions and cache in the local ephemeral container (`DATA_DIR=google_auth`). In this case, users will simply re-authenticate if the instance sleeps or restarts.

---

## 5. Security & Reverse Proxy Architecture

MailMind incorporates enterprise-grade security controls configured specifically for Render's reverse proxy:

1. **Proxy Headers (`--proxy-headers --forwarded-allow-ips "*"`):**
   Render terminates SSL at its outer edge and forwards plain HTTP traffic to your container on `$PORT`. The start command informs Uvicorn to trust incoming `X-Forwarded-Proto` and `X-Forwarded-Host` headers so the backend knows the client is on HTTPS.
2. **Secure Session Cookies:**
   Under `ENVIRONMENT=production`, session cookies (`mailmind_session_id`, `mailmind_oauth_verifier`) are strictly tagged with:
   - `Secure=True` (only transmitted over HTTPS)
   - `HttpOnly=True` (inaccessible to JavaScript / XSS protection)
   - `SameSite=Lax` (CSRF protection)
3. **Disabled Test Endpoints:**
   In production, the unauthenticated test-session bypass route (`/api/auth/test-session`) returns HTTP `403 Forbidden`.
4. **Zero Frontend Credential Exposure:**
   Tokens and Google API secrets reside exclusively in the backend runtime. The frontend receives only sanitized session cookies.

---

## 6. Post-Deployment Verification Checklist

Once the Render build succeeds and the service transitions to **Live**:

### Step 6.1: Verify Health Probes
```bash
curl -I https://<YOUR-RENDER-SERVICE>.onrender.com/health
curl -s https://<YOUR-RENDER-SERVICE>.onrender.com/api/health
```
- Expected response: HTTP 200 JSON: `{"status":"ok",...}`.

### Step 6.2: Verify Protected Endpoints Require Authentication
```bash
curl -I https://<YOUR-RENDER-SERVICE>.onrender.com/api/stats
```
- Expected response: HTTP 401 Unauthorized: `{"detail":"Not authenticated"}`.

### Step 6.3: Verify Test Session Disabled
```bash
curl -X POST https://<YOUR-RENDER-SERVICE>.onrender.com/api/auth/test-session
```
- Expected response: HTTP 403 Forbidden.

### Step 6.4: Verify Full User Journey in Browser
1. Open `https://<YOUR-RENDER-SERVICE>.onrender.com` in your browser.
2. Confirm the clean, premium MailMind landing page loads.
3. Click **Connect Gmail**.
4. You should be redirected to `accounts.google.com` with `redirect_uri=https://<YOUR-RENDER-SERVICE>.onrender.com/api/auth/callback`.
5. Grant consent.
6. Verify smooth return to MailMind dashboard with active session, live email sync, and ML priority scoring (`priority-v5.1`).

---

## 7. Rollback & Disaster Recovery Procedures

### 7.1 Instant Service Rollback in Render
If a bad commit is pushed:
1. In the Render Dashboard, go to your service.
2. Click **Events** or **Deploys**.
3. Locate the previous working deploy (e.g. `v5.4.1-verified-production`).
4. Click **Rollback to this deploy**.

### 7.2 ML Model Rollback (`priority-v4.1`)
MailMind preserves the verified previous production model `priority-v4.1` in the repository.
If an anomaly is detected with `priority-v5.1`:
1. In `backend/app/core/config.py`, change `ACTIVE_MODEL_VERSION = "priority-v4.1"`.
2. Commit and push:
   ```bash
   git commit -am "Rollback active model to priority-v4.1"
   git push origin main
   ```
3. Render will automatically build and deploy the rollback model within 2 minutes.
