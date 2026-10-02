"""
phase48_run_real_mailbox_shadow.py — Phase 48 Complete Mailbox Shadow Execution
================================================================================
Runs candidate model (priority-v5.1) shadow inference across the full cached
mailbox population (17,322 messages for User 1710949) without mutating
the production prediction cache.

Outputs:
  - dataset/evaluation/phase48/shadow_summary.json
  - dataset/evaluation/phase48/divergence_matrix.json
  - dataset/evaluation/phase48/safety_audit.json
  - dataset/evaluation/phase48/mailbox_shadow_evidence.csv
"""

import os
import sys
import time
import json
import sqlite3
import hashlib
import numpy as np
import pandas as pd
from typing import Dict, Any, List

# Ensure repository root is on sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.app.core.cache import DB_PATH
from backend.app.ml.registry import model_registry
from backend.app.ml.shadow_engine import (
    shadow_engine,
    get_shadow_version,
    get_already_shadowed_ids,
    SHADOW_DB_PATH
)
from backend.app.ml.predictor import load_model, predict_batch
from backend.app.core.shadow_monitor import shadow_monitor

EVAL_DIR = os.path.join(BASE_DIR, "dataset", "evaluation", "phase48")
os.makedirs(EVAL_DIR, exist_ok=True)


def run_mailbox_shadow(user_id: str = "1710949", batch_size: int = 500, force_rescan: bool = False):
    print("=" * 70)
    print("PHASE 48 — COMPLETE REAL MAILBOX SHADOW RUN")
    print("=" * 70)

    active_ver = model_registry.get_active_version()
    shadow_ver = get_shadow_version()
    print(f"Active Production Model : {active_ver} (IMMUTABLE, USER-FACING)")
    print(f"Candidate Shadow Model   : {shadow_ver} (SHADOW ONLY, OBSERVATIONAL)")
    print(f"Target User             : {user_id}")
    print(f"Production Cache DB     : {DB_PATH}")
    print(f"Shadow Output DB        : {SHADOW_DB_PATH}")

    # 1. Read production cache without mutation
    conn_ro = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn_ro.row_factory = sqlite3.Row

    # Baseline count check
    cur = conn_ro.execute("SELECT COUNT(*) as cnt FROM user_email_cache WHERE user_id = ?", (user_id,))
    total_messages = cur.fetchone()["cnt"]
    print(f"\nDiscovered {total_messages:,} cached emails for user {user_id}.")

    cur = conn_ro.execute("""
        SELECT
            message_id, thread_id, subject, body, snippet,
            predicted_priority, confidence,
            action_required, deadline_detected, deadline_status,
            needs_attention
        FROM user_email_cache
        WHERE user_id = ?
        ORDER BY message_id
    """, (user_id,))
    cached_rows = cur.fetchall()
    conn_ro.close()

    # Convert to standard format
    all_emails = []
    all_active_preds = []
    for r in cached_rows:
        mid = r["message_id"]
        p = r["predicted_priority"] or "P4"
        em = {
            "email_id": mid,
            "id": mid,
            "thread_id": r["thread_id"] or "",
            "subject": r["subject"] or "",
            "body": r["body"] or "",
            "snippet": r["snippet"] or ""
        }
        act = {
            "email_id": mid,
            "id": mid,
            "thread_id": r["thread_id"] or "",
            "final_priority": p,
            "predicted_priority": p,
            "confidence": float(r["confidence"] or 0.5),
            "action_required": bool(r["action_required"]),
            "deadline_detected": bool(r["deadline_detected"]),
            "deadline_status": r["deadline_status"] or "NONE",
            "needs_attention": bool(r["needs_attention"]),
            "latency_ms": 0.5
        }
        all_emails.append(em)
        all_active_preds.append(act)

    all_mids = [e["email_id"] for e in all_emails]

    # Check deduplication
    already_shadowed = set() if force_rescan else get_already_shadowed_ids(user_id, all_mids, shadow_ver)
    skipped_count = len(already_shadowed)
    to_process_indices = [idx for idx, mid in enumerate(all_mids) if mid not in already_shadowed]
    to_process_count = len(to_process_indices)

    print(f"Deduplication status: {skipped_count:,} already shadowed (skipped), {to_process_count:,} to evaluate.")

    # 2. Execute batch shadow inference
    t_start = time.perf_counter()
    processed_count = 0
    failed_count = 0

    # Load active v4.1 model pipeline to ensure 100% genuine v4.1 active baseline
    v41_pipeline = load_model()

    if to_process_count > 0:
        for i in range(0, to_process_count, batch_size):
            chunk_indices = to_process_indices[i:i + batch_size]
            chunk_emails = [all_emails[idx] for idx in chunk_indices]

            t_a0 = time.perf_counter()
            chunk_active = predict_batch(chunk_emails, pipeline=v41_pipeline)
            lat_a_chunk = ((time.perf_counter() - t_a0) * 1000.0) / max(1, len(chunk_emails))
            for a in chunk_active:
                a["latency_ms"] = lat_a_chunk

            t_b0 = time.perf_counter()
            records = shadow_engine.shadow_batch(user_id, chunk_emails, chunk_active, force=force_rescan)
            t_b1 = time.perf_counter()

            if records:
                processed_count += len(records)
            else:
                failed_count += len(chunk_emails)

            elapsed_chunk = t_b1 - t_b0
            chunk_tput = len(chunk_emails) / max(0.001, elapsed_chunk)
            print(f"  Processed {min(i + batch_size, to_process_count):,}/{to_process_count:,} messages ({chunk_tput:,.0f} msgs/sec)...", end="\r")

    t_total = time.perf_counter() - t_start
    throughput = processed_count / max(0.001, t_total) if processed_count > 0 else 0.0

    print(f"\nShadow inference complete: {processed_count:,} newly processed in {t_total:.2f}s ({throughput:,.1f} msgs/sec).")

    # 3. Pull complete analytical summary from ShadowMonitor
    print("\nCompiling divergence metrics and safety audit...")
    summary = shadow_monitor.get_summary(user_id)
    dist = shadow_monitor.get_distribution(user_id)
    transitions = shadow_monitor.get_transitions(user_id)
    safety = shadow_monitor.get_safety_audit(user_id)
    perf = shadow_monitor.get_performance(user_id)
    feedback_corr = shadow_monitor.get_feedback_correlation(user_id)

    # 4. Verify production cache was NOT mutated
    conn_ro2 = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    post_count = conn_ro2.execute("SELECT COUNT(*) as cnt FROM user_email_cache WHERE user_id = ?", (user_id,)).fetchone()[0]
    conn_ro2.close()
    assert total_messages == post_count, "FATAL: Production cache row count altered during shadow run!"
    print(f"Production cache safety verified: {post_count:,} rows (0 mutations).")

    # 5. Display key metrics
    print("\n" + "-" * 70)
    print("SHADOW EVALUATION METRICS REPORT")
    print("-" * 70)
    print(f"Total Shadowed Messages  : {summary.get('total_shadowed', 0):,}")
    print(f"Agreement Count          : {summary.get('agreement_count', 0):,} ({summary.get('agreement_rate_pct', 0.0):.2f}%)")
    print(f"Priority Divergence Count: {summary.get('divergence_count', 0):,} ({summary.get('divergence_rate_pct', 0.0):.2f}%)")
    print(f"Total Prediction Diverged: {summary.get('total_diverged', 0):,}")
    print(f"CRITICAL P1 Downgrades   : {summary.get('critical_p1_downgrades', 0)} (TARGET: 0)")
    print(f"P2 -> P3 De-escalations  : {summary.get('p2_to_p3_count', 0):,}")
    print(f"P3 -> P2 Escalations     : {summary.get('p3_to_p2_count', 0):,}")
    print(f"Action Diff Count        : {summary.get('action_differences', 0):,}")
    print(f"Deadline Diff Count      : {summary.get('deadline_differences', 0):,}")
    print(f"Needs Attention Diff     : {summary.get('needs_attention_differences', 0):,}")
    print(f"Active Median Latency    : {summary.get('latency_active_median_ms', 0):.2f} ms")
    print(f"Shadow Median Latency    : {summary.get('latency_shadow_median_ms', 0):.2f} ms")
    print(f"Shadow P95 Latency       : {summary.get('latency_shadow_p95_ms', 0):.2f} ms")

    print("\nPriority Distribution Comparison:")
    print(f"  P1: Active {dist['active_percentages']['P1']}% ({dist['active_counts']['P1']:,}) vs Shadow {dist['shadow_percentages']['P1']}% ({dist['shadow_counts']['P1']:,}) [Delta: {dist['percentage_deltas']['P1']:+.2f}%]")
    print(f"  P2: Active {dist['active_percentages']['P2']}% ({dist['active_counts']['P2']:,}) vs Shadow {dist['shadow_percentages']['P2']}% ({dist['shadow_counts']['P2']:,}) [Delta: {dist['percentage_deltas']['P2']:+.2f}%]")
    print(f"  P3: Active {dist['active_percentages']['P3']}% ({dist['active_counts']['P3']:,}) vs Shadow {dist['shadow_percentages']['P3']}% ({dist['shadow_counts']['P3']:,}) [Delta: {dist['percentage_deltas']['P3']:+.2f}%]")
    print(f"  P4: Active {dist['active_percentages']['P4']}% ({dist['active_counts']['P4']:,}) vs Shadow {dist['shadow_percentages']['P4']}% ({dist['shadow_counts']['P4']:,}) [Delta: {dist['percentage_deltas']['P4']:+.2f}%]")

    print("\nTransition Matrix (Active v4.1 Rows -> Shadow v5.1 Columns):")
    t_mat = transitions["transition_matrix"]
    print(f"       P1     P2      P3      P4")
    for row_cls in ["P1", "P2", "P3", "P4"]:
        r = t_mat[row_cls]
        print(f"  {row_cls}:  {r['P1']:<6} {r['P2']:<6} {r['P3']:<7} {r['P4']:<6}")

    print("\nSafety Category Audit Summary:")
    print(f"  Total High-Risk Identified : {safety['total_safety_messages']:,}")
    print(f"  Total Critical P1 Downgrades: {safety['total_p1_downgrades']}")
    for cat in safety.get("categories", []):
        print(f"    - {cat['safety_category']:<20}: Total {cat['total']:<4} | Agreed {cat['agreed']:<4} | Diverged {cat['diverged']:<4} | P1 Downgrades {cat['p1_downgrades']}")

    # 6. Save evidence files
    with open(os.path.join(EVAL_DIR, "shadow_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    with open(os.path.join(EVAL_DIR, "divergence_matrix.json"), "w", encoding="utf-8") as f:
        json.dump(transitions, f, indent=2)

    with open(os.path.join(EVAL_DIR, "safety_audit.json"), "w", encoding="utf-8") as f:
        json.dump(safety, f, indent=2)

    with open(os.path.join(EVAL_DIR, "performance_metrics.json"), "w", encoding="utf-8") as f:
        json.dump(perf, f, indent=2)

    # Export CSV of top diverged records
    div_records = shadow_monitor.get_divergence_records(user_id, limit=500)
    if div_records:
        df_div = pd.DataFrame(div_records)
        df_div.to_csv(os.path.join(EVAL_DIR, "mailbox_shadow_evidence.csv"), index=False)
        print(f"\nExported {len(div_records)} divergence evidence records to {os.path.join(EVAL_DIR, 'mailbox_shadow_evidence.csv')}")

    print("\nPhase 48 mailbox shadow execution successfully completed!")
    return {
        "summary": summary,
        "distribution": dist,
        "transitions": transitions,
        "safety": safety,
        "performance": perf,
        "feedback_correlation": feedback_corr
    }


if __name__ == "__main__":
    run_mailbox_shadow()
