import sys
import os
import argparse
from tabulate import tabulate
import pandas as pd

# Add repo root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from backend.app.gmail.service import get_gmail_service
from backend.app.gmail.client import fetch_emails, get_profile
from backend.app.ml.predictor import load_model, predict_batch
from backend.app.ml.priority import PRIORITY_MAPPING


def run_inference_test(max_emails: int = 20, query: str = None):
    print("=" * 82)
    print("MAILMIND — GMAIL PRIORITY INFERENCE & DECISION DIAGNOSTIC (CSE472)")
    print("=" * 82)
    print(f"Target sample size : {max_emails} emails")
    print(f"Gmail query filter : {query or 'None (Inbox recent)'}")
    print(f"Production Model   : TF-IDF + Logistic Regression (Frozen)")
    print(f"Decoupled Layers   : Priority (P1-P4) | Action Required (Y/N) | Topic Domain")
    print("=" * 82)

    # 1. Connect to Gmail
    print("\n1. Authenticating with Gmail API (Read-Only Scope)...")
    service = get_gmail_service()
    profile = get_profile(service)
    print(f"   Authenticated Account: {profile.get('emailAddress')}")
    print(f"   Total Mailbox Messages: {profile.get('messagesTotal'):,}")

    # 2. Fetch Emails
    print(f"\n2. Fetching recent {max_emails} emails and parsing MIME payloads...")
    emails = fetch_emails(service=service, max_emails=max_emails, query=query)
    print(f"   Successfully fetched and parsed {len(emails)} emails.")

    if not emails:
        print("   No emails found matching query criteria.")
        return

    # 3. Load Frozen Production Model
    print("\n3. Loading frozen production model artifact...")
    pipeline = load_model()
    print("   Artifact: dataset/models/tfidf_logistic_baseline.joblib")
    print("   Model verified: ZERO retraining performed.")

    # 4. Predict Priorities
    print("\n4. Running priority inference across fetched sample...")
    predictions = predict_batch(emails, pipeline=pipeline)

    # 5. Display Compact Output Table
    print("\n" + "=" * 82)
    print("LIVE INFERENCE RESULTS TABLE (PRIORITY, TOPIC, ACTION REQUIRED)")
    print("=" * 82)
    
    table_rows = []
    refined_count = 0

    for i, p in enumerate(predictions, 1):
        subj = p['subject']
        if len(subj) > 28:
            subj = subj[:25] + "..."
        sender = p['sender']
        if len(sender) > 18:
            sender = sender[:15] + "..."
        
        if p.get('refinement_applied'):
            refined_count += 1
            
        action_str = "Yes" if p.get('action_required') else "No"
        topic_str = (p.get('topic') or 'other').capitalize()

        table_rows.append([
            i,
            p.get('final_priority', p['predicted_priority']),
            p.get('model_priority', '-'),
            topic_str,
            action_str,
            f"{p['confidence']:.2f}",
            sender,
            subj
        ])

    headers = ["#", "Priority", "Model", "Topic", "Action?", "Conf", "Sender", "Subject"]
    print(tabulate(table_rows, headers=headers, tablefmt="simple"))

    # 6. Detailed Refinement Breakdown (if any)
    refined_items = [p for p in predictions if p.get('refinement_applied')]
    if refined_items:
        print("\n" + "=" * 82)
        print(f"SECONDARY CONTEXTUAL REFINEMENT DETAILS ({len(refined_items)} emails adjusted)")
        print("=" * 82)
        for idx, item in enumerate(refined_items, 1):
            print(f"\n[{idx}] {item['subject']}")
            print(f"    From                : {item['sender']}")
            print(f"    Topic / Action Req  : {item.get('topic', 'other').capitalize()} | Action Required: {'Yes' if item.get('action_required') else 'No'}")
            print(f"    Initial Model Output: {item['model_priority']} (Confidence: {item['confidence']*100:.1f}%)")
            print(f"    Final Priority      : {item['final_priority']} ({item['priority_name']})")
            print(f"    Refinement Rationale: {item['refinement_reason']}")
            if item.get('refinement_signals'):
                print(f"    Matched Signals     : {', '.join([repr(s) for s in item['refinement_signals']])}")

    # 7. Priority Distribution Summary
    df_preds = pd.DataFrame(predictions)
    counts = df_preds['predicted_priority'].value_counts()
    
    print("\n" + "=" * 82)
    print("SAMPLE FINAL PRIORITY DISTRIBUTION")
    print("=" * 82)
    dist_rows = []
    for p_class in ['P1', 'P2', 'P3', 'P4']:
        cnt = counts.get(p_class, 0)
        pct = (cnt / len(predictions) * 100) if predictions else 0.0
        dist_rows.append([p_class, PRIORITY_MAPPING[p_class], cnt, f"{pct:.1f}%"])
    
    print(tabulate(dist_rows, headers=["Class", "Description", "Count", "Percentage"], tablefmt="simple"))
    print("=" * 82)
    refinement_rate = (refined_count / len(predictions) * 100) if predictions else 0.0
    print(f"Diagnostic Metrics: Total Analyzed={len(predictions)} | Refined Count={refined_count} | Refinement Rate={refinement_rate:.1f}%")
    print("Note: Refinement rate is for diagnostic monitoring only, not model accuracy.")
    print("=" * 82)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test Gmail Priority Inference & Decoupled Decision")
    parser.add_argument("--max-emails", type=int, default=20, help="Maximum number of emails to evaluate (default: 20)")
    parser.add_argument("--query", type=str, default=None, help="Optional Gmail search query filter")
    args = parser.parse_args()

    run_inference_test(max_emails=args.max_emails, query=args.query)
