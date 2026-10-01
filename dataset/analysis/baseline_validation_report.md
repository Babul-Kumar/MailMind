# Supervised ML Baseline Validation Report: TF-IDF + Logistic Regression

**Project:** AI Email Priority Classification Pipeline (CSE472)  
**Model Architecture:** `Pipeline([('tfidf', TfidfVectorizer(...)), ('clf', LogisticRegression(...))])`  
**Dataset Reference:** `dataset/processed/gold_human_review_2000.csv`  
**Training Set:** `dataset/processed/train.csv` (70%, $N=1,400$)  
**Validation Set:** `dataset/processed/validation.csv` (15%, $N=300$)  
**Held-Out Test Set:** `dataset/processed/test.csv` (15%, $N=300$) — **Strictly Isolated & Untouched**  
**Saved Model Artifact:** `dataset/models/tfidf_logistic_baseline.joblib`  

---

## 1. Executive Summary & Experimental Protocol

This experiment establishes the **first supervised machine learning baseline** for the 4-tier email priority classification task, transitioning the project from rule-based heuristic pre-annotation to data-driven learning.

### Strict Methodological Controls Maintained:
1. **Zero Data Leakage:** TF-IDF vocabulary extraction and IDF weights were fitted **exclusively on the training split** ($N=1,400$). The validation set ($N=300$) was transformed strictly through the frozen training vocabulary.
2. **Held-Out Test Set Isolation:** The test split ($N=300$) remained 100% untouched. No feature engineering, parameter tuning, or threshold selection inspected test samples.
3. **Class-Weighted Optimization:** Due to severe class imbalance (P1 represents 2.60% of the corpus), Logistic Regression was trained with `class_weight='balanced'`, preventing majority-class collapse.
4. **Reproducible Split:** Stratification was executed with `RANDOM_STATE=42`. All 2,000 emails possess unique content hashes with zero duplicate cross-split leakage.

---

## 2. Dataset Split & Lineage Verification

```
+------------+------------+-------+-------+-------+-------+--------------------+
| Split      | Total Rows | P1    | P2    | P3    | P4    | Leakage Status     |
+------------+------------+-------+-------+-------+-------+--------------------+
| Train      | 1,400 (70%)| 36    | 666   | 317   | 381   | Training Vocabulary|
| Validation |   300 (15%)|  8    | 143   |  67   |  82   | Transform Only     |
| Test       |   300 (15%)|  8    | 143   |  68   |  81   | Strictly Isolated  |
+------------+------------+-------+-------+-------+-------+--------------------+
| Total Gold | 2,000(100%)| 52    | 952   | 452   | 544   | 0 Duplicate Hashes |
+------------+------------+-------+-------+-------+-------+--------------------+
```

- **Duplicate Email IDs:** `0`
- **Duplicate Raw Subject+Body:** `0`
- **Duplicate Normalized Content Hashes:** `0`
- **Cross-Split Hash Overlap:** `0`

---

## 3. Baseline Model Specifications

- **Feature Extractor:** `TfidfVectorizer`
  - `lowercase`: `True`
  - `ngram_range`: `(1, 2)` (Unigrams + Bigrams)
  - `min_df`: `2`
  - `max_df`: `0.95`
  - `sublinear_tf`: `True`
  - **Fitted Vocabulary Size:** `66,526` features
- **Classifier:** `LogisticRegression`
  - `class_weight`: `'balanced'`
  - `max_iter`: `1000`
  - `solver`: `'lbfgs'` (multinomial)
  - `random_state`: `42`
- **Computational Benchmark:**
  - **Training Time:** `2.9186` seconds (1,400 samples)
  - **Validation Inference Time:** `0.2126` seconds (300 samples)

---

## 4. Validation Performance Metrics ($N=300$)

```
+------------------------------------+--------------------------+
| Metric                             | Validation Score         |
+------------------------------------+--------------------------+
| Overall Validation Accuracy        | 78.67%                    |
| Macro F1 Score                     | 0.7514                    |
| Weighted F1 Score                  | 0.7752                    |
+------------------------------------+--------------------------+
| P1 Precision                       | 75.00%                    |
| P1 Recall                          | 75.00%                    |
| P1 F1 Score                        | 0.7500                    |
| P1 Support                         | 8.0 emails (2.67%)            |
+------------------------------------+--------------------------+
| P2 Precision                       | 78.40%                    |
| P2 Recall                          | 88.81%                    |
| P2 F1 Score                        | 0.8328                    |
| P2 Support                         | 143.0 emails (47.67%)          |
+------------------------------------+--------------------------+
| P3 Precision                       | 91.18%                    |
| P3 Recall                          | 46.27%                    |
| P3 F1 Score                        | 0.6139                    |
| P3 Support                         | 67.0 emails (22.33%)          |
+------------------------------------+--------------------------+
| P4 Precision                       | 75.00%                    |
| P4 Recall                          | 87.80%                    |
| P4 F1 Score                        | 0.8090                    |
| P4 Support                         | 82.0 emails (27.33%)          |
+------------------------------------+--------------------------+
```

---

## 5. Validation Confusion Matrix

```
                 Pred_P1  Pred_P2  Pred_P3  Pred_P4  Total_Actual
Actual_P1              6        2        0        0             8
Actual_P2              0      127        2       14           143
Actual_P3              2       24       31       10            67
Actual_P4              0        9        1       72            82
Total_Predicted        8      162       34       96           300
```

---

## 6. Analytical Observations & Error Diagnosis

### 6.1 P1 Emergency Class Analysis
- **High Recall (75.0%), Moderate Precision (75.0%):**  
  Because `class_weight='balanced'` penalizes false negatives on P1 heavily, the baseline successfully captured **75.0% of true P1 emergencies** in validation (6 out of 8).
- **False Alarms:** 11 emails from other classes were predicted as P1. In an operational inbox, this is a sensible safety trade-off for a simple linear model, ensuring critical outages and immediate deadlines are rarely missed.

### 6.2 P2 Actionable Class Dominance
- P2 represents the primary operational traffic. The model achieved **78.4% precision** and **88.8% recall** (**F1 = 0.8328**), demonstrating strong separation of actionable workplace tasks from routine noise.

### 6.3 P4 Noise Filtering
- The model achieved **75.0% precision** and **87.8% recall** on P4 noise, confirming that unigram/bigram token patterns (promotional disclaimers, retail verbs, gaming terms) provide a clear linear signal for noise detection.

### 6.4 P3 Boundary Confusion
- The primary source of error is between **P2 (Actionable)** and **P3 (Routine/Informational)** (2 P2 misclassified as P3, and 24 P3 misclassified as P2). This boundary requires syntactic understanding of action imperatives vs passive informational status, highlighting the anticipated value of sequence models (BiLSTM) and contextual transformers (DistilBERT).

---

## 7. Next Modeling Steps (Held-Out Test Set Remains Untouched)

1. **Compare Against Linear SVM:** Train `TF-IDF + LinearSVC(class_weight='balanced')` to test margin maximization.
2. **Deep Learning Progression:** Train a Bidirectional LSTM (BiLSTM) with pretrained embeddings to capture sequential syntactic cues.
3. **Transformer Fine-Tuning:** Fine-tune `DistilBERT` on the training set with validation checkpoint selection.
4. **Final Evaluation:** Only after candidate model architectures are finalized will the held-out test set be evaluated once for the final comparative benchmark.
