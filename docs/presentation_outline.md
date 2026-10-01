# CSE472 Final Presentation Outline: AI Email Priority Classification System

**Presenter:** Babul Kumar  
**Course:** CSE472 — Natural Language Processing / Applied Artificial Intelligence  
**Duration:** 10–12 Minutes  
**Slide Deck Structure:** 15 Slides + Live System Demonstration  

---

### Slide 1: Title & Academic Context
- **Title:** AI Email Priority Classification System & Real-Time Inbox Triage Dashboard
- **Presenter:** Babul Kumar
- **Course:** CSE472: Natural Language Processing / Applied Artificial Intelligence
- **Core Contribution:** End-to-end pipeline spanning rigorous human benchmark curation ($N=2,000$), progressive ML benchmarking (TF-IDF, BiLSTM, DistilBERT), and real-time read-only Gmail API integration with model-grounded explainability.
- **Visual / Demo:** Title slide with system architecture preview badge and course credentials.
- **Verbal Explanation:** *"Good morning/afternoon. Today I am presenting my CSE472 capstone project: the AI Email Priority Classification System. This project bridges rigorous natural language processing research with production systems engineering, taking a real-world email problem from corpus curation and human adjudication through deep learning experiments and into a live, read-only Gmail triage dashboard."*

---

### Slide 2: Problem Statement
- **Information Asymmetry:** Professional inboxes receive hundreds of daily messages with wildly divergent urgency.
- **Cognitive Overload:** Critical operational emergencies (e.g., system outages) are submerged under marketing newsletters, promotional blasts, and automated notifications.
- **High-Cost Delayed Response:** Missing a P1 critical event causes real operational downtime and SLA penalties.
- **Visual / Demo:** Split visual: Overloaded chaotic inbox on the left vs. Structured four-tier priority triage on the right.
- **Verbal Explanation:** *"The fundamental problem is not just email volume; it is information asymmetry. A 50% discount email and a server outage notification land in the same inbox. In high-stakes environments, missing a time-sensitive issue can cause severe operational and financial damage."*

---

### Slide 3: Motivation & Heuristic Limitations
- **The Failure of Traditional Filters:** Keyword-based rules fail because promotional mail actively mimics emergency language (*"URGENT: 50% discount ends tonight!"*).
- **Subject Line Masking:** Substantive action requests are often hidden behind bland subject lines like *"Quick update"* or *"Meeting"*.
- **Boilerplate Legal Distortion:** Automated legal confidentiality disclaimers (*"notify sender immediately and delete"*) trigger false emergency alarms.
- **The Need for Statistical Learning:** Priority is a composite function of urgency, required action, and operational consequence.
- **Visual / Demo:** Concrete snippet of a promotional email flagged as urgent by keyword matching vs. correctly suppressed by contextual ML.
- **Verbal Explanation:** *"Why not just use simple keyword filters? Because modern promotional marketing routinely hijacks urgent vocabulary. Furthermore, corporate disclaimers that say 'notify sender immediately' artificially inflate priority. We need statistical NLP models that weigh lexical features across the full text while respecting contextual boundaries."*

---

### Slide 4: End-to-End System Architecture
- **Ingestion:** Google Gmail API with strict `gmail.readonly` OAuth 2.0 scope.
- **MIME Extraction:** Recursive multipart decoder extracting clean UTF-8 plaintext with sanitized HTML fallback.
- **Frozen ML Engine:** Pre-warmed TF-IDF + Logistic Regression pipeline ($66,526$ N-gram features).
- **Explainability Layer:** Mathematical feature attribution ($X_{0, j} \cdot 	heta_{k, j}$) extracting top positive signal tokens.
- **Serving & UI:** Asynchronous FastAPI backend delivering real-time predictions to a responsive Single-Page Dashboard.
- **Visual / Demo:** End-to-end architectural block diagram showing data flow from Gmail servers to browser client.
- **Verbal Explanation:** *"Here is our end-to-end architecture. Starting at the top, we securely ingest raw messages via Google's Gmail API under a strictly read-only scope. The MIME parser decodes the multipart payload, feeds the normalized text into our pre-warmed, frozen ML inference engine, extracts lexical explanations, and streams structured JSON to our FastAPI backend and reactive web dashboard."*

---

### Slide 5: Dataset Provenance & Data Preparation
- **Corpus Sources:** Multi-signal corporate communications from the Enron Corpus and structured Email Importance datasets.
- **Deduplication:** Removal of exact hash duplicates, reply chains, and redundant forwards.
- **Boilerplate Legal Sanitization:** Regex-based removal of standard legal and confidentiality notices before scoring.
- **Data Leakage Prevention:** Strict isolation of features, no test set contamination, and frozen training boundaries.
- **Visual / Demo:** Flowchart illustrating raw email ingestion, deduplication, regex boilerplate stripping, and train/val/test partitioning.
- **Verbal Explanation:** *"Our ground truth began with real corporate email corpora. We instituted strict data cleaning, including duplicate removal and automated stripping of recurring legal footers. Crucially, we enforced strict data leakage controls: all feature extractors and vocabulary limits were fit strictly on the training partition."*

---

### Slide 6: Human Annotation & Adjudication Benchmark
- **Authoritative Benchmark:** 2,000 emails independently reviewed by human annotators (`gold_human_review_2000.csv`).
- **Four-Tier Operational Taxonomy:**
  - **P1 (Critical / Urgent):** 52 emails (2.6%) — Outages, security incidents, emergency blockers.
  - **P2 (Important / Actionable):** 952 emails (47.6%) — Direct deliverables, deadlines, client requests.
  - **P3 (Routine / Informational):** 452 emails (22.6%) — Status digests, meeting notes, automated updates.
  - **P4 (Low / Promotional / Noise):** 544 emails (27.2%) — Marketing, cold outreach, spam, receipts.
- **The 200-Row Adjudication Pass:** Human adjudicator resolved disputed edge cases, separating label noise from genuine model errors.
- **Visual / Demo:** Bar chart of the 2,000-email class distribution highlighting the realistic 2.6% rarity of P1 crises.
- **Verbal Explanation:** *"To train reliable models, we established an authoritative 2,000-email human ground truth. Notice the class distribution: P1 emergencies represent just 2.6% of real email traffic. This extreme rarity reflects corporate reality and dictates that we evaluate models on Macro F1 rather than raw accuracy. Disputed boundary cases were resolved via a dedicated 200-row human adjudication pass."*

---

### Slide 7: Heuristic Rule Calibration (V1 to V2)
- **V1 Baseline Heuristic:** Rule engine suffered from an 84.8% false-positive rate on P1 (46 predicted P1s vs 8 actual).
- **V2 Engineering Enhancements:**
  - Enforced dual-condition crisis gating (explicit operational disruption + immediate hard deadline).
  - Added promotional negation filters (`unsubscribe`, `discount`, `deal`).
  - Implemented imperative action detection in email bodies.
- **Outcome:** Reduced P1 false alarms by **67.4%** and increased P2 actionable recall to **80.0%**.
- **Freezing at V2:** Frozen as a pre-annotation candidate generator; stopped before supervised training.
- **Visual / Demo:** Confusion matrix comparison: V1 (46 P1 candidate alerts) vs. V2 (15 P1 candidate alerts).
- **Verbal Explanation:** *"Before training machine learning models, we developed a heuristic rule engine to understand domain signals. Version 1 flagged 46 emails as P1 when only 8 were real. In Version 2, we introduced dual-condition gating and promotional suppression, dropping false alarms by 67% and boosting P2 recall to 80%. We then froze V2 to prevent heuristic leakage into our supervised phase."*

---

### Slide 8: Machine Learning Progression & Candidate Models
- **Four Evaluated Architectures:**
  1. **TF-IDF + Logistic Regression:** Sublinear TF, unigram/bigram ($66,526$ features), balanced class weights, $C=1.0$.
  2. **Bidirectional LSTM (PyTorch):** 128-dim learned embeddings, 2-layer BiLSTM ($h=128$), spatial dropout ($0.3$), pooling head.
  3. **DistilBERT Sequence Classifier (SeqLen=128):** Pretrained `distilbert-base-uncased` fine-tuned with AdamW ($	ext{lr}=2	imes 10^{-5}$).
  4. **DistilBERT Long Context (SeqLen=256):** Extended sequence window to capture downstream body context in longer corporate emails.
- **Controlled Validation Progression:** Systematic evaluation across validation split ($N=300$).
- **Visual / Demo:** Model architecture diagram comparing sparse linear classification against recurrent and transformer pipelines.
- **Verbal Explanation:** *"We progressed through four modeling paradigms: a linear TF-IDF baseline, a deep recurrent BiLSTM trained in PyTorch, and two pretrained DistilBERT transformer models with 128- and 256-token context windows. All models were trained strictly on the 1,400 training split and evaluated on the 300 validation split."*

---

### Slide 9: Final Held-Out Evaluation (Section 25)
- **Held-Out Test Results ($N=300$, Strictly Evaluated Once):**
  - **TF-IDF + Logistic Regression:** **80.67% Accuracy**, **0.7943 Macro F1**, **0.8005 Weighted F1**.
  - **DistilBERT (256):** 78.33% Accuracy, 0.7490 Macro F1, 0.7511 Weighted F1.
  - **DistilBERT (128):** 77.00% Accuracy, 0.7337 Macro F1, 0.7577 Weighted F1.
  - **BiLSTM:** 74.00% Accuracy, 0.7496 Macro F1, 0.7395 Weighted F1.
- **Scientific Takeaway:** Linear model achieved the highest accuracy, macro F1, and class F1 across all priority tiers.
- **Why Linear Models Won:** High lexical salience, sample efficiency on $N=1,400$, and resistance to overfitting compared to 66M parameters.
- **Inference Speed:** TF-IDF + Logistic Regression executed in 0.36s for all 300 test emails (~1.2ms/email) vs. 36.45s for DistilBERT-256 (>100x speedup).
- **Visual / Demo:** Comparative bar chart of Test Accuracy, Macro F1, and CPU Latency.
- **Verbal Explanation:** *"In Phase 25, we unsealed the held-out test set of 300 emails. The empirical findings were definitive: TF-IDF with regularized Logistic Regression won across every single metric, achieving 80.67% accuracy and 0.7943 Macro F1. Why did a classical linear model beat a 66-million parameter transformer? First, sample efficiency: with 1,400 training examples, DistilBERT overfits subtle phrasing. Second, email priority is lexically anchored: phrases like 'server down' or 'unsubscribe' are decisive signals that linear models capture perfectly. Third, it is over 100 times faster on CPU."*

---

### Slide 10: Production Engineering & Real-Time Gmail Ingestion
- **Authentication:** OAuth 2.0 with minimal privilege: `https://www.googleapis.com/auth/gmail.readonly`.
- **Parsing:** Recursive MIME payload extraction handles plain text and HTML alternatives with graceful fallbacks.
- **Model Pre-Warming:** FastAPI lifespan startup loads the frozen joblib pipeline once into RAM ($0.00$s reload overhead).
- **Zero Retraining Guarantee:** Inference pipeline strictly calls `.predict()` and `.predict_proba()`; zero `.fit()` calls.
- **Visual / Demo:** Code snippet of FastAPI lifespan handler and recursive MIME traversal logic.
- **Verbal Explanation:** *"To operationalize this model, we built a production backend in FastAPI. We connected to the user's live Gmail account using a read-only OAuth scope. When the server launches, a lifespan handler pre-warms the frozen model into memory. Crucially, our inference path contains zero training logic—it executes strictly read-only predictions in under 15 milliseconds."*

---

### Slide 11: Live Dashboard Demonstration
- **Real-Time Synchronization:** Fetches live email threads directly from user inbox.
- **Dynamic Triage Bar:** Visual distribution of P1 (Critical), P2 (Actionable), P3 (Routine), and P4 (Promotional).
- **Instant Client-Side Filtering:** Interactive priority tabs, search query input, and multi-criteria sorting.
- **Master-Detail Layout:** Inspect subject, sender, RFC 2822 timestamps, and full decoded plain-text bodies.
- **Visual / Demo:** Live walkthrough of the responsive dashboard running at `http://127.0.0.1:8000`.
- **Verbal Explanation:** *"Here is the live dashboard running at localhost:8000. Clicking 'Sync Inbox' ingests and classifies the latest emails in real time. The top triage bar summarizes priority distribution, while priority chips allow instant filtering. When we click an email card, the detail panel displays the parsed text, model confidence, and contributing signals."*

---

### Slide 12: Model-Grounded Explainability & Confidence UX
- **Mathematical Attribution:** Features are extracted directly from the logistic regression decision boundary:
  $$	ext{Contribution}_{j} = X_{0, j} \cdot 	heta_{k, j}$$
- **Visual Signal Chips:** Renders top positive lexical drivers (e.g., `['urgent', 'deadline', 'client']`).
- **Tiered Confidence:** Categorized into High ($\ge 60\%$), Moderate ($40\% - 59\%$), and Low ($< 40\%$).
- **Contextual Advisory:** Low-confidence predictions display an explicit warning: `"(Note: Model confidence is relatively low; review email context)"`.
- **Visual / Demo:** Screenshot of the email detail modal highlighting the Signal Chips and Confidence Indicator.
- **Verbal Explanation:** *"AI systems in corporate communication must be transparent. We implemented exact mathematical feature attribution derived directly from our linear model's learned weights. The dashboard highlights the top lexical signals responsible for the prediction. Furthermore, if model confidence falls below 40%, the system explicitly alerts the user that human review is recommended."*

---

### Slide 13: Security, Privacy & System Hardening
- **Zero Write Privileges:** App cannot compose, send, archive, or delete user emails.
- **Credential Protection:** `credentials.json` and `token.json` are excluded from git via strict `.gitignore`.
- **Ephemeral Processing:** Email bodies are processed purely in volatile RAM; zero emails are stored in databases or log files.
- **Hardened CORS & Input Bounds:** API restricted to local loopback origins; parameters validated (`1 <= max_emails <= 100`).
- **Sanitized Errors:** Internal server errors never leak stack traces or file system paths to the client.
- **Visual / Demo:** Table of security hardening checks verified by automated unit tests.
- **Verbal Explanation:** *"Security was a core design priority. The system requests strictly read-only access. Email contents are processed ephemerally in RAM and never saved to disk or external databases. CORS is locked down to local loopback addresses, and all error handlers return sanitized messages without leaking system internals."*

---

### Slide 14: Limitations & Production Challenges
- **Domain Adaptation:** Vocabulary learned from corporate data may require re-anchoring for technical bug trackers or personal mail.
- **Context Truncation:** Very long threads (>50 replies) require hierarchical summarization.
- **Sender Social Graph:** Current model relies purely on text; incorporating sender frequency and reply history would enhance P2/P3 separation.
- **Single-User Scope:** Currently configured for individual desktop OAuth sessions.
- **Visual / Demo:** Diagram showing future integration points: Social Graph, Thread Aggregator, and Active Learning loop.
- **Verbal Explanation:** *"Every engineering system has trade-offs. Our current model evaluates text semantics but does not yet incorporate sender social graphs or relationship frequency. Furthermore, while the model excels on corporate communication, adapting to specialized medical or legal domains would benefit from domain-specific tuning."*

---

### Slide 15: Conclusion & Pedagogical Takeaways
- **Academic Rigor:** Built a fully documented, 77-cell reproducible trajectory from raw corpus to deployed application.
- **Empirical Principle:** High-quality human adjudication and sample-efficient linear models can outperform massive neural architectures on domain-specific classification tasks.
- **Engineering Completeness:** 31 automated tests passing with 100% success rate; complete cryptographic verification of frozen artifacts.
- **Visual / Demo:** Final summary slide with test verification badge, GitHub repository link, and Q&A prompt.
- **Verbal Explanation:** *"In conclusion, this project demonstrated that in practical NLP, data quality and benchmark adjudication matter far more than model complexity. A regularized linear model, when properly trained on high-quality human ground truth, achieved 80.67% accuracy, superior macro F1, and sub-15ms latency. Thank you, and I look forward to your questions."*
