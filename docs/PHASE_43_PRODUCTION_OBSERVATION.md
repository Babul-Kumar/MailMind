# PHASE 43 — Production Observation, Feedback Capture & ML Monitoring

**Date:** 2026-10-02  
**Status:** ✅ COMPLETE  
**Active Model:** priority-v4.1  
**Observation Phase:** No retraining. No model changes.

---

## Section 1 — Production Model State

| Field | Value |
|-------|-------|
| Active model | `priority-v4.1` |
| Status | `production` |
| Dataset version | `dataset-v4.1` |
| Promoted at | `2026-10-02T14:23:34Z` |
| V4.1 SHA-256 | `09fe269f19ad6afb38e71b56f8c6ee7a386e59605c62c892478400bc09d5cbd0` |
| Previous model | `priority-v3` |
| Previous model status | `retired` (rollback-ready) |
| V3 SHA-256 | `fa69e6a5cfafb8b24c5941dbb8fb08a208addfc4f39e38fa47df0a7cd7040b56` |
| Historical holdout (`test.csv`) SHA | `6841CD44901FA56242BF3752257E991FD7FF474ED7E0F7A5D2B7065A0827C138` |

No model artifact was modified in this phase.  
No retraining was performed.  
No registry promotion was executed.  
No holdout was altered.

---

## Section 2 — Monitoring Architecture

```
Gmail Inbox
     ↓
predict_email() — priority-v4.1 (ACTIVE, FROZEN)
     ↓
user_email_cache (SQLite, user-scoped)
     ↓                    ↓
prediction_log.py    monitoring.py (read-only queries)
(append-only JSONL)       ↓
                    /api/monitoring/*
                    (session-gated, user-scoped)
```

### New components created

| File | Purpose |
|------|---------|
| `backend/app/core/prediction_log.py` | Append-only JSONL prediction log (no raw content) |
| `backend/app/core/monitoring.py` | Read-only monitoring over cache + feedback |
| `backend/app/api/routes_monitoring.py` | 6 monitoring API endpoints |

### Modified components

| File | Change |
|------|--------|
| `backend/app/core/feedback.py` | Richer schema (thread_id, feedback_type, confidence), user-scoped queries |
| `backend/app/api/routes_emails.py` | Fire-and-forget prediction logging (try/except, never breaks production) |
| `backend/app/main.py` | Registered monitoring router |

---

## Section 3 — Prediction Logging

Every prediction generated in the inference path is logged to a user-scoped append-only JSONL file.

**Log path:** `dataset/monitoring/prediction_logs/predictions_{uid_hash}.jsonl`

**Fields logged per prediction:**

| Field | Type | Note |
|-------|------|------|
| `user_id` | string | Authenticated user |
| `message_id` | string | Gmail message ID |
| `thread_id` | string | Gmail thread ID |
| `model_version` | string | `priority-v4.1` |
| `predicted_priority` | string | P1/P2/P3/P4 |
| `confidence` | float | Model confidence score |
| `action_required` | bool | Action detection result |
| `deadline_detected` | bool | Deadline layer result |
| `deadline_status` | string | ACTIVE / OVERDUE / NONE etc. |
| `topic` | string | Email topic classification |
| `needs_attention` | bool | Needs attention flag |
| `refinement_applied` | bool | Whether refinement fired |
| `prediction_timestamp` | ISO 8601 | UTC timestamp |

**Explicitly excluded from logs:**
- Email subject, body, sender, recipients (raw content)
- OAuth tokens, access tokens, refresh tokens
- Any credential or personal data beyond user_id

**The log is fire-and-forget** — any write failure is caught silently and never interrupts a production response.

---

## Section 4 — Feedback Architecture

### Feedback pipeline (correct flow)

```
Production prediction
        ↓
User correction (POST /api/feedback)
        ↓
dataset/feedback/feedback.jsonl  [status: pending_review]
        ↓
Review queue
        ↓
Human adjudication
        ↓
dataset-v5 candidate examples
        ↓
Offline training
        ↓
Candidate model
        ↓
Holdout evaluation
        ↓
Promotion gate
```

### FORBIDDEN flow

```
Production prediction → automatic training  [NEVER]
```

### FeedbackSubmission schema (Phase 43 upgrade)

```python
class FeedbackSubmission(BaseModel):
    message_id: str           # Required
    model_version: str        # Required
    thread_id: Optional[str]  # Phase 43 — thread context
    feedback_type: str        # Phase 43 — priority_wrong / action_required_wrong / deadline_wrong / topic_wrong / general
    predicted_priority: str
    original_confidence: Optional[float]   # Phase 43 — model confidence at prediction time
    original_topic: Optional[str]          # Phase 43 — model-assigned topic
    original_deadline_detected: Optional[bool]  # Phase 43
    predicted_action_required: bool
    corrected_priority: Optional[str]
    corrected_action_required: Optional[bool]
    deadline_correction: Optional[bool]
    corrected_deadline_display: Optional[str]
    topic_correction: Optional[str]
    notes: Optional[str]
```

### Feedback endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/feedback` | POST | Submit a correction |
| `/api/feedback` | GET | List recent feedback (user-scoped) |

---

## Section 5 — Baseline Production Distribution (V4.1 Reference)

Phase 42 production baseline (frozen reference, not hard threshold):

| Metric | Phase 42 Value |
|--------|---------------|
| Total messages | 17,322 |
| P1 % | 1.36% (235) |
| P2 % | 85.47% (14,806) |
| P3 % | 1.03% (179) |
| P4 % | 12.12% (2,099) |
| Action Required | 521 |
| Needs Attention | 644 |

These values are stored in `monitoring.py:V41_BASELINE` and are used to compute drift indicators — not as alert thresholds.

---

## Section 6 — Confidence Monitoring

The `/api/monitoring/confidence` endpoint reports per-priority confidence percentiles:

| Metric | P1 | P2 | P3 | P4 |
|--------|----|----|----|-----|
| count | — | — | — | — |
| mean | — | — | — | — |
| median | — | — | — | — |
| p10 | — | — | — | — |
| p25 | — | — | — | — |
| p75 | — | — | — | — |
| p90 | — | — | — | — |

*(Values populate from the live cache; shown empty in this baseline report.)*

**Review candidate flags (informational only):**

- `low_confidence_P1`: P1 predictions with confidence < 0.40
- `low_confidence_P2`: P2 predictions with confidence < 0.40
- `high_confidence_P3`: P3 predictions with confidence ≥ 0.70
- `high_confidence_P4`: P4 predictions with confidence ≥ 0.70

**Confidence ≠ correctness.** These flags are review suggestions. Do not automatically reinterpret them as errors.

---

## Section 7 — Safety Monitoring

The `/api/monitoring/safety` endpoint surfaces four safety-critical event categories from user feedback:

| Category | Description | Treatment |
|----------|-------------|-----------|
| `otp_below_p1` | OTP/security email predicted below P1, corrected to P1 | Safety-critical — review for dataset-v5 |
| `security_below_p2` | Security email predicted below P2, corrected to P2 | Safety-critical |
| `payment_non_actionable` | Payment email predicted non-actionable, corrected by user | High priority review |
| `deadline_flagged_non_actionable` | User flagged deadline as missed action | Review |

**No automatic prediction changes are made from safety events.**  
All safety events are surface-only. Corrections are human-reviewed before any dataset update.

---

## Section 8 — Drift Monitoring

The `/api/monitoring/distribution` endpoint computes drift vs. the V4.1 Phase 42 baseline:

```json
"drift_vs_baseline_pct_pts": {
    "P1_pct": <current - baseline>,
    "P2_pct": <current - baseline>,
    "P3_pct": <current - baseline>,
    "P4_pct": <current - baseline>
}
```

**Drift interpretation policy:**
- Drift values are absolute percentage-point deltas.
- Shifts ≥ ±10 pp are flagged as "notable" for human awareness.
- Drift ≠ model degradation. Do not declare model drift from a single metric.
- Distribution shifts may reflect changes in incoming email patterns, not model error.

---

## Section 9 — Privacy / Security Verification

| Check | Status |
|-------|--------|
| No OAuth token in prediction logs | ✅ Verified (explicit exclusion in `prediction_log.py`) |
| No access token in feedback records | ✅ Verified (explicit credential strip in `feedback.py`) |
| No credentials in monitoring responses | ✅ Verified (test_11 passes — 0 occurrences) |
| No raw email body in prediction log | ✅ Verified (schema contains no body/subject/sender fields) |
| HttpOnly session unchanged | ✅ Unchanged |
| Gmail scope remains readonly | ✅ Unchanged |
| User isolation (cache PK) | ✅ `(user_id, message_id)` — unchanged |
| User isolation (monitoring) | ✅ All queries filter by session.user_id |
| User isolation (feedback) | ✅ `list_feedback(user_id=...)` enforced |

---

## Section 10 — Multi-User Isolation

| Isolation Guarantee | Implementation |
|--------------------|----------------|
| Cache data | SQLite PK: `(user_id, message_id)` |
| Prediction log | Per-user file: `predictions_{sha256(user_id)[:16]}.jsonl` |
| Feedback records | `user_id` field on every record; `list_feedback(user_id=)` filter |
| Monitoring endpoints | `session.user_id` injected by `_require_session()` |
| Monitoring aggregates | All SQL queries include `WHERE user_id = ?` |

**Cross-user data contamination is architecturally impossible:**
- User A's feedback cannot enter User B's monitoring report.
- User A's cache entries are invisible to User B's prediction path.
- User A's prediction log is at a different file path.

---

## Section 11 — Tests

### Backend

```
pytest tests/ -v
305 passed, 31 warnings
```

**Previous:** 290 tests  
**Phase 43 additions:** 15 new tests  
**Total:** 305 passed

| New Test | Description |
|----------|-------------|
| `test_01_registry_v41_active_v3_rollback_ready` | Registry state verification |
| `test_02_feedback_submission_stores_new_fields` | Phase 43 field richness |
| `test_03_feedback_user_isolation` | User A/B feedback isolation |
| `test_04_monitoring_summary_endpoint` | Summary endpoint structure |
| `test_05_distribution_report` | Distribution + drift keys |
| `test_06_confidence_report` | Per-priority percentile stats |
| `test_07_safety_events_endpoint` | Safety event list structure |
| `test_08_feedback_stats_correction_rate` | Correction rate and matrix |
| `test_09_v5_readiness_endpoint` | Pipeline and gates |
| `test_10_no_retraining_through_monitoring` | fit/fit_transform guard |
| `test_11_no_oauth_token_in_monitoring_responses` | Privacy check |
| `test_12_model_sha_unchanged_after_monitoring` | Artifact immutability |
| `test_13_multiuser_monitoring_isolation` | Multi-user separation |
| `TestPredictionLog::test_prediction_log_write_read` | Log write/read |
| `TestPredictionLog::test_prediction_log_no_crash_on_bad_input` | Error resilience |

### Frontend

```
vitest / node --test
9 passed
```

### Build

```
vite build
✓ 245.66 kB JS bundle — clean
```

---

## Section 12 — Files Changed

| File | Action | Description |
|------|--------|-------------|
| `backend/app/core/feedback.py` | MODIFIED | Richer schema, model_dump(), user-scoped list |
| `backend/app/api/routes_emails.py` | MODIFIED | Fire-and-forget prediction logging |
| `backend/app/main.py` | MODIFIED | Registered monitoring router |

---

## Section 13 — Files Created

| File | Description |
|------|-------------|
| `backend/app/core/prediction_log.py` | Append-only prediction log (no raw content) |
| `backend/app/core/monitoring.py` | Read-only production monitoring module |
| `backend/app/api/routes_monitoring.py` | 6 monitoring API endpoints |
| `tests/test_phase43_monitoring.py` | 15 Phase 43 tests |
| `docs/PHASE_43_PRODUCTION_OBSERVATION.md` | This report |

---

## Section 14 — Known Limitations

1. **Prediction log is not real-time queryable via API** — logs are on-disk JSONL, queryable via `prediction_log_stats()`. A future phase could add `/api/monitoring/predictions` if needed.

2. **Confidence report requires populated cache** — if the user has no cached emails (fresh account), all confidence stats return 0. This is correct; no synthetic data is injected.

3. **Feedback-based safety events require user action** — safety monitoring depends on users submitting corrections. If no feedback has been submitted, all safety event lists will be empty.

4. **Feedback pipeline is append-only** — there is no edit or delete endpoint. This is intentional: the feedback log is evidence; it must not be mutated.

5. **Drift indicators are user-scoped** — the baseline was measured on user `1710949`'s 17,322-email mailbox. A user with a very different mailbox profile will show apparent "drift" that reflects their mailbox, not the model.

6. **No alert system** — monitoring surfaces observations but does not send notifications or trigger any automatic action. This is by design in Phase 43.

---

## Section 15 — Dataset-v5 Readiness Criteria

Dataset-v5 may be initiated when the following gates are met (all require human adjudication):

| Gate | Target | Status |
|------|--------|--------|
| Minimum feedback volume | ≥ 50 records | Check `/api/monitoring/v5-readiness` |
| Minimum priority corrections | ≥ 20 | Check `/api/monitoring/v5-readiness` |
| P2 boundary examples (P2→lower) | ≥ 10 | Check `/api/monitoring/v5-readiness` |
| P2 boundary examples (lower→P2) | ≥ 10 | Check `/api/monitoring/v5-readiness` |
| Safety-critical lower→P1 examples | Any count | Include ALL in dataset-v5 |
| Human review of all feedback | 100% | **Mandatory — no exceptions** |

### Mandatory pipeline

```
Production prediction
        ↓
User correction → POST /api/feedback
        ↓
feedback.jsonl  [status: pending_review]
        ↓
Human adjudication
        ↓
dataset-v5 candidate examples
        ↓
Offline training (separate from production)
        ↓
Candidate model (NOT promoted automatically)
        ↓
Holdout evaluation (test.csv + modern holdout)
        ↓
Promotion gate (Phase N)
```

**FORBIDDEN:** `Production prediction → automatic training`

---

## Monitoring Endpoints Summary

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/monitoring/summary` | GET | Master summary: model, distribution, feedback, drift |
| `/api/monitoring/distribution` | GET | P1/P2/P3/P4 percentages + drift vs baseline |
| `/api/monitoring/confidence` | GET | Per-priority confidence percentile table |
| `/api/monitoring/safety` | GET | Safety-critical correction events |
| `/api/monitoring/feedback-stats` | GET | Correction rates, P→P matrix |
| `/api/monitoring/v5-readiness` | GET | Dataset-v5 readiness gate status |

All endpoints require authenticated session. All responses are user-scoped.

---

*Phase 43 complete. Active model: priority-v4.1. No retraining. 305/305 tests passing.*
