import os
import sys
import time
import json
import psutil
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.app.core.session import session_manager
from backend.app.gmail.service import get_user_gmail_service
from backend.app.gmail.scan_engine import scan_manager, MailboxScanJob, ScanJobState
from backend.app.core.cache import user_email_cache

SESSION_ID = "0mIcF1YhMP1FyXoZtAmaM6rhHnL3imAcCR5kT4Agys4"


def main():
    print("=" * 60)
    print("MAILMIND — REAL GMAIL MAILBOX VALIDATION")
    print("=" * 60)

    sess = session_manager.get_session(SESSION_ID)
    if not sess:
        print(f"Error: Session {SESSION_ID} not found.")
        sys.exit(1)

    user_id = sess.user_id
    email_addr = sess.email
    print(f"Authenticated User: {email_addr} (User ID: {user_id})")

    service = get_user_gmail_service(session=sess)
    profile = service.users().getProfile(userId="me").execute()
    print(f"Gmail Profile messagesTotal: {profile.get('messagesTotal')}")
    print(f"Gmail Profile threadsTotal:  {profile.get('threadsTotal')}")
    print(f"Gmail Profile historyId:     {profile.get('historyId')}")

    process = psutil.Process()
    peak_memory_mb = process.memory_info().rss / (1024 * 1024)

    print("\n--- STAGE 1: FULL MAILBOX SCAN ---")
    start_time = time.perf_counter()

    # Create and execute the scan job
    job = MailboxScanJob(
        user_id=user_id,
        service=service,
        scope="mailbox",
        mode="full",
        force_rescan=False,
        batch_size=100
    )

    import threading
    worker = threading.Thread(target=job.execute, daemon=True)
    worker.start()

    last_print = 0
    while worker.is_alive():
        cur_mem = process.memory_info().rss / (1024 * 1024)
        if cur_mem > peak_memory_mb:
            peak_memory_mb = cur_mem

        state = dict(job.state)
        now = time.time()
        if now - last_print >= 5:
            last_print = now
            print(
                f"[{state.get('status')}] Discovered: {state.get('discovered', 0)} | "
                f"Analyzed: {state.get('analyzed', 0)}/{state.get('total', 0)} "
                f"({state.get('newly_analyzed', 0)} new, {state.get('cached', 0)} cached, {state.get('failed', 0)} failed) | "
                f"Progress: {state.get('progress_percent', 0.0):.1f}% | "
                f"Mem: {cur_mem:.1f} MB (Peak: {peak_memory_mb:.1f} MB) | "
                f"Elapsed: {state.get('elapsed_seconds', 0.0):.1f}s",
                flush=True
            )
        time.sleep(1.0)

    worker.join()
    final_state = dict(job.state)
    end_time = time.perf_counter()
    total_duration = end_time - start_time

    cur_mem = process.memory_info().rss / (1024 * 1024)
    if cur_mem > peak_memory_mb:
        peak_memory_mb = cur_mem

    print("\n" + "=" * 60)
    print("STAGE 1 SCAN RESULTS:")
    print("=" * 60)
    print(f"Status:                     {final_state.get('status')}")
    print(f"Mailbox messages discovered: {final_state.get('discovered')}")
    print(f"Pages scanned:              {final_state.get('pages_scanned')}")
    print(f"Already cached:             {final_state.get('cached')}")
    print(f"Newly analyzed:             {final_state.get('newly_analyzed')}")
    print(f"Failed:                     {final_state.get('failed')}")
    print(f"Gmail API calls:            {final_state.get('api_calls')}")
    print(f"Retry count:                {final_state.get('retry_count')}")
    print(f"Total scan time:            {total_duration:.2f} sec")
    throughput = (final_state.get('newly_analyzed', 0) / max(0.001, total_duration))
    print(f"Average throughput:         {throughput:.1f} emails/sec")
    print(f"Peak memory:                {peak_memory_mb:.2f} MB")
    print(f"Cache hit rate:             {final_state.get('cache_hit_rate', 0.0):.2f}%")

    # Verify SQLite cache
    _, total_in_db = user_email_cache.query_emails(user_id, page_size=1)
    print(f"Final cache count in SQLite:{total_in_db}")

    print("\n--- STAGE 2: SUBSEQUENT INCREMENTAL SYNC REFRESH ---")
    t_inc_start = time.perf_counter()
    inc_job = MailboxScanJob(
        user_id=user_id,
        service=service,
        scope="mailbox",
        mode="incremental",
        force_rescan=False,
        batch_size=100
    )
    inc_state = inc_job.execute()
    t_inc_end = time.perf_counter()
    inc_dur = t_inc_end - t_inc_start

    print("=" * 60)
    print("INCREMENTAL SYNC RESULTS:")
    print("=" * 60)
    print(f"Status:                     {inc_state.get('status')}")
    print(f"Mailbox messages discovered: {inc_state.get('discovered')}")
    print(f"Already cached:             {inc_state.get('cached')}")
    print(f"Newly analyzed:             {inc_state.get('newly_analyzed')}")
    print(f"Failed:                     {inc_state.get('failed')}")
    print(f"Cache hit rate:             {inc_state.get('cache_hit_rate'):.2f}%")
    print(f"Duration:                   {inc_dur:.2f} sec")
    print("=" * 60)

    # Save summary json
    summary_path = os.path.join(BASE_DIR, "real_gmail_validation_report.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump({
            "user_email": email_addr,
            "user_id": user_id,
            "gmail_messages_total": profile.get("messagesTotal"),
            "stage_1_full_scan": {
                "discovered": final_state.get("discovered"),
                "pages_scanned": final_state.get("pages_scanned"),
                "already_cached": final_state.get("cached"),
                "newly_analyzed": final_state.get("newly_analyzed"),
                "failed": final_state.get("failed"),
                "api_calls": final_state.get("api_calls"),
                "retry_count": final_state.get("retry_count"),
                "total_duration_sec": round(total_duration, 2),
                "throughput_emails_per_sec": round(throughput, 1),
                "peak_memory_mb": round(peak_memory_mb, 2),
                "cache_hit_rate": final_state.get("cache_hit_rate"),
                "sqlite_cache_count": total_in_db
            },
            "stage_2_incremental_sync": {
                "discovered": inc_state.get("discovered"),
                "already_cached": inc_state.get("cached"),
                "newly_analyzed": inc_state.get("newly_analyzed"),
                "failed": inc_state.get("failed"),
                "cache_hit_rate": inc_state.get("cache_hit_rate"),
                "duration_sec": round(inc_dur, 2)
            }
        }, f, indent=2)
    print(f"Saved validation report to: {summary_path}")


if __name__ == "__main__":
    main()
