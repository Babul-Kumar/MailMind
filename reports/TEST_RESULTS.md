# MailMind — Test Execution Results & Regression Evidence

This document records the actual commands executed, test totals, pass/fail counts, execution times, build metrics, and sanitized logs during the senior QA audit.

---

## 1. Test Execution Summary

| Test Suite / Target | Framework / Tool | Tests Run | Passed | Failed | Skipped | Status |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Complete Backend Suite** | `pytest 9.1.1 (Python 3.11)` | 652 | 650 | 0 | 2* | **PASS** |
| **Priority Filtering Regression** | `unittest` | 9 | 9 | 0 | 0 | **PASS** |
| **Smart Action Queue Suite** | `unittest` | 34 | 34 | 0 | 0 | **PASS** |
| **OAuth Handoff & Deployment** | `unittest` | 31 | 31 | 0 | 0 | **PASS** |
| **Frontend Utilities & API Client** | `Node.js test runner` | 14 | 14 | 0 | 0 | **PASS** |
| **Frontend Production Build** | `Vite 5.4.21` | 1613 modules | 1613 | 0 | 0 | **PASS** |
| **Model Invariant Integrity** | `hashlib SHA-256` | 1 | 1 | 0 | 0 | **PASS** |
| **Server Runtime Health** | `FastAPI /api/health` | 1 | 1 | 0 | 0 | **PASS** |

*\*Note: 2 skipped tests in `tests/test_gmail_pipeline.py` correspond to developer integration tests requiring physical offline Google OAuth tokens (`token.json`), which gracefully skip when no physical developer token exists.*

---

## 2. Model Hash Verification Log

* **Command:**
  ```powershell
  python -c "import hashlib; h = hashlib.sha256(open('dataset/models/priority-v5.1-candidate/model.joblib', 'rb').read()).hexdigest(); print('Model SHA-256:', h); assert h == '8524ad73965859ee022f1271caee0040928e7805ab7d32c49b2f26e994f98c06'"
  ```
* **Output:**
  ```text
  Model SHA-256: 8524ad73965859ee022f1271caee0040928e7805ab7d32c49b2f26e994f98c06
  ```
* **Verification:** Baseline SHA-256 hash verified intact before and after all changes. Zero retraining or feature modification occurred.

---

## 3. Full Backend Pytest Suite Run

* **Command:**
  ```powershell
  python -m pytest tests/
  ```
* **Execution Time:** `43.48s`
* **Output Log:**
  ```text
  ============================= test session starts =============================
  platform win32 -- Python 3.11.9, pytest-9.1.1, pluggy-1.6.0
  rootdir: C:\Users\babul\Desktop\cse472
  plugins: anyio-4.14.2, hydra-core-1.3.2, typeguard-4.6.0
  collected 652 items

  tests\test_concurrency.py .                                              [  0%]
  tests\test_dashboard_api.py ..........                                   [  1%]
  tests\test_deadline_cases.py .......................                     [  5%]
  tests\test_environment_separation.py ..........                          [  6%]
  tests\test_gmail_pipeline.py ss.........                                 [  8%]
  tests\test_model_lifecycle.py ........                                   [  9%]
  tests\test_multiuser_auth.py ...........                                 [ 11%]
  tests\test_oauth_handoff.py ..................                           [ 14%]
  tests\test_phase28_hardening.py ..........                               [ 15%]
  tests\test_phase31_multiuser_e2e.py .......                              [ 16%]
  tests\test_phase32_complete_mailbox.py .........................         [ 20%]
  tests\test_phase33_otp_verification.py ................................. [ 25%]
  ..............................................                           [ 32%]
  tests\test_phase34_generalization_and_gmail.py ......................... [ 36%]
  ......                                                                   [ 37%]
  tests\test_phase37_action_deadline.py ..........................         [ 41%]
  tests\test_phase37_threads.py ........                                   [ 42%]
  tests\test_phase39_v4_candidate.py .............                         [ 44%]
  tests\test_phase40_v4_1_candidate.py .................                   [ 47%]
  tests\test_phase43_monitoring.py ...............                         [ 49%]
  tests\test_phase45_dataset_v5_audit.py ..............                    [ 51%]
  tests\test_phase46_v5_candidate.py ................                      [ 54%]
  tests\test_phase47_v5_1_remediation.py ........................          [ 57%]
  tests\test_phase48_live_shadow.py .........................              [ 61%]
  tests\test_phase49_canary.py .........................                   [ 65%]
  tests\test_phase50_production_promotion.py ....................          [ 68%]
  tests\test_phase51_monitoring.py ....................................... [ 74%]
  ...........                                                              [ 76%]
  tests\test_phase52_adjudication.py ............................          [ 80%]
  tests\test_phase53_production_feedback.py ........................       [ 84%]
  tests\test_phase54_deployment_readiness.py ............................. [ 88%]
  ..                                                                       [ 88%]
  tests\test_priority_filtering_regression.py .........                    [ 90%]
  tests\test_priority_refinement.py ..........                             [ 91%]
  tests\test_render_deployment_readiness.py .............                  [ 93%]
  tests\test_smart_action_queue.py ..................................      [ 99%]
  tests\test_ui_refinement.py ......                                       [100%]

  ================ 650 passed, 2 skipped, 59 warnings in 43.48s =================
  ```

---

## 4. Priority Filtering Regression Test Suite

* **Command:**
  ```powershell
  python -m unittest tests/test_priority_filtering_regression.py
  ```
* **Execution Time:** `2.97s`
* **Test Case Details:**
  1. `test_01_p1_filter_strict_isolation`: P1 filter returns strictly P1 messages, 0 P2/P3/P4. (PASS)
  2. `test_02_p2_filter_strict_isolation`: P2 filter returns strictly P2 messages, 0 P1/P3/P4. (PASS)
  3. `test_03_p3_filter_strict_isolation`: P3 filter returns strictly P3 messages, 0 P1/P2/P4. (PASS)
  4. `test_04_p4_filter_strict_isolation`: P4 filter returns strictly P4 messages, 0 P1/P2/P3. (PASS)
  5. `test_05_all_mail_returns_all_records`: All Mail returns complete expected records. (PASS)
  6. `test_06_needs_attention_preserves_p3_priority`: Needs Attention surfaces actionable items while strictly preserving true P3 priority badge. (PASS)
  7. `test_07_action_state_enrichment_and_isolation`: User A action states attached and isolated from User B. (PASS)
  8. `test_08_search_and_priority_composition`: Search composed with priority filter returns exact intersection. (PASS)
  9. `test_09_pagination_consistency`: Slicing boundaries, total count, and page counts agree. (PASS)
* **Result:** `Ran 9 tests in 2.973s — OK`.

---

## 5. Smart Action Queue Suite Run

* **Command:**
  ```powershell
  python -m unittest tests/test_smart_action_queue.py
  ```
* **Execution Time:** `3.31s`
* **Result:** `Ran 34 tests in 3.313s — OK` (All 34 passed).

---

## 6. Frontend Automated Unit & Formatting Tests

* **Command:**
  ```powershell
  npm test (in frontend/)
  ```
* **Execution Time:** `15.17s`
* **Output Log:**
  ```text
  > mailmind@2.0.0 test
  > node --test src/utils/formatting.test.js src/services/api.test.js

  ✔ 1. getApiBaseUrl returns empty string or dev fallback when unset in non-production (1.6616ms)
  ✔ 2. apiFetch sets credentials to include (0.9785ms)
  ✔ 3. apiFetch merges json body and content-type header (0.4258ms)
  ✔ 4. fetchAuthExchange posts handoff code to /api/auth/exchange (4.7653ms)
  ✔ 1. future deadline (general) (7.3047ms)
  ✔ 2. deadline today (0.8293ms)
  ✔ 3. past deadline (general overdue) (0.4091ms)
  ✔ 4. date-only future deadline (0.3508ms)
  ✔ 5. date-only past deadline (0.6295ms)
  ✔ 6. datetime future (0.3201ms)
  ✔ 7. datetime past (0.2722ms)
  ✔ 8. historical deadline (date-only) (0.2764ms)
  ✔ 9. historical deadline (datetime) (0.4603ms)
  ✔ 10. cleanSenderName cleans display name, quotes, and addresses (0.589ms)
  ℹ tests 14
  ℹ suites 0
  ℹ pass 14
  ℹ fail 0
  ℹ cancelled 0
  ℹ skipped 0
  ℹ todo 0
  ℹ duration_ms 15174.3663
  ```

---

## 7. Production Frontend Bundle Build

* **Command:**
  ```powershell
  npm run build (in frontend/)
  ```
* **Execution Time:** `4.34s`
* **Output Log:**
  ```text
  > mailmind@2.0.0 build
  > vite build && node -e "import fs from 'node:fs'; fs.copyFileSync('dist/index.html', 'dist/404.html');"

  vite v5.4.21 building for production...
  transforming...
  ✓ 1613 modules transformed.
  rendering chunks...
  computing gzip size...
  dist/index.html                   0.91 kB │ gzip:  0.48 kB
  dist/assets/index-DqU7T20P.css   21.02 kB │ gzip:  4.67 kB
  dist/assets/index-CrVXv4aR.js   361.33 kB │ gzip: 94.50 kB
  ✓ built in 4.34s
  ```

---

## 8. Server Runtime Health Checks

* **Backend Health Check (`GET http://127.0.0.1:8000/api/health`):**
  ```json
  {
    "status": "healthy",
    "service": "AI Email Priority Dashboard",
    "model_loaded": true,
    "timestamp": "2026-10-21T17:26:41.575177+00:00"
  }
  ```
  Status: **200 OK**.
* **Frontend Dev Server (`GET http://localhost:5173`):**
  Status: **200 OK**.
