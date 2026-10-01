# BiLSTM Deep Learning Baseline: Validation Report

**Project:** AI Email Priority Classification Pipeline (CSE472)  
**Experiment:** Deep Learning Baseline 1 — Bidirectional LSTM (`BiLSTMClassifier`)  
**Dataset Reference:** `dataset/processed/gold_human_review_2000.csv`  
**Training Split:** `dataset/processed/train.csv` (70%, $N=1,400$)  
**Validation Split:** `dataset/processed/validation.csv` (15%, $N=300$)  
**Held-Out Test Split:** `dataset/processed/test.csv` (15%, $N=300$) — **Strictly Isolated & Untouched**  
**Saved Model Artifacts:**
- `dataset/models/bilstm_priority_baseline.pt` (PyTorch state_dict checkpoint)
- `dataset/models/bilstm_vocab.joblib` (Vocabulary mapping and tokenization parameters)

---

## 1. Executive Summary & Experimental Protocol

This report documents the implementation and validation evaluation of the **first deep learning baseline (BiLSTM)** for 4-class email priority classification.

### Methodological Safeguards:
1. **Strict Vocabulary Isolation:** The vocabulary (17,830 tokens) was constructed **exclusively from the 1,400 training emails** (`min_freq=2`). Validation and test texts were transformed using `<UNK>=1` for out-of-vocabulary terms.
2. **Class-Weighted Loss:** Balanced class weights were derived strictly from training distribution ($P1=9.7222, P2=0.5255, P3=1.1041, P4=0.9186$), penalizing errors on rare P1 emergencies heavily.
3. **Early Stopping & Checkpoint Serialization:** Training monitored validation Macro F1 across 20 epochs with a patience of 5. The best validation checkpoint (Epoch 10) was restored for evaluation.
4. **Test Set Isolation:** The held-out test set ($N=300$) was **never loaded, evaluated, or inspected**.

---

## 2. Model & Tokenizer Architecture

```
+------------------------------------+---------------------------------------------------------------+
| Component                          | Specification                                                 |
+------------------------------------+---------------------------------------------------------------+
| Tokenization                       | Regex alphanumeric tokenization ([a-zA-Z0-9_'-]+)         |
| Vocabulary Size                    | 17,830 tokens (fitted on Train only, min_freq=2)           |
| Special Tokens                     | <PAD>=0, <UNK>=1                                              |
| Maximum Sequence Length            | 256 tokens (truncated if longer, zero-padded if shorter)|
| Embedding Layer                    | Embedding(num_embeddings=17830, embed_dim=128, padding_idx=0)|
| Recurrent Layer                    | Bidirectional LSTM (input_size=128, hidden_size=64, layers=1)|
| Pooling                            | Concatenation of final forward & backward hidden states       |
| Regularization                     | Dropout(p=0.3)                                              |
| Output Layer                       | Linear(in_features=128, out_features=4) (4 classes)            |
| Total Trainable Parameters         | 2,382,084                                              |
+------------------------------------+---------------------------------------------------------------+
```

---

## 3. Training & Validation Dynamics

```
+------------------------------------+--------------------------+
| Metric                             | Value                    |
+------------------------------------+--------------------------+
| Training Samples                   | 1,400 emails             |
| Validation Samples                 | 300 emails               |
| Batch Size                         | 32                     |
| Optimizer                          | Adam (lr=1e-3, weight_decay=1e-5) |
| Loss Function                      | CrossEntropyLoss (balanced class weights) |
| Total Training Duration            | 71.14 seconds           |
| Total Epochs Completed             | 15                       |
| Best Validation Epoch              | Epoch 10                  |
| Best Train Loss                    | 0.1185                   |
| Best Validation Loss               | 0.9317                   |
| Best Validation Accuracy           | 70.33%                   |
| Best Validation Macro F1           | 0.6932                   |
+------------------------------------+--------------------------+
```

---

## 4. Final Validation Metrics ($N=300$)

Evaluated on the restored Epoch 10 checkpoint:

```
+------------------------------------+--------------------------+
| Metric                             | BiLSTM Validation Score  |
+------------------------------------+--------------------------+
| Overall Validation Accuracy        | 70.33%                   |
| Macro F1 Score                     | 0.6932                   |
| Weighted F1 Score                  | 0.7000                   |
+------------------------------------+--------------------------+
| P1 Precision                       | 75.00%                   |
| P1 Recall                          | 75.00%                   |
| P1 F1 Score                        | 0.7500                   |
| P1 Support                         | 8.0 emails (2.67%)           |
+------------------------------------+--------------------------+
| P2 Precision                       | 74.19%                   |
| P2 Recall                          | 80.42%                   |
| P2 F1 Score                        | 0.7718                   |
| P2 Support                         | 143.0 emails (47.67%)         |
+------------------------------------+--------------------------+
| P3 Precision                       | 64.91%                   |
| P3 Recall                          | 55.22%                   |
| P3 F1 Score                        | 0.5968                   |
| P3 Support                         | 67.0 emails (22.33%)         |
+------------------------------------+--------------------------+
| P4 Precision                       | 66.25%                   |
| P4 Recall                          | 64.63%                   |
| P4 F1 Score                        | 0.6543                   |
| P4 Support                         | 82.0 emails (27.33%)         |
+------------------------------------+--------------------------+
```

### Validation Confusion Matrix ($N=300$)

```
                 Pred_P1  Pred_P2  Pred_P3  Pred_P4  Total_Actual
Actual_P1              6        1        0        1             8
Actual_P2              0      115       13       15           143
Actual_P3              2       17       37       11            67
Actual_P4              0       22        7       53            82
Total_Predicted        8      155       57       80           300
```

---

## 5. Comparative Evaluation: TF-IDF + Logistic Regression vs. BiLSTM

```
+------------------------------------+--------------------------+--------------------------+
| Metric                             | TF-IDF + Logistic Reg.   | BiLSTM Deep Learning     |
+------------------------------------+--------------------------+--------------------------+
| Overall Accuracy                   | 78.67%                   | 70.33%                   |
| Macro F1 Score                     | 0.7514                   | 0.6932                   |
| Weighted F1 Score                  | 0.7752                   | 0.7000                   |
+------------------------------------+--------------------------+--------------------------+
| P1 F1 Score                        | 0.7500 (P=75.0%, R=75.0%)| 0.7500 (P=75.0%, R=75.0%) |
| P2 F1 Score                        | 0.8328 (P=78.4%, R=88.8%)| 0.7718 (P=74.2%, R=80.4%) |
| P3 F1 Score                        | 0.6139 (P=91.2%, R=46.3%)| 0.5968 (P=64.9%, R=55.2%) |
| P4 F1 Score                        | 0.8090 (P=75.0%, R=87.8%)| 0.6543 (P=66.2%, R=64.6%) |
+------------------------------------+--------------------------+--------------------------+
```

---

## 6. Analytical Insights & Failure Mode Analysis

### 6.1 Why Linear Baseline Outperforms Randomly-Initialized BiLSTM on Small Data ($N=1,400$)
1. **Sample Efficiency of TF-IDF n-grams:**  
   The TF-IDF model operates on 66,526 unigram and bigram features, where informative tokens (*"caiso"*, *"crawler"*, *"nominate"*, *"wire"*, *"unsubscribe"*) provide direct linear decision boundaries.
2. **Untrained Word Embeddings in BiLSTM:**  
   With only 1,400 training documents, training a 128-dimensional embedding layer from scratch with 17,830 tokens suffers from extreme parameter sparsity. Many domain-specific words appear only 2–5 times, making it difficult for an uninitialized LSTM to learn robust semantic representations without pretrained embeddings (GloVe/FastText) or contextual attention (Transformers).
3. **P3 $	o$ P2 Boundary Confusion:**  
   Like the linear model, BiLSTM struggles on the subtle distinction between routine status reports and actionable requests (17 P3 emails misclassified as P2).

### 6.2 P1 Emergency Performance
- BiLSTM achieved **75.0% precision** and **75.0% recall** on P1 emergencies (6 out of 8 captured).
- In comparison, Logistic Regression achieved 75.0% precision and 75.0% recall (6/8 captured).

---

## 7. Next Modeling Steps (Held-Out Test Set Remains Untouched)

1. **Transformer Fine-Tuning (DistilBERT):**
   - The primary weakness of BiLSTM on small corpora (uninitialized embeddings) is directly overcome by pretrained contextual language models (`DistilBERT` or `DeBERTa-v3-small`).
   - Transfer learning from pretrained weights will provide rich syntactic and semantic representations from Step 1.
2. **Test Set Protocol:**
   - The test set ($N=300$) remains strictly isolated until the model progression is completed.
