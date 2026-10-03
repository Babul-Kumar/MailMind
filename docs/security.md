# MailMind Security Architecture & Threat Model

**System**: MailMind AI Email Priority Classification System  
**Release**: `v5.4.1-verified-production`  
**Security Classification**: Production-Hardened Personal & Enterprise Email Assistant  

---

## 1. Security Architecture Principles

MailMind enforces defense-in-depth across the application stack, adhering to six core principles:
1. **Zero Client Trust**: All identity, session validation, classification inference, feedback provenance, and scan parameters are resolved, validated, and enforced on the server.
2. **Principle of Least Privilege**: Access to Google Workspace is restricted to the minimal readonly OAuth scope (`https://www.googleapis.com/auth/gmail.readonly`). Write, delete, send, and settings modification scopes are forbidden.
3. **No Persistent Raw Content**: Raw email bodies, full MIME attachments, passwords, and OAuth tokens are never written to disk, SQLite cache, or prediction audit logs.
4. **Multi-User Isolation**: Every database query, cache entry, session file, and feedback record is scoped by a verified `user_id`. Cross-user data leakage is strictly prevented.
5. **Path Traversal Immunity**: Session identifiers and file storage operations are subject to strict regex whitelisting, canonical path resolution, and commonpath boundary verification.
6. **Immutable ML Governance**: Model weights, test holdouts, and registry metadata are cryptographically locked with SHA-256 validation. User feedback cannot automatically trigger model retraining or promotion.

---

## 2. Authentication & Session Security

### Google OAuth 2.0 with PKCE
- **Flow**: Authorization Code Flow with Proof Key for Code Exchange (PKCE, RFC 7636).
- **State Token**: Cryptographically random 32-byte state parameter stored server-side with a 10-minute expiration window to prevent Cross-Site Request Forgery (CSRF).
- **PKCE Verifier**: Ephemeral `code_verifier` stored server-side and consumed atomically upon token exchange.
- **Minimal Scope**: Only `gmail.readonly` is requested. MailMind cannot send, delete, archive, or alter user emails.

### Session Identification & Cookie Hardening
- **Format**: Cryptographically random, URL-safe base64 / hex string matching `^[A-Za-z0-9_\-~]{16,128}$`.
- **Cookie Security**:
  - `HttpOnly`: Accessible only via HTTP headers; inaccessible to JavaScript execution, preventing XSS-based session hijacking.
  - `SameSite=Lax`: Defends against cross-site request forgery attacks while permitting standard top-level navigation.
  - `Secure`: Dynamically bound to `True` whenever `ENVIRONMENT=production`. In production, cookies are transmitted exclusively over TLS/HTTPS.
- **Path Traversal Defense**: The session manager validates session IDs using:
  ```python
  def _is_safe_session_id(self, session_id: Optional[str]) -> bool:
      if not session_id or not re.match(r"^[A-Za-z0-9_\-~]{16,128}$", session_id):
          return False
      target_path = os.path.realpath(os.path.abspath(os.path.join(SESSIONS_DIR, f"{session_id}.json")))
      sessions_base = os.path.realpath(os.path.abspath(SESSIONS_DIR))
      try:
          return os.path.commonpath([sessions_base, target_path]) == sessions_base and target_path.startswith(sessions_base + os.sep)
      except ValueError:
          return False
  ```
  Even internal session persistence calls (`_persist_session`) enforce `_is_safe_session_id` before writing to disk.

---

## 3. Data Protection & Privacy

### No Raw Email Persistence
- During mailbox synchronization, messages are fetched in `format='metadata'` (headers and snippet).
- Snippets and headers are held in RAM during classification and cached in SQLite to prevent duplicate API calls.
- Raw message bodies are never written to disk or logged.

### Prediction Audit Log Pseudonymization
- Audit logs are partitioned per user and stored at:
  `dataset/monitoring/prediction_logs/predictions_<sha256(user_id)[:16]>.jsonl`
- User identifiers in logs are pseudonymized using a 16-character SHA-256 digest prefix.
- Logs strictly record metadata: `model_version`, `predicted_priority`, `confidence`, `action_required`, `deadline_status`, `topic`, `prediction_timestamp`.
- Log records are audited to guarantee absence of: `body`, `raw_body`, `sender`, `subject`, `token`, `access_token`, `refresh_token`, `client_secret`, or `password`.

---

## 4. Multi-User & Cache Isolation

- **SQLite Cache Partitioning**: All email entries in `mailmind_cache.db` are keyed by composite primary key `(user_id, message_id, model_version)`.
- All database queries enforce explicit parameter binding:
  ```sql
  SELECT * FROM email_cache WHERE user_id = ? AND message_id = ?
  ```
- If User A and User B both receive an identical corporate email with the same Gmail `message_id`, their cache entries, classifications, and feedback remain isolated in their respective `user_id` partitions.
- Feedback records queried via `GET /api/feedback` enforce `WHERE user_id = session.user_id`. No user can inspect or alter another user's feedback.

---

## 5. Trust Boundaries & Production Guardrails

### Production Test Session Endpoint Restrictions
- The endpoint `/api/auth/test-session` allows automated test suites to mock authentication.
- **Production Guardrail**: In `ENVIRONMENT=production`, the endpoint is disabled by default:
  ```python
  is_production = os.getenv("ENVIRONMENT", "development").lower() == "production"
  allow_test = os.getenv("ALLOW_TEST_ENDPOINTS", "false" if is_production else "true").lower() in ("true", "1", "yes")
  if is_production and not allow_test:
      raise HTTPException(status_code=403, detail="Test session creation endpoint is disabled in production environment.")
  ```
  Any attempt to invoke `/api/auth/test-session` in production yields immediate HTTP 403 Forbidden.

### Server-Side Feedback Provenance
- Clients submitting feedback via `POST /api/feedback` cannot forge ground-truth model predictions or model versions.
- The server retrieves the verified prediction record from `user_email_cache` for `(user_id, message_id, active_model)` and copies server-derived priority, confidence, topic, and model version directly into the feedback record.

---

## 6. Threat Model & Mitigation Matrix

| Threat Category | Specific Attack Vector | Target Surface | Mitigation Implemented | Verification Method |
| :--- | :--- | :--- | :--- | :--- |
| **Path Traversal** | Forged session cookie containing `../../` or absolute path | `session.py:get_session`, `_persist_session`, `delete_session` | Strict regex `^[A-Za-z0-9_\-~]{16,128}$` + `realpath` + `commonpath` validation | 27 adversarial vectors tested in `test_phase54_deployment_readiness.py` (all rejected) |
| **Authentication Bypass** | Invoking `/api/auth/test-session` in production to forge session | `routes_auth.py:create_test_session` | Default `ALLOW_TEST_ENDPOINTS="false"` in production mode; returns HTTP 403 Forbidden | Tested in `test_test_session_endpoint_disabled_in_prod` (returns 403) |
| **CSRF / Session Hijacking** | Cross-site request or cookie sniffing over HTTP | Browser Cookie Store | `HttpOnly=True`, `SameSite=Lax`, and `Secure=True` in production | Tested cookie header serialization and attributes in `routes_auth.py` |
| **Cross-User Data Leakage** | User A querying emails or feedback of User B | `routes_emails.py`, `cache.py`, `feedback.py` | Every SQL query bound to `session.user_id`; composite primary key in SQLite | Tested in `test_identical_message_id_across_users` and multi-user E2E tests |
| **Data Poisoning / Model Spoofing** | Attacker submitting false feedback to bias model weights | `routes_emails.py:submit_feedback`, ML pipeline | Server-side provenance lookup; zero automated retraining; human adjudication gate | Tested in `test_feedback_resolves_cached_prediction` and Phase 52 tests |
| **Buffer Exhaustion / DoS** | Excessive string payload in scan query | `routes_emails.py:start_scan` | Query parameter truncated to 200 characters; scope and mode whitelisted | Tested in adversarial parameter test harness |
| **Credential Leakage in Git** | Accidental commit of OAuth credentials or tokens | Git repository | `.gitignore` rules for `credentials.json`, `token.json`, `.env`, and session stores | Automated regex secret scanner across all git-tracked files (0 findings) |
| **Privilege Escalation** | Requesting destructive Gmail scopes (send/delete) | Google OAuth consent | Hardcoded readonly scope `https://www.googleapis.com/auth/gmail.readonly` | Verified in `config.py:GMAIL_SCOPES` and OAuth flow tests |

---

## 7. Production Secrets & Deployment Policy
1. `.env` files must NEVER be committed to Git. Deployments must utilize `.env.example` as a template and provide secrets via environment injection (e.g., Docker, Kubernetes secrets, or cloud key vaults).
2. The `SESSION_SECRET` must be set to a cryptographically secure random value generated via `secrets.token_hex(32)`.
3. In production, HTTPS termination at reverse proxy (e.g. Nginx, Cloudflare, AWS ALB) is mandatory to ensure cookie `Secure=True` functions properly.
