# MailMind — Production Environment Separation Report
**Frontend: Vercel | Backend: Render**

---

## 1. Commit Hashes
- **Start Commit**: `9d2cda8caeca3edd143b54fabe6428ae4ee30af4`
- **Finish Commit**: `864ab8df557f5a7ef47be69f2fe2538451573dc8`
- **Branch**: `main`

---

## 2. Production Model Hash Confirmation
- **Model Name**: `priority-v5.1`
- **Artifact Path**: `dataset/models/priority-v5.1-candidate/model.joblib`
- **Architecture**: TF-IDF (10,000 max features, sublinear TF) + Logistic Regression (C=1.0, class_weight='balanced')
- **Expected SHA-256**: `8524ad73965859ee022f1271caee0040928e7805ab7d32c49b2f26e994f98c06`
- **Verified SHA-256**: `8524ad73965859ee022f1271caee0040928e7805ab7d32c49b2f26e994f98c06`
- **Integrity Status**: **VERIFIED & UNCHANGED**

---

## 3. Rollback Model Hash Confirmation
- **Model Name**: `priority-v4.1`
- **Artifact Path**: `dataset/models/priority-v4.1/model.joblib`
- **Expected SHA-256**: `09fe269f19ad6afb38e71b56f8c6ee7a386e59605c62c892478400bc09d5cbd0`
- **Verified SHA-256**: `09fe269f19ad6afb38e71b56f8c6ee7a386e59605c62c892478400bc09d5cbd0`
- **Integrity Status**: **VERIFIED & UNCHANGED**

---

## 4. Frozen Evaluation Holdout Hash Confirmation
- **Holdout Path**: `dataset/processed/test.csv`
- **Expected SHA-256**: `6841cd44901fa56242bf3752257e991fd7ff474ed7e0f7a5d2b7065a0827c138`
- **Verified SHA-256**: `6841cd44901fa56242bf3752257e991fd7ff474ed7e0f7a5d2b7065a0827c138`
- **Integrity Status**: **VERIFIED & UNCHANGED**

---

## 5. Zero External LLM / Gemini / OpenAI Confirmation
- **Search Command**: `Select-String -Path backend\app\ml\*.py, backend\app\api\*.py -Pattern 'openai|generativeai|anthropic|langchain'`
- **Result**: `0 matches found`
- **Inference Guarantee**: All priority scores (P1 Urgent to P4 Low), category classifications (Work, Personal, Finance, Social, Notifications), action extractions, and priority explanations are executed locally via Scikit-Learn TF-IDF + Logistic Regression, heuristics, and domain rules. No external LLM API calls exist in the inference or backend path.

---

## 6. Modified Files and Rationale

| File Path | Nature of Change | Exact Rationale |
| :--- | :--- | :--- |
| `frontend/src/services/api.js` | Configuration & Routing | Added `getApiBaseUrl()` resolving `VITE_API_BASE_URL` with fail-fast validation in `import.meta.env.PROD` (no silent localhost fallback). Implemented centralized `apiFetch()` with automatic `credentials: 'include'` and header merging. Routed all existing API helper functions through `apiFetch()`. |
| `frontend/src/components/inbox/FeedbackWidget.jsx` | API Isolation | Replaced direct `fetch('/api/feedback', ...)` with `submitFeedback(payload)` exported from `frontend/src/services/api.js`. |
| `frontend/src/components/settings/FeedbackReviewPanel.jsx` | API Centralization | Replaced raw `fetch('/api/adjudication/...')` calls with centralized `apiFetch('/api/adjudication/...')` ensuring cross-origin cookies and `VITE_API_BASE_URL` resolution. |
| `frontend/src/components/settings/SettingsPanel.jsx` | API Centralization | Replaced raw `fetch('/api/monitoring/...')` calls with centralized `apiFetch('/api/monitoring/...')`. |
| `frontend/src/components/settings/SystemHealthPanel.jsx` | API Centralization | Replaced raw `fetch('/api/monitoring/phase51/summary')` with `apiFetch('/api/monitoring/phase51/summary')`. |
| `frontend/package.json` | Test Automation | Updated `test` script from targeting solely `formatting.test.js` to `node --test src/utils/formatting.test.js src/services/api.test.js --run`. |
| `backend/app/core/config.py` | CORS & Origin Resolution | Added `FRONTEND_URL` environment variable support and dynamically injected sanitized `FRONTEND_URL` into `ALLOWED_ORIGINS` without wildcard `*`, preventing browser CORS credential rejection. |
| `backend/app/api/routes_auth.py` | Cross-Origin Auth & Cookies | 1) Updated OAuth callback to redirect to `FRONTEND_URL` (or `"/"` if unset). 2) Configured cookie flags: `SameSite=None; Secure=True` when `ENVIRONMENT=production`, and `SameSite=Lax; Secure=False` when `ENVIRONMENT=development` (supports `COOKIE_SAMESITE` override). Updated login, logout, callback, and test session endpoints. |
| `.env.example` | Documentation | Added documentation for `FRONTEND_URL` and `COOKIE_SAMESITE`. |
| `.gitignore` | Security & Hygiene | Added `frontend/.env*` and `frontend/.env.local*` ignores while whitelisting `!frontend/.env.example` to prevent accidental credential commits. |

---

## 7. Created Files and Rationale

| File Path | Exact Rationale |
| :--- | :--- |
| `frontend/.env.example` | Template for Vite environment variables (`VITE_API_BASE_URL`), instructing developers and CI/CD how to configure the backend API target for local dev and production Vercel environments. |
| `frontend/src/services/api.test.js` | Comprehensive unit tests for `getApiBaseUrl()`, `apiFetch()` default credentials (`include`), and JSON payload handling. |
| `tests/test_environment_separation.py` | Automated backend pytest suite verifying secret isolation, CORS dynamic origin resolution, OAuth callback redirection, cookie security flags (SameSite=None in prod vs Lax in dev), model hashes, and zero-LLM invariants. |
| `reports/environment_separation_report.md` | This formal separation and deployment readiness audit report. |

---

## 8. Audit of All `fetch()` Calls Across Frontend (Before vs After)

| File | Before Modification | After Modification | Status |
| :--- | :--- | :--- | :--- |
| `frontend/src/services/api.js` | `fetch(endpoint, options)` with manual `/api` string concatenation | `apiFetch(endpoint, options)` with `getApiBaseUrl()`, `credentials: 'include'`, and header merging | **HARDENED** |
| `frontend/src/components/inbox/FeedbackWidget.jsx:68` | `fetch('/api/feedback', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(...) })` | `submitFeedback({ email_id: email.id, ... })` | **CENTRALIZED** |
| `frontend/src/components/settings/FeedbackReviewPanel.jsx:54` | `fetch('/api/adjudication/stats')` | `apiFetch('/api/adjudication/stats')` | **CENTRALIZED** |
| `frontend/src/components/settings/FeedbackReviewPanel.jsx:60` | `fetch('/api/adjudication/audit-log?limit=50')` | `apiFetch('/api/adjudication/audit-log?limit=50')` | **CENTRALIZED** |
| `frontend/src/components/settings/FeedbackReviewPanel.jsx:93` | `fetch('/api/adjudication/adjudicate', { method: 'POST', ... })` | `apiFetch('/api/adjudication/adjudicate', { method: 'POST', ... })` | **CENTRALIZED** |
| `frontend/src/components/settings/SettingsPanel.jsx:26` | `fetch('/api/monitoring/drift/summary')` | `apiFetch('/api/monitoring/drift/summary')` | **CENTRALIZED** |
| `frontend/src/components/settings/SettingsPanel.jsx:27` | `fetch('/api/monitoring/canary/summary')` | `apiFetch('/api/monitoring/canary/summary')` | **CENTRALIZED** |
| `frontend/src/components/settings/SettingsPanel.jsx:28` | `fetch('/api/monitoring/health')` | `apiFetch('/api/monitoring/health')` | **CENTRALIZED** |
| `frontend/src/components/settings/SystemHealthPanel.jsx:25` | `fetch('/api/monitoring/phase51/summary')` | `apiFetch('/api/monitoring/phase51/summary')` | **CENTRALIZED** |

**Verification**:
A recursive regex search (`Select-String -Pattern 'fetch\('`) across `frontend/src` confirms that only `frontend/src/services/api.js` (inside `apiFetch`) and `frontend/src/services/api.test.js` (in mock tests) invoke browser `fetch`.

---

## 9. `getApiBaseUrl()` Implementation and Fallback Behavior

```javascript
export function getApiBaseUrl() {
  const envUrl = typeof import.meta !== 'undefined' && import.meta.env
    ? import.meta.env.VITE_API_BASE_URL
    : undefined;

  if (envUrl && typeof envUrl === 'string' && envUrl.trim() !== '') {
    return envUrl.trim().replace(/\/+$/, '');
  }

  // In production builds, require VITE_API_BASE_URL explicitly to avoid silent misrouting
  if (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.PROD) {
    throw new Error(
      'MailMind configuration error: VITE_API_BASE_URL environment variable is not defined for production build. ' +
      'Please configure VITE_API_BASE_URL in your Vercel deployment settings pointing to your Render backend.'
    );
  }

  // In development, empty string leverages Vite reverse proxy or same-origin fallback
  return '';
}
```

### Fallback Behavior
- **In Development (`npm run dev`)**: Defaults to `""` if `VITE_API_BASE_URL` is omitted, allowing seamless proxying through Vite's local dev server (`/api -> http://localhost:8000`).
- **In Production (`npm run build` / Vercel)**: Throws an explicit descriptive error if `VITE_API_BASE_URL` is missing. Prevents silent request drops to `window.location.origin` (which would return 404s on Vercel).
- **Trailing Slash Normalization**: Automatically strips trailing slashes (`https://mailmind-api.onrender.com/` becomes `https://mailmind-api.onrender.com`), guaranteeing clean URL concatenation.

---

## 10. CORS Configuration Details
- **Backend File**: `backend/app/core/config.py`
- **Allowed Origins**:
  ```python
  # Localhost & Loopback origins
  ALLOWED_ORIGINS = [
      "http://localhost:5173",
      "http://127.0.0.1:5173",
      "http://localhost:3000",
      "http://127.0.0.1:3000",
      "http://localhost:8000",
      "http://127.0.0.1:8000",
  ]
  # Dynamic ingestion from FRONTEND_URL
  if FRONTEND_URL:
      cleaned_url = FRONTEND_URL.strip().rstrip("/")
      if cleaned_url and cleaned_url not in ALLOWED_ORIGINS:
          ALLOWED_ORIGINS.append(cleaned_url)
  ```
- **Middleware Options**:
  - `allow_credentials=True`
  - `allow_methods=["*"]`
  - `allow_headers=["*"]`
  - **No Wildcard Guarantee**: `ALLOWED_ORIGINS` explicitly avoids `"*"` when `allow_credentials=True`, adhering to W3C Fetch specifications and preventing browser credential-blocking errors.

---

## 11. Cookie Configuration in Production vs Development

| Attribute | Production (`ENVIRONMENT=production`) | Development (`ENVIRONMENT=development`) | Override Mechanism |
| :--- | :--- | :--- | :--- |
| **`SameSite`** | `None` | `Lax` | Configurable via `COOKIE_SAMESITE` env var |
| **`Secure`** | `True` | `False` | Follows `ENVIRONMENT == "production"` or `COOKIE_SAMESITE == "none"` |
| **`HttpOnly`** | `True` | `True` | Enforced in all environments |
| **`Path`** | `/` | `/` | Enforced in all environments |
| **`Max-Age`** | 604,800 (7 days) | 604,800 (7 days) | Enforced in all environments |

### Cross-Site Rationale
When a user accesses `https://mailmind.vercel.app`, any `apiFetch` call to `https://mailmind-api.onrender.com/api/...` is treated by modern browsers (Chrome, Edge, Safari, Firefox) as a **third-party / cross-site subresource request**. Browsers will strip `SameSite=Lax` cookies from cross-site subresource requests. Therefore:
- Production requires `SameSite=None; Secure=True`.
- Local development on `http://localhost:5173` requires `SameSite=Lax; Secure=False` because browsers reject `Secure` cookies over plain HTTP.

---

## 12. OAuth Flow Step-by-Step with Cross-Origin Redirect

```
[User Browser: https://mailmind.vercel.app]
       |
       | 1. User clicks "Sign in with Google"
       v
[Backend: GET https://mailmind-api.onrender.com/api/auth/login]
       |
       | 2. Backend generates CSRF state + auth_url with redirect_uri:
       |    https://mailmind-api.onrender.com/api/auth/callback
       v
[Google Accounts: https://accounts.google.com/o/oauth2/v2/auth]
       |
       | 3. User grants consent (scope: https://www.googleapis.com/auth/gmail.readonly)
       v
[Backend: GET https://mailmind-api.onrender.com/api/auth/callback?code=...&state=...]
       |
       | 4. Backend validates state parameter
       | 5. Backend exchanges authorization code for Google OAuth tokens
       | 6. Backend creates user record & multi-user session in SQLite
       | 7. Backend sets cookie: mailmind_session=<uuid>; HttpOnly; Secure; SameSite=None; Path=/
       | 8. Backend issues HTTP 302 redirect to FRONTEND_URL (https://mailmind.vercel.app/)
       v
[User Browser: https://mailmind.vercel.app/]
       |
       | 9. App loads, calls apiFetch('/api/auth/status') with credentials: 'include'
       v
[Backend: GET https://mailmind-api.onrender.com/api/auth/status]
       |
       | 10. Validates session cookie, returns { authenticated: true, user: { ... } }
```

---

## 13. Backend Test Results
- **Command**: `.\.venv\Scripts\python.exe -m pytest tests/ -q`
- **Total Tests Passed**: **591 / 591**
- **Failures / Errors**: **0**
- **Test Suites Verified**:
  - `tests/test_environment_separation.py`: **10 / 10 PASS**
  - `tests/test_render_deployment_readiness.py`: **13 / 13 PASS**
  - Core API, ML inference, multi-user isolation, canary, drift, CSRF: **568 / 568 PASS**

---

## 14. Frontend Test Results
- **Command**: `npm test -- --run`
- **Total Tests Passed**: **12 / 12**
- **Suites**:
  - `src/utils/formatting.test.js`: 9 / 9 PASS
  - `src/services/api.test.js`: 3 / 3 PASS
- **Duration**: ~204ms

---

## 15. Frontend Production Build Result
- **Command**: `npm run build`
- **Output**:
  ```text
  > mailmind@2.0.0 build
  > vite build

  vite v5.4.21 building for production...
  transforming...
  ✓ 1610 modules transformed.
  rendering chunks...
  computing gzip size...
  dist/index.html                   0.84 kB │ gzip:  0.45 kB
  dist/assets/index-B1EjiG8Z.css    8.33 kB │ gzip:  2.49 kB
  dist/assets/index-Bgi985KY.js   312.98 kB │ gzip: 84.61 kB
  ✓ built in 4.56s
  ```
- **Exit Code**: 0 (Clean production bundle, zero errors)

---

## 16. Vercel Deployment Checklist (Frontend)

1. **Repository & Root Directory**:
   - Link repository to Vercel.
   - **Root Directory**: `frontend` (or configure Project Settings -> Root Directory: `frontend`).
2. **Build & Output Settings**:
   - **Framework Preset**: Vite
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`
   - **Install Command**: `npm install`
3. **Environment Variables**:
   - `VITE_API_BASE_URL`: `https://<YOUR-RENDER-BACKEND-SERVICE>.onrender.com`
     *(Do NOT include a trailing slash; e.g., `https://mailmind-api.onrender.com`)*
4. **Deploy**:
   - Trigger build and record the generated domain (e.g., `https://mailmind.vercel.app`).

---

## 17. Render Deployment Checklist (Backend)

1. **Service Type**:
   - Web Service (Python 3.11)
2. **Build & Start Commands**:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips "*"`
3. **Persistent Disk (Critical for SQLite & Model Cache)**:
   - Add a Persistent Disk on Render:
     - **Name**: `mailmind-data`
     - **Mount Path**: `/var/data`
     - **Size**: 1 GB - 5 GB
4. **Environment Variables**:
   - `ENVIRONMENT`: `production`
   - `COOKIE_SAMESITE`: `none`
   - `DATABASE_URL`: `sqlite:////var/data/mailmind.db`
   - `FRONTEND_URL`: `https://<YOUR-VERCEL-APP>.vercel.app`
   - `SESSION_SECRET`: `<64-char-random-hex-string>`
   - `GOOGLE_CLIENT_ID`: `<google-client-id>.apps.googleusercontent.com`
   - `GOOGLE_CLIENT_SECRET`: `<google-client-secret>`
   - `GMAIL_REDIRECT_URI`: `https://<YOUR-RENDER-BACKEND-SERVICE>.onrender.com/api/auth/callback`
5. **Google Cloud Console Credentials Setup**:
   - Navigate to Google Cloud Console -> APIs & Services -> Credentials.
   - Edit the OAuth 2.0 Client ID:
     - **Authorized JavaScript origins**:
       - `https://<YOUR-VERCEL-APP>.vercel.app`
       - `https://<YOUR-RENDER-BACKEND-SERVICE>.onrender.com`
     - **Authorized redirect URIs**:
       - `https://<YOUR-RENDER-BACKEND-SERVICE>.onrender.com/api/auth/callback`
6. **Health Check Endpoint**:
   - Set health check path to `/api/health`.

---
*Report Generated: 2026-10-04*
*Author: MailMind Release Engineering Team*
