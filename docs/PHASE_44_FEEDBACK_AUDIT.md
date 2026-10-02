# PHASE 44 — FEEDBACK AUDIT REPORT
MailMind / CSE472 NLP Project
Generated: 2026-10-02
Active Model: priority-v4.1 (unchanged)
Feedback store: dataset/feedback/feedback.jsonl

## 1. Raw Inventory

| Metric | Value |
|--------|-------|
| Total raw records | 108 |
| Unique users | 4 |
| Unique messages | 5 |
| Feedback type labelled | 5 records (priority_wrong) |
| Feedback type unlabelled | 103 records (none) |

NOTE: 103 of 108 raw records are exact duplicates caused by a UI retry loop.

## 2. Raw Records by User

| user_id | Records | Distinct messages |
|---------|---------|-------------------|
| user_test_fb | 38 | 1 (msg_feedback_001) |
| user_a_uid_101 | 34 | 1 (msg_a_1) |
| user_b_uid_202 | 34 | 1 (msg_b_1) |
| phase43_test_user | 2 | 2 (phase43_test_msg_001, isolation_msg_user_a) |

User concentration: 100% concentrated in 4 users. Not representative.

## 3. Unique (User, Message) Pairs After Deduplication

| # | user_id | message_id | original->corrected | model_version | raw_count |
|---|---------|-----------|---------------------|---------------|-----------|
| A | user_test_fb | msg_feedback_001 | P4->P2 | priority-v1 | 38 |
| B | user_a_uid_101 | msg_a_1 | P3->P1 | (none) | 34 |
| C | user_b_uid_202 | msg_b_1 | P4->P2 | (none) | 34 |
| D | phase43_test_user | phase43_test_msg_001 | P3->P2 | priority-v4.1 | 1 |
| E | phase43_test_user | isolation_msg_user_a | P4->P2 | priority-v4.1 | 1 |

## 4. Feedback by Model Version

| model_version | Records (raw) | Unique pairs |
|---------------|---------------|--------------|
| priority-v1 (retired) | 38 | 1 |
| priority-v4.1 (production) | 2 | 2 |
| (none) unrecorded | 68 | 2 |

## 5. Priority Direction (all upgrades, no downgrades)

P4->P2: 3 pairs (A, C, E)
P3->P1: 1 pair (B)
P3->P2: 1 pair (D)

## 6. Action Required Corrections

Pair A: False -> True
All others: unrecorded or unchanged.

## 7. Deadline Corrections

Pair A: Oct 1, 2026 (HISTORICAL)
Pairs B-E: None.

## 8. Structural Issues Found

1. UI retry duplication: 103/108 records are duplicates.
2. Missing model_version: 68 records lack model_version field.
3. Missing email content: No subject/body stored in feedback store.
4. Synthetic test artifacts: Records D and E from Phase 43 test injection.
5. No action_required baseline for pairs B and C.

## 9. Recommendations

1. Add idempotency key to feedback endpoint.
2. Enforce model_version as required field.
3. Cache email metadata at feedback submission time.
4. Label synthetic test feedback with test_artifact=true flag.
5. Expand user base: target >= 20 distinct users before Phase 45 training.

Feedback records unmodified. This is a read-only audit.
