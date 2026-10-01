# DistilBERT Transformer Classifier: Validation Report

**Project:** AI Email Priority Classification Pipeline (CSE472)  
**Experiment:** Section 23 — Pretrained DistilBERT Sequence Classifier (`distilbert-base-uncased`)  
**Gold Benchmark:** `dataset/processed/gold_human_review_2000.csv`  
**Training Split:** `dataset/processed/train.csv` (70%, $N=1,400$)  
**Validation Split:** `dataset/processed/validation.csv` (15%, $N=300$)  
**Held-Out Test Split:** `dataset/processed/test.csv` (15%, $N=300$) — **Strictly Isolated & Untouched**  

---

## 1. Motivation
Following the classical linear baseline (TF-IDF + Logistic Regression, Acc=78.67%, Macro F1=0.7514) and the sequence deep learning baseline (BiLSTM, Acc=70.33%, Macro F1=0.6932), this experiment introduces a pretrained contextual language model: **DistilBERT** (`distilbert-base-uncased`).

The primary motivation is twofold:
1. **Pretrained Semantic Transfer:** Overcome the sample-sparsity bottleneck of BiLSTM, where training 128-dimensional word embeddings from scratch on $N=1,400$ emails led to lower generalization.
2. **Contextual disambiguation of P3 vs P2:** Determine whether bidirectional self-attention can better distinguish actionable workplace requests (P2) from passive informational updates (P3).

---

## 2. Dataset & Split Protocol
- **Dataset Reference:** 2,000 human-reviewed Enron emails with audited and adjudicated ground-truth labels.
- **Split Distribution:**
  - Train: 1,400 emails (P1: 36, P2: 666, P3: 317, P4: 381)
  - Validation: 300 emails (P1: 8, P2: 143, P3: 67, P4: 82)
  - Test: 300 emails — **Completely Isolated & Untouched**
- **Target Variable:** `final_label` (adjudicated label if present, else reviewer label).
- **Class Mapping:** `P1 -> 0`, `P2 -> 1`, `P3 -> 2`, `P4 -> 3`.

---

## 3. Tokenization & Long-Email Truncation Handling
- **Pretrained Tokenizer:** `DistilBertTokenizerFast` from `distilbert-base-uncased` (Vocabulary Size: 30,522 WordPiece tokens). No vocabulary was fitted from our dataset.
- **Input Composition:** `Subject: <subject>

<body>` ensures subject keywords are always positioned within the primary attention window.
- **Truncation Policy:** Sequences are truncated at `max_length = 128` tokens. 
  - Truncated Training Emails: 1,128 / 1400 (80.57%)
  - Truncated Validation Emails: 239 / 300 (79.67%)
- **Rationale:** Preserving the subject prefix and the initial 100+ tokens of the body captures the primary reason for communication in workplace emails without incurring quadratic attention latency on CPU.

---

## 4. Class Imbalance Safeguards
Balanced class weights were calculated **exclusively from the 1,400 training split labels**:
```
P1 Weight (class 0): 9.7222
P2 Weight (class 1): 0.5255
P3 Weight (class 2): 1.1041
P4 Weight (class 3): 0.9186
```
These weights were incorporated into `nn.CrossEntropyLoss` to heavily penalize errors on rare P1 emergencies (2.57% train prevalence).

---

## 5. Model Architecture & Training Configuration
- **Base Architecture:** `DistilBertForSequenceClassification` (`distilbert-base-uncased`)
- **Hidden Dimension:** 768
- **Transformer Layers:** 6
- **Attention Heads:** 12
- **Total Parameters:** 66,956,548
- **Trainable Parameters:** 66,956,548 (End-to-end fine-tuning)
- **Device:** cpu (8 CPU threads)
- **Batch Size:** 16
- **Learning Rate:** 2e-05 (AdamW with linear warmup over 10% steps and weight decay = 0.01)
- **Epochs:** 3
- **Training Duration:** 1170.91 seconds (19.52 min)
- **Best Validation Epoch:** Epoch 3 (Train Loss: 0.6546, Val Loss: 0.7187, Val Macro F1: 0.7144)

---

## 6. Validation Results & Confusion Matrix ($N=300$)

Evaluated on restored Epoch 3 checkpoint:

```
+------------------------------------+--------------------------+
| Metric                             | DistilBERT Score         |
+------------------------------------+--------------------------+
| Overall Validation Accuracy        | 76.33%                   |
| Macro F1 Score                     | 0.7144                   |
| Weighted F1 Score                  | 0.7602                   |
+------------------------------------+--------------------------+
| P1 Precision                       | 54.55%                   |
| P1 Recall                          | 75.00%                   |
| P1 F1 Score                        | 0.6316                   |
| P1 Support                         | 8.0 emails (2.67%)           |
+------------------------------------+--------------------------+
| P2 Precision                       | 82.14%                   |
| P2 Recall                          | 80.42%                   |
| P2 F1 Score                        | 0.8127                   |
| P2 Support                         | 143.0 emails (47.67%)         |
+------------------------------------+--------------------------+
| P3 Precision                       | 67.27%                   |
| P3 Recall                          | 55.22%                   |
| P3 F1 Score                        | 0.6066                   |
| P3 Support                         | 67.0 emails (22.33%)         |
+------------------------------------+--------------------------+
| P4 Precision                       | 75.53%                   |
| P4 Recall                          | 86.59%                   |
| P4 F1 Score                        | 0.8068                   |
| P4 Support                         | 82.0 emails (27.33%)         |
+------------------------------------+--------------------------+
```

### Validation Confusion Matrix
```
                 Pred_P1  Pred_P2  Pred_P3  Pred_P4  Total_Actual
Actual_P1              6        2        0        0             8
Actual_P2              2      115       13       13           143
Actual_P3              3       17       37       10            67
Actual_P4              0        6        5       71            82
Total_Predicted       11      140       55       94           300
```

---

## 7. Multi-Model Comparison Table

```
                       Model Accuracy Macro F1 Weighted F1  P1 F1  P2 F1  P3 F1  P4 F1   P3->P2 Errors
TF-IDF + Logistic Regression   78.67%   0.7514      0.7752 0.7500 0.8328 0.6139 0.8090 24 / 67 (35.8%)
        BiLSTM Deep Learning   70.33%   0.6932      0.7000 0.7500 0.7718 0.5968 0.6543 17 / 67 (25.4%)
      DistilBERT Transformer   76.33%   0.7144      0.7602 0.6316 0.8127 0.6066 0.8068 17 / 67 (25.4%)
```

---

## 8. Detailed Comparative Analysis & P3 $	o$ P2 Confusion

### 8.1 Comparison Against Logistic Regression & BiLSTM
- **BiLSTM Comparison:** DistilBERT demonstrates the substantial benefit of pretrained contextual representations over training recurrent word embeddings from scratch on small corpora ($N=1,400$).
- **Linear Baseline Comparison:** The linear model (TF-IDF + Logistic Regression) benefits from explicitly memorizing 66,526 domain n-grams (e.g., energy trade acronyms, scheduling notices), whereas DistilBERT provides contextual semantic representations.

### 8.2 P3 $	o$ P2 Error Analysis
- In the initial Logistic Regression baseline, **24 of 67 actual P3 emails (35.8%)** were falsely predicted as P2 actionable.
- In the BiLSTM baseline, **17 of 67 actual P3 emails (25.4%)** were predicted as P2.
- In DistilBERT, **17 of 67 actual P3 emails (25.4%)** were predicted as P2.

---

## 9. Limitations & Next Steps
1. **Context Length Constraint:** The current experiment used `max_length = 128` to preserve operational efficiency on CPU. For long legal contracts or extensive regulatory filings, multi-chunk hierarchical aggregation could capture downstream clauses.
2. **Held-Out Test Set Isolation:** The test split ($N=300$) remains untouched. Final evaluation across all three models will occur in the designated test evaluation phase.
