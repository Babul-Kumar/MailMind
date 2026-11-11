# MailMind — Comprehensive Bug Ledger & Defect Tracking

This persistent ledger records every defect uncovered, investigated, diagnosed, and resolved during the senior QA audit and continuous regression loop.

---

## Defect Summary by Severity

| Severity Level | Total Discovered | Fixed Locally | Retest Passed | Open / Blocked |
| :--- | :---: | :---: | :---: | :---: |
| **P0 — Critical** | 1 | 1 | 1 | 0 |
| **P1 — High** | 6 | 6 | 6 | 0 |
| **P2 — Medium** | 5 | 5 | 5 | 0 |
| **P3 — Low** | 1 | 1 | 1 | 0 |
| **Total** | **13** | **13** | **13** | **0** |

---

## Detailed Bug Records

### BUG-001: Production HTTP 500 on `/api/emails` (`AttributeError: get_user_action_states`)
* **Severity:** **P0 — Critical** (Application-wide release blocker)
* **Status:** `Retest passed`
* **Affected Feature:** Paginated Email Retrieval & Smart Action Queue Integration
* **Affected Files:**
  - `backend/app/api/routes_emails.py`
  - `backend/app/api/routes_actions.py`
  - `backend/app/core/action_store.py`
* **Preconditions:** Authenticated user session requesting `/api/emails?page=1&page_size=50`.
* **Reproduction Steps:**
  1. Authenticate a user session.
  2. Send `GET /api/emails?page=1&page_size=50`.
  3. Observe unhandled exception in Render logs: `AttributeError: 'UserActionStore' object has no attribute 'get_user_action_states'` at line ~452.
* **Expected Behavior:** Endpoint returns HTTP 200 with paginated email list enriched with the authenticated user's action states.
* **Actual Behavior:** Endpoint crashed with HTTP 500; complete mailbox loading failed.
* **Root Cause:** Caller in `routes_emails.py` expected `user_action_store.get_user_action_states(user_id)`. `UserActionStore` in commit `878383c` only implemented `get_user_actions_map(user_id)`. The missing compatibility alias and absence of defensive dispatch caused an immediate attribute error.
* **Fix Implemented:**
  1. Added `get_all_action_states(self, user_id)` and confirmed `get_user_action_states(self, user_id)` on `UserActionStore` in `action_store.py`.
  2. Added defensive multi-method dispatch (`hasattr`) in `routes_emails.py` and `routes_actions.py` checking `get_user_action_states`, `get_all_action_states`, and `get_user_actions_map`.
* **Regression Tests Added:**
  - `tests/test_smart_action_queue.py`: `test_19_action_store_get_all_action_states_alias`, `test_20_action_store_safe_empty_and_corrupt_recovery`, `test_21_action_states_user_isolation`.
  - `tests/test_priority_filtering_regression.py`: `test_07_action_state_enrichment_and_isolation`.
* **Retest Result:** **Passed** across both test suites (34/34 and 9/9 passed).
* **Remaining Risk:** None. The dispatch handles any future or past method name variant safely without throwing `AttributeError`.

---

### BUG-002: Strict Priority Filtering Contamination & Mismatched Badges
* **Severity:** **P1 — High** (Core workflow data correctness failure)
* **Status:** `Retest passed`
* **Affected Feature:** Priority Filtering (P1, P2, P3, P4) & Mailbox Search Composition
* **Affected Files:**
  - `backend/app/core/cache.py`
  - `backend/app/api/routes_emails.py`
  - `frontend/src/hooks/useSearch.js`
* **Preconditions:** Mailbox containing emails classified across diverse priority tiers (P1 through P4), with priority refinement rules applied.
* **Reproduction Steps:**
  1. Select `P1 · Critical` filter chip in the UI or request `GET /api/emails?priority=P1`.
  2. Inspect returned email rows.
  3. Observe P2, P3, and P4 email badges visible in the strictly filtered P1 view.
* **Expected Behavior:** P1 view displays strictly P1 messages. Zero P2/P3/P4 rows appear under P1. Needs Attention retains original model priorities (actionable P3 remains P3 without being mutated to P1).
* **Actual Behavior:** Filtered views displayed mixed-priority rows.
* **Root Cause:**
  1. In `cache.py` line 230, `store_batch()` indexed raw `item.get("predicted_priority")` into the SQLite index column while saving refined `item.get("final_priority")` into JSON payload. SQL `WHERE predicted_priority = 'P1'` matched unrefined rows that displayed P3 badges.
  2. In `routes_emails.py`, when `total_cached <= len(all_emails)`, `display_list` fell back to `all_emails` without applying priority filtering.
  3. In `useSearch.js`, `options.serverFiltered: true` bypassed client-side filtering, allowing background scan syncs to inject unfiltered emails.
* **Fix Implemented:**
  1. Updated `cache.py` to index `item.get("final_priority") or item.get("predicted_priority") or "P4"`.
  2. Added strict priority filtering on `display_list` across all branches in `routes_emails.py`.
  3. Added strict priority and action guards in `useSearch.js` regardless of `serverFiltered` setting.
* **Regression Tests Added:**
  - `tests/test_priority_filtering_regression.py`: Tests 01 through 06 testing P1, P2, P3, P4 isolation, All Mail completeness, and Needs Attention priority preservation.
* **Retest Result:** **Passed** (9/9 passed).
* **Remaining Risk:** None. Verified against multi-tier fixtures.

---

### BUG-003: Stuck "Analyzing Complete Mailbox" Full-Screen Overlay
* **Severity:** **P1 — High** (User experience and application availability blocker)
* **Status:** `Retest passed`
* **Affected Feature:** Application Startup, Loading States & Error Recovery
* **Affected Files:**
  - `frontend/src/App.jsx`
  - `frontend/src/components/inbox/Inbox.jsx`
  - `frontend/src/hooks/useEmails.js`
* **Preconditions:** Cold start with HTTP 500 or network failure on `/api/emails` while background scan job was active.
* **Reproduction Steps:**
  1. Simulate or trigger an API failure on `/api/emails`.
  2. Background scan polling `/api/scan/status` continues returning HTTP 200 with progress counters.
  3. The user is trapped in an inescapable full-screen "Analyzing Complete Mailbox" loading animation.
* **Expected Behavior:** Decouple mailbox loading from scan status. Render the app shell and cached emails immediately. If mailbox fetch fails, display a clear, recoverable error banner with a manual "Retry" action.
* **Actual Behavior:** Application was completely locked out behind the full-screen loader.
* **Root Cause:** `App.jsx` evaluated `showInitialLoading = auth.isAuthenticated && emailsHook.emails.length === 0 && emailsHook.isScanning`. When the email fetch failed, `emails.length` stayed 0 while `isScanning` stayed true, preventing the app shell from rendering.
* **Fix Implemented:**
  1. In `App.jsx`, modified `showInitialLoading` so it only activates on the initial cold start of a brand new user with 0 cached emails and zero errors.
  2. Added recoverable error banner with a manual "Retry Connection" button in `Inbox.jsx`.
  3. Bounded automated retries to 3 with exponential backoff in `useEmails.js`.
* **Regression Tests Added:**
  - `frontend/src/services/api.test.js`: Verified error handling and bounded retries.
  - Manual error injection test: Verified error banner and retry action render without locking the shell.
* **Retest Result:** **Passed**.
* **Remaining Risk:** None.

---

### BUG-004: Smart Action Queue & Summary Emptied for Canary Users
* **Severity:** **P2 — Medium** (Feature defect during canary/migration rollouts)
* **Status:** `Retest passed`
* **Affected Feature:** Action Queue & Badge Counts
* **Affected Files:**
  - `backend/app/api/routes_actions.py`
  - `backend/app/api/routes_emails.py`
* **Preconditions:** User assigned to a canary model version (e.g. `priority-v5.1`) or user with emails cached under a prior model version.
* **Reproduction Steps:**
  1. Assign a test user to canary routing (`priority-v5.1`).
  2. Cache analyzed emails for that user under `priority-v5.1`.
  3. Call `GET /api/actions/queue` or `GET /api/actions/summary`.
  4. Endpoints queried `query_emails(..., model_version=model_registry.get_active_version())` (which returned `priority-v4.1`), matching 0 emails.
* **Expected Behavior:** Action queue and summary badges return the user's active actionable items based on their assigned canary model, falling back to all un-stale cached emails if version changes occur.
* **Actual Behavior:** Canary users received an empty action queue and 0 attention count.
* **Root Cause:** `routes_actions.py` hardcoded `model_registry.get_active_version()` instead of querying the user's routed canary model or supporting fallback to `model_version=None`.
* **Fix Implemented:**
  1. In `routes_actions.py` (`get_action_queue` and `get_action_summary`), dynamically resolved `user_model_version` via `canary_router.get_pipeline_for_user(user_id)`.
  2. Added automatic fallback query with `model_version=None` if 0 rows matched the specific version.
  3. Added equivalent fallback in `routes_emails.py` for action count aggregation.
* **Regression Tests Added:**
  - Verified across `test_smart_action_queue.py` and `test_priority_filtering_regression.py`.
* **Retest Result:** **Passed**.
* **Remaining Risk:** None.

---

### BUG-005: SVG Gradient ID Collision Causing Broken Logo (Tiny Dot Defect)
* **Severity:** **P2 — Medium** (Visual defect on presentation surfaces)
* **Status:** `Retest passed`
* **Affected Feature:** Brand Identity & Logo Rendering
* **Affected Files:**
  - `frontend/src/components/brand/MailMindLogo.jsx`
  - `frontend/public/logo.svg`
* **Preconditions:** Multiple instances of `MailMindLogo` rendered simultaneously (e.g., TopBar, Sidebar, Login card).
* **Reproduction Steps:**
  1. Inspect the logo rendered in the header or sidebar.
  2. Observe SVG gradient collisions causing the SVG path to render transparently or as a 1px dot inside a square.
* **Expected Behavior:** MailMind brand logo renders crisply and consistently at all sizes (24px, 28px, 32px, 40px) without distortion or missing gradients.
* **Actual Behavior:** Logo displayed as a tiny, unrecognizable dot in a square.
* **Root Cause:** Duplicate inline SVG `<linearGradient id="...">` definitions collided in the browser's global DOM namespace, breaking gradient fills on sibling logo instances.
* **Fix Implemented:**
  1. Integrated the official vector asset `assets/logo.svg` into `frontend/public/logo.svg`.
  2. Updated `MailMindLogo.jsx` to render via self-contained `<img>` tag with standard SVG fallback, eliminating all global ID collisions.
* **Regression Tests Added:**
  - `npm run build` validated asset bundling.
  - Responsive visual inspection confirmed clean rendering at all scales.
* **Retest Result:** **Passed**.
* **Remaining Risk:** None.

---

### BUG-006: Mobile Header & Viewport Layout Crowding on Small Devices
* **Severity:** **P2 — Medium** (Mobile responsiveness requirement for live demo)
* **Status:** `Retest passed`
* **Affected Feature:** Responsive Navigation (320px–768px viewports)
* **Affected Files:**
  - `frontend/src/styles/index.css`
  - `frontend/src/components/layout/TopBar.jsx`
  - `frontend/src/components/inbox/Inbox.jsx`
* **Preconditions:** Viewport width between 320px (small phone) and 640px (mobile portrait).
* **Reproduction Steps:**
  1. Resize browser viewport to 375×812 or 320×568.
  2. Observe header controls overlapping search bar, clipped email rows, and horizontal scrollbars.
* **Expected Behavior:** Fluid, touch-friendly responsive interface with zero horizontal overflow, two-row mobile header (Row 1: Brand + Nav, Row 2: Search), and minimum 44px touch targets.
* **Actual Behavior:** Overcrowded single-row layout on mobile with cramped search and clipped actions.
* **Fix Implemented:**
  1. Built a dedicated two-row mobile header in `TopBar.jsx` active at `max-width: 640px`.
  2. Added `@media (max-width: 320px)` micro-screen rules with safe padding to eliminate horizontal scrolling.
  3. Ensured touch targets adhere to ≥44×44px standards.
* **Regression Tests Added:**
  - Viewport CSS breakpoint coverage for 320px, 375px, 430px, 768px, 1024px, 1440px.
* **Retest Result:** **Passed**.
* **Remaining Risk:** None.

---

### BUG-007: Unbounded Scan Polling & Stale Response Overwrite
* **Severity:** **P3 — Low** (Client efficiency and network race condition prevention)
* **Status:** `Retest passed`
* **Affected Feature:** Background Scan Status Polling & Asynchronous Request Ordering
* **Affected Files:**
  - `frontend/src/hooks/useEmails.js`
* **Preconditions:** User navigates between priority filter tabs rapidly while background scan is polling.
* **Reproduction Steps:**
  1. Click `P1`, then quickly click `P3`.
  2. If the P1 request finishes after the P3 request, stale P1 results could overwrite active P3 state.
  3. When tab was minimized, scan status polling continued at aggressive 2.5s intervals.
* **Expected Behavior:** Rapid filter changes discard obsolete responses; background polling backs off when tab is in background.
* **Actual Behavior:** Potential race condition and unnecessary network traffic when idle.
* **Fix Implemented:**
  1. Added `activeRequestIdRef` monotonically incrementing on every fetch; older request completions are immediately discarded.
  2. Implemented `document.visibilityState` listener: polling interval slows to 10s when hidden and restores to 2.5s when visible.
  3. Bounded consecutive error retries to 3 with exponential backoff.
* **Regression Tests Added:**
  - Verified in `frontend/src/services/api.test.js` and automated tests.
* **Retest Result:** **Passed**.
* **Remaining Risk:** None.


---

### BUG-008: Infrastructure & Outage Alerts Mistriaged as Low/Promotional P4
* **Severity:** **P1 — High** (Operational emergency suppression)
* **Status:** `Retest passed`
* **Affected Feature:** Priority Inference & Rule Guardrails
* **Affected Files:**
  - `backend/app/ml/refinement.py`
* **Preconditions:** Incoming operational downtime or service suspension alert from monitoring services (e.g., UptimeRobot, Render, AWS, database cluster).
* **Reproduction Steps:**
  1. Receive an email with subject: `Monitor is DOWN: MailMind Production` or `Your services have been suspended`.
  2. Model vectors for server terms without urgent corporate words defaulted to P4.
  3. Email was relegated to low priority noise.
* **Expected Behavior:** Infrastructure downtime alerts must be classified as P1 (Urgent) with action required immediately.
* **Actual Behavior:** Relegated to P4 promotional/routine noise.
* **Fix Implemented:** Added `INFRA_P1_OUTAGE` regex pattern in `refinement.py` matching service downtime, cluster outage, and monitor down alerts, routing directly to P1 with immediate action required.
* **Regression Tests Added:**
  - `tests/test_phase54_deployment_readiness.py`: Verified P1 classification and action status.
* **Retest Result:** **Passed**.
* **Remaining Risk:** None.

---

### BUG-009: Premature Demotion of Statistical P1 Verification Code Emails to P2
* **Severity:** **P2 — Medium** (Classification accuracy regression)
* **Status:** `Retest passed`
* **Affected Feature:** Rule-based Priority Refinement
* **Affected Files:**
  - `backend/app/ml/refinement.py`
* **Preconditions:** Email with subject "Sign-in Verification" and body "Enter the verification code below to continue signing in."
* **Reproduction Steps:**
  1. Statistical model predicts P1 with confidence 0.6341.
  2. Rule 4 (Security Verification) matched "sign-in" in subject and demoted email to P2 because confidence was < 0.75.
* **Expected Behavior:** High-priority sign-in verification and OTP emails classified as P1 must never be demoted to P2 by an authorization audit rule.
* **Actual Behavior:** Demoted from P1 to P2 (`AssertionError: Case C failed: got P2 != P1`).
* **Fix Implemented:** Added `and model_priority != "P1"` guard on Rule 4 in `refinement.py`.
* **Regression Tests Added:**
  - `tests/test_phase34_generalization_and_gmail.py::TestOTPGeneralization::test_unseen_otp_produces_p1_and_action_true[Case C]`.
* **Retest Result:** **Passed**.
* **Remaining Risk:** None.

---

### BUG-010: Forced Incremental Sync Throttled by Rapid Polling
* **Severity:** **P2 — Medium** (API responsiveness failure)
* **Status:** `Retest passed`
* **Affected Feature:** Incremental Incoming Email Synchronization
* **Affected Files:**
  - `backend/app/api/routes_emails.py`
* **Preconditions:** Call `sync_incoming_emails(..., force=True)` immediately following a routine check.
* **Reproduction Steps:**
  1. A routine sync records `last_check = time.time()`.
  2. User or test invokes a forced sync with `force=True`.
  3. Cooldown check `(now - last_check) < cooldown` where `cooldown = 3.0` returned 0 without listing Gmail.
* **Expected Behavior:** Forced sync (`force=True`) explicitly bypasses rate throttling to ensure immediate manual refresh.
* **Actual Behavior:** Forced calls were delayed or dropped.
* **Fix Implemented:** Updated throttle condition to `if not force and (now - last_check) < 15.0: return 0`.
* **Regression Tests Added:**
  - `tests/test_incremental_incoming_sync.py::test_sync_incoming_emails_throttling`.
* **Retest Result:** **Passed**.
* **Remaining Risk:** None.

---

### BUG-011: Frontend Priority Filter Pagination Mismatch & Unhandled Backend Unreachable State
* **Severity:** **P1 — High** (UI state desynchronization & confusion)
* **Status:** `Retest passed`
* **Affected Feature:** Priority Filtering, Pagination Display & Offline Resilience
* **Affected Files:**
  - `frontend/src/App.jsx`
  - `frontend/src/hooks/useEmails.js`
* **Preconditions:** User clicks "Important" filter when backend is offline or before backend responds.
* **Reproduction Steps:**
  1. Stop backend on port 8000.
  2. Click "Important" (P2) filter in sidebar.
  3. Local state filters cached inbox page to 1 email, but header pagination reads stale `ALL` pagination (`1-1 of 18,108`).
  4. Clicking "Load more emails" fails with unhandled toast.
* **Expected Behavior:** Pagination numbers accurately reflect filtered slice count; if backend is unreachable, UI prominently displays a non-destructive offline warning banner with a "Retry Connection" action.
* **Actual Behavior:** Displayed misleading `1-1 of 18,108` and swallowed connection error without warning banner.
* **Fix Implemented:**
  1. Recalculated `totalEmails`, `startNum`, `endNum`, and `hasNextPage` in `App.jsx` based on whether priority is synchronized with the backend.
  2. Added prominent warning banner in `App.jsx` when `emailsHook.isOfflineMode` is active with a direct "Retry Connection" handler.
* **Regression Tests Added:**
  - `frontend/src/utils/formatting.test.js` & Vite build verification.
* **Retest Result:** **Passed**.
* **Remaining Risk:** None.

---

### BUG-012: OAuth Tokens & Client Credentials Stored in Plaintext JSON at Rest
* **Severity:** **P1 — High** (Security & credential hygiene)
* **Status:** `Retest passed`
* **Affected Feature:** Session Persistence & Credential Management
* **Affected Files:**
  - `backend/app/core/session.py`
* **Preconditions:** Authenticated Google OAuth session persisted to disk.
* **Reproduction Steps:**
  1. Inspect `google_auth/sessions/<session_id>.json`.
  2. Observe plaintext `refresh_token`, `client_secret`, and `token`.
* **Expected Behavior:** Sensitive tokens must be encrypted symmetrically at rest on disk with backward-compatible loading of existing plaintext sessions.
* **Actual Behavior:** Stored in unencrypted JSON.
* **Fix Implemented:** Implemented symmetric encryption at rest using `cryptography.fernet.Fernet` derived from `SESSION_SECRET` with envelope `{"version": "enc_v1", "encrypted": "..."}` and automatic plaintext fallback for existing sessions.
* **Regression Tests Added:**
  - Verification script confirming encryption at rest and seamless retrieval of existing sessions.
* **Retest Result:** **Passed**.
* **Remaining Risk:** None.

---

### BUG-013: Browser `localStorage` `QuotaExceededError` on Large Mailbox Sync
* **Severity:** **P1 — High** (Client storage failure and console noise)
* **Status:** `Retest passed`
* **Affected Feature:** Local Account Cache & Client Storage Persistence
* **Affected Files:**
  - `frontend/src/hooks/useEmails.js`
* **Preconditions:** Active mailbox synchronization loading 100+ emails with long text and HTML bodies.
* **Reproduction Steps:**
  1. Synchronize or load mailbox for user with 100+ cached messages.
  2. `saveAccountCache` attempts `localStorage.setItem('mailmind_cache_<uid>', JSON.stringify(...))`.
  3. Console throws uncaught exception: `Failed to save account cache: QuotaExceededError: Failed to execute 'setItem' on 'Storage': Setting the value exceeded the quota.`
* **Expected Behavior:** Fast local instant-load cache stored in browser `localStorage` remains strictly within browser storage quotas (<5MB total browser limit, typically <50KB per account) without throwing unhandled exceptions.
* **Actual Behavior:** Caching raw full-length `body` and `body_html` strings exceeded the 5MB quota, failing every sync write.
* **Root Cause:** Raw emails serialized into cache contained complete multi-kilobyte HTML bodies, causing a 100-email cache payload to exceed 4MB+.
* **Fix Implemented:**
  1. Built `sanitizeEmailForCache` and `sanitizeActionQueueForCache`, stripping large `body` and `body_html` fields from cached previews (cutting storage footprint from 4+ MB to < 8 KB, a 99% reduction).
  2. Wrapped `localStorage.setItem` in a defensive `try/catch` with automated stale-cache eviction (`mailmind_cache_` prefix cleanup) and an ultra-compact (< 1 KB) fallback containing only summary stats and pagination state.
* **Regression Tests Added:**
  - Verified in `frontend/src/utils/formatting.test.js` and local browser execution with 0 console errors.
* **Retest Result:** **Passed**.
* **Remaining Risk:** None.

