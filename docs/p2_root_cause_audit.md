# CSE472: P2 Priority Root-Cause Diagnosis & Audit Report

## 1. Executive Summary

A comprehensive empirical audit was conducted on 100 live Gmail messages to determine why the **Important (P2)** view currently contains 23 emails.

The investigation conclusively reveals:
- **22 of 23 observed P2 emails were native predictions from the frozen baseline model, while one was promoted by refinement** (Google OAuth Security Alert, which legitimately requires account review).
- **The root cause of the observed P2 inflation was identified** as vocabulary overlap with the Enron training corpus, rather than refinement rule inflation.
- **Zero emails were shifted to P2 from P3 or P1.**

```
┌────────────────────────────────────────────────────────────────────────┐
│                        LIVE P2 INBOX BREAKDOWN                         │
├──────────────────────────────────────┬─────────────┬───────────────────┤
│ Transition                           │ Count       │ Percentage        │
├──────────────────────────────────────┼─────────────┼───────────────────┤
│ original_model_P2 (Native Baseline)  │ 22 emails   │ 95.7%             │
│ P4_to_P2 (Contextual Refinement)     │ 1 email     │ 4.3%              │
│ P3_to_P2                             │ 0 emails    │ 0.0%              │
│ P1_to_P2                             │ 0 emails    │ 0.0%              │
├──────────────────────────────────────┼─────────────┼───────────────────┤
│ Total P2 Emails                      │ 23 emails   │ 100.0%            │
└──────────────────────────────────────┴─────────────┴───────────────────┘
```

**System Architecture:** A frozen ML baseline combined with contextual priority refinement, independent action detection, deadline extraction, and an attention-oriented user interface. The model remains frozen. The action-oriented workflow was insulated from much of the impact through the separate Needs Attention layer.

---

## 2. Why the Frozen Baseline Predicts P2 on Modern Emails

The production baseline model was trained on the corporate Enron email corpus. In that corpus, specific communication and business tokens carry positive linear weights for class P2:
- `call` (+0.0558 weight in Qoder, +0.0186 in ByteByteGo)
- `days` (+0.0329 in Naukri, +0.1009 in Flipkart)
- `review` (+0.0242 in DoraHacks, +0.0392 in ZebPay, +0.0179 in Substack)
- `thanks` / `thank you` (+0.0296 in DoraHacks, +0.0339 in Neon, +0.0275 in ZebPay)
- `billing` / `pay` / `trade` (+0.0239 in Supabase, +0.0445 in ZebPay)
- `access` / `auth` (+0.0230 in PDFAid, +0.0115 in ByteByteGo)

When modern tech newsletters (e.g., *ByteByteGo*, *Substack*, *The Pragmatic Engineer*), platform policy updates (*DoraHacks Terms of Use*, *ZebPay Terms*), and promotional offers (*Flipkart*, *Qoder*) contain these terms, the dot product produces a Softmax output that narrowly selects P2 with moderate-to-low confidence (average confidence: **39.4%**).

---

## 3. Why Sender-Specific & Keyword Rules Are Rejected

Per the design principles of CSE472:
1. **No Sender Hardcoding:** Implementing rules like `Qoder → P3`, `DoraHacks → P3`, `ByteByteGo → P4` or `Google → P2` creates brittle, overfitted systems that fail as senders change.
2. **No Keyword Heuristics:** Keywords like `"security"`, `"assignment"`, or `"terms"` cannot monolithicly dictate priority. A security newsletter is P4, while unauthorized account access is P1/P2.
3. **Sound ML Architecture:** Rather than suppressing valid model outputs with arbitrary overrides, the system treats **Priority**, **Action Required**, and **Deadlines** as independent dimensions.

---

## 4. Architectural Resolution: The Decoupled Triad

To prevent P2 from misleading users into thinking they have 23 urgent tasks:

1. **Clear UI Semantics:**
   - In the sidebar and inbox header, P2 is labeled as **`P2 · Important`** (reflecting the ML classification) rather than an imperative task queue.
2. **Needs Attention Synthesis:**
   - The task-oriented view is **Needs Attention**, defined by:
     $$\text{Needs Attention} = P_1 \lor (P_2 \land \text{action\_required}) \lor (\text{action\_required} \land \text{genuine\_deadline})$$
   - Needs Attention narrowed the 100-email sample to 4 emails requiring attention: 3 actionable P2 items (Google Security Alert, Neon Azure Deletion, Supabase Pause) plus 1 P4 deadline item (Kaggle).
3. **First-Class Deadlines:**
   - Deadlines are extracted and displayed prominently with absolute date and relative time, completely independent of priority classification.

---

## 5. Audit Data Artifacts
- Diagnostic dataset: `dataset/analysis/p2_root_cause_audit.csv`
- Error analysis dataset: `dataset/analysis/refinement_error_analysis.csv`
- Production baseline: `dataset/models/tfidf_logistic_baseline.joblib` (Strictly Frozen)
