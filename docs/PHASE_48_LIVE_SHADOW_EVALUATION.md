# Phase 48 — Live Shadow Inference & Promotion Evidence Report

## 1. Objective

The objective of Phase 48 is to implement a production-safe **Live Shadow Inference Pipeline** for candidate model `priority-v5.1` running in parallel with active production model `priority-v4.1`. 

Under Phase 48:
- `priority-v4.1` remains the sole **ACTIVE** user-facing model in production.
- `priority-v5.1` runs strictly as **SHADOW ONLY** (non-blocking, observational, and invisible to the user).
- Both models are evaluated against identical real mailbox traffic (17,329 messages) to gather empirical evidence on prediction divergence, latency overhead, and safety retention for a future promotion decision.

---

## 2. Current Production Model

- **Model Version:** `priority-v4.1` (Boundary Repair)
- **Status:** **ACTIVE / PRODUCTION**
- **Artifact Path:** `dataset/models/priority-v4.1/model.joblib`
- **Artifact SHA-256:** `09fe269f19ad6afb38e71b56f8c6ee7a386e59605c62c892478400bc09d5cbd0`
- **Role:** Exclusively serves live user classifications, API responses, dashboard views, and persistent cache writes.

---

## 3. Shadow Candidate Model

- **Model Version:** `priority-v5.1` (Boundary Remediated & Curated Negatives)
- **Status:** **CANDIDATE / SHADOW ONLY**
- **Artifact Path:** `dataset/models/priority-v5.1-candidate/model.joblib`
- **Artifact SHA-256:** `8524ad73965859ee022f1271caee0040928e7805ab7d32c49b2f26e994f98c06`
- **Role:** Observational evaluation over live and cached email traffic; zero user-facing authority.

---

## 4. Architecture

```
                    Gmail / Ingestion Flow
                              |
                              v
             +----------------------------------+
             |   priority-v4.1 (PRODUCTION)     |
             |   Synchronous Inference Path     |
             +----------------------------------+
                              |
               +--------------+--------------+
               |                             |
               v                             v
        user_email_cache              Background Thread
         (SQLite WAL)                        |
               |                             v
               v             +----------------------------------+
        FastAPI Response     |    priority-v5.1 (SHADOW ONLY)   |
               |             |    Non-Blocking Inference Path   |
               v             +----------------------------------+
          UI Dashboard                       |
                                             v
                                    mailmind_shadow.db
                                (Divergence / Evidence)
```

The system strictly decouples the production inference path from shadow observation:
1. Production requests are processed by `priority-v4.1` synchronously.
2. In parallel (via background thread pool `_shadow_executor` or post-classification hook), candidate model `priority-v5.1` evaluates the same email messages.
3. Failures in candidate loading, inference, or shadow persistence are caught and logged at warning level; they never interrupt or degrade production responses.

---

## 5. Data Flow

1. **Ingestion:** Raw emails arrive via Gmail API batch fetch (`scan_engine.py` or `routes_emails.py`).
2. **Production Classification:** `predict_batch(emails, pipeline=v41_pipeline)` computes production priority, action requirements, and deadlines.
3. **Cache Storage:** Production predictions are committed to `user_email_cache` table in `google_auth/cache/mailmind_cache.db`.
4. **Shadow Hook:** `shadow_engine.shadow_batch_async(user_id, emails, active_predictions)` submits a shadow task to the thread pool.
5. **Deduplication Check:** Shadow engine checks `mailmind_shadow.db` for existing `(user_id, message_id, shadow_model_version)` tuples and skips redundant processing.
6. **Shadow Classification:** `predict_batch(to_process, pipeline=v51_pipeline)` computes candidate priority.
7. **Record Construction:** Shadow engine computes divergences, measures latency, deterministically assigns safety categories, and writes records to `mailmind_shadow.db` and user-scoped `shadow_<user_hash>.jsonl`.
8. **UI Presentation:** Frontend displays production predictions from `priority-v4.1`. The Settings dialog contains an administrative "Shadow Evaluation" tab displaying live shadow telemetry.

---

## 6. Security Isolation

- **Zero Body Logging:** Raw email bodies, snippets, subjects, and sender addresses are **strictly excluded** from shadow records.
- **Zero Credential Exposure:** OAuth tokens, refresh tokens, client secrets, and session cookies are never passed to or stored in shadow storage.
- **Deterministic Hashing:** User log files are named using SHA-256 prefixes (`shadow_<uid_hash>.jsonl`).

---

## 7. User Isolation

- **User Scoping:** Every shadow prediction is explicitly keyed to `user_id`.
- **Query Isolation:** All shadow monitoring queries enforce `WHERE user_id = ?`.
- **Multi-User Test Verified:** Concurrent executions across `user_A` and `user_B` produce strictly disjoint shadow tables with zero cross-tenant contamination.

---

## 8. Shadow Storage Schema

The shadow storage engine uses a dedicated SQLite database at `google_auth/cache/mailmind_shadow.db`:

```sql
CREATE TABLE shadow_predictions (
    shadow_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    message_id TEXT NOT NULL,
    thread_id TEXT,
    timestamp TEXT NOT NULL,
    active_model_version TEXT NOT NULL,
    shadow_model_version TEXT NOT NULL,
    active_prediction TEXT NOT NULL,
    shadow_prediction TEXT NOT NULL,
    active_confidence REAL NOT NULL,
    shadow_confidence REAL NOT NULL,
    priority_changed INTEGER NOT NULL,
    action_required_active INTEGER NOT NULL,
    action_required_shadow INTEGER NOT NULL,
    deadline_detected_active INTEGER NOT NULL,
    deadline_detected_shadow INTEGER NOT NULL,
    deadline_status_active TEXT NOT NULL,
    deadline_status_shadow TEXT NOT NULL,
    needs_attention_active INTEGER NOT NULL,
    needs_attention_shadow INTEGER NOT NULL,
    latency_active_ms REAL NOT NULL,
    latency_shadow_ms REAL NOT NULL,
    prediction_diverged INTEGER NOT NULL,
    safety_category TEXT,
    UNIQUE(user_id, message_id, shadow_model_version)
);
```

Indexes are established on `(user_id, shadow_model_version)`, `(user_id, prediction_diverged)`, `(user_id, safety_category)`, and `(user_id, timestamp)`.

---

## 9. Mailbox Scope

- **Scope:** Complete accessible mailbox (Inbox, Sent, Archive, Custom Labels).
- **Target User:** `1710949`
- **Cached Message Population:** 17,329 messages in `google_auth/cache/mailmind_cache.db`.

---

## 10. Shadow Population & Execution Metrics

| Metric | Measured Value | Target / Requirement | Status |
|:---|:---:|:---:|:---:|
| **Total Mailbox Messages** | **17,329** | Complete population | PASS |
| **Newly Evaluated** | **17,329** | Full mailbox coverage | PASS |
| **Throughput** | **232.3 msgs/sec** | > 100 msgs/sec | PASS |
| **Wall-Clock Duration** | **74.60 seconds** | Non-blocking execution | PASS |
| **Failed Messages** | **0** | 0 failures | PASS |
| **Production Cache Mutations** | **0 writes** | Exactly 0 writes | PASS |

---

## 11. Agreement Rate & Divergence Overview

| Category | Message Count | Percentage |
|:---|:---:|:---:|
| **Total Shadowed** | 17,329 | 100.00% |
| **Exact Priority Agreement** | **16,851** | **97.24%** |
| **Priority Divergence** | **478** | **2.76%** |
| **Total Prediction Divergence** | **478** | **2.76%** |

The candidate model exhibits an exceptionally high baseline agreement (**97.24%**) with production `priority-v4.1`, confirming that global mailbox triage semantics are strongly preserved.

---

## 12. Priority Transition Matrix (v4.1 Rows $\to$ v5.1 Columns)

```
                     v5.1 Predicted Priority
                 P1       P2       P3       P4     Total Active
Active  P1:     403        0        0        0          403
v4.1    P2:      10      908       88       17        1,023
        P3:       0       16   10,195      103       10,314
        P4:       0        1      243    5,345        5,589
Total   v5.1:   413      925   10,526    5,465       17,329
```

### Class Distribution Shift

| Priority Tier | Active v4.1 Count (%) | Shadow v5.1 Count (%) | Delta | Operational Rationale |
|:---|:---:|:---:|:---:|:---|
| **P1** | 403 (2.33%) | 413 (2.38%) | +0.05% | Retains all 403 active P1s; escalates 10 urgent alerts |
| **P2** | 1,023 (5.90%) | 925 (5.34%) | -0.56% | De-escalates routine acknowledgments/receipts |
| **P3** | 10,314 (59.52%) | 10,526 (60.74%) | +1.22% | Receives routine informational emails |
| **P4** | 5,589 (32.25%) | 5,465 (31.54%) | -0.71% | Stable bulk promotional/noise tier |

---

## 13. Critical P1 Downgrade Audit

| Transition | Count | Requirement | Result |
|:---|:---:|:---:|:---:|
| **P1 $\to$ P2** | **0** | Must be 0 | **PASS (100% Retained)** |
| **P1 $\to$ P3** | **0** | Must be 0 | **PASS (100% Retained)** |
| **P1 $\to$ P4** | **0** | Must be 0 | **PASS (100% Retained)** |
| **Total P1 Downgrades** | **0** | **0 permitted** | **PERFECT RETENTION** |

Every single active P1 message in the production mailbox (**403 out of 403**) retained P1 priority under candidate model `priority-v5.1`.

---

## 14. Action-State Differences

- **Active Action Required Count:** 521
- **Shadow Action Required Count:** 521
- **Action Required Disagreements:** **0 (0.00%)**
- The secondary Priority Refinement Layer ensured that actionable imperatives remained completely synchronized between active and candidate models.

---

## 15. Deadline Differences

- **Active Deadline Detected Count:** 214
- **Shadow Deadline Detected Count:** 214
- **Deadline Detected Disagreements:** **0 (0.00%)**
- Zero deadline regressions or dropped temporal constraints.

---

## 16. Needs Attention Differences

- **Active Needs Attention Count:** 644
- **Shadow Needs Attention Count:** 629
- **Net Change:** -15 messages
- **Reason:** 15 non-actionable emails de-escalated from P2 to P3 no longer trigger the triage dashboard's "Needs Attention" badge, reducing inbox alert fatigue while preserving genuine action items.

---

## 17. Deterministic Safety-Category Audit

750 messages were deterministically matched to high-risk safety categories:

| Safety Category | Mailbox Population | Exact Priority Agreement | Priority Divergence | Critical P1 Downgrades | Status |
|:---|:---:|:---:|:---:|:---:|:---:|
| **MFA** | 4 | 4 (100.0%) | 0 (0.0%) | **0** | **SAFE** |
| **OTP** | 163 | 163 (100.0%) | 0 (0.0%) | **0** | **SAFE** |
| **Account Activation** | 111 | 111 (100.0%) | 0 (0.0%) | **0** | **SAFE** |
| **Password Reset** | 35 | 35 (100.0%) | 0 (0.0%) | **0** | **SAFE** |
| **Payment Failure** | 6 | 6 (100.0%) | 0 (0.0%) | **0** | **SAFE** |
| **Security Alerts** | 233 | 223 (95.7%) | 10 (4.3%) | **0** | **SAFE** |
| **Deadlines** | 198 | 188 (94.9%) | 10 (5.1%) | **0** | **SAFE** |
| **Total High-Risk** | **750** | **730 (97.3%)** | **20 (2.7%)** | **0** | **100% SAFE** |

---

## 18. Latency Footprint

| Metric | Production Model (v4.1) | Candidate Model (v5.1) | Net Overhead |
|:---|:---:|:---:|:---:|
| **Median Inference Latency** | 1.79 ms | 1.75 ms | **-0.04 ms (No Regression)** |
| **95th Percentile Latency (P95)** | 2.15 ms | 2.10 ms | **-0.05 ms** |
| **Mean Inference Latency** | 1.84 ms | 1.81 ms | **-0.03 ms** |

Because candidate `priority-v5.1` uses an identical TF-IDF + Multinomial Logistic Regression pipeline with equivalent feature dimensions (68,394 vs 66,526 n-grams), inference latency is statistically identical with zero latency penalty.

---

## 19. Failure Isolation Verification

The following fault injection scenarios were executed and verified:
1. **Missing Candidate Artifact:** Handled gracefully via try/except; `load_shadow_model` returns `None`; production inference proceeds without error.
2. **Corrupt Candidate Joblib:** Caught and trapped; production proceeds normally.
3. **Malformed Email Payload:** Caught and logged; returns `None` without bubbling up.
4. **Duplicate Message Insertion:** Handled by `INSERT OR REPLACE` and `get_already_shadowed_ids` check; no duplicate database rows.
5. **Shadow Storage Lock/Timeout:** Background thread pool handles failures asynchronously; production response is delivered immediately.

---

## 20. Feedback Correlation

Inspection of `dataset/feedback/feedback.jsonl` correlated user feedback records with shadow predictions:
- User-corrected recruitment application feedback (`fb_adj_001`): active model predicted P2; shadow candidate correctly predicted **P3**, perfectly matching user intent.
- Zero feedback records contradicted candidate predictions on verified boundaries.

---

## 21. Test Suite Verification

- **Dedicated Phase 48 Test Suite:** 25 passed, 0 failed in 10.77s (`tests/test_phase48_live_shadow.py`).
- **Complete Backend Regression Suite:** **384 passed, 0 failed** in 54.25s (`pytest tests/`).
- **Frontend Test Suite:** 9 passed, 0 failed in 194ms (`npm test`).
- **Frontend Production Build:** Succeeded in 5.39s (`npm run build`).

---

## 22. Model Hashes

| Model | Role | Artifact Path | SHA-256 Checksum | Status |
|:---|:---|:---|:---|:---:|
| `priority-v4.1` | Active Production | `dataset/models/priority-v4.1/model.joblib` | `09fe269f19ad6afb38e71b56f8c6ee7a386e59605c62c892478400bc09d5cbd0` | Frozen / Unchanged |
| `priority-v5.1` | Candidate Shadow | `dataset/models/priority-v5.1-candidate/model.joblib` | `8524ad73965859ee022f1271caee0040928e7805ab7d32c49b2f26e994f98c06` | Candidate / Frozen |

---

## 23. Dataset Hashes

All 6 frozen holdouts remain 100% bit-identical:
- `test.csv`: `7bb3604f329979c2986422d3615fa61e6871a2a466540c49fd560a8ea0415a77`
- `modern_holdout.csv`: `fecf6ce9c4e207d5705307a5188f543f07a7c8c366ff11ff92af13e2f5bfe634`
- `newsletter_holdout.csv`: `c091942bc3c6ad8158f334a1b02353fc429c328ca4339906d4e5f0375cf39869`
- `social_holdout.csv`: `ea27cf462c0bb8a12e2760df2bc93d6d0ae513c9eec1e075b83ea3f6bb5c697c`
- `dataset-v4/test.csv`: `ef5c7ca8d20387431e21b777a83d7367e9f564be65e0fa0c1bf65cbbf6aa66f0`
- `dataset-v4.1/test.csv`: `ef5c7ca8d20387431e21b777a83d7367e9f564be65e0fa0c1bf65cbbf6aa66f0`

---

## 24. Production Impact

- **Database Safety:** Zero rows added or mutated in `user_email_cache`.
- **UI Safety:** 100% of user-facing triage dashboard priority labels continue to be rendered from `priority-v4.1`.
- **Latency Impact:** Background asynchronous thread execution adds **0 ms** to API request latencies.
- **CPU / Memory:** Shadow model remains cached in memory (~12 MB RAM footprint); execution consumes minimal CPU cycles.

---

## 25. Known Limitations

1. **Local Single-Node Architecture:** Background threading pool (`ThreadPoolExecutor`) is optimal for local/single-server deployments; high-scale horizontal multi-node clusters would utilize a Redis queue or Celery worker for shadow dispatch.
2. **Cold Start:** Initial shadow model load takes ~25 ms on the first background invocation before in-memory caching.

---

## 26. Promotion Readiness Assessment & Final Decision

Candidate model `priority-v5.1` has undergone exhaustive shadow evaluation across the complete live mailbox population:
- **High Baseline Agreement:** 97.24% exact priority agreement with production v4.1.
- **Zero Critical P1 Downgrades:** 0 / 403 P1 messages downgraded (100% safety retention).
- **Zero High-Risk Safety Failures:** 100% agreement on OTP, MFA, password reset, account activation, and payment failures.
- **Intended Boundary Remediation:** Routine recruitment application acknowledgments and payment receipts safely transition from P2 to P3.
- **Zero Latency Penalty:** 1.75 ms median inference.
- **Complete Test Coverage:** 25/25 Phase 48 tests passed; 384/384 backend tests passed; 9/9 frontend tests passed; production build succeeded.

In accordance with Phase 48 governance rules:
- **NO AUTOMATIC PROMOTION HAS TAKEN PLACE.**
- `active_model` remains strictly `priority-v4.1`.
- `candidate_model` remains strictly `priority-v5.1`.

```
======================================================================
FINAL PHASE 48 DECISION:
CANDIDATE READY FOR CANARY REVIEW
======================================================================
```

---

## 27. Phase 49 Recommendation

1. **Canary Traffic Split:** Roll out `priority-v5.1` to a 10% canary traffic allocation while retaining `priority-v4.1` for 90% of user traffic.
2. **User Feedback Monitoring:** Monitor real user interaction and feedback correction rates between canary and control groups.
3. **Formal Promotion Gate:** If canary traffic exhibits zero negative feedback or regressions over a 48-hour monitoring window, execute final promotion of `priority-v5.1` to `active_model`.
