# CSE472 Viva Voce Comprehensive Question & Answer Bank

**Project:** AI Email Priority Classification System & Real-Time Triage Dashboard  
**Author:** Babul Kumar  
**Course:** CSE472: Natural Language Processing / Applied Artificial Intelligence  
**Coverage:** 30 In-Depth Technical Questions Across All Project Dimensions  

---

### 1. What is the core problem your project addresses?
**Answer:** The project addresses information overload and urgency asymmetry in email communication. In professional environments, high-stakes operational emergencies (P1) are submerged under high volumes of routine updates (P3) and promotional noise (P4). Traditional keyword filters fail because marketing emails borrow urgent phrasing (*"URGENT: Sale ends tonight"*), while legal disclaimers inflate false alarms. The project solves this by constructing a statistical NLP classifier that categorizes emails into a four-tier operational taxonomy based on urgency, actionable demand, and operational consequence.

---

### 2. Explain the four-tier priority taxonomy (P1 to P4).
**Answer:**
- **P1 (Critical / Urgent):** Severe operational disruptions, system outages, security breaches, or direct executive emergencies requiring immediate response.
- **P2 (Important / Actionable):** Direct task assignments, deadlines, client inquiries, and meeting requests requiring action within 24–48 hours.
- **P3 (Routine / Informational):** Status reports, meeting notes, project tracking digests, and broadcast announcements requiring reading but no immediate action.
- **P4 (Low / Promotional / Noise):** Marketing blasts, product discounts, newsletters, spam, and automated transactional receipts.

---

### 3. What were your dataset sources, and how did you prevent data leakage?
**Answer:** The dataset was constructed using multi-signal corporate emails from the Enron Corpus and structured Email Importance datasets. To prevent data leakage:
1. Exact text and hash duplicates were eliminated prior to partitioning.
2. The dataset was partitioned into fixed, stratified splits: Train ($N=1,400$, 70%), Validation ($N=300$, 15%), and Test ($N=300$, 15%).
3. All feature extractors (TF-IDF vectorizer vocabulary, inverse document frequencies, and label encoders) were fit **strictly on the training split**. The validation and held-out test sets were transformed using frozen parameters.
4. The test set was sealed and evaluated strictly once during Phase 25.

---

### 4. What was the 200-row human adjudication pass, and why was it necessary?
**Answer:** Initial heuristic-to-reviewer agreement was distorted by ambiguous boundary cases, such as marketing emails using urgent language or administrative updates mislabeled as P2. Rather than overriding labels with automated heuristics, a 200-email sample was reviewed by an independent adjudicator. Each disputed row was reviewed against standardized guidelines, establishing `adjudicated_label` and `adjudication_notes` while preserving the original `reviewer_label`. This resolved boundary distortions, established ground-truth clarity, and raised heuristic-benchmark alignment from 65.0% to 69.5%.

---

### 5. What is the class distribution of the 2,000 gold emails, and what challenge does it present?
**Answer:** In the authoritative 2,000-email benchmark (`gold_human_review_2000.csv`):
- P1: 52 emails (2.60%)
- P2: 952 emails (47.60%)
- P3: 452 emails (22.60%)
- P4: 544 emails (27.20%)
The primary challenge is **severe class imbalance**: genuine P1 emergencies constitute only 2.6% of real email traffic. If a model simply ignored P1, it could still achieve ~97.4% accuracy on that subset. Therefore, we used class-weighted cross-entropy loss, balanced class weights, and prioritized Macro F1 and per-class recall over overall accuracy.

---

### 6. Why did you use Macro F1 and Weighted F1 in addition to Accuracy?
**Answer:**
- **Accuracy** measures the overall fraction of correct predictions, which is heavily dominated by the majority classes (P2 and P4).
- **Macro F1** calculates the unweighted arithmetic mean of F1 scores across all four classes:
  $$	ext{Macro F1} = rac{1}{4} \sum_{k=1}^4 	ext{F1}_k$$
  This treats the rare P1 class (2.6%) with equal importance to the common P2 class (47.6%), penalizing models that fail to identify emergencies.
- **Weighted F1** weights each class's F1 score by its support in the dataset, providing a balanced metric of overall operational effectiveness.

---

### 7. How did you calibrate your heuristic candidate generator from V1 to V2?
**Answer:** In V1, the heuristic engine flagged 46 candidate P1s out of 200 benchmark emails, resulting in an 84.8% false-positive rate due to corporate legal disclaimers containing words like *"notify immediately and destroy"*. In V2:
1. Implemented regex-based legal and confidentiality boilerplate stripping.
2. Enforced a **Dual-Condition Gate** for P1: requiring both explicit crisis vocabulary (e.g., *outage, breach, failure*) AND a hard immediate deadline.
3. Added promotional negation suppressors (e.g., detecting *unsubscribe, discount, deal*).
This reduced P1 false alarms by 67.4% and boosted P2 actionable recall from 47.2% to 67.6% (and 80.0% on the adjudicated benchmark). V2 was then frozen as a pre-annotation candidate generator.

---

### 8. Explain the feature extraction setup for the TF-IDF baseline.
**Answer:** We used scikit-learn's `TfidfVectorizer` configured with:
- `ngram_range=(1, 2)`: Captures both unigrams (*"urgent"*, *"outage"*) and bigrams (*"action required"*, *"system failure"*).
- `sublinear_tf=True`: Replaces term frequency $tf$ with $1 + \log(tf)$ to dampen the impact of repeated words in long emails.
- `min_df=2`: Excludes idiosyncratic tokens appearing in only a single email.
- `max_features=None`: Yielded a comprehensive vocabulary of $66,526$ unique N-gram features extracted strictly from the 1,400 training examples.

---

### 9. Why did you use Logistic Regression as your linear baseline?
**Answer:** Multinomial Logistic Regression is the gold standard linear classifier for text classification:
1. **Convex Optimization:** Optimizing the cross-entropy loss with $L_2$ regularization is convex, guaranteeing convergence to a global optimum.
2. **Calibrated Probabilities:** The softmax function yields true posterior probability distributions $P(y=k \mid \mathbf{x})$, enabling confidence scoring.
3. **Class Weighting:** Supports `class_weight='balanced'` to scale loss inversely proportional to class frequencies, countering the 2.6% P1 imbalance.
4. **Interpretability:** Learned coefficients $	heta_{k, j}$ provide direct mathematical feature attribution for every priority class.

---

### 10. Describe the architecture and training of the BiLSTM model.
**Answer:** Built in PyTorch:
- **Input:** Tokenized sequences padded/truncated to 128 tokens.
- **Embedding Layer:** 128-dimensional learned embeddings initialized randomly.
- **Recurrent Layer:** 2-layer Bidirectional LSTM with 128 hidden units per direction (total hidden size = 256), with spatial dropout of 0.3.
- **Pooling Head:** Concatenation of global average pooling and max pooling over time.
- **Classifier:** Fully connected layer with Cross-Entropy Loss and Adam optimizer ($	ext{lr}=10^{-3}$, weight decay $=10^{-4}$) trained over 15 epochs with validation early stopping.
- **Result:** Validation accuracy: 70.33%, Macro F1: 0.6932.

---

### 11. Describe your DistilBERT model and fine-tuning setup.
**Answer:** We used `distilbert-base-uncased` (66 million parameters) from Hugging Face Transformers:
- Sequence classification head with 4 output logits.
- Tokenizer: WordPiece with padding, truncation, and special tokens (`[CLS]`, `[SEP]`).
- Optimizer: AdamW with weight decay $0.01$ and learning rate $2 	imes 10^{-5}$.
- Schedule: Linear warmup over 10% of training steps followed by linear decay.
- Batch size: 16, mixed precision enabled, trained over 3 epochs with checkpointing on validation Macro F1.

---

### 12. What was the controlled context experiment comparing DistilBERT-128 vs. DistilBERT-256?
**Answer:** In Phase 24, we hypothesized that truncating emails to 128 tokens discarded critical context located in the middle or end of corporate emails. We trained an identical DistilBERT architecture with max sequence length extended to 256 tokens:
- **DistilBERT-128:** Validation Acc: 76.33%, Macro F1: 0.7144, Weighted F1: 0.7602.
- **DistilBERT-256:** Validation Acc: 77.67%, Macro F1: 0.7409, Weighted F1: 0.7727.
Extended context improved validation Macro F1 by +0.0265, confirming that longer sequences help capture actionable requests in multi-paragraph emails. However, on the held-out test set, DistilBERT-256 reached 78.33% accuracy, still trailing the linear baseline.

---

### 13. What were the final results on the held-out test set?
**Answer:** Evaluated on $N=300$ held-out test emails (`dataset/processed/test.csv`):
- **TF-IDF + Logistic Regression:** **Accuracy: 80.67%**, **Macro F1: 0.7943**, **Weighted F1: 0.8005**
- **DistilBERT (Context=256):** Accuracy: 78.33%, Macro F1: 0.7490, Weighted F1: 0.7511
- **DistilBERT (Context=128):** Accuracy: 77.00%, Macro F1: 0.7530, Weighted F1: 0.7577
- **BiLSTM:** Accuracy: 74.00%, Macro F1: 0.7496, Weighted F1: 0.7395
The linear model achieved superior performance across every composite metric.

---

### 14. Why did TF-IDF + Logistic Regression outperform deep transformers on your benchmark?
**Answer:** Three core scientific factors explain this result:
1. **Sample Efficiency:** DistilBERT has 66M parameters. With $N=1,400$ training examples, the parameter-to-sample ratio is ~47,400:1, leading to subtle overfitting on idiosyncratic phrasing. Regularized logistic regression has far fewer effective degrees of freedom and generalizes with lower variance.
2. **Lexical Salience:** Email priority is primarily determined by explicit lexical tokens (*"system down"*, *"emergency"*, *"unsubscribe"*, *"discount"*). TF-IDF N-grams capture these exact combinations directly without needing complex relational attention.
3. **Subword Fragmentation:** DistilBERT's WordPiece tokenizer fragments domain-specific terms (server paths, error codes, disclaimers) into subwords, diluting attention, whereas TF-IDF treats them as discrete N-gram features.

---

### 15. How does inference latency compare across the models?
**Answer:** On the 300 test emails using standard CPU hardware:
- **TF-IDF + Logistic Regression:** 0.36 seconds total (~1.2 ms per email).
- **BiLSTM:** 0.23 seconds total (~0.77 ms per email).
- **DistilBERT-128:** 18.03 seconds total (~60.1 ms per email).
- **DistilBERT-256:** 36.45 seconds total (~121.5 ms per email).
The linear baseline is over **100x faster** than DistilBERT-256 on CPU, enabling immediate real-time inbox triage without GPU accelerators.

---

### 16. How does the Google Gmail OAuth 2.0 flow work in your system?
**Answer:** Implemented in `src/gmail_client.py`:
1. The app reads OAuth client secrets from `google_auth/credentials.json`.
2. It requests an authorization code via local web server (`InstalledAppFlow.from_client_secrets_file`).
3. Upon user consent in the browser, tokens are exchanged and cached locally in `google_auth/token.json`.
4. Subsequent requests use `google.auth.transport.requests.Request` to automatically refresh expired access tokens using the refresh token.

---

### 17. Why is the Gmail OAuth scope restricted to `gmail.readonly`?
**Answer:** Under the principle of least privilege, priority classification requires only reading message metadata and bodies. Restricting the scope to `https://www.googleapis.com/auth/gmail.readonly` guarantees that the application is technically incapable of sending, editing, deleting, or archiving emails. This ensures total data protection and eliminates the possibility of destructive side effects.

---

### 18. How do you handle MIME parsing for multipart emails?
**Answer:** The Gmail API returns MIME messages as nested payload trees. In `src/gmail_client.py`, `_extract_body()` recursively walks the parts:
- For `text/plain`, it base64-url decodes the raw bytes into UTF-8 text.
- If plain text is absent, it decodes `text/html` and sanitizes it using regex/HTML parsers to strip markup, CSS, and scripts while preserving text content.
- If parts are nested inside `multipart/alternative` or `multipart/mixed`, recursion extracts the substantive text body.
- Edge cases (missing subject, empty bodies) return sanitized fallbacks (`"(No Subject)"`, `""`).

---

### 19. How does the FastAPI backend pre-warm the model?
**Answer:** Rather than loading the 3.7MB model joblib file from disk during each incoming HTTP request, `src/app.py` utilizes FastAPI's `lifespan` context manager:
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _GLOBAL_MODEL
    _GLOBAL_MODEL = load_model()
    yield
```
This loads the vectorizer and classifier into memory at server startup, ensuring $0.00$s disk reload overhead and sub-millisecond local inference per request.

---

### 20. What does "strictly frozen" mean in your production inference path?
**Answer:** It means the production model artifact (`tfidf_logistic_baseline.joblib`) is strictly static. During inference, neither the vectorizer nor the classifier calls `.fit()` or `.fit_transform()`. The model only executes `.transform()`, `.predict()`, and `.predict_proba()`. Automated unit tests (`test_10_no_fit_called_in_inference_path` and `test_09_no_fit_called_under_any_condition`) dynamically mock `.fit()` and assert it is never called.

---

### 21. How is model explainability computed mathematically?
**Answer:** For any email with TF-IDF vector $\mathbf{x} = [X_{0, 1}, X_{0, 2}, \dots, X_{0, D}]$ and predicted priority class $k$, the logit score before softmax is:
$$z_k = b_k + \sum_{j=1}^D X_{0, j} \cdot 	heta_{k, j}$$
The contribution of each individual feature $j$ to the prediction of class $k$ is given by the linear product:
$$	ext{Signal Weight}_j = X_{0, j} \cdot 	heta_{k, j}$$
`extract_feature_signals()` sorts all features where $	ext{Signal Weight}_j > 0$ in descending order and returns the top terms (e.g., `["outage", "server", "critical"]`) as explainable evidence.

---

### 22. How does the dashboard communicate uncertainty to the user?
**Answer:**
1. Every card displays an explicit confidence percentage derived from the maximum softmax probability.
2. Predictions are categorized into confidence tiers: **High** ($\ge 60\%$), **Moderate** ($40\% - 59\%$), and **Low** ($< 40\%$).
3. Low-confidence predictions display an amber warning chip and an explicit contextual advisory note: `"(Note: Model confidence is relatively low; review email context)"`.
This transparency prevents users from placing blind trust in marginal predictions.

---

### 23. What security measures prevent credential and token exposure?
**Answer:**
1. `.gitignore` explicitly excludes `google_auth/credentials.json`, `google_auth/token.json`, `.env`, and `.pytest_cache/`.
2. The `/api/profile` endpoint returns only the authenticated email address and message count; it never returns access tokens, refresh tokens, or client secrets.
3. Automated test `test_01_gitignore_security` and `test_02_no_tokens_leaked_in_profile` continuously assert that tokens cannot be committed or leaked.

---

### 24. How did you harden CORS and API input parameters?
**Answer:**
- **CORS:** Instead of wildcard `allow_origins=["*"]`, CORS is restricted to local loopback origins (`127.0.0.1:8000`, `localhost:8000`, `127.0.0.1:3000`, `localhost:3000`, `localhost:5173`).
- **Input Validation:** In `/api/emails`, Pydantic enforces:
  - `max_emails: int = Query(default=20, ge=1, le=100)`: Restricts requests to 1–100 emails to prevent memory exhaustion.
  - `query: Optional[str] = Query(default=None, max_length=200)`: Caps search query length at 200 characters to prevent query injection.

---

### 25. How do you guarantee the test set cannot be modified by the live system?
**Answer:**
1. The held-out test set (`dataset/processed/test.csv`) is completely decoupled from the production application code.
2. Ingestion paths write only to ephemeral in-memory objects, never modifying CSV files on disk.
3. Automated regression tests verify that `test.csv` has exactly 300 rows and matches its frozen SHA256 checksum: `6841cd44901fa56242bf3752257e991fd7ff474ed7e0f7a5d2b7065a0827c138`.

---

### 26. What happens if the Gmail API is unreachable or rate-limited?
**Answer:** If the Gmail API raises an exception (e.g., timeout, network failure, HTTP 429 rate limit):
1. `src/app.py` catches the exception cleanly.
2. It returns a standardized HTTP 502 Bad Gateway response with JSON:
   `{"status": "error", "message": "Gmail API connection error: ...", "detail": "..."}`.
3. The frontend catches the 502 response and renders a user-friendly error banner with a "Retry" button.
4. Internal stack traces are logged to the console but never leaked to the client.

---

### 27. What are the key limitations of your current system?
**Answer:**
1. **Context Beyond Text:** The system analyzes email text and headers, but does not incorporate the sender's relational social graph (e.g., email exchange frequency or organizational hierarchy).
2. **Long Email Chains:** Deep nested reply chains (>50 messages) are currently evaluated as a concatenated text block without hierarchical thread modeling.
3. **Domain Vocabulary Specificity:** The vocabulary was trained on corporate and general communications; highly specialized domains (e.g., medical clinical trials or legal filings) would require domain-specific vocabulary tuning.

---

### 28. How would you implement an Active Learning loop in future work?
**Answer:** Users could click a "Correct Priority" button in the dashboard to reassign misclassified emails. The corrected sample would be staged in a secure feedback buffer. Once the buffer reaches a threshold (e.g., 100 verified corrections), an offline training job would re-run cross-validation and evaluate against the frozen test set. If the candidate model improves Macro F1 without regressing P1 recall, it would be promoted to production via versioned model artifacts.

---

### 29. How did you verify the entire project before declaring it complete?
**Answer:**
1. **Automated Testing:** 31 comprehensive unit and integration tests across three test suites (`test_gmail_pipeline.py`, `test_dashboard_api.py`, `test_phase28_hardening.py`) achieved a 100% pass rate.
2. **Cryptographic Checksums:** Verified SHA256 hashes of `test.csv`, model joblib weights, and Section 25 reports.
3. **Master Notebook:** Executed all 77 cells across Sections 1 to 26 in `index.ipynb`.
4. **Live Verification:** Queried all endpoints on the running FastAPI server (`/api/health`, `/api/model-info`, `/api/profile`, `/api/emails`) with live Gmail ingestion.

---

### 30. What was your most significant scientific takeaway from this project?
**Answer:** The most compelling finding was that **benchmark quality and sample efficiency supersede model scale in domain-specific tasks**. While modern NLP leans toward massive deep transformers, fine-tuning a 66-million parameter model like DistilBERT on 1,400 examples yielded lower test Macro F1 (0.7551 vs 0.7943) than a regularized linear model. The investment in human adjudication and clean feature representations produced a faster, more interpretable, and more accurate production system.
