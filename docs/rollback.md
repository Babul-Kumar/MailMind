# MAILMIND — PRODUCTION ROLLBACK & RECOVERY GUIDE

**Author:** Senior Cloud Infrastructure & Reliability Engineering Team  
**Date:** November 4, 2026  
**Document Classification:** Standard Operating Procedure (SOP)

---

## 1. Rollback Triggers

Initiate a production rollback if any of the following conditions occur post-deployment:
1. **Critical Authentication Failure (P0):** Users cannot authenticate via Google OAuth or session validation consistently returns 401/500 errors.
2. **Inference Pipeline Failure (P0):** Production ML model fails to load or prediction endpoint raises unhandled exceptions.
3. **Database Lock Contention (P1):** SQLite experiences unrecoverable `database is locked` errors under concurrent operations.
4. **Out-of-Memory Crash (P1):** Render backend container exceeds 512MB RAM and enters a crash-restart loop.
5. **Data Loss / Unintended Action Deletion (P0):** Active tasks or security incidents are deleted or omitted from the mailbox.

---

## 2. Frontend Rollback (Vercel)

If a frontend issue is detected:
1. In the Vercel Dashboard for `mail-mind`, navigate to **Deployments**.
2. Identify the previous stable production deployment.
3. Click the three dots (`...`) and select **Instant Rollback (Promote to Production)**.
4. Traffic routes to the prior build instantly ($<1$ second) without triggering a rebuild.

---

## 3. Backend Code Rollback (Render)

To roll back the FastAPI backend to the previous stable release commit:

```bash
# 1. Fetch latest git history
git fetch origin

# 2. Revert to the pre-migration stable tag / commit
git checkout <pre-migration-commit-sha>

# 3. Verify clean working directory
git status

# 4. Push to production release branch
git push origin <pre-migration-commit-sha>:main --force-with-lease
```

Render will detect the commit update and rebuild the Python service automatically.

---

## 4. Database Backward Compatibility & Migration Rollback

The database migrations introduced in this release were designed to be strictly **additive and non-breaking**:
- **New Tables:** `analysis_preferences` and `analysis_jobs`.
- **New Columns on `user_email_cache`:** `is_analyzed` (defaults to `1`) and `model_artifact_hash` (defaults to `NULL`).

The previous backend codebase queries `user_email_cache` by explicit column names (`SELECT email_id, thread_id, subject, snippet, ... FROM user_email_cache`) and does not use `SELECT *`. As a result, older backend code can read the migrated database without syntax errors or schema conflicts.

### Manual Database Recovery Procedure (If Database Corruption Occurs)
If the SQLite file `mailmind_cache.db` becomes corrupted or irrecoverable:

```bash
# 1. Stop backend service on Render
# 2. Reset cache via python command:
python -c "from backend.app.core.cache import user_email_cache; user_email_cache.clear_all()"

# Or rename corrupt database file:
mv mailmind_cache.db mailmind_cache.db.corrupt.$(date +%s)

# 3. Restart backend service
# The application will automatically execute _init_db() and create a pristine database.
```
*Note: Because MailMind uses Gmail as the single source of truth for email content, clearing the local SQLite cache causes zero data loss; the next mailbox scan will repopulate emails directly from Gmail.*

---

## 5. Post-Rollback Verification Checklist

Following rollback completion, verify system integrity:

- [ ] **Health Endpoint:** `curl -f https://<backend-url>/api/health` returns HTTP 200 with `"status": "healthy"`.
- [ ] **Model Integrity:** Run SHA-256 check on the model artifact:
  ```bash
  python -c "import hashlib; assert hashlib.sha256(open('dataset/models/priority-v5.1-candidate/model.joblib', 'rb').read()).hexdigest() == '8524ad73965859ee022f1271caee0040928e7805ab7d32c49b2f26e994f98c06'"
  ```
- [ ] **OAuth Authentication:** Complete a full Google OAuth login flow.
- [ ] **Mailbox Sync:** Scan the inbox and verify that P1/P2/P3/P4 classifications render accurately.
- [ ] **Smart Action Queue:** Confirm active tasks and security alerts appear in the action queue.
