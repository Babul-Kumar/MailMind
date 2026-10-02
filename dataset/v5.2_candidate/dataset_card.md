# Dataset-v5.2 Candidate

**Status:** CANDIDATE — NOT TRAINED — NOT PRODUCTION

**Phase:** Phase 52 — Production Feedback, Human Adjudication & Dataset-v5.2 Candidate

**Created:** 2026-10-02T22:16:44Z

**Parent dataset:** dataset-v5.1

---

## Overview

This is a CANDIDATE dataset assembled from human-adjudicated production feedback.

It is NOT used for training. It is NOT in production.

The candidate pool contains **0** accepted adjudicated examples.

> **Evidence Collecting** — Insufficient adjudicated production feedback. This candidate is empty by design. DO NOT fabricate data.

---

## Class Distribution (Candidate Additions)

| Priority | Candidate Count | v5.1 Train Baseline |
|----------|-----------------|---------------------|
| P1 | 0 | 70 |
| P2 | 0 | 735 |
| P3 | 0 | 552 |
| P4 | 0 | 523 |
| **Total** | **0** | **1880** |

---

## Provenance

All candidate examples come from:
1. **Production feedback** — user corrections via `POST /api/feedback`
2. **Human adjudication** — explicit reviewer acceptance via adjudication workflow
3. **Leakage audit** — verified zero overlap with frozen holdouts

Provenance chain per example:
```
user_id + message_id → feedback_id → adjudication_id → corrected_priority
```

## Governance

- priority-v5.1 remained the active production model during Phase 52
- priority-v4.1 remained the rollback baseline
- No automated retraining occurred during Phase 52
- No automated model promotion occurred during Phase 52
- No fabricated data was added
- All candidate examples have explicit human adjudication records

## Leakage Audit

- Frozen files checked: test.csv, train.csv, v5.1_train.csv, v5.1_validation.csv, v5.1_boundary_holdout.csv
- Leakage count: 0
- Leakage free: ✅ YES

---

## Required Pipeline Before Training

```
Accepted candidates (this file)
        ↓
Human review of all provenance.csv entries
        ↓
Merge with dataset-v5.1 (offline, controlled)
        ↓
Leakage audit (re-run on merged set)
        ↓
Offline training
        ↓
Candidate model evaluation (holdouts)
        ↓
Shadow deployment
        ↓
Canary deployment
        ↓
Explicit promotion gate
```

**FORBIDDEN:** Automatic training from this candidate dataset.
