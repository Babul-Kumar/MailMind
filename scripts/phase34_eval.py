"""
Phase 34 Evaluation: §34.3-34.7
- OTP generalization tests (§34.3)
- Negative generalization tests (§34.4)
- Modern holdout metrics (§34.5)
- Category breakdown (§34.6)
- v2 vs v3 comparison (§34.7)
"""
import sys, json
from pathlib import Path
from collections import defaultdict, Counter

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix

from backend.app.ml.predictor import load_model, predict_email, predict_batch, invalidate_cached_pipeline
from backend.app.ml.registry import model_registry

invalidate_cached_pipeline()

# ── Load models ──────────────────────────────────────────────────────────────
print("Loading priority-v3 (active)...")
v3_pipeline = load_model()  # active = v3

print("Loading priority-v2 for comparison...")
model_registry.set_active("priority-v2")
invalidate_cached_pipeline()
v2_pipeline = load_model()
model_registry.set_active("priority-v3")
invalidate_cached_pipeline()
print()

# ── §34.3: OTP Generalization Tests ─────────────────────────────────────────
print("=" * 65)
print("§34.3 OTP GENERALIZATION TEST (unseen examples)")
print("=" * 65)

OTP_TESTS = [
    ("A", "Google sign-in code", "Your Google sign-in code is 482913. It expires in 10 minutes."),
    ("B", "Identity verification", "Use 918274 to verify your identity. This code is valid for 5 minutes."),
    ("C", "Continue signing in", "Enter the verification code below to continue signing in to your account. Code: 748291. Expires soon."),
    ("D", "One-time passcode expiry", "Your one-time passcode will expire shortly. Please use it to complete your authentication."),
    ("E", "MFA login code", "Use this MFA code to complete your login: 293847. Valid for 2 minutes."),
    ("F", "Password reset code", "Your password reset code is 391827. Use this code to set a new password. Expires in 10 minutes."),
    ("G", "Banking OTP", "Your banking OTP is 445678. Valid for 5 minutes to complete your transaction. Do not share."),
    ("H", "Admin dashboard login", "Use code 849201 to log in to the admin dashboard. This code expires in 5 minutes."),
]

print(f"\n{'Ex':<4} {'Priority':<10} {'Action':<8} {'Deadline':<30} {'Conf':<8} {'Topic':<12}")
print("-" * 80)
otp_p1_count = 0
otp_action_count = 0
for ex, subj, body in OTP_TESTS:
    r = predict_email({"id": f"otp_{ex}", "subject": subj, "body": body}, v3_pipeline)
    prio = r.get("predicted_priority", "?")
    action = r.get("action_required", False)
    deadline = r.get("deadline_display", "")[:28] if r.get("deadline_detected") else "(none)"
    conf = r.get("confidence", 0.0)
    topic = r.get("topic", "")
    if prio == "P1":
        otp_p1_count += 1
    if action:
        otp_action_count += 1
    flag = "✓" if (prio == "P1" and action) else "✗"
    print(f"{ex:<4} {prio:<10} {str(action):<8} {deadline:<30} {conf:<8.4f} {topic:<12} {flag}")

print(f"\nOTP P1 rate: {otp_p1_count}/{len(OTP_TESTS)} = {otp_p1_count/len(OTP_TESTS)*100:.1f}%")
print(f"OTP action_required rate: {otp_action_count}/{len(OTP_TESTS)} = {otp_action_count/len(OTP_TESTS)*100:.1f}%")

# ── §34.4: Negative Generalization Tests ────────────────────────────────────
print("\n" + "=" * 65)
print("§34.4 NEGATIVE GENERALIZATION TEST (non-actionable security)")
print("=" * 65)

NEG_TESTS = [
    ("N1", "Account verified", "Your account verification was completed successfully. You now have full access."),
    ("N2", "Security settings updated", "Your security settings were updated. Two-factor authentication is now enabled. No action required."),
    ("N3", "Monthly security report", "Your monthly security report is ready. All systems operated normally. No suspicious activity was detected."),
    ("N4", "Account verified yesterday", "Your account was verified yesterday. Welcome to the platform. Explore your dashboard."),
    ("N5", "Previous login verified", "Your previous login verification was successful. No further steps are required from you."),
    ("N6", "Password changed confirm", "Your account password has been successfully changed. If you made this change, no further action is needed."),
    ("N7", "Security compliance", "This is your quarterly security compliance summary. All services passed security benchmarks."),
    ("N8", "2FA enabled confirmation", "Two-factor authentication was successfully enabled on your account. This is a confirmation email."),
]

print(f"\n{'Ex':<4} {'Priority':<10} {'Action':<8} {'Conf':<8} {'IsP1?'}")
print("-" * 50)
neg_not_p1 = 0
neg_not_action = 0
for ex, subj, body in NEG_TESTS:
    r = predict_email({"id": f"neg_{ex}", "subject": subj, "body": body}, v3_pipeline)
    prio = r.get("predicted_priority", "?")
    action = r.get("action_required", False)
    conf = r.get("confidence", 0.0)
    correct = (prio != "P1") and (not action)
    if prio != "P1":
        neg_not_p1 += 1
    if not action:
        neg_not_action += 1
    flag = "✓" if correct else "✗"
    print(f"{ex:<4} {prio:<10} {str(action):<8} {conf:<8.4f} {flag}")

print(f"\nCorrectly NOT P1: {neg_not_p1}/{len(NEG_TESTS)} = {neg_not_p1/len(NEG_TESTS)*100:.1f}%")
print(f"Correctly NOT action: {neg_not_action}/{len(NEG_TESTS)} = {neg_not_action/len(NEG_TESTS)*100:.1f}%")

# ── Load holdouts ────────────────────────────────────────────────────────────
hist_df = pd.read_csv("dataset/processed/test.csv")
hist_texts = (hist_df["subject"].fillna("") + " " + hist_df["body"].fillna("")).tolist()
hist_labels = hist_df["final_label"].tolist()

mod_df = pd.read_csv("dataset/processed/modern_email_holdout_v2.csv")
mod_texts = (mod_df["subject"].fillna("") + " " + mod_df["body"].fillna("")).tolist()
mod_labels = mod_df["final_label"].tolist()

# ── §34.7: v2 vs v3 comparison ───────────────────────────────────────────────
print("\n" + "=" * 65)
print("§34.7 V2 VS V3 COMPARISON")
print("=" * 65)

from sklearn.metrics import accuracy_score, f1_score, recall_score, precision_score

def metrics(labels, preds):
    classes = sorted(set(labels))
    acc = accuracy_score(labels, preds)
    mf1 = f1_score(labels, preds, average="macro", zero_division=0)
    wf1 = f1_score(labels, preds, average="weighted", zero_division=0)
    p1_prec = precision_score(labels, preds, labels=["P1"], average="micro", zero_division=0)
    p1_rec  = recall_score(labels, preds, labels=["P1"], average="micro", zero_division=0)
    p1_f1   = f1_score(labels, preds, labels=["P1"], average="micro", zero_division=0)
    return acc, mf1, wf1, p1_prec, p1_rec, p1_f1

v2_hist_preds = v2_pipeline.predict(hist_texts)
v3_hist_preds = v3_pipeline.predict(hist_texts)
v2_mod_preds  = v2_pipeline.predict(mod_texts)
v3_mod_preds  = v3_pipeline.predict(mod_texts)

v2h = metrics(hist_labels, v2_hist_preds)
v3h = metrics(hist_labels, v3_hist_preds)
v2m = metrics(mod_labels, v2_mod_preds)
v3m = metrics(mod_labels, v3_mod_preds)

print(f"\n{'Dataset':<12} {'Metric':<16} {'v2':>8} {'v3':>8} {'Delta':>8}")
print("-" * 56)
rows = [
    ("Historical", "Accuracy",   v2h[0], v3h[0]),
    ("Historical", "Macro F1",   v2h[1], v3h[1]),
    ("Historical", "Wt F1",      v2h[2], v3h[2]),
    ("Historical", "P1 Prec",    v2h[3], v3h[3]),
    ("Historical", "P1 Recall",  v2h[4], v3h[4]),
    ("Historical", "P1 F1",      v2h[5], v3h[5]),
    ("Modern",     "Accuracy",   v2m[0], v3m[0]),
    ("Modern",     "Macro F1",   v2m[1], v3m[1]),
    ("Modern",     "Wt F1",      v2m[2], v3m[2]),
    ("Modern",     "P1 Recall",  v2m[4], v3m[4]),
    ("Modern",     "P1 F1",      v2m[5], v3m[5]),
]
for ds, metric, v2v, v3v in rows:
    delta = v3v - v2v
    sign = "+" if delta >= 0 else ""
    print(f"{ds:<12} {metric:<16} {v2v:>8.4f} {v3v:>8.4f} {sign}{delta:>7.4f}")

# ── §34.5: Full modern holdout metrics ──────────────────────────────────────
print("\n" + "=" * 65)
print("§34.5 MODERN HOLDOUT METRICS (v3 only, 100 rows)")
print("=" * 65)

print("\nClassification Report (v3 on modern holdout):")
print(classification_report(mod_labels, v3_mod_preds, zero_division=0))

print("Confusion Matrix (P1/P2/P3/P4):")
cm = confusion_matrix(mod_labels, v3_mod_preds, labels=["P1","P2","P3","P4"])
print("         Pred P1  Pred P2  Pred P3  Pred P4")
for i, lbl in enumerate(["True P1","True P2","True P3","True P4"]):
    print(f"  {lbl}  {cm[i]}")

# ── §34.6: Category breakdown ────────────────────────────────────────────────
print("\n" + "=" * 65)
print("§34.6 CATEGORY BREAKDOWN (v3)")
print("=" * 65)

# Map topics to display names
TOPIC_DISPLAY = {
    "otp_auth":       "OTP/Auth",
    "password_reset": "Password Reset",
    "security_alert": "Security Alert",
    "security_info":  "Security Info",
    "payments":       "Payments",
    "deadlines":      "Deadlines",
    "recruitment":    "Recruitment",
    "saas":           "SaaS",
    "academic":       "Academic",
    "newsletter":     "Newsletter",
    "promotional":    "Promotional",
    "informational":  "Informational",
}

topics = mod_df["topic"].tolist()
per_cat = defaultdict(lambda: {"true": [], "pred": [], "act_true": [], "act_pred": []})
action_true = [a == "True" for a in mod_df["expected_action"].tolist()]

for i, (t, l, p) in enumerate(zip(topics, mod_labels, v3_mod_preds)):
    per_cat[t]["true"].append(l)
    per_cat[t]["pred"].append(p)
    per_cat[t]["act_true"].append(action_true[i])

print(f"\n{'Category':<18} {'N':>4} {'Acc':>7} {'P1 Rec':>8} {'P1 corr':>8}")
print("-" * 50)
for cat, data in sorted(per_cat.items()):
    n = len(data["true"])
    acc = sum(t==p for t,p in zip(data["true"],data["pred"])) / n
    p1_true = sum(1 for l in data["true"] if l == "P1")
    p1_corr = sum(1 for l,p in zip(data["true"],data["pred"]) if l=="P1" and p=="P1")
    p1_rec  = p1_corr / p1_true if p1_true > 0 else float("nan")
    p1_rec_str = f"{p1_rec:.2f}" if p1_true > 0 else "  N/A"
    disp = TOPIC_DISPLAY.get(cat, cat)
    print(f"{disp:<18} {n:>4} {acc:>7.4f} {p1_rec_str:>8} {p1_corr:>8}")

# ── Save results ─────────────────────────────────────────────────────────────
results = {
    "otp_generalization": {
        "total": len(OTP_TESTS),
        "p1_count": int(otp_p1_count),
        "action_count": int(otp_action_count),
        "p1_rate": round(otp_p1_count/len(OTP_TESTS)*100, 1),
        "action_rate": round(otp_action_count/len(OTP_TESTS)*100, 1),
    },
    "negative_generalization": {
        "total": len(NEG_TESTS),
        "not_p1_count": int(neg_not_p1),
        "not_action_count": int(neg_not_action),
        "not_p1_rate": round(neg_not_p1/len(NEG_TESTS)*100, 1),
        "not_action_rate": round(neg_not_action/len(NEG_TESTS)*100, 1),
    },
    "historical_holdout": {
        "n": len(hist_labels),
        "v2": {"accuracy": round(v2h[0],4), "macro_f1": round(v2h[1],4), "weighted_f1": round(v2h[2],4),
               "p1_precision": round(v2h[3],4), "p1_recall": round(v2h[4],4), "p1_f1": round(v2h[5],4)},
        "v3": {"accuracy": round(v3h[0],4), "macro_f1": round(v3h[1],4), "weighted_f1": round(v3h[2],4),
               "p1_precision": round(v3h[3],4), "p1_recall": round(v3h[4],4), "p1_f1": round(v3h[5],4)},
    },
    "modern_holdout": {
        "n": len(mod_labels),
        "v2": {"accuracy": round(v2m[0],4), "macro_f1": round(v2m[1],4), "weighted_f1": round(v2m[2],4),
               "p1_recall": round(v2m[4],4), "p1_f1": round(v2m[5],4)},
        "v3": {"accuracy": round(v3m[0],4), "macro_f1": round(v3m[1],4), "weighted_f1": round(v3m[2],4),
               "p1_recall": round(v3m[4],4), "p1_f1": round(v3m[5],4)},
    },
}
out = Path("dataset/models/priority-v3/phase34_eval.json")
out.write_text(json.dumps(results, indent=2))
print(f"\nResults saved to {out}")
print("\n=== DONE ===")
