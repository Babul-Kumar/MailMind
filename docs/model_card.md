# Model Card — MailMind Priority Classifier v5.1

## Model Details
- **Model Name**: MailMind Priority Classifier (`priority-v5.1`)
- **Model Version**: `v5.1` (Production Active)
- **Model Type**: Supervised Text Classification Pipeline (TF-IDF Vectorizer + Multinomial Logistic Regression)
- **Framework**: Python 3.11 / scikit-learn 1.4+
- **Artifact File**: `dataset/models/priority-v5.1-candidate/model.joblib`
- **Artifact SHA-256**: `8524ad73965859ee022f1271caee0040928e7805ab7d32c49b2f26e994f98c06`
- **Release Date**: October 2, 2026
- **License**: Proprietary / Educational Project (CSE472)
- **Contact / Maintainer**: MailMind Engineering Team

---

## Intended Use & Scope
### Primary Intended Uses
- Prioritizing incoming personal and enterprise emails into 4 operational tiers:
  - **P1 (Critical / Urgent)**: Security breaches, account compromises, payment fraud, critical infrastructure outages, immediate OTP verifications.
  - **P2 (Important / Action Required)**: Legitimate authentication alerts, academic deadlines, financial invoices, direct human communication requiring timely follow-up.
  - **P3 (Normal / Routine)**: General organizational updates, routine notifications, non-urgent newsletters, shipping confirmations.
  - **P4 (Low / Promotional)**: Automated marketing campaigns, bulk social media digests, newsletters, cold outreach.
- Identifying explicit temporal commitments and deadlines (e.g., assignment submissions, billing due dates).
- Flagging actionable emails requiring user response, independent of priority tier.

### Out-of-Scope & Non-Intended Uses
- Automated deletion or irreversible triage of user emails without human oversight.
- Spam filtering or malware/phishing attachment analysis (users must rely on standard Gmail native protections).
- Processing non-English emails without prior localized language evaluation.
- High-stakes automated financial or medical decision making based solely on email priority scores.

---

## Training & Dataset Architecture
- **Training Dataset**: Curated Dataset v5.1 (`dataset/v5.1_candidate/` / `dataset/processed/train.csv`)
- **Training Sample Count**: 1,880 rigorously audited and adjudicated email records.
- **Vocabulary Size**: 68,394 unique unigram and bigram tokens with sublinear term-frequency scaling.
- **Holdout Partitioning**:
  - `dataset/processed/test.csv`: 200 frozen historical benchmark emails (SHA-256: `6841cd44901fa56242bf3752257e991fd7ff474ed7e0f7a5d2b7065a0827c138`).
  - `dataset/processed/modern_holdout.csv`: Modern multi-category real-world email holdout.
  - `dataset/processed/newsletter_holdout.csv` & `dataset/processed/social_holdout.csv`: Specialized negative control holdouts.
- **Data Governance**: Zero synthetic data was fabricated. All training samples originated from anonymized benchmarks, contrastive pairs, and human-adjudicated production feedback.

---

## Performance & Evaluation Metrics

### Validation Performance (Train/Val Split)
- **Validation Accuracy**: 80.84%
- **Macro F1-Score**: 0.7974
- **Weighted F1-Score**: 0.8059

| Class | Precision | Recall | F1-Score | Support |
| :--- | :---: | :---: | :---: | :---: |
| **P1 (Critical)** | 0.7500 | 0.8182 | 0.7826 | 11 |
| **P2 (Important)** | 0.8021 | 0.9146 | 0.8547 | 164 |
| **P3 (Routine)** | 0.8455 | 0.6940 | 0.7623 | 134 |
| **P4 (Low)** | 0.7899 | 0.7899 | 0.7899 | 119 |

### Benchmark Safety Gates Evaluation
- **Historical Holdout Accuracy (`test.csv`)**: 82.00% (Threshold: >= 80.0%)
- **Historical Holdout Macro F1 (`test.csv`)**: 0.8048 (Threshold: >= 0.75)
- **Modern Domain P2 Recall**: 100.0% (Threshold: >= 95.0%)
- **Newsletter P2 False Positive Rate**: 1.67% (Threshold: <= 5.0%)
- **Social Digest P2 False Positive Rate**: 0.00% (Threshold: <= 5.0%)
- **Critical P1 Downgrades**: 0 (Zero-tolerance threshold: 0)
- **OTP Verification Retention**: 100.0% (3/3 test vectors retained at P1)
- **Security Alert Recall**: 100.0%
- **Contrastive Boundary Accuracy**: 100.0% (5/5 contrastive test pairs correct)

### Live Shadow Mailbox Evaluation (Phase 48)
- **Messages Evaluated**: 17,329 live mailbox headers.
- **Inference Latency Overhead**: 0.00 ms added latency compared to baseline.
- **Shadow Safety Violations**: 0 security downgrades observed.

---

## Known Limitations & Biases
1. **Language Scope**: Optimized primarily for English-language email communication. Non-English email classification has not been benchmarked.
2. **Context Horizon**: The underlying TF-IDF vectorizer operates on joined subject and snippet text. Very long attachments or body sections beyond the snippet horizon are not processed.
3. **Domain Vocabulary Drift**: New marketing jargon, newly launched SaaS platforms, or novel notification formats may initially be misclassified as P2 or P3 until collected in feedback and reviewed during scheduled offline model releases.
4. **Thread Disconnects**: Independent message-level classification does not incorporate historical reply chain context unless reflected in the subject line or message snippet.

---

## Safety & Governance Controls
- **Refinement Safety Guardrails**: Domain contextual regex rules ensure that critical security alerts, password resets, and OTP verifications cannot be downgraded below P1 or P2 regardless of raw statistical scores.
- **Zero Online Learning**: Production user feedback is stored in an append-only JSONL log (`feedback.jsonl`) for offline human adjudication. The production model never fits weights dynamically at runtime.
- **Immutable Frozen Holdouts**: Test holdout datasets are cryptographically locked with pre-test and post-test SHA-256 assertions.
- **Rollback Baseline**: The previous production baseline (`priority-v4.1`, SHA-256: `09fe269f19ad6afb38e71b56f8c6ee7a386e59605c62c892478400bc09d5cbd0`) is permanently retained on disk for instant, non-destructive fallback.
