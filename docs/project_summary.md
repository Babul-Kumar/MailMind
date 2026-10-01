# CSE472 Course Project Summary: AI Email Priority Classification System

**Course:** CSE472 — Natural Language Processing / Applied Artificial Intelligence  
**Author:** Babul Kumar  
**Date:** September 2026  
**Project Repository:** CSE472 AI Email Priority Classification  
**Production Status:** Complete, Hardened, Verified, and Operational  

---

## 1. Executive Summary

This report provides a comprehensive academic retrospective and technical synthesis of the **AI Email Priority Classification System**. Developed as the final capstone project for CSE472, the initiative tackled the challenging problem of real-time email prioritization using natural language processing and statistical machine learning.

Over the course of 28 structured phases, the project progressed from raw corpus exploration and human annotation to heuristic candidate calibration, supervised linear modeling, deep neural architecture experimentation (BiLSTM and DistilBERT), rigorous held-out test evaluation, and production deployment with live, read-only Google Gmail API integration.

### Complete Lifecycle Progression

```
Problem (Email Overload & Asymmetric Urgency)
   ↓
Dataset (Enron Corpus + Labeled Importance)
   ↓
Data Cleaning (RFC-822 Parsing, Content Hashing, Leakage Prevention)
   ↓
Human Labeling (2,000-Email Gold Review & Guidelines)
   ↓
Candidate Scoring (Rule-Based Heuristic Matching)
   ↓
V2 Calibration (Promotional Suppressors & 200-Row Adjudication)
   ↓
ML Baselines (TF-IDF + Logistic Regression)
   ↓
BiLSTM (Deep Recurrent Sequence Modeling)
   ↓
DistilBERT (Pretrained Transformer Context=128)
   ↓
Controlled Context Experiment (DistilBERT Context=256)
   ↓
Held-Out Test (Single Frozen Evaluation, N=300)
   ↓
Production Model Selection (TF-IDF + Logistic Regression Frozen)
   ↓
Gmail API (Read-Only OAuth 2.0 Ingestion)
   ↓
Real-Time Inference (MIME Parsing & Feature Attribution)
   ↓
Dashboard (Responsive SPA & Explainable Triage)
```

### Core Quantitative Findings
- **Authoritative Dataset:** 2,000 human-reviewed emails (`gold_human_review_2000.csv`) with a 200-email adjudicated benchmark establishing rigorous label boundaries across four priority tiers: **P1 (Critical)**, **P2 (Actionable)**, **P3 (Routine)**, and **P4 (Low/Promotional)**.
- **Empirical Model Selection:** On the strictly held-out test set ($N=300$), **TF-IDF + Logistic Regression** achieved the highest overall accuracy (**80.67%**), macro F1 (**0.7943**), and weighted F1 (**0.8005**), outperforming a BiLSTM (74.00%) and fine-tuned DistilBERT models with context length 128 (77.00%) and context length 256 (78.33%).
- **Operational Efficiency:** The linear model delivers sub-15ms inference latency per 20-email batch on standard CPU hardware (>68x faster than DistilBERT), enabling seamless real-time inbox triage without specialized accelerators.
- **Production Delivery:** A secure FastAPI backend with pre-warmed model caching, a responsive Single-Page Application (SPA) dashboard, model-grounded explainability, and 31 automated tests with 100% pass rates.

---

## 2. Problem Statement & Motivation

Email communication remains the ubiquitous backbone of professional and personal workflows. However, information overload and the asymmetric urgency of messages pose major productivity bottlenecks. Users frequently miss critical outages, urgent customer escalations, or deadline-sensitive requests because they are submerged under promotional mail, marketing newsletters, and automated notifications.

Traditional email filters rely heavily on static heuristics (e.g., matching `"urgent"` in the subject line or checking sender domains). These approaches exhibit fatal flaws:
1. **Severe False-Positive Rates:** Promotional marketing routinely borrows urgency vocabulary (*"URGENT: 50% discount ends tonight!"*), causing spam to masquerade as emergency notifications.
2. **Context Blindness:** A message from a colleague stating *"The production server is throwing 500 errors"* lacks explicit priority keywords but represents a critical P1 emergency.
3. **Rigid Inflexibility:** Heuristic systems cannot quantify decision confidence or adapt to nuanced linguistic patterns across varying communication styles.

The goal of this project was to establish a scientifically sound, statistically robust, and privacy-preserving priority classification system that resolves these deficiencies.

---

## 3. Dataset Curation, Annotation & Human Adjudication

### 3.1 Ground Truth Curation
A foundational principle of this project was that model quality is bounded by label quality. Rather than relying on noisy pseudo-labels, the project curated an authoritative gold benchmark of **2,000 emails** (`dataset/processed/gold_human_review_2000.csv`).

Each email was assigned to one of four mutually exclusive priority categories based on standardized labeling guidelines:
- **P1 — Critical / Urgent:** Immediate operational disruption, severe security alerts, client outages, high-stakes escalations requiring instant attention.
- **P2 — Important / Actionable:** Direct assignments, personal inquiries, scheduled deliverables, requests requiring thoughtful action within 24 to 48 hours.
- **P3 — Routine / Informational:** Status updates, meeting notes, project tracking digests, broadcast announcements that inform but require no direct response.
- **P4 — Low / Promotional / Noise:** Marketing campaigns, vendor outreach, product discounts, automated transactional receipts, unsolicited spam.

### 3.2 The 200-Row Human Adjudication Pass
Initial reviewer agreements revealed systemic edge cases, particularly around:
- Promotional emails using urgent call-to-action phrasing.
- Operational digests labeled P2 by reviewers but functioning as P3 routine updates.
- Polite conversational emails misclassified as high-priority tasks.

To eliminate label noise without corrupting the historical record, a **200-row human adjudication queue** was constructed. Each disputed row was reviewed by an adjudicator using independent contextual analysis, establishing explicit `adjudicated_label` and `adjudication_notes` columns while preserving the original `reviewer_label`. This adjudicated benchmark achieved 69.5% alignment with early heuristic candidates while correcting critical label distortions.

### 3.3 Strict Stratified Dataset Partitioning
The curated 2,000 emails were partitioned into stratified splits:
- **Train ($N=1,400$, 70%):** Model parameter optimization and vocabulary derivation.
- **Validation ($N=300$, 15%):** Model selection, hyperparameter tuning, and architecture comparisons.
- **Held-Out Test ($N=300$, 15%):** Strictly isolated and sealed until the final Section 25 verification.

---

## 4. Heuristic Rule Calibration (V1 vs. V2)

Before implementing statistical learning, a rule-based candidate generator was developed to model domain intuition:
- **Heuristic V1:** Relied on broad keyword dictionaries and regex patterns. On the 200-row benchmark, V1 over-triggered on P1, predicting 46 critical alerts where only 8 actual P1s existed (an unsustainable 82.6% false-positive rate).
- **Heuristic V2 Calibration:** Introduced contextual suppression gates:
  - Promotional negation filters (e.g., detecting `unsubscribe`, `deal`, `discount`, `shop now` to block P1/P2 elevation).
  - Header-body interaction rules.
  - Sender domain reputation heuristics.
- **Outcome:** V2 reduced candidate P1 predictions from 46 down to 15 (a **67.4% reduction in false positives**), lifted P2 recall to 80.0%, and reached 75.93% precision on P4.
- **Methodological Decision:** At Phase 20, the heuristic generator was **frozen** at V2 (`src/priority_scoring_v2.py`) to prevent leakage into subsequent supervised experiments.

---

## 5. Supervised Modeling & Empirical Progression

Four distinct model families were implemented, trained on the 1,400-email training set, and evaluated on the 300-email validation set:

```
[Phase 21: TF-IDF + Logistic Regression]
       │
       ▼ (Val Acc: 78.67%, Macro F1: 0.7514)
[Phase 22: BiLSTM (PyTorch)]
       │
       ▼ (Val Acc: 70.33%, Macro F1: 0.6932)
[Phase 23: DistilBERT Sequence Classifier (SeqLen=128)]
       │
       ▼ (Val Acc: 76.33%, Macro F1: 0.7144)
[Phase 24: DistilBERT Long Context (SeqLen=256)]
       │
       ▼ (Val Acc: 78.00%, Macro F1: 0.7420)
```

### 1. TF-IDF + Logistic Regression Baseline (Phase 21)
- **Features:** Word and character-level N-grams (1, 2), sublinear term-frequency scaling, minimum document frequency of 2, producing a 66,526-dimensional sparse feature space.
- **Classifier:** Multinomial Logistic Regression with $L_2$ regularization penalty ($C=1.0$), class-weight balancing, and L-BFGS optimization.
- **Validation Metrics:** Accuracy: **78.67%**, Macro F1: **0.7514**, Weighted F1: **0.7752**.

### 2. Bidirectional LSTM (Phase 22)
- **Architecture:** Tokenized integer sequences fed into an embedding layer ($d=128$), a 2-layer Bidirectional LSTM ($h=128$ per direction), spatial dropout (0.3), global average and max pooling, and a linear softmax classification head.
- **Validation Metrics:** Accuracy: 70.33%, Macro F1: 0.6932, Weighted F1: 0.7000.
- **Analysis:** While capable of capturing sequential word order, the BiLSTM suffered from limited training data ($N=1,400$) when training embeddings from scratch, leading to underfitting on sparse tail vocabulary.

### 3. DistilBERT Sequence Classifier (Context=128) (Phase 23)
- **Architecture:** Pretrained `distilbert-base-uncased` (66M parameters) fine-tuned with a sequence classification head, dropout (0.2), AdamW ($	ext{lr}=2	imes 10^{-5}$), batch size 16, linear warmup over 3 epochs.
- **Validation Metrics:** Accuracy: 76.33%, Macro F1: 0.7144, Weighted F1: 0.7602.
- **Analysis:** Captured rich bidirectional contextual embeddings. Significantly improved the P3 $	o$ P2 error rate (reducing misclassifications from 35.8% to 25.4%), but incurred slightly lower overall precision on routine emails.

### 4. DistilBERT Long Context (Context=256) (Phase 24)
- **Motivation:** Investigation into whether truncating emails at 128 tokens discarded critical downstream task context.
- **Architecture:** Extended max sequence length to 256 tokens.
- **Validation Metrics:** Accuracy: 78.00%, Macro F1: 0.7420, Weighted F1: 0.7770.
- **Analysis:** Extended context improved representation of multi-paragraph operational emails, bringing performance within 0.67% of the linear baseline on the validation set.

---

## 6. Final Held-Out Test Evaluation (Section 25)

In Phase 25, model development was formally frozen. The single held-out test set ($N=300$, `dataset/processed/test.csv`) was evaluated across all four frozen candidates.

### Comparative Performance Matrix ($N=300$)

| Evaluation Metric | TF-IDF + Logistic Reg | DistilBERT (256) | DistilBERT (128) | BiLSTM |
|:---|:---:|:---:|:---:|:---:|
| **Test Accuracy** | **80.67%** | 78.33% | 77.00% | 74.00% |
| **Macro F1 Score** | **0.7943** | 0.7490 | 0.7337 | 0.7188 |
| **Weighted F1 Score** | **0.8005** | 0.7816 | 0.7674 | 0.7380 |
| **P1 Class F1 (Critical)** | **0.8235** | 0.7778 | 0.7059 | 0.7778 |
| **P2 Class F1 (Actionable)**| **0.8498** | 0.8178 | 0.8062 | 0.7778 |
| **P3 Class F1 (Routine)**   | **0.6970** | 0.5897 | 0.6129 | 0.5806 |
| **P4 Class F1 (Noise)**     | **0.8070** | 0.8105 | 0.8095 | 0.7391 |
| **Test Set Log Loss**      | **0.6385** | 0.7120 | 0.7450 | 0.8840 |
| **CPU Latency per Batch**  | **~12 ms** | ~820 ms | ~440 ms | ~65 ms |

### Key Test Findings
1. **Unanimous Linear Superiority:** The frozen TF-IDF + Logistic Regression model dominated across every composite metric: Accuracy (+2.34% over DistilBERT-256), Macro F1 (+0.0453), and Weighted F1 (+0.0189).
2. **Superior P1 and P2 Recall:** For critical real-world inbox triage, identifying P1 and P2 emails without excessive false alarms is paramount. The linear model achieved an F1 of 0.8235 on P1 and 0.8498 on P2, outperforming all neural architectures.
3. **P3 Routine Email Discrimination:** DistilBERT struggled substantially with P3 classification on the unseen test set (F1: 0.5897), frequently confusing routine digests with actionable requests. Logistic Regression retained a strong F1 of 0.6970.

### Crucial Distinction: Held-Out Benchmark vs. Live Gmail Inference
- **Held-Out Test Benchmark:** The quantitative metrics reported above (**80.67% accuracy**, **0.7943 macro F1**, **0.8005 weighted F1**) were evaluated strictly on the sealed, human-annotated held-out test split ($N=300$, `dataset/processed/test.csv`). This partition was evaluated exactly once in Section 25 and never modified or used for training.
- **Live Gmail Inference:** In contrast, live inbox triage executes read-only inference across the authenticated user's real-world unlabelled mailbox emails. Because live emails lack human gold standard annotations, live predictions serve as decision-support triage recommendations, not empirical accuracy benchmarks.

---

## 7. Scientific Discussion: Why Linear Models Outperformed Deep Transformers

The superiority of TF-IDF + Logistic Regression over pretrained transformers in this project is an important scientific finding that mirrors classic findings in practical NLP:

### 1. Sample Efficiency & Parameter-to-Data Ratio
A standard DistilBERT sequence classifier contains approximately 66,365,956 trainable parameters. With an effective training corpus of $N=1,400$ documents, the parameter-to-sample ratio is approximately **47,400 to 1**. Even with aggressive regularization, dropout, and pretrained weight initialization, gradient updates over 3–5 epochs risk subtle overfitting to idiosyncratic lexical combinations present in the training partition.

Conversely, multinomial logistic regression with convex $L_2$ regularization operates as a linear separator in high-dimensional feature space. The convex optimization problem guarantees convergence to a unique global optimum without stochastic initialization noise or catastrophic forgetting.

### 2. Lexical Salience vs. Deep Compositionality
Unlike sentiment analysis or natural language inference, where meaning hinges on complex syntactic negation, sarcasm, or coreference, email priority classification is predominantly driven by **lexical salience**:
- The presence of tokens such as `"system outage"`, `"incident response"`, or `"emergency deployment"` decisively indicates P1, regardless of sentence structure.
- Tokens like `"unsubscribe"`, `"limited time offer"`, or `"digest"` decisively indicate P4.
The TF-IDF vectorizer captures 66,526 unigram and bigram combinations directly. The linear model assigns explicit, calibrated log-odds weights to these exact tokens without needing to learn multi-head self-attention paths.

### 3. Generalization on Domain-Specific Noise
Email text contains high concentrations of non-standard syntax: email signatures, header metadata, server logs, URLs, hex codes, and automated footers. WordPiece tokenization in DistilBERT breaks these domain-specific terms into long sequences of subword fragments, diluting the attention distribution. TF-IDF preserves these tokens as unified N-gram features.

---

## 8. Production Engineering: Live Gmail Integration & Dashboard

To validate the model in a realistic user environment, Phase 26–28 implemented a production-ready application stack:

```
[Google Gmail API]
       │
       ▼ (OAuth 2.0 Read-Only)
[src/gmail_client.py: MIME Parsing]
       │
       ▼ (UTF-8 Clean Text)
[src/gmail_priority_predictor.py: Frozen ML Pipeline]
       │
       ▼ (Predictions + Feature Attributions)
[src/app.py: FastAPI REST Service]
       │
       ▼ (JSON REST Payloads)
[src/static/: Responsive Vanilla ES6 Dashboard]
```

### 1. Read-Only Gmail OAuth 2.0 Ingestion
- Ingestion operates strictly under `https://www.googleapis.com/auth/gmail.readonly`.
- MIME parser recursively traverses multipart structures (`multipart/alternative`, `multipart/mixed`), preferring clean plain text and extracting sanitized text from HTML fallbacks.
- Handles edge cases gracefully: empty bodies, missing subjects, multi-recipient headers.

### 2. Pre-Warmed FastAPI Server Architecture
- Implemented with FastAPI and Uvicorn.
- Features a **lifespan startup handler** that pre-warms the frozen TF-IDF + Logistic Regression model into memory at application initialization. This eliminates repetitive disk I/O and provides sub-millisecond local inference.
- Secure loopback CORS middleware restricts access to local authorized development hosts.

### 3. Model-Grounded Explainability & Confidence UX
- **Attribution Weights:** For each classified email, the system computes linear feature attribution:
  $$	ext{Contribution}_{j} = X_{0, j} \cdot 	heta_{k, j}$$
  extracting the top positive lexical signals that drove the model's decision.
- **Visual Signal Chips:** The dashboard renders these influential terms as clickable chips.
- **Confidence Advisory:** Predictions with confidence below 40% automatically trigger a user advisory banner recommending human verification.

---

## 9. Security, Privacy & Compliance Posture

The application adheres to enterprise data privacy principles:
- **Zero Write Privileges:** Read-only access guarantees the application cannot delete, modify, or send emails on the user's behalf.
- **Ephemeral In-Memory Triage:** Ingested emails and predictions exist solely in volatile RAM during request execution. No emails are persisted to disk or external databases.
- **Credential Isolation:** OAuth secrets (`credentials.json`, `token.json`) are strictly gitignored and excluded from version control.
- **Sanitized Errors:** Error handlers catch exceptions internally and return structured JSON responses without revealing stack traces, file paths, or system internals.

---

## 10. Comprehensive Verification Matrix

The integrity and correctness of the system are verified by **31 automated tests** with a 100% pass rate:

| Test Suite | File Location | Tests | Focus Area | Status |
|:---|:---|:---:|:---|:---:|
| **Gmail Pipeline** | `tests/test_gmail_pipeline.py` | 11 | OAuth, MIME decoding, edge cases, zero-retraining | **PASS** (11/11) |
| **Dashboard API** | `tests/test_dashboard_api.py` | 10 | REST endpoints, parameters, static files, error handling | **PASS** (10/10) |
| **Phase 28 Hardening** | `tests/test_phase28_hardening.py` | 10 | Security, CORS, token leaks, explainability, checksums | **PASS** (10/10) |
| **Total** | | **31** | **End-to-End System Verification** | **PASS** (31/31) |

### Cryptographic Checksum Verification
- `dataset/processed/test.csv`: `6841cd44901fa56242bf3752257e991fd7ff474ed7e0f7a5d2b7065a0827c138` (Strictly 300 rows)
- `dataset/models/tfidf_logistic_baseline.joblib`: `040496611b8a15247b6b00330f531670dedca34772c923439ddefec445c55a6e` (Frozen)
- `dataset/analysis/final_test_evaluation_report.md`: `887b6b68cd327857ca16e5019a61196b7c9428469ec849d2888c156eb63d2aa9` (Frozen)
- `index.ipynb`: 77 executed cells across Sections 1 to 26 documenting the full reproducible trajectory.

---

## 11. Pedagogical Takeaways & Conclusion

The CSE472 AI Email Priority Classification System demonstrates that successful machine learning engineering requires balancing state-of-the-art modeling with pragmatic domain considerations:

1. **Benchmark Rigor Over Model Complexity:** Investing time in the 200-row human adjudication pass yielded cleaner ground truth, which proved far more valuable than increasing neural network depth.
2. **The "Bigger is Not Always Better" Principle:** Despite the ubiquity of large language models, linear models with TF-IDF remain formidable competitors on domain-specific classification tasks where lexical signals dominate and training data is moderately sized ($N pprox 10^3$).
3. **End-to-End Engineering Matters:** A model that remains inside a Jupyter notebook provides zero utility. Integrating the frozen model with live OAuth Gmail ingestion, a pre-warmed REST API, and a transparent explainability dashboard converted theoretical research into an impactful, functional tool.

The system stands complete, fully validated, and production-hardened.
