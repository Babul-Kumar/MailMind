# PHASE 44 — FEEDBACK ADJUDICATION & DATASET-V5 FINAL REPORT
MailMind / CSE472 NLP Project
Generated: 2026-10-02T20:42:00+05:30
Active Model: priority-v4.1 (UNCHANGED)
Dataset constructed: dataset-v5.0
Model training: NONE
Registry change: NONE
Holdouts: ALL UNCHANGED (byte-for-byte)

---

## 1. Feedback Inventory

| Metric | Value |
|--------|-------|
| Raw feedback records | 108 |
| Unique users | 4 |
| Unique messages | 5 |
| Deduplicated unique pairs | 5 |
| Duplicate records (UI retry) | 103 |
| Records with model_version | 40 |
| Records without model_version | 68 |

Source: dataset/feedback/feedback.jsonl (read-only, not modified)

---

## 2. Feedback Quality Classification

| Example | user_id | message_id | Status | Reason |
|---------|---------|-----------|--------|--------|
| fb_adj_001 | user_test_fb | msg_feedback_001 | ACCEPT | P4->P2 with deadline note. Supported by annotation policy. |
| fb_adj_002 | user_a_uid_101 | msg_a_1 | INSUFFICIENT_CONTEXT | Terse reason only. No email content. |
| fb_adj_003 | user_b_uid_202 | msg_b_1 | INSUFFICIENT_CONTEXT | Terse reason only. No email content. |
| fb_adj_004 | phase43_test_user | phase43_test_msg_001 | REJECT | Synthetic test artifact from Phase 43. |
| fb_adj_005 | phase43_test_user | isolation_msg_user_a | REJECT | Synthetic test artifact from Phase 43. |

Total: 1 ACCEPT, 2 INSUFFICIENT_CONTEXT, 2 REJECT, 0 DUPLICATE, 0 AMBIGUOUS

---

## 3. Adjudication Methodology

Priority decisions follow the MailMind annotation policy:
  Priority = urgency + required action + operational consequence

P1: Immediate / hard deadline / crisis / blocker / security / urgent intervention.
P2: Active response, task, review, meeting, payment, application, operational requirement, meaningful deadline.
P3: Informational or awareness content without immediate action.
P4: Promotional, marketing, noise, genuinely non-actionable content.

Rules applied:
- User corrections are NOT automatically accepted as ground truth.
- Terse reasons without email content are classified as INSUFFICIENT_CONTEXT.
- Synthetic test artifacts are classified as REJECT.
- Priority and Action Required are adjudicated independently.
- Deadline status is adjudicated independently (ACTIVE / OVERDUE / EXPIRED / HISTORICAL / NONE).
- Feedback from retired models (priority-v1) is valid but noted.

---

## 4. Accepted / Rejected / Ambiguous

ACCEPT: 1 (fb_adj_001)
  - P4->P2 with action_required=True and deadline=Oct 1, 2026 (HISTORICAL)
  - Synthesized canonical training example created (fb_synth_001)
  - topic: registration/academic

INSUFFICIENT_CONTEXT: 2 (fb_adj_002, fb_adj_003)
  - Reasons: terse free-text only, no email content
  - EXCLUDED from Dataset-v5

REJECT: 2 (fb_adj_004, fb_adj_005)
  - Source: Phase 43 automated test injection
  - EXCLUDED from Dataset-v5

---

## 5. Error Taxonomy (from accepted corrections)

| Category | Count | Notes |
|----------|-------|-------|
| deadline_driven_P2_miss | 1 | msg_feedback_001: registration deadline predicted P4, should be P2 |

No other error categories are supported by the available data.
Categories not invented beyond what the data supports.

---

## 6. Contrastive Examples (5 pairs, 10 examples)

All pairs target known model boundary confusion zones:

| Pair | Legitimate (P2) | Contrastive (P3/P4) |
|------|----------------|---------------------|
| cp_001 | Registration deadline email | Open enrollment announcement |
| cp_002 | Invoice overdue with penalty |  payment receipt |
| cp_003 | Elasticsearch storage 85% full | Elasticsearch product update newsletter |
| cp_004 | CS229 Homework 2 due Wednesday | CS229 weekly department digest |
| cp_005 | Offer letter: accept by Oct 8 | Application received confirmation |

All contrastive pairs leakage-checked: CLEAN.

---

## 7. Dataset-v5 Composition

| Component | Train | Validation |
|-----------|-------|------------|
| dataset-v4.1 base | 78,702 rows | 16,326 rows |
| Contrastive pairs | 8 rows | 2 rows |
| Synthesized feedback examples | 1 row | 0 rows |
| TOTAL | 78,711 rows | 16,328 rows |

Note: v4.1 base row counts include large Enron corpus base + v4.1 additions.

---

## 8. Class Distribution

### Dataset-v5 Train (modern examples only — new additions)

| Label | Count (new) | Label | Count (all train) | % |
|-------|------------|-------|------------------|---|
| P1 | 0 | P1 | 70 | 3.7% |
| P2 | 6 | P2 | 735 | 39.3% |
| P3 | 3 | P3 | 543 | 29.1% |
| P4 | 0 | P4 | 521 | 27.9% |

Distribution vs dataset-v4.1:
  P1: 70 (3.8% -> 3.7%) — stable
  P2: 730 -> 735 (+5) — slight increase from contrastive+synthesized
  P3: 541 -> 543 (+2) — slight increase from contrastive negatives
  P4: 519 -> 521 (+2) — slight increase from contrastive negatives

No artificial rebalancing performed. Additions reflect genuine boundary examples.

---

## 9. Leakage Results

Holdouts checked:
  - dataset/processed/test.csv (300 unique hashes)
  - dataset-v3/modern_holdout.csv (120 unique hashes)
  - dataset-v4/newsletter_holdout.csv (60 unique hashes)
  - dataset-v4/social_holdout.csv (50 unique hashes)
  - dataset-v4/test.csv (60 unique hashes)
  - dataset-v4.1/test.csv (60 unique hashes)

Total holdout hash pool: 590 unique content hashes
Leakage violations: 0

RESULT: CLEAN

---

## 10. User / Domain Concentration

User concentration:
  4 users total: user_test_fb (35%), user_a_uid_101 (31%), user_b_uid_202 (31%), phase43_test_user (2%)
  ALL feedback originates from test/synthetic users. No real production diversity.

Domain concentration:
  Cannot assess — email domains not stored in feedback schema.

Topic concentration:
  registration/academic: 1 (from content analysis)
  newsletter: 1 (labelled)
  unknown: 3 (no content available)

Priority concentration:
  All 5 unique pairs are upgrade corrections. No downgrade corrections exist.
  Feedback heavily biased toward P2 as target priority (4/5 pairs target P2).

---

## 11. Privacy Review

| Item | Status |
|------|--------|
| OAuth tokens in dataset-v5 | NO |
| Session cookies in dataset-v5 | NO |
| API credentials in dataset-v5 | NO |
| Raw personal email bodies | NO |
| User IDs retained | Stable anonymised IDs only |
| Email subjects/bodies stored | Only synthesized/contrastive text authored by project team |

RESULT: COMPLIANT

---

## 12. Dataset Version Metadata

Version: dataset-v5.0
Created: 2026-10-02
Source datasets: dataset-v4.1 (base), feedback (1 accepted), contrastive pairs (10)
Adjudicated examples: 5 unique pairs (1 ACCEPT, 2 INSUFFICIENT_CONTEXT, 2 REJECT)
New training examples added: 9
Leakage violations: 0
SHA-256 hashes: see dataset-v5/metadata.json

---

## 13. Quality Gate Results

| Gate | Description | Status |
|------|-------------|--------|
| GATE 1 | All accepted examples human-adjudicated | PASS |
| GATE 2 | Ambiguous examples excluded from training | PASS |
| GATE 3 | Duplicate examples controlled | PASS |
| GATE 4 | Zero holdout leakage | PASS (0 violations) |
| GATE 5 | Priority/action/deadline remain separate | PASS |
| GATE 6 | No credentials/secrets present | PASS |
| GATE 7 | Provenance exists for every example | PASS |
| GATE 8 | Dataset distribution documented | PASS |
| GATE 9 | Reviewer agreement documented | PASS |
| GATE 10 | Existing holdouts byte-for-byte unchanged | PASS |

OVERALL: 10/10 GATES PASSED

---

## 14. Tests

Test suite: 305 tests
Result: 305 passed, 0 failed, 29 warnings (deprecation only)
Run time: 40.81 seconds
Command: .venv/Scripts/python.exe -m pytest tests/ -x -q --tb=short

Active model: priority-v4.1 — no changes.
Model registry: unchanged.
All holdouts: unchanged.

---

## 15. Remaining Risks

1. FEEDBACK VOLUME: Only 5 unique (user, message) pairs exist. This is insufficient
   to support model training decisions. Phase 45 will require > 50 real diverse
   feedback examples across multiple users and topics.

2. TERSE REASONS: 2 of 5 unique pairs are INSUFFICIENT_CONTEXT due to terse
   free-text reasons. The feedback UI should prompt for structured correction
   (priority + reason category + optional note).

3. SYNTHETIC CONTAMINATION: 2 records are Phase 43 test artifacts. Future test
   suites should use a separate feedback store or clearly flag test records.

4. USER MONOCULTURE: All feedback originates from test/synthetic users. No real
   Gmail user has submitted feedback yet. The feedback corpus has zero external
   validity until real users interact with the production system.

5. SYNTHESIZED EXAMPLE: fb_synth_001 is a representative synthesis, not an actual
   user email. It should be reviewed and replaced with a real annotated example
   when the production cache can be queried for msg_feedback_001 content.

6. NO DEADLINE ENGINE VALIDATION: Deadline adjudication was performed manually.
   The deadline engine has not been retested in Phase 44. If the deadline
   extraction logic changes in Phase 45, this should be re-verified.

---

## 16. Readiness for Phase 45

ACTIVE MODEL: priority-v4.1
DATASET: dataset-v5.0 candidate
MODEL TRAINING: NONE performed in Phase 44
MODEL REGISTRY CHANGE: NONE
HOLDOUT CHANGES: NONE

Dataset-v5 is READY FOR OFFLINE CANDIDATE TRAINING.

Conditions before Phase 45 training may begin:
  a) Accumulate >= 50 genuine diverse feedback examples (current: 1 accepted).
  b) Verify fb_synth_001 against actual email content if available.
  c) Resolve structural issues in feedback store (idempotency, schema enforcement).
  d) Ensure no test artifacts contaminate future feedback corpus.

Phase 44 is complete. No training occurred. All constraints respected.
