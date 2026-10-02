# PHASE 45 — DATASET-V5 TRAINING READINESS & PROVENANCE AUDIT REPORT

**MailMind · CSE472 Machine Learning & NLP Project**  
**Audit Timestamp:** 2026-10-02T23:35:00+05:30  
**Audit Status:** COMPLETE  
**Audited Dataset:** `dataset-v5` (`train.csv`, `validation.csv`, `metadata.json`, `adjudication_queue.json`, `contrastive_pairs.json`)  
**Active Production Model:** `priority-v4.1` (UNCHANGED, UNTOUCHED)  
**Final Decision:** **`READY FOR OFFLINE TRAINING`**

---

## Executive Summary

Dataset-v5 was constructed during Phase 44 from the verified `dataset-v4.1` foundation, augmented with human-adjudicated production feedback and 10 human-authored contrastive boundary pairs. This Phase 45 audit independently inspected all 78,711 training text lines (1,869 logical RFC 4180 CSV records) and 16,328 validation text lines (429 logical CSV records) across 17 structured audit dimensions.

**Key Findings:**
1. **Physical Lines vs Logical Records:** The reported 78,711 training rows and 16,328 validation rows represent physical newline counts in the CSV files caused by multiline raw email bodies from the historical Enron email corpus. In terms of discrete, logical email examples, Dataset-v5 contains **1,869 training records** and **429 validation records** (2,298 total).
2. **Label Provenance:** 100% of rows trace to known, documented origins. 2,287 examples (99.52%) are inherited from previous verified datasets (`dataset-v4.1`), 10 examples (0.43%) are human-authored contrastive pairs, and 1 example (0.04%) is a canonical synthesized representation of accepted production feedback (`fb_adj_001`).
3. **Leakage Audit:** **ZERO** exact hash overlaps and **ZERO** normalized content hash overlaps between train and validation. **ZERO** leakage across all 650 frozen holdout examples in `test.csv`, `modern_holdout.csv`, `newsletter_holdout.csv`, `social_holdout.csv`, `dataset-v4/test.csv`, and `dataset-v4.1/test.csv`.
4. **Thread & Conversation Integrity:** **ZERO** thread ID leakage across splits. The 10 new Phase 44 examples exhibit **0** cross-split subject overlap. 30 subject overlaps exist in the inherited historical Enron baseline (differing dates of automated reports/newsletters, such as daily reports or travel digests), with 19 pairs having Jaccard similarity > 0.9.
5. **Accidental Relabeling:** **ZERO** label shifts detected. 100% of inherited rows from `dataset-v4.1` retained their exact prior priority label.
6. **Training Readiness Gates:** **13/13 Gates Passed**.
7. **Strict Compliance:** Absolutely **NO model training** was performed. Active production model `priority-v4.1` and model registry remain completely intact.

---

## 1. Dataset Inventory

### 1.1 Row and Line Counts

| Split | Logical CSV Records | Physical Text Lines | Physical Data Lines (excl. Header) | File Size |
|---|:---:|:---:|:---:|:---:|
| **Train (`train.csv`)** | **1,869** | 78,712 | **78,711** | 3,814,712 bytes (3.81 MB) |
| **Validation (`validation.csv`)** | **429** | 16,329 | **16,328** | 762,793 bytes (762 KB) |
| **Combined Dataset-v5** | **2,298** | 95,041 | **95,039** | 4,577,505 bytes (4.58 MB) |

### 1.2 Class Distribution (Logical Records)

| Priority Class | Train Count | Train % | Val Count | Val % | Combined Count | Combined % |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **P1 (Urgent / Immediate)** | 70 | 3.7% | 11 | 2.6% | 81 | 3.5% |
| **P2 (Operational / Action)** | 735 | 39.3% | 164 | 38.2% | 899 | 39.1% |
| **P3 (Informational / Passive)** | 543 | 29.1% | 135 | 31.5% | 678 | 29.5% |
| **P4 (Promotional / Routine)** | 521 | 27.9% | 119 | 27.7% | 640 | 27.9% |
| **Total** | **1,869** | **100.0%** | **429** | **100.0%** | **2,298** | **100.0%** |

### 1.3 Source Datasets and Provenance Summary

| Source Dataset Component | Train Records | Val Records | Total Records | Role in Dataset-v5 |
|---|:---:|:---:|:---:|---|
| `dataset-v4.1` base | 1,860 | 427 | 2,287 | Base foundation (Enron Gold 2,000 + Modern curated + v4.1 boundary repair) |
| `phase44_contrastive` | 8 | 2 | 10 | Human-authored contrastive boundary pairs (cp_001–cp_005) |
| `feedback_synthesized` | 1 | 0 | 1 | Synthesized canonical representation of accepted feedback `fb_adj_001` |
| **Total Dataset-v5** | **1,869** | **429** | **2,298** | **Full Candidate Dataset** |

---

## 2. Label Provenance

Every single row in `dataset-v5` was mapped to one of the six formal provenance categories:

### 2.1 Provenance Categorization Breakdown

| Category | Description | Train | Val | Total | % of Dataset |
|---|---|:---:|:---:|:---:|:---:|
| **A. HUMAN_REVIEW** | Verified examples from historical Gold 2,000 human review pool | 1,365 | 296 | 1,661 | 72.28% |
| **B. HUMAN_ADJUDICATED** | Disagreements resolved via formal 2-adjudicator consensus in Gold 2,000 | 35 | 4 | 39 | 1.70% |
| **C. PREVIOUS_GOLD_DATASET** | Modern curated examples introduced in v3/v4 (OTP, newsletters, notifications) | 349 | 88 | 437 | 19.02% |
| **D. SYNTHETIC/CURATED** | Boundary repair pairs (v4.1) + Phase 44 contrastive pairs (10 examples) | 119 | 41 | 160 | 6.96% |
| **E. PRODUCTION_FEEDBACK** | Canonical example derived from accepted user feedback (`fb_synth_001`) | 1 | 0 | 1 | 0.04% |
| **F. OTHER** | Unverified or machine-generated pseudo-labels | 0 | 0 | 0 | 0.00% |
| **Total** | | **1,869** | **429** | **2,298** | **100.00%** |

### 2.2 Answers to Critical Provenance Questions

1. **How many NEW independently human-adjudicated examples actually entered Dataset-v5?**
   - **11 new examples** entered Dataset-v5 in Phase 44:
     - 1 canonical synthesized example (`fb_synth_001`) from accepted feedback `fb_adj_001` (reviewed and adjudicated by `phase44_adjudicator`).
     - 10 human-authored contrastive boundary examples (5 pairs, cp_001a through cp_005b).
     - Breakdown by split: **9 new train rows**, **2 new validation rows**.
2. **How many rows are inherited from previous datasets?**
   - **2,287 examples** (99.52% of logical records; 1,860 train + 427 val) are inherited directly from `dataset-v4.1`.
   - Tracing further back: 1,700 are directly descended from the original Gold 2,000 human-labeled corpus (`dataset/processed/train.csv` and `validation.csv`), 437 from modern curated v3/v4 expansions, and 150 from v4.1 boundary review.
3. **How many are synthetic/contrastive?**
   - Across the entire dataset, **161 examples** (7.01%) are curated/synthetic:
     - Phase 44 contrastive pairs: **10 examples** (8 train, 2 val).
     - Phase 44 feedback synthesis: **1 example** (train).
     - Phase 40/41 boundary repair pairs: **150 examples** (111 train, 39 val).
   - Crucially, synthetic examples represent only **7.01%** of the dataset and do not dominate the corpus.
4. **How many originated from the single accepted Phase 44 feedback?**
   - **Exactly 1 example**: `fb_synth_001` (added to train, label P2, topic `registration/academic`, `action_required=True`, deadline `Oct 1, 2026`).

---

## 3. Train / Validation Split Integrity

### 3.1 Content Deduplication

All examples were converted to both raw content hashes (`sha256(subject|body)`) and normalized content hashes (`sha256(norm_subject|norm_body)` with punctuation removed, whitespace collapsed, and lowercased).

| Integrity Check | Train | Validation | Cross-Split | Result | Status |
|---|:---:|:---:|:---:|:---:|:---:|
| **Exact Content Hash Collisions** | 0 | 0 | **0** | Clean partition | **PASS** |
| **Normalized Content Hash Collisions** | 0 | 0 | **0** | Clean partition | **PASS** |
| **Subject + Body Exact Matches** | 0 | 0 | **0** | Clean partition | **PASS** |
| **Message ID Cross-Split Overlap** | N/A | N/A | **0** | No overlapping IDs | **PASS** |

Both train and validation splits are 100% free of cross-split duplicate content.

---

## 4. Holdout Leakage Audit

Dataset-v5 was audited against all frozen historical and modern holdout sets.

| Holdout Dataset | File Path | Total Rows | Hash Pool Size | Matches in Train | Matches in Val | Status |
|---|---|:---:|:---:|:---:|:---:|:---:|
| **Historical Test** | `dataset/processed/test.csv` | 300 | 300 | 0 | 0 | **CLEAN** |
| **Modern Holdout** | `dataset-v3/modern_holdout.csv` | 120 | 120 | 0 | 0 | **CLEAN** |
| **Newsletter Holdout** | `dataset-v4/newsletter_holdout.csv` | 60 | 60 | 0 | 0 | **CLEAN** |
| **Social Holdout** | `dataset-v4/social_holdout.csv` | 50 | 50 | 0 | 0 | **CLEAN** |
| **V4 Test Set** | `dataset-v4/test.csv` | 60 | 60 | 0 | 0 | **CLEAN** |
| **V4.1 Test Set** | `dataset-v4.1/test.csv` | 60 | 60 | 0 | 0 | **CLEAN** |
| **Total Holdout Pool** | | **650** | **590 unique** | **0** | **0** | **ZERO LEAKAGE** |

**Verification:** All holdout files remain byte-for-byte unmodified in git. Holdout integrity is 100% preserved.

---

## 5. Thread / Conversation Leakage Audit

### 5.1 Formal Thread Identity
- `thread_id` field does not exist in `dataset-v5/train.csv` or `validation.csv`.
- In the feedback queue, only `fb_adj_004` had a `thread_id` (`thread_phase43_001`), and this record was **REJECTED** and completely excluded.
- **Formal thread overlap where thread identity exists:** **0**.

### 5.2 Phase 44 Additions Cross-Split Overlap
- Phase 44 train subjects (`cp_001`–`cp_004`, `fb_synth_001`) vs validation: **0 overlapping subjects**.
- Phase 44 validation subjects (`cp_005`) vs train: **0 overlapping subjects**.
- Contrastive pair groups are strictly partitioned: Pairs 1–4 are exclusively in train; Pair 5 is exclusively in validation. No pair group straddles splits.

### 5.3 Repeated Subject Lines in Inherited Base
- Normalizing subject lines (stripping `Re:`, `Fwd:`, `[tag]`, whitespace) revealed **30 repeated subject strings** between train and validation.
- **Root Cause Analysis:** Tracing these 30 subjects revealed that 25 were inherited from the original Enron Gold 2,000 random split in `dataset/processed/train.csv` and `validation.csv` (originating in 2001), and 5 were added during v4 modern curated expansions.
- **Nature of Overlapping Messages:**
  - Automated recurring newsletters: *"breaking news from abcnews.com"*, *"company sleuth daily report for wmson"*, *"diabetes e-news now!"*.
  - Automated system logs: *"schedule crawler: hourahead failure"*.
  - Account notices: *"your instagram password has been changed"*.
  - Templated managerial reports: *"expense reports awaiting your approval"*.
- **Token Jaccard Similarity:** 19 cross-split pairs exhibited token Jaccard similarity > 0.9 due to shared boilerplate templates with varying parameters (e.g., date, hour, or employee name).
- **Audit Assessment:** Because these are distinct operational alerts sent on different dates with different metadata rather than multi-turn conversational exchanges, and because they form the historical baseline across all model versions (v1–v4.1), they do not constitute active conversation thread leakage. Offline training can safely proceed, provided offline model evaluation is anchored on the frozen holdouts.

---

## 6. Class Distribution Across Versions

| Priority Class | Gold 2,000 (Historical) | Dataset-v4.1 (Pre-Phase 44) | Dataset-v5 Train | Dataset-v5 Val | Dataset-v5 Total |
|---|:---:|:---:|:---:|:---:|:---:|
| **P1** | 58 (2.9%) | 81 (3.5%) | 70 (3.7%) | 11 (2.6%) | **81 (3.5%)** |
| **P2** | 970 (48.5%) | 893 (39.0%) | 735 (39.3%) | 164 (38.2%) | **899 (39.1%)** |
| **P3** | 448 (22.4%) | 675 (29.5%) | 543 (29.1%) | 135 (31.5%) | **678 (29.5%)** |
| **P4** | 524 (26.2%) | 638 (27.9%) | 521 (27.9%) | 119 (27.7%) | **640 (27.9%)** |
| **Total** | **2,000** | **2,287** | **1,869** | **429** | **2,298** |

### Observations:
- **P1 Stability:** P1 remains a tightly controlled, high-precision tier (~3.5% of total data), guarding against alarm fatigue.
- **P2 Balance:** P2 represents 39.1% of the dataset, providing robust representation for operational, deadline-driven emails.
- **P3/P4 Proportions:** P3 (informational) and P4 (promotional/routine) are balanced at ~29.5% and ~27.9% respectively.
- **No Artificial Rebalancing:** No synthetic oversampling, SMOTE, or artificial label manipulation was applied. Distribution documentation is empirical.

---

## 7. Label Transition Analysis (v4.1 → v5)

Every row inherited from `dataset-v4.1` was checked against its prior label in `dataset-v4.1/train.csv` and `validation.csv` using content hashing.

| v4.1 Label | v5 Label | Inherited Rows | Transition Status | Accidental Relabeling? |
|:---:|:---:|:---:|:---:|:---:|
| **P1** | **P1** | 81 | IDENTICAL | NO |
| **P1** | P2 / P3 / P4 | 0 | — | NO |
| **P2** | **P2** | 893 | IDENTICAL | NO |
| **P2** | P1 / P3 / P4 | 0 | — | NO |
| **P3** | **P3** | 675 | IDENTICAL | NO |
| **P3** | P1 / P2 / P4 | 0 | — | NO |
| **P4** | **P4** | 638 | IDENTICAL | NO |
| **P4** | P1 / P2 / P3 | 0 | — | NO |
| **Total Inherited** | | **2,287** | **100% Retained** | **ZERO Relabeling Errors** |

**Conclusion:** Exactly zero inherited examples changed labels during the construction of Dataset-v5. Dataset integrity is 100% preserved.

---

## 8. Phase 44 Contribution Isolation

| Phase 44 Item | Source Identifier | Role | Split | Label | Action Req. | Deadline | Status in Dataset-v5 |
|---|---|---|:---:|:---:|:---:|:---:|---|
| **Accepted Feedback** | `fb_synth_001` | Canonical representative for `fb_adj_001` | Train | **P2** | True | Oct 1, 2026 | **INCLUDED (1 row)** |
| **Contrastive Pair 1a** | `cp_001a` | Registration deadline | Train | **P2** | True | Oct 1 | **INCLUDED (1 row)** |
| **Contrastive Pair 1b** | `cp_001b` | Course enrollment open | Train | **P3** | False | None | **INCLUDED (1 row)** |
| **Contrastive Pair 2a** | `cp_002a` | Overdue invoice with suspension | Train | **P2** | True | 5 days | **INCLUDED (1 row)** |
| **Contrastive Pair 2b** | `cp_002b` | $0.00 payment confirmation | Train | **P4** | False | None | **INCLUDED (1 row)** |
| **Contrastive Pair 3a** | `cp_003a` | Elasticsearch storage 85% full | Train | **P2** | True | 48 hours | **INCLUDED (1 row)** |
| **Contrastive Pair 3b** | `cp_003b` | Elasticsearch product update | Train | **P4** | False | None | **INCLUDED (1 row)** |
| **Contrastive Pair 4a** | `cp_004a` | CS229 Homework due Wednesday | Train | **P2** | True | Wed 11:59 PM | **INCLUDED (1 row)** |
| **Contrastive Pair 4b** | `cp_004b` | CS229 weekly department digest | Train | **P3** | False | None | **INCLUDED (1 row)** |
| **Contrastive Pair 5a** | `cp_005a` | Offer letter accept by Oct 8 | Val | **P2** | True | Oct 8, 2026 | **INCLUDED (1 row)** |
| **Contrastive Pair 5b** | `cp_005b` | Application received confirmation | Val | **P3** | False | None | **INCLUDED (1 row)** |

### Verification of Exclusions:
- **103 Duplicate Records:** Excluded. Only 1 canonical example retained.
- **Rejected Feedback (`fb_adj_004`, `fb_adj_005`):** Excluded. Synthetic automated test artifacts correctly blocked from training data.
- **Insufficient-Context Feedback (`fb_adj_002`, `fb_adj_003`):** Excluded. Terse notes without email body blocked from training data.

---

## 9. Synthetic Data Audit

### 9.1 Quantitative Representation

| Synthetic Component | Train Count | Train % | Val Count | Val % | Total Count | Total % |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Phase 44 Contrastive Pairs** | 8 | 0.43% | 2 | 0.47% | 10 | 0.43% |
| **Phase 44 Synthesized Feedback** | 1 | 0.05% | 0 | 0.00% | 1 | 0.04% |
| **v4.1 Boundary Repair Pairs** | 111 | 5.94% | 39 | 9.09% | 150 | 6.53% |
| **Total Synthetic / Curated** | **120** | **6.42%** | **41** | **9.56%** | **161** | **7.01%** |

### 9.2 Vocabulary Dominance Assessment
- Base Dataset Vocabulary: **30,197 unique tokens**
- Synthetic Examples Vocabulary: **1,414 unique tokens**
- Novel Tokens Introduced by Synthetic Data: **3 tokens** (`elasticsearch`, `85%`, `datacore`)
- Vocabulary Dominance Metric: **0.01% of base vocabulary**
- **Conclusion:** Synthetic examples do NOT dominate model vocabulary. They provide targeted boundary signal without distorting word frequencies.

---

## 10. Domain Distribution

| Domain / Category | Base Inherited | Synthetic | Total Examples | Percentage |
|---|:---:|:---:|:---:|:---:|
| **General Business** | 1,403 | 99 | 1,502 | 65.36% |
| **Promotional / Marketing** | 364 | 1 | 365 | 15.88% |
| **Security & Authentication** | 122 | 2 | 124 | 5.40% |
| **Newsletters & Digests** | 95 | 5 | 100 | 4.35% |
| **Payments & Invoicing** | 60 | 25 | 85 | 3.70% |
| **Recruitment & Hiring** | 32 | 11 | 43 | 1.87% |
| **Account & Verification (OTP)** | 38 | 3 | 41 | 1.78% |
| **Academic & Coursework** | 9 | 7 | 16 | 0.70% |
| **Social Media & Networking** | 10 | 3 | 13 | 0.57% |
| **SaaS & Infrastructure** | 4 | 5 | 9 | 0.39% |
| **Total** | **2,137** | **161** | **2,298** | **100.00%** |

### Overrepresented Domains:
- **General Business (65.4%):** Inherited from the historical Enron corporate corpus.
- **Promotional (15.9%):** Typical for real-world personal mailboxes.

### Synthetic-Only Domain Audit:
- **Result: NONE**. Every single domain contains authentic, base-inherited examples in addition to targeted synthetic boundary pairs.

---

## 11. Class × Domain Matrix

This matrix verifies that legitimate operational P2 examples now exist across modern domains, directly resolving the root cause of the earlier priority-v4 regression.

| Domain / Category | P1 | P2 | P3 | P4 | Total | Operational P2 Health |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **General Business** | 53 | 604 | 470 | 375 | 1,502 | **HEALTHY** (604 P2) |
| **Promotional** | 4 | 140 | 69 | 152 | 365 | **HEALTHY** (140 P2) |
| **Security** | 8 | 53 | 18 | 45 | 124 | **HEALTHY** (53 P2) |
| **Newsletters** | 0 | 7 | 66 | 27 | 100 | **HEALTHY** (7 P2 actionable newsletters) |
| **Payments & Invoicing** | 0 | 42 | 30 | 13 | 85 | **HEALTHY** (42 P2 invoices) |
| **Recruitment** | 1 | 22 | 11 | 9 | 43 | **HEALTHY** (22 P2 offers/interviews) |
| **Account / Verification** | 14 | 14 | 7 | 6 | 41 | **HEALTHY** (14 P2 verifications) |
| **Academic** | 0 | 12 | 2 | 2 | 16 | **HEALTHY** (12 P2 registration/deadlines) |
| **SaaS / Infrastructure** | 1 | 5 | 3 | 0 | 9 | **HEALTHY** (5 P2 quota/outage alerts) |
| **Social** | 0 | 0 | 2 | 11 | 13 | P3/P4 only (Standard social notices) |
| **Total** | **81** | **899** | **678** | **640** | **2,298** | **Operational P2 present in 9/10 domains** |

---

## 12. Contrastive Pair Validation

All 5 contrastive pairs from `dataset-v5/contrastive_pairs.json` were audited for grounding in action, urgency, consequence, and deadline rather than keyword artifacts:

### Pair 1: Academic / Registration (`cp_001`)
- **Positive (`cp_001a`):** *"Registration deadline: Submit your course enrollment by Oct 1"*  
  Label: **P2** | Action Required: **True** | Deadline: **Oct 1**  
  Consequence: Inability to attend course. Immediate operational necessity.
- **Negative (`cp_001b`):** *"Course enrollment season is now open for all students"*  
  Label: **P3** | Action Required: **False** | Deadline: **None**  
  Consequence: None. Passive informational broadcast.
- **Grounding Basis:** Distinguishes urgent deadline-bound registration from broad informational season announcements.

### Pair 2: Payments / Invoicing (`cp_002`)
- **Positive (`cp_002a`):** *"Invoice #20491 overdue: Payment required to avoid service suspension"*  
  Label: **P2** | Action Required: **True** | Deadline: **5 business days**  
  Consequence: Account suspension and late fees.
- **Negative (`cp_002b`):** *"Your payment of $0.00 has been processed"*  
  Label: **P4** | Action Required: **False** | Deadline: **None**  
  Consequence: None. Routine automated receipt.
- **Grounding Basis:** Distinguishes overdue invoices requiring financial settlement from routine zero-dollar receipts.

### Pair 3: SaaS / Infrastructure (`cp_003`)
- **Positive (`cp_003a`):** *"Elasticsearch storage 85% full: Immediate action required"*  
  Label: **P2** | Action Required: **True** | Deadline: **within 48 hours**  
  Consequence: Ingestion failure and potential data loss.
- **Negative (`cp_003b`):** *"Elasticsearch product update: What is new in 8.12"*  
  Label: **P4** | Action Required: **False** | Deadline: **None**  
  Consequence: None. Educational release digest.
- **Grounding Basis:** Distinguishes actionable storage capacity warnings from brand newsletters sharing the keyword "Elasticsearch".

### Pair 4: Academic / Coursework (`cp_004`)
- **Positive (`cp_004a`):** *"CS229: Homework 2 submission due Wednesday 11:59 PM"*  
  Label: **P2** | Action Required: **True** | Deadline: **Wednesday 11:59 PM**  
  Consequence: 20% penalty per day late.
- **Negative (`cp_004b`):** *"CS229 Weekly Department Digest - Oct 2026"*  
  Label: **P3** | Action Required: **False** | Deadline: **None**  
  Consequence: None. Passive weekly course summary.
- **Grounding Basis:** Distinguishes assignment submission deadlines from routine course digest emails.

### Pair 5: Recruitment / Hiring (`cp_005`)
- **Positive (`cp_005a`):** *"Offer letter enclosed: Accept or decline by October 8"*  
  Label: **P2** | Action Required: **True** | Deadline: **October 8, 2026**  
  Consequence: Offer expiration. Explicit written decision required.
- **Negative (`cp_005b`):** *"Application received: DataCore Inc Software Engineer"*  
  Label: **P3** | Action Required: **False** | Deadline: **None**  
  Consequence: None. Automated application acknowledgement.
- **Grounding Basis:** Distinguishes actionable offer deadlines from passive application confirmations.

---

## 13. Dataset Size Sanity Check

### Technical Reconciliation of Row Counts

| Metric | Train File | Validation File | Combined Dataset |
|---|:---:|:---:|:---:|
| **Physical Text Lines (`wc -l`)** | **78,712 lines** (78,711 data + 1 header) | **16,329 lines** (16,328 data + 1 header) | **95,041 lines** |
| **Logical CSV Records (`DictReader`)** | **1,869 records** | **429 records** | **2,298 records** |
| **Average Lines per Record** | 42.1 lines/email | 38.1 lines/email | 41.4 lines/email |

### Lineage Accounting Across Historical Versions

| Version | Phase | Train Lines | Train Records | Val Lines | Val Records | Notes |
|---|---|:---:|:---:|:---:|:---:|---|
| **Gold 2,000** | Initial | 78,243 | 1,400 | 16,200 | 300 | Base Enron corpus (+ 300 test) |
| **Dataset-v3** | Phase 33 | 78,279 | 1,418 | 16,209 | 304 | Added modern OTP & authentication examples |
| **Dataset-v4** | Phase 39 | 78,592 | 1,749 | 16,288 | 388 | Added modern Gmail, newsletters, and social |
| **Dataset-v4.1** | Phase 40 | 78,703 | 1,860 | 16,327 | 427 | Added 150 boundary review repair pairs |
| **Dataset-v5** | Phase 44 | **78,712** | **1,869** | **16,329** | **429** | Added 10 contrastive pairs + 1 feedback synth |

### Cause of the Discrepancy:
The Enron email corpus contains multiline email bodies with embedded CRLF/LF line breaks inside quoted CSV fields (RFC 4180 standard). A naive line count tool (`wc -l` or PowerShell `Get-Content`) counts every line of text in an email body as a separate row, giving 78,711 lines. When properly parsed by a standard CSV parser, `dataset-v5` contains **1,869 discrete training emails** and **429 validation emails**.

---

## 14. Training Readiness Gates (13 Gates)

| Gate | Description | Target | Observed | Status |
|:---:|---|:---:|:---:|:---:|
| **GATE 1** | All rows have documented provenance | 100% | 2,298 / 2,298 rows traced | **PASS** |
| **GATE 2** | All labels trace to valid priority classes | 100% | All rows in {P1, P2, P3, P4} | **PASS** |
| **GATE 3** | Zero train / validation content leakage | 0 | 0 exact / 0 normalized | **PASS** |
| **GATE 4** | Zero holdout leakage against all 6 holdouts | 0 | 0 violations (650 checked) | **PASS** |
| **GATE 5** | Zero thread leakage where thread identity exists | 0 | 0 thread ID overlap; 0 P44 overlap | **PASS** |
| **GATE 6** | Synthetic examples are quantified | Documented | 161 examples (7.01%) | **PASS** |
| **GATE 7** | Phase 44 contribution is correctly isolated | Exactly 11 | 9 train / 2 val | **PASS** |
| **GATE 8** | Class distribution documented across splits | Documented | Complete counts & % documented | **PASS** |
| **GATE 9** | Domain × priority distribution documented | Documented | Full matrix documented | **PASS** |
| **GATE 10** | Contrastive pairs validated & grounded | 5 pairs | All 5 pairs grounded in action/deadline | **PASS** |
| **GATE 11** | No rejected or ambiguous feedback included | 0 | 0 rejected, 0 ambiguous | **PASS** |
| **GATE 12** | No secrets, credentials, or session tokens | 0 | No regex pattern matches | **PASS** |
| **GATE 13** | Existing production model & registry untouched | Untouched | `priority-v4.1` verified in git | **PASS** |

**Summary: 13 / 13 Gates Passed.**

---

## 15. Model Preservation & Training Restriction

- **Model Training Execution:** **NONE**.
- **Prohibited Functions:** Absolutely no calls to `fit()`, `fit_transform()`, `partial_fit()`, hyperparameter grid search, or candidate model serialization were executed.
- **Active Production Model:** `priority-v4.1` (`dataset/models/priority-v4.1/model.joblib`) remains the active production classifier.
- **Model Registry:** `dataset/models/registry.json` is completely unchanged and verified.
- **Historical Assets:** `priority-v3` remains archived and unmodified.

---

## 16. Test Verification

Comprehensive automated test execution was conducted to ensure system integrity:

1. **Phase 45 Dedicated Readiness Gate Tests:**
   - Command: `.venv\Scripts\python.exe -m pytest tests/test_phase45_dataset_v5_audit.py`
   - Result: **14 passed, 0 failed in 1.91s**.
2. **Full System Test Suite:**
   - Command: `.venv\Scripts\python.exe -m pytest tests/ -q`
   - Result: **319 passed, 0 failed in 43.39s** (expanded from 305 tests).
3. **Frontend Automated Unit Tests:**
   - Command: `npm test -- --run`
   - Result: **9 passed, 0 failed in 187ms**.
4. **Frontend Production Build:**
   - Command: `npm run build`
   - Result: **Vite build succeeded cleanly** (chunks rendered, gzip verified).

---

## 17. Risks & Mitigations

| Risk | Severity | Mitigation Strategy |
|---|:---:|---|
| **Domain Imbalance** (65.4% General Business from Enron) | Medium | Handled via modern domain additions (v3, v4, v4.1, v5) and evaluation on the 4 modern holdouts. |
| **Near-Duplicate Templates in Inherited Base** (30 subjects, 19 pairs Jaccard > 0.9) | Low | Overlaps are limited to background automated alerts. Evaluation must use the 4 frozen holdouts, not validation alone. |
| **Single Feedback Example Synthesis** (`fb_synth_001`) | Low | Synthesized example was explicitly vetted by human adjudicator and labeled as canonical representative. |

---

## 18. Final Decision

Based on comprehensive empirical verification across all 17 audit sections and the passing of all 13 training readiness gates:

```
======================================================================
                         FINAL DECISION:
                   READY FOR OFFLINE TRAINING
======================================================================
```

Dataset-v5 is fully verified, correctly sourced, free of holdout leakage, and ready for offline candidate training in Phase 46. No training was performed in Phase 45.
