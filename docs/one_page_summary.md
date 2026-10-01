# AI Email Priority Classification System: Project Summary Sheet

**Course:** CSE472: Natural Language Processing / Applied Artificial Intelligence  
**Author:** Babul Kumar | **Institution:** Course Capstone Project | **Date:** September 2026  
**System Status:** Complete • Code Frozen • 31/31 Automated Tests Passing • Operational  

---

### 1. Problem & Objectives
Information overload and urgency asymmetry in professional email communications lead to critical operational blind spots. Conventional rule-based filters fail because promotional marketing routinely borrows urgency vocabulary (*"URGENT: Sale ends tonight"*), while legal disclaimers inflate false emergency alerts. This project designs, evaluates, and deploys an end-to-end intelligent triage system categorizing emails into a four-tier operational taxonomy: **P1 (Critical / Urgent)**, **P2 (Important / Actionable)**, **P3 (Routine / Informational)**, and **P4 (Low / Promotional / Noise)**.

---

### 2. Dataset & Human Adjudication Benchmark
- **Gold Benchmark:** 2,000 real-world corporate emails from the Enron Corpus and structured Importance datasets (`gold_human_review_2000.csv`).
- **Ground Truth Distribution:** P1: 52 (2.6%), P2: 952 (47.6%), P3: 452 (22.6%), P4: 544 (27.2%). Reflects real-world crisis rarity.
- **Human Adjudication Pass:** A 200-row adjudicated benchmark resolved boundary edge cases, establishing clean ground truth without heuristic corruption.
- **Stratified Partitioning (Frozen):** Train: 1,400 (70%), Validation: 300 (15%), Held-Out Test: 300 (15%). Sealed until final evaluation.

---

### 3. Empirical Modeling Progression & Final Test Results ($N=300$)
Four candidate modeling paradigms were developed and comparatively evaluated on the sealed held-out test set:

| Model Architecture | Test Accuracy | Test Macro F1 | Test Weighted F1 | P1 Class F1 | P2 Class F1 | P3 Class F1 | P4 Class F1 | Latency (CPU) |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **TF-IDF + Logistic Regression** | **80.67%** | **0.7943** | **0.8005** | **0.8235** | **0.8366** | **0.6909** | **0.8263** | **0.36 s (~1.2 ms/email)** |
| **DistilBERT (Context=256)** | 75.33% | 0.7551 | 0.7511 | 0.8235 | 0.7889 | 0.6250 | 0.7831 | 36.45 s (~121.5 ms/email) |
| **DistilBERT (Context=128)** | 76.00% | 0.7530 | 0.7577 | 0.7778 | 0.7817 | 0.6406 | 0.8118 | 18.03 s (~60.1 ms/email) |
| **BiLSTM (PyTorch)** | 74.00% | 0.7496 | 0.7395 | 0.8235 | 0.7778 | 0.7007 | 0.6962 | 0.23 s (~0.77 ms/email) |

**Key Empirical Finding:** Classical regularized linear modeling with 66,526 TF-IDF N-grams outperformed 66M-parameter deep transformers across all composite metrics. Linear models provided superior sample efficiency on $N=1,400$, avoided subtle overfitting to training phrasing, and delivered **>100x faster inference** on CPU.

---

### 4. Production Engineering & Real-Time Dashboard
- **Gmail Ingestion:** Google OAuth 2.0 client operating under strict `gmail.readonly` scope; recursive multipart MIME decoder.
- **FastAPI Service:** Lifespan pre-warming loads the frozen model artifact into memory once at startup ($0.00$s reload latency).
- **Responsive Dashboard:** Vanilla ES6 + CSS3 Single-Page Application featuring live triage bars, instant priority filtering, keyword search, and master-detail email inspection.
- **Model Explainability:** Exact mathematical feature attribution ($X_{0, j} \cdot 	heta_{k, j}$) extracts top positive lexical signals rendered as visual chips. Tiered confidence indicators (High $\ge 60\%$, Moderate $40\%-59\%$, Low $< 40\%$) display contextual advisories on low-certainty predictions.

---

### 5. Security, Quality Assurance & Frozen Integrity
- **Security & Privacy:** Strictly read-only access (no email writing, editing, or deletion). Credentials and tokens gitignored. Ephemeral in-memory processing with zero database storage of email bodies. Loopback-restricted CORS and bound-validated queries.
- **Automated Test Coverage:** **31 / 31 passing tests** across `test_gmail_pipeline.py` (11), `test_dashboard_api.py` (10), and `test_phase28_hardening.py` (10).
- **Frozen Integrity:** Confirmed zero `.fit()` or `.fit_transform()` calls in the inference path. Cryptographic SHA256 checksums verified for `test.csv` ($N=300$) and `tfidf_logistic_baseline.joblib`. Master notebook `index.ipynb` fully preserved with 77 executed cells.
