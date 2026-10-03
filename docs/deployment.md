# MailMind Production Deployment Runbook

**Release Version**: `v5.4.1-verified-production`  
**Git Baseline**: Commit `bee1c9c`  
**Active Production Model**: `priority-v5.1` (SHA-256: `8524ad73965859ee022f1271caee0040928e7805ab7d32c49b2f26e994f98c06`)  
**Rollback Model Baseline**: `priority-v4.1` (SHA-256: `09fe269f19ad6afb38e71b56f8c6ee7a386e59605c62c892478400bc09d5cbd0`)  

---

## 1. Pre-Deployment Prerequisites & Verification

### 1.1 Environment Configuration
1. Create `.env` from template:
   ```bash
   cp .env.example .env
   ```
2. Verify mandatory production settings in `.env`:
   ```bash
   ENVIRONMENT=production
   ALLOW_TEST_ENDPOINTS=false
   HOST=0.0.0.0
   PORT=8000
   SESSION_SECRET=<generate-using-python-secrets-token-hex-32>
   ```

### 1.2 Google Cloud Console & OAuth Configuration
1. Navigate to [Google Cloud Console](https://console.cloud.google.com/) > **APIs & Services** > **Enabled APIs & Services**.
2. Verify **Gmail API** is enabled.
3. In **Credentials** > **OAuth 2.0 Client IDs**:
   - Application type: **Web application**
   - Authorized redirect URIs:
     - Development: `http://127.0.0.1:8000/api/auth/callback`
     - Production: `https://<your-domain>/api/auth/callback`
4. Download client secret JSON and place at:
   `google_auth/credentials.json`
   *(Ensure file permissions are restricted: `chmod 600 google_auth/credentials.json`)*.

### 1.3 Cryptographic Integrity Check
Execute pre-deployment hash check to ensure model weights and holdouts have not been altered:
```bash
python -c "
import hashlib
files = [
    ('priority-v5.1', 'dataset/models/priority-v5.1-candidate/model.joblib', '8524ad73965859ee022f1271caee0040928e7805ab7d32c49b2f26e994f98c06'),
    ('priority-v4.1', 'dataset/models/priority-v4.1/model.joblib', '09fe269f19ad6afb38e71b56f8c6ee7a386e59605c62c892478400bc09d5cbd0'),
    ('test.csv', 'dataset/processed/test.csv', '6841cd44901fa56242bf3752257e991fd7ff474ed7e0f7a5d2b7065a0827c138'),
]
for name, path, expected in files:
    h = hashlib.sha256(open(path, 'rb').read()).hexdigest()
    assert h == expected, f'HASH MISMATCH on {name}!'
print('All pre-deployment cryptographic hashes verified: 100% EXACT')
"
```

### 1.4 Dependency Installation & Test Verification
1. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Install frontend dependencies and compile production bundle:
   ```bash
   cd frontend
   npm ci
   npm test -- --watchAll=false
   npm run build
   cd ..
   ```
3. Run backend test suite:
   ```bash
   pytest tests/ -q
   ```
   *Verify: 562 passed, 0 failed.*

---

## 2. Deployment Procedure

### 2.1 Backend Service Startup
Start the production ASGI application with Uvicorn (or Gunicorn worker manager):
```bash
uvicorn backend.app.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4 \
  --proxy-headers \
  --forwarded-allow-ips="*"
```

### 2.2 Reverse Proxy Configuration (Nginx Example)
Configure Nginx with TLS termination (ensures `Secure=True` cookies function):
```nginx
server {
    listen 443 ssl http2;
    server_name mailmind.example.com;

    ssl_certificate /etc/letsencrypt/live/mailmind.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/mailmind.example.com/privkey.pem;

    # Serve compiled React frontend assets
    location / {
        root /path/to/cse472/frontend/dist;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    # Proxy API and OAuth requests to FastAPI backend
    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }
}
```

### 2.3 Health Verification
Confirm the service is running and reporting healthy:
```bash
curl -f https://mailmind.example.com/api/health
```
Expected response:
```json
{"status": "healthy", "version": "5.4.1", "active_model": "priority-v5.1"}
```

---

## 3. Post-Deployment Smoke Test Protocol

Follow this checklist immediately after deployment:
1. **Unauthenticated Health & Status**:
   - `GET /api/health` -> HTTP 200 OK.
   - `GET /api/auth/status` -> HTTP 200 OK, `{"authenticated": false}`.
   - `POST /api/auth/test-session` -> HTTP 403 Forbidden (verifying test bypass is blocked).
2. **Google OAuth Login**:
   - In browser, navigate to application landing page.
   - Click "Continue with Google".
   - Complete Google consent screen.
   - Verify redirect back to application; session cookie received with `HttpOnly`, `SameSite=Lax`, `Secure`.
3. **Mailbox Ingestion & Classification**:
   - Click "Scan Mailbox" / "Sync".
   - Verify scanner executes batches and discovers email headers.
   - Inspect email list: verify emails render with P1, P2, P3, P4 badges, topic tags, and action/deadline indicators.
4. **Email Detail & Ground-Truth Provenance**:
   - Click an email row: verify drawer opens smoothly.
   - Submit user feedback (e.g. correct P3 to P2 with comment).
   - Verify toast confirmation "Feedback recorded for review".
5. **Account Disconnection**:
   - Click "Sign Out".
   - Verify session cookie is deleted and user is returned to the unauthenticated landing screen.
6. **Multi-User Scoping**:
   - Log in with Account B: verify Account B sees 0 emails from Account A and has an independent cache.

---

## 4. Emergency Rollback Runbook (`v5.1` -> `v4.1`)

If an operational anomaly, safety regression, or unexpected latency spike occurs in production, execute an immediate non-destructive rollback.

### 4.1 Automated Single-Command Rollback
Execute the rollback script from the repository root:
```bash
python -c "
from backend.app.ml.canary_router import canary_router
from backend.app.ml.registry import model_registry
from backend.app.ml.predictor import invalidate_cached_pipeline

canary_router.rollback()
invalidate_cached_pipeline()

reg = model_registry.get_registry()
print('Rollback executed successfully!')
print(f'Active model is now: {reg.get(\"active_model\")}')
assert reg.get('active_model') == 'priority-v4.1', 'Rollback verification failed!'
"
```

### 4.2 Manual Fallback Procedure (Direct Registry Update)
If scripts are unavailable:
1. Edit `dataset/models/registry.json`:
   ```json
   {
     "active_model": "priority-v4.1",
     "candidate_model": "priority-v5.1",
     "previous_model": "priority-v3",
     "status": "ROLLED_BACK"
   }
   ```
2. Restart FastAPI or call `GET /api/health` to confirm active model has shifted:
   ```bash
   curl https://mailmind.example.com/api/model-info
   ```
   *Expected: `"active_model": "priority-v4.1"`.*

### 4.3 Post-Rollback Integrity Verification
- Zero data loss: Existing cached emails and feedback remain intact.
- Model SHA-256 for `priority-v4.1` must match `09fe269f19ad6afb38e71b56f8c6ee7a386e59605c62c892478400bc09d5cbd0`.
- All subsequent inferences execute against the verified v4.1 model weights.
