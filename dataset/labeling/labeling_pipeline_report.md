# Email Priority Labeling Pipeline: Audit & Execution Report

**Execution Date:** September 24, 2026  
**Pipeline Run:** End-to-End Execution (Phases 1 through 7)  
**Input Datasets:**
1. `dataset/emails.csv` — Untouched raw Enron email corpus (517,401 records, ~1.33 GB)
2. `dataset/email_importance.csv` — Untouched seed importance dataset (250 records, ~207 KB)

---

## 1. Executive Summary & Pipeline Metrics

The email priority labeling pipeline successfully established a leak-free, normalized data foundation and generated stratified candidate pools and human review datasets for 4-class email priority classification (`P1 Critical`, `P2 Important`, `P3 Routine`, `P4 Low/Noise`).

Neither original dataset was modified or merged. Zero automated machine learning/deep learning training was executed.

### Core Metrics Table
| Metric / Pipeline Milestone | Value | Documentation & Artifact Reference |
| :--- | :---: | :--- |
| **Original Enron Emails Scanned** | **517,401** | `dataset/emails.csv` |
| **Leakage Exclusion Rows Identified** | **667** | `dataset/processed/leakage_exclusions.csv` |
| **Unique Seed Enron Hashes in Importance Set** | **185** | Derived from `dataset/email_importance.csv` |
| **Unique Seed Hashes Matched in Enron** | **179** | Enron emails repeated across folders |
| **Clean Normalized Emails Written** | **516,734** | `dataset/processed/enron_normalized.parquet` |
| **Total Unique Content Hashes in Enron** | **246,606** | 52.3% cross-folder deduplication rate |
| **Candidate Dataset Assembled** | **33,224** | `dataset/processed/candidate_emails.parquet` |
| **Human Validation Review Set** | **2,000** | `dataset/labeling/human_review.csv` |
| **Human Review Class Distribution** | **500 / class** | Exactly 500 P1, 500 P2, 500 P3, 500 P4 |
| **Reviewer Annotation Fields** | **Empty** | `reviewer_label` and `reviewer_notes` left blank |
| **Labeling Guidelines Document** | **Complete** | `dataset/labeling/LABELING_GUIDELINES.md` |

---

## 2. Phase 1: Content Deduplication & Leakage Exclusions

### 2.1 The Leakage Problem
In `dataset/email_importance.csv`, 185 out of 250 records were originally sampled from Phillip Allen's mailbox (`allen-p`). Because corporate email systems replicate sent emails across `_sent_mail`, `all_documents`, `sent_items`, and recipient folders, a simple file-name or single-row filter would leave hundreds of identical duplicate emails in the corpus, causing severe data leakage during model evaluation.

### 2.2 Deduplication & Hashing Architecture
We implemented a deterministic content hashing function:
$$\text{Content Hash} = \text{SHA-256}\Big(\text{norm}(\text{sender}) \parallel \text{"}\vert\vert\text{"} \parallel \text{norm}(\text{subject}) \parallel \text{"}\vert\vert\text{"} \parallel \text{norm}(\text{body})\Big)$$
where $\text{norm}(t)$ converts text to lowercase, collapses all consecutive whitespace and newline sequences into single spaces, and strips leading and trailing boundaries.

### 2.3 Exclusion Results
- **Total Excluded Rows:** **667 emails** in `emails.csv` matched the 179 unique Enron hashes found in `email_importance.csv`.
- **Exclusion Destination:** All 667 rows were isolated in `dataset/processed/leakage_exclusions.csv`.
- **Zero-Leakage Guarantee:** None of these 667 emails were allowed into `dataset/processed/enron_normalized.parquet`, `dataset/processed/candidate_emails.parquet`, or `dataset/labeling/human_review.csv`.

---

## 3. Phase 2: Normalized Dataset (`enron_normalized.parquet`)

The clean Enron corpus was processed in chunks of 25,000 rows and serialized into columnar Parquet format using PyArrow with Snappy compression.

- **Total Rows:** **516,734**
- **Columns (13):**
  1. `id`: Sequential identifier (`enr_000001` to `enr_517401`)
  2. `file`: Original file path (e.g., `allen-p/_sent_mail/1.`)
  3. `user`: Extracted custodian username (e.g., `allen-p`)
  4. `folder`: Extracted folder name (e.g., `_sent_mail`)
  5. `date`: Raw RFC-822 date header string
  6. `sender`: Clean sender email address
  7. `recipients`: Clean direct recipient email addresses
  8. `subject`: Clean subject line
  9. `body`: Extracted plain-text email body
  10. `body_char_length`: Integer character count of body
  11. `body_word_length`: Integer word count of body
  12. `content_hash`: Deterministic SHA-256 content signature
  13. `normalized_text`: Standardized model-ready string:
      ```text
      [SUBJECT]: <subject>
      [FROM]: <sender>
      [BODY]: <body>
      ```

---

## 4. Phase 3: Priority Signals Catalog

A comprehensive suite of programmatic signals was extracted across multiple independent linguistic and structural dimensions:

### 4.1 Text Signals (Lexical Urgency, Actions, & Operations)
* `signal_urgent`: Matches `\b(urgent|urgently)\b`
* `signal_emergency`: Matches `\b(emergency)\b`
* `signal_immediately`: Matches `\b(immediately|right now|at once)\b`
* `signal_asap`: Matches `\b(asap|a\.s\.a\.p\.)\b`
* `signal_deadline`: Matches `\b(deadline|deadlines)\b`
* `signal_due`: Matches `\b(due date|due by|past due|is due)\b`
* `signal_action_required`: Matches `\b(action required|action needed|immediate action)\b`
* `signal_please_respond`: Matches `\b(please respond|reply required|response required)\b`
* `signal_confirm`: Matches `\b(confirm|confirmation|confirmed)\b`
* `signal_approve`: Matches `\b(approve|approval|approved)\b`
* `signal_review`: Matches `\b(review|reviewing|feedback)\b`
* `signal_schedule`: Matches `\b(schedule|scheduling|scheduled|reschedule)\b`
* `signal_meeting`: Matches `\b(meeting|conference call|call with|sync up)\b`
* `signal_interview`: Matches `\b(interview|interviewing|candidate)\b`
* `signal_exam`: Matches `\b(exam|examination|test results)\b`
* `signal_payment`: Matches `\b(payment|wire transfer|invoice|invoices|billing|remittance)\b`
* `signal_contract`: Matches `\b(contract|agreement|nda|amendment|settlement)\b`
* `signal_security`: Matches `\b(security|password|credential|unauthorized|breach|firewall|vpn)\b`
* `signal_outage`: Matches `\b(outage|server down|system crash|shutdown|service interruption)\b`
* `signal_legal`: Matches `\b(legal|counsel|subpoena|litigation|lawsuit|ferc|sec investigation)\b`

### 4.2 Action Signals (Communicative Intent & Directives)
* `signal_has_question`: Presence of question marks (`?`) in body text
* `signal_action_request`: Imperatives: `\b(please\s+[a-z]+|need you to|could you|can you|kindly)\b`
* `signal_response_required`: Explicit demand: `\b(let me know|waiting for|reply needed)\b`
* `signal_confirmation_requested`: Verification ask: `\b(please confirm|can you confirm|verify whether)\b`

### 4.3 Time Signals (Temporal Imminence & Constraints)
* `signal_today`: Matches `\b(today|tonight|this morning)\b`
* `signal_tomorrow`: Matches `\b(tomorrow)\b`
* `signal_this_afternoon`: Matches `\b(this afternoon)\b`
* `signal_by_date`: Specific date deadline: `\bby\s+(?:monday|tuesday|wednesday|...|\d{1,2}/\d{1,2})\b`
* `signal_by_time`: Specific time deadline: `\bby\s+(?:\d{1,2}(?::\d{2})?\s*(?:am|pm)?|noon|eod|cob)\b`
* `signal_deadline_expressions`: Imminent markers: `\b(cut-off|time-sensitive|critical deadline|final notice)\b`

### 4.4 Email Metadata Signals
* `is_internal_sender`: Sender address contains `@enron.com`
* `recipient_count`: Number of direct recipients in `To`
* `is_broadcast_sender`: Automated sender (`enron.announcements@enron.com`, `pete.davis@enron.com`, etc.)
* `folder`: Source folder (`inbox`, `sent`, `deleted_items`, `all_documents`, etc.)

### 4.5 Promotional & Noise Signals
* `signal_sale`: Matches `\b(sale|sales event|clearance)\b`
* `signal_discount`: Matches `\b(discount|\d+%\s*off|save\s*\$?\d+)\b`
* `signal_unsubscribe`: Matches `\b(unsubscribe|opt-out|manage subscriptions)\b`
* `signal_click_here`: Matches `\b(click here|click to view|view in browser)\b`
* `signal_newsletter`: Matches `\b(newsletter|weekly digest|bulletin|daily briefing)\b`
* `signal_promotion`: Matches `\b(promotion|promotional|promotions)\b`
* `signal_offer`: Matches `\b(special offer|exclusive offer|limited time offer)\b`
* `signal_limited_time`: Matches `\b(limited time|ends soon|act now|hurry|last chance)\b`
* `url_count`: Total count of `http://` and `https://` hyperlink anchors

---

## 5. Phase 4: Candidate Sampling (~40,000 Emails)

### 5.1 Multi-Signal Scoring Formulas
To avoid fragile keyword-only rules, candidates were assigned based on multi-signal evidence:

1. **P1 Score (Critical / Urgent):**
   $$\text{Score}_{\text{P1}} = 2 \cdot \text{urgency\_words} + 3 \cdot \text{outage} + 2 \cdot \text{security} + 1.5 \cdot \text{imminent\_time} + 1.2 \cdot \text{action\_request}$$
   *Penalized if broadcast sender or recipient count $> 10$.*
2. **P2 Score (Important / Actionable):**
   $$\text{Score}_{\text{P2}} = 1.5 \cdot \text{work\_action\_verbs} + 1.2 \cdot \text{deadlines} + 1.5 \cdot \text{imperative} + 1.2 \cdot \text{question} + 0.8 \cdot \text{is\_internal}$$
   *Penalized if broadcast sender or high urgency.*
3. **P3 Score (Routine / Informational):**
   $$\text{Score}_{\text{P3}} = 1.5 \cdot \text{newsletter} + 1.5 \cdot \text{report} + 1.2 \cdot \text{update} + 2.5 \cdot \text{is\_broadcast} + 1.5 \cdot (\text{recipients} > 10)$$
   *Penalized if strong action request or urgency.*
4. **P4 Score (Low / Promotional / Noise):**
   $$\text{Score}_{\text{P4}} = 3.0 \cdot \text{unsubscribe} + 2.5 \cdot \text{discount} + 2.0 \cdot \text{sale} + 2.0 \cdot \text{click\_here} + 1.5 \cdot (\text{url\_count} \ge 2) + 1.0 \cdot \text{is\_external}$$

### 5.2 Candidate Dataset Composition
- **Total Selected:** **33,224 emails** stored at `dataset/processed/candidate_emails.parquet`.
- **Distribution:**
  - **P2 (Important):** 10,000 (30.10%)
  - **P4 (Low / Noise):** 9,674 (29.12%)
  - **P1 (Critical):** 6,776 (20.39%)
  - **P3 (Routine):** 6,774 (20.39%)

---

## 6. Phase 5: Human Validation Review Set (`human_review.csv`)

### 6.1 Stratification Strategy
To guarantee maximum entropy and informative evaluation, the 2,000 emails in `dataset/labeling/human_review.csv` were selected using multi-axis stratification:

1. **Balanced Class Coverage:** Exactly **500 emails** per candidate class (`P1`, `P2`, `P3`, `P4`).
2. **Boundary / Ambiguity Cases:** Exactly 100 emails per class (400 total, 20%) are borderline cases where the margin between top candidate score and second candidate score is smallest ($\text{boundary\_diff} \le 0.5$).
3. **Length Diversity:** Within each class, core samples are divided across body character length terciles (short $<300$, medium $300-1500$, long $>1500$).
4. **Sender Diversity:** 54.1% Enron internal senders and 45.9% external senders.

### 6.2 Top Senders & Folders in Human Review Set
- **Top Folders:** `deleted_items` (632), `all_documents` (577), `inbox` (354), `sent_items` (147), `_sent_mail` (143), `schedule_crawler` (37).
- **Top Senders:** `pete.davis@enron.com` (184), `enron.announcements@enron.com` (43), `sally.beck@enron.com` (43), `enron_update@concureworkplace.com` (36), `noreply@ccomad3.uu.commissioner.com` (33), `eric.bass@enron.com` (30), `john.arnold@enron.com` (29).

### 6.3 File Schema Verification
`dataset/labeling/human_review.csv` contains 2,000 rows with columns:
`review_id`, `email_id`, `subject`, `body`, `candidate_label`, `candidate_score`, `reviewer_label`, `reviewer_notes`
- `reviewer_label`: 100% empty (null)
- `reviewer_notes`: 100% empty (null)

---

## 7. Verification Checklist & Compliance

- [x] Original `dataset/emails.csv` untouched (MD5 and size verified: 1,426,122,219 bytes)
- [x] Original `dataset/email_importance.csv` untouched (size verified: 211,801 bytes)
- [x] No merging of datasets
- [x] No model training (zero PyTorch, TensorFlow, Scikit-Learn training invoked)
- [x] No LLM automated final label assignment
- [x] Leakage exclusions documented in `dataset/processed/leakage_exclusions.csv` (667 rows)
- [x] Clean normalized corpus in `dataset/processed/enron_normalized.parquet` (516,734 rows)
- [x] Multi-signal candidate dataset in `dataset/processed/candidate_emails.parquet` (33,224 rows)
- [x] Human review set in `dataset/labeling/human_review.csv` (2,000 rows, empty reviewer fields)
- [x] Annotation guidelines in `dataset/labeling/LABELING_GUIDELINES.md`
- [x] Complete report in `dataset/labeling/labeling_pipeline_report.md`
