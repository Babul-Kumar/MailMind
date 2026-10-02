import time
import json
import logging
from typing import Dict, Any, Optional
from googleapiclient.errors import HttpError
from backend.app.core.cache import user_email_cache

logger = logging.getLogger("mailmind.cache_migration")


def migrate_thread_ids_for_user(
    service,
    user_id: str,
    max_results_per_page: int = 500,
    commit_batch_size: int = 500
) -> Dict[str, Any]:
    """
    Safely and incrementally migrates missing thread IDs in user_email_cache for a specific user.
    
    Guarantees:
      - STRICTLY USER-SCOPED: Only modifies records matching the specified user_id.
      - PRESERVATION: Leaves predicted_priority, action_required, deadline_detected, 
        model_version, feedback, and timestamps completely untouched.
      - IDEMPOTENT: Only updates records where thread_id is empty or NULL.
      - ACCURATE: Extracts the actual threadId from Gmail API messages.list resource.
    """
    t_start = time.perf_counter()
    api_requests = 0

    conn = user_email_cache._get_connection()

    # Step 1: Count currently valid and missing records for this user
    cur = conn.cursor()
    cur.execute(
        """
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN thread_id IS NOT NULL AND thread_id != '' THEN 1 END) as valid_count,
            COUNT(CASE WHEN thread_id IS NULL OR thread_id = '' THEN 1 END) as missing_count
        FROM user_email_cache
        WHERE user_id = ?
        """,
        (user_id,)
    )
    row = cur.fetchone()
    total_records = row[0] or 0
    records_already_valid = row[1] or 0
    records_missing = row[2] or 0

    if records_missing == 0:
        return {
            "user_id": user_id,
            "total_records": total_records,
            "records_repaired": 0,
            "records_already_valid": records_already_valid,
            "records_unable_to_resolve": 0,
            "api_requests_used": 0,
            "duration": round(time.perf_counter() - t_start, 2),
            "status": "ALREADY_VALID"
        }

    # Step 2: Fetch message ID -> thread ID mapping from Gmail API messages.list
    msg_to_thread: Dict[str, str] = {}
    page_token = None
    seen_tokens = set()

    while True:
        kwargs: Dict[str, Any] = {
            "userId": "me",
            "maxResults": min(max_results_per_page, 500),
            "includeSpamTrash": False
        }
        if page_token:
            kwargs["pageToken"] = page_token

        response = None
        for attempt in range(1, 4):
            try:
                api_requests += 1
                req = service.users().messages().list(**kwargs)
                response = req.execute()
                break
            except HttpError as http_err:
                status_code = getattr(http_err.resp, "status", None)
                if status_code in (429, 500, 503) and attempt < 3:
                    time.sleep(1.0 * (2 ** (attempt - 1)))
                else:
                    raise
            except Exception:
                if attempt == 3:
                    raise
                time.sleep(0.5)

        if not response:
            break

        messages = response.get("messages", [])
        for m in messages:
            mid = m.get("id")
            tid = m.get("threadId")
            if mid and tid:
                msg_to_thread[mid] = tid

        page_token = response.get("nextPageToken")
        if not page_token or page_token in seen_tokens:
            break
        seen_tokens.add(page_token)

    # Step 3: Fetch all missing records for user and update thread_id and data_json
    cur.execute(
        """
        SELECT message_id, data_json
        FROM user_email_cache
        WHERE user_id = ? AND (thread_id IS NULL OR thread_id = '')
        """,
        (user_id,)
    )
    missing_rows = cur.fetchall()

    records_repaired = 0
    records_unable_to_resolve = 0
    update_batch = []

    for r in missing_rows:
        mid = r[0]
        data_json_raw = r[1]
        actual_thread_id = msg_to_thread.get(mid)

        if actual_thread_id:
            try:
                data_dict = json.loads(data_json_raw)
                data_dict["thread_id"] = actual_thread_id
                updated_json = json.dumps(data_dict)
            except Exception:
                updated_json = data_json_raw

            update_batch.append((actual_thread_id, updated_json, user_id, mid))
            records_repaired += 1
        else:
            records_unable_to_resolve += 1

        if len(update_batch) >= commit_batch_size:
            with user_email_cache._lock:
                cur.executemany(
                    """
                    UPDATE user_email_cache
                    SET thread_id = ?, data_json = ?
                    WHERE user_id = ? AND message_id = ?
                    """,
                    update_batch
                )
                conn.commit()
            update_batch = []

    if update_batch:
        with user_email_cache._lock:
            cur.executemany(
                """
                UPDATE user_email_cache
                SET thread_id = ?, data_json = ?
                WHERE user_id = ? AND message_id = ?
                """,
                update_batch
            )
            conn.commit()

    # Clear in-memory cache for user so updated records are loaded
    with user_email_cache._lock:
        user_email_cache._mem_cache.pop(user_id, None)

    duration = round(time.perf_counter() - t_start, 2)
    return {
        "user_id": user_id,
        "total_records": total_records,
        "records_repaired": records_repaired,
        "records_already_valid": records_already_valid,
        "records_unable_to_resolve": records_unable_to_resolve,
        "api_requests_used": api_requests,
        "duration": duration,
        "status": "COMPLETED"
    }
