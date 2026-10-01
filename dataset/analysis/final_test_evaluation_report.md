# Section 25: Final Held-Out Test Evaluation Report

**Project:** AI Email Priority Classification Pipeline (CSE472)  
**Evaluation Scope:** Single, Unbiased Held-Out Test Set Evaluation ($N=300$)  
**Dataset Reference:** `dataset/processed/test.csv`  
**Model State:** All models, hyperparameters, and feature pipelines **STRICTLY FROZEN**  

---

## 1. Executive Summary & Verification Protocol

This report provides the definitive, unbiased generalization evaluation of all four candidate models on the held-out test set ($N=300$). 
In strict compliance with machine learning best practices:
1. **Zero Data Leakage:** The test set was never loaded, inspected, or evaluated prior to this section.
2. **Zero Retraining or Tuning:** All model weights, vocabulary files, tokenizer rules, and classification thresholds were frozen exactly as established during the validation phase.
3. **Primary Model Pre-Selection:** In accordance with standard methodology, model selection was decided **exclusively on the validation benchmark**, where **TF-IDF + Logistic Regression** was selected as the primary production architecture (Validation Accuracy: 78.67%, Macro F1: 0.7514).

### Test Set Verification:
- **Total Test Samples:** 300 emails
- **Missing Labels:** 0
- **Class Distribution:**
  - **P1 (Critical / Urgent):** 8 emails (2.67%)
  - **P2 (Actionable / Important):** 143 emails (47.67%)
  - **P3 (Routine / Informational):** 68 emails (22.67%)
  - **P4 (Low / Noise / Promotional):** 81 emails (27.00%)

---

## 2. Validation vs. Test Generalization Benchmark

```
                       Model Validation_Accuracy Test_Accuracy Diff_Accuracy Validation_Macro_F1 Test_Macro_F1 Diff_Macro_F1 Validation_Weighted_F1 Test_Weighted_F1
TF-IDF + Logistic Regression              78.67%        80.67%        +2.00%              0.7514        0.7943       +0.0429                 0.7752           0.8005
                      BiLSTM              70.33%        74.00%        +3.67%              0.6932        0.7496       +0.0564                 0.7000           0.7395
      DistilBERT Context=128              76.33%        76.00%        -0.33%              0.7144        0.7530       +0.0386                 0.7602           0.7577
      DistilBERT Context=256              77.67%        75.33%        -2.34%              0.7409        0.7551       +0.0142                 0.7727           0.7511
```

---

## 3. Detailed Final Test Performance Metrics ($N=300$)

```
+-------------------------------+------------+------------+------------+---------------+---------------+---------------+---------------+
| Model                         | Test Acc   | Macro F1   | Wt. F1     | P1 F1 (P / R) | P2 F1 (P / R) | P3 F1 (P / R) | P4 F1 (P / R) |
+-------------------------------+------------+------------+------------+---------------+---------------+---------------+---------------+
| TF-IDF + Logistic Regression  | 80.67%     | 0.7943     | 0.8005     | 0.8235 (77.8%/87.5%) | 0.8366 (78.5%/89.5%) | 0.6909 (90.5%/55.9%) | 0.8263 (80.2%/85.2%) |
| BiLSTM                        | 74.00%     | 0.7496     | 0.7395     | 0.8235 (77.8%/87.5%) | 0.7778 (77.2%/78.3%) | 0.7007 (69.6%/70.6%) | 0.6962 (71.4%/67.9%) |
| DistilBERT (Context=128)      | 76.00%     | 0.7530     | 0.7577     | 0.7778 (70.0%/87.5%) | 0.7817 (78.7%/77.6%) | 0.6406 (68.3%/60.3%) | 0.8118 (77.5%/85.2%) |
| DistilBERT (Context=256)      | 75.33%     | 0.7551     | 0.7511     | 0.8235 (77.8%/87.5%) | 0.7889 (78.1%/79.7%) | 0.6250 (66.7%/58.8%) | 0.7831 (76.5%/80.2%) |
+-------------------------------+------------+------------+------------+---------------+---------------+---------------+---------------+
```

---

## 4. Special Error & Failure Mode Analysis

### 4.1 Rare Emergency Detection: P1 Analysis (Actual N = 8 emails)
*Statistical Caution: With only 8 P1 emails in the test split, each individual sample represents 12.5% of recall.*
```
+-------------------------------+-------+-------+-------+----------+-----------+--------+---------+
| Model                         | TP    | FP    | FN    | FAR (%)  | Precision | Recall | P1 F1   |
+-------------------------------+-------+-------+-------+----------+-----------+--------+---------+
| TF-IDF + Logistic Regression  | 7     | 2     | 1     | 0.68%    | 77.78%    | 87.50% | 0.8235  |
| BiLSTM                        | 7     | 2     | 1     | 0.68%    | 77.78%    | 87.50% | 0.8235  |
| DistilBERT (Context=128)      | 7     | 3     | 1     | 1.03%    | 70.00%    | 87.50% | 0.7778  |
| DistilBERT (Context=256)      | 7     | 2     | 1     | 0.68%    | 77.78%    | 87.50% | 0.8235  |
+-------------------------------+-------+-------+-------+----------+-----------+--------+---------+
```

### 4.2 Semantic Boundary Confusion: P3 $	o$ P2 Error Analysis (Actual N = 68 emails)
```
+-------------------------------+-------------------+---------------------+
| Model                         | P3 -> P2 Errors   | Error Percentage    |
+-------------------------------+-------------------+---------------------+
| TF-IDF + Logistic Regression  | 22 / 68          | 32.35%              |
| BiLSTM                        | 14 / 68          | 20.59%              |
| DistilBERT (Context=128)      | 20 / 68          | 29.41%              |
| DistilBERT (Context=256)      | 21 / 68          | 30.88%              |
+-------------------------------+-------------------+---------------------+
```

---

## 5. Confusion Matrices ($N=300$)

### Confusion Matrix: TF-IDF + Logistic Regression
```
                 Pred_P1  Pred_P2  Pred_P3  Pred_P4  Total_Actual
Actual_P1              7        1        0        0             8
Actual_P2              1      128        4       10           143
Actual_P3              1       22       38        7            68
Actual_P4              0       12        0       69            81
Total_Predicted        9      163       42       86           300
```

### Confusion Matrix: BiLSTM
```
                 Pred_P1  Pred_P2  Pred_P3  Pred_P4  Total_Actual
Actual_P1              7        1        0        0             8
Actual_P2              1      112       13       17           143
Actual_P3              1       14       48        5            68
Actual_P4              0       18        8       55            81
Total_Predicted        9      145       69       77           300
```

### Confusion Matrix: DistilBERT Context=128
```
                 Pred_P1  Pred_P2  Pred_P3  Pred_P4  Total_Actual
Actual_P1              7        1        0        0             8
Actual_P2              2      111       16       14           143
Actual_P3              1       20       41        6            68
Actual_P4              0        9        3       69            81
Total_Predicted       10      141       60       89           300
```

### Confusion Matrix: DistilBERT Context=256
```
                 Pred_P1  Pred_P2  Pred_P3  Pred_P4  Total_Actual
Actual_P1              7        1        0        0             8
Actual_P2              1      114       14       14           143
Actual_P3              1       21       40        6            68
Actual_P4              0       10        6       65            81
Total_Predicted        9      146       60       85           300
```



---

## 6. Final Model Selection & Methodological Conclusions

1. **Pre-Selected Model Performance on Test:**
   - **TF-IDF + Logistic Regression** was selected based on validation performance.
   - Its test performance confirmed robust generalization with minimal generalization gap between validation and test splits.
2. **Transformer Generalization:**
   - Both DistilBERT variants demonstrated consistent behavior with their validation benchmarks.
3. **Statistical Caution & Sound Science:**
   - The test set consists of 300 emails. Differences of 1–2 percentage points are within normal sample variance.
   - In accordance with rigorous ML methodology, the final operational model is **TF-IDF + Logistic Regression**, selected on validation and verified on test.

---
*End of Model Development Pipeline. The test set remains frozen and untouched.*
