# DistilBERT Long-Context Experiment: Validation Report

**Project:** AI Email Priority Classification Pipeline (CSE472)  
**Experiment:** Section 24 — Controlled DistilBERT Long-Email Context Expansion (MAX_LEN = 256)  
**Gold Benchmark:** `dataset/processed/gold_human_review_2000.csv`  
**Training Split:** `dataset/processed/train.csv` (70%, $N=1,400$)  
**Validation Split:** `dataset/processed/validation.csv` (15%, $N=300$)  
**Held-Out Test Split:** `dataset/processed/test.csv` (15%, $N=300$) — **Strictly Isolated & Untouched**  

---

## 1. Executive Summary & Experimental Rationale

In Section 23, the initial DistilBERT baseline operated with `MAX_LEN = 128` tokens, resulting in a substantial truncation rate of **80.57% in training** and **79.67% in validation**. To address this experimental limitation before finalizing model selection, this controlled experiment **doubles the effective sequence context window to 256 tokens**, expanding substantive body capture while preserving identical model, split, class weights, and optimization settings.

### Experimental Controls:
- **Identical Dataset Splits:** Train ($N=1,400$), Validation ($N=300$). Test ($N=300$) strictly isolated.
- **Identical Model Base:** `distilbert-base-uncased` fine-tuned end-to-end.
- **Identical Balanced Class Weights:** $P1=9.7222, P2=0.5255, P3=1.1041, P4=0.9186$ (train labels only).
- **Identical Optimization:** AdamW (lr = 2e-5, weight_decay = 0.01, linear warmup).
- **Single Variable Changed:** Input sequence context window increased from **128 to 256 tokens**.

---

## 2. Context Window & Truncation Impact

```
+------------------------------------+--------------------------+--------------------------+
| Metric                             | Context = 128 (Sec 23)   | Context = 256 (Sec 24)   |
+------------------------------------+--------------------------+--------------------------+
| Max Sequence Length                | 128 tokens               | 256 tokens (+100% tokens)|
| Training Truncation Rate           | 80.57% (1,128 / 1,400)   | 62.50% (875 / 1400)  |
| Validation Truncation Rate         | 79.67% (239 / 300)       | 62.33% (187 / 300)    |
| Relative Truncation Reduction      | Baseline                 | -18.07% percentage points |
+------------------------------------+--------------------------+--------------------------+
```

---

## 3. Validation Performance ($N=300$, Best Checkpoint: Epoch 2)

```
+------------------------------------+--------------------------+
| Metric                             | DistilBERT (256 Context) |
+------------------------------------+--------------------------+
| Overall Validation Accuracy        | 77.67%                   |
| Macro F1 Score                     | 0.7409                   |
| Weighted F1 Score                  | 0.7727                   |
| Validation Inference Latency       | 37.71 seconds              |
+------------------------------------+--------------------------+
| P1 Precision                       | 66.67%                   |
| P1 Recall                          | 75.00%                   |
| P1 F1 Score                        | 0.7059                   |
| P1 Support                         | 8.0 emails (2.67%)           |
+------------------------------------+--------------------------+
| P2 Precision                       | 80.26%                   |
| P2 Recall                          | 85.31%                   |
| P2 F1 Score                        | 0.8271                   |
| P2 Support                         | 143.0 emails (47.67%)         |
+------------------------------------+--------------------------+
| P3 Precision                       | 70.37%                   |
| P3 Recall                          | 56.72%                   |
| P3 F1 Score                        | 0.6281                   |
| P3 Support                         | 67.0 emails (22.33%)         |
+------------------------------------+--------------------------+
| P4 Precision                       | 78.82%                   |
| P4 Recall                          | 81.71%                   |
| P4 F1 Score                        | 0.8024                   |
| P4 Support                         | 82.0 emails (27.33%)         |
+------------------------------------+--------------------------+
```

### Validation Confusion Matrix
```
                 Pred_P1  Pred_P2  Pred_P3  Pred_P4  Total_Actual
Actual_P1              6        2        0        0             8
Actual_P2              0      122       10       11           143
Actual_P3              3       19       38        7            67
Actual_P4              0        9        6       67            82
Total_Predicted        9      152       54       85           300
```

---

## 4. Multi-Model Benchmark Comparison Table

```
                        Model Accuracy Macro F1 Weighted F1  P1 F1  P2 F1  P3 F1  P4 F1   P3->P2 Errors
 TF-IDF + Logistic Regression   78.67%   0.7514      0.7752 0.7500 0.8328 0.6139 0.8090 24 / 67 (35.8%)
         BiLSTM Deep Learning   70.33%   0.6932      0.7000 0.7500 0.7718 0.5968 0.6543 17 / 67 (25.4%)
     DistilBERT (Context=128)   76.33%   0.7144      0.7602 0.6316 0.8127 0.6066 0.8068 17 / 67 (25.4%)
DistilBERT Long Context (256)   77.67%   0.7409      0.7727 0.7059 0.8271 0.6281 0.8024 19 / 67 (28.4%)
```

---

## 5. Methodological Conclusions & Final Freeze Recommendation

1. **Context Expansion Effect:**
   - Expanding context to 256 tokens captured substantive body content for 525 training emails (37.5%), reducing the truncation bottleneck significantly.
2. **Comparison with TF-IDF + Logistic Regression:**
   - Even with 256 tokens of bidirectional context, the **TF-IDF + Logistic Regression baseline remains the strongest validation performer** (78.67% Accuracy, 0.7514 Macro F1).
   - This provides the empirical evidence requested: on this 2,000-email benchmark, linear models with full n-gram vocabulary features provide superior sample efficiency and discriminative capability over deep sequence models.
3. **Model Freeze Recommendation:**
   - All candidate models (Logistic Regression, BiLSTM, DistilBERT) are now frozen.
   - Proceed to the single, one-time held-out test set evaluation ($N=300$) for final unbiased generalization estimation.
