import os
import gc
import time
import json
import logging
import threading
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Set, Tuple, Union
from googleapiclient.errors import HttpError

from backend.app.core.config import BASE_DIR
from backend.app.core.cache import user_email_cache, compute_content_hash
from backend.app.gmail.parser import parse_message
from backend.app.ml.predictor import load_model, predict_batch
from backend.app.ml.registry import model_registry

logger = logging.getLogger("mailmind.scan_engine")
SCANS_DIR = os.path.join(BASE_DIR, "google_auth", "scans")


class ScanJobState:
    QUEUED = "QUEUED"
    SCANNING = "SCANNING"
    ANALYZING = "ANALYZING"
    FINALIZING = "FINALIZING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


def discover_mailbox_message_ids(
    service,
    scope: str = "mailbox",
    query: Optional[str] = None,
    label_ids: Optional[List[str]] = None,
    stop_event: Optional[threading.Event] = None,
    on_page_discovered: Optional[Any] = None,
    max_results_per_page: int = 500,
    return_stats: bool = False
) -> Union[List[str], Tuple[List[str], Dict[str, Any]]]:
    """
    Robust Gmail message discovery using nextPageToken pagination across the complete mailbox.
    Safely discovers all accessible messages without imposing arbitrary 20/50/100 email ceilings.

    Guarantees:
      - Loop safety: Tracks seen tokens to prevent infinite loops on malformed Gmail responses.
      - Deduplication: Maintains discovered ID set to remove any duplicate messages returned.
      - Rate limit resilience: Retries transient 429 and 5xx errors with exponential backoff.
      - Responsive cancellation: Regularly checks stop_event to allow fast user cancellation.
    """
    t_start = time.perf_counter()
    discovered_ids: List[str] = []
    seen_ids: Set[str] = set()
    seen_tokens: Set[str] = set()

    page_token: Optional[str] = None
    pages_scanned = 0
    duplicates_removed = 0
    api_calls = 0
    retry_count = 0

    while True:
        if stop_event and stop_event.is_set():
            logger.info("Discovery interrupted by cancellation request.")
            break

        kwargs: Dict[str, Any] = {
            "userId": "me",
            "maxResults": min(max_results_per_page, 500),
            "includeSpamTrash": False
        }

        if page_token:
            kwargs["pageToken"] = page_token

        # Scope handling: mailbox vs label
        if scope == "label" or label_ids:
            kwargs["labelIds"] = label_ids or ["INBOX"]

        if query and query.strip():
            kwargs["q"] = query.strip()

        # Retry logic with exponential backoff for 429 and 5xx
        response = None
        for attempt in range(1, 4):
            if stop_event and stop_event.is_set():
                break
            try:
                api_calls += 1
                req = service.users().messages().list(**kwargs)
                response = req.execute()
                break
            except HttpError as http_err:
                status_code = getattr(http_err.resp, "status", None)
                if status_code in (429, 500, 503):
                    retry_count += 1
                    sleep_dur = 1.0 * (2 ** (attempt - 1))
                    logger.warning(
                        f"Gmail API HTTP {status_code} on list page {pages_scanned + 1}. "
                        f"Retrying in {sleep_dur:.1f}s (attempt {attempt}/3)..."
                    )
                    time.sleep(sleep_dur)
                    if attempt == 3:
                        raise
                else:
                    raise
            except Exception as ex:
                retry_count += 1
                if attempt == 3:
                    raise
                time.sleep(1.0)

        if not response or stop_event and stop_event.is_set():
            break

        pages_scanned += 1
        raw_msgs = response.get("messages", [])

        for m in raw_msgs:
            mid = m.get("id")
            if not mid:
                continue
            if mid not in seen_ids:
                seen_ids.add(mid)
                discovered_ids.append(mid)
            else:
                duplicates_removed += 1

        if on_page_discovered:
            try:
                on_page_discovered(pages_scanned, len(discovered_ids))
            except Exception:
                pass

        page_token = response.get("nextPageToken")
        if not page_token:
            break

        # Infinite loop defense: if Gmail returns the same nextPageToken twice
        if page_token in seen_tokens:
            logger.warning(f"Duplicate page token '{page_token}' detected. Halting pagination.")
            break
        seen_tokens.add(page_token)

    elapsed = round(time.perf_counter() - t_start, 2)
    logger.info(
        f"Discovery finished: {len(discovered_ids)} unique messages, {pages_scanned} pages, "
        f"{duplicates_removed} duplicates removed, {api_calls} API calls in {elapsed}s."
    )

    stats = {
        "pages_scanned": pages_scanned,
        "duplicates_removed": duplicates_removed,
        "api_calls": api_calls,
        "retry_count": retry_count,
        "elapsed_sec": elapsed
    }
    if return_stats:
        return discovered_ids, stats
    return discovered_ids


def fetch_message_metadata_batch(
    service,
    message_ids: List[str],
    stop_event: Optional[threading.Event] = None,
    sub_batch_size: int = 25
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], int, int]:
    """
    Fetches lightweight message metadata in controlled sub-batches using
    service.new_batch_http_request().
    Captures: From, To, Subject, Date, Snippet, ThreadId, Labels.
    Uses sub-batching (default 25) and per-item 429/5xx retry with exponential backoff
    to guarantee safe throughput without triggering Gmail API concurrency limits.
    Returns:
        (valid_parsed_messages, failed_items, api_calls, retry_count)
    """
    if not message_ids:
        return [], [], 0, 0

    results_map: Dict[str, Dict[str, Any]] = {}
    errors_map: Dict[str, str] = {}
    api_calls = 0
    retry_count = 0

    for chunk_start in range(0, len(message_ids), sub_batch_size):
        if stop_event and stop_event.is_set():
            break

        chunk_ids = message_ids[chunk_start:chunk_start + sub_batch_size]
        pending_ids = list(chunk_ids)

        for attempt in range(1, 4):
            if (stop_event and stop_event.is_set()) or not pending_ids:
                break

            current_errors: Dict[str, str] = {}

            def _make_callback(err_dict, res_dict):
                def _cb(req_id, response, exception):
                    if exception is not None:
                        err_dict[req_id] = str(exception)
                    else:
                        res_dict[req_id] = response
                return _cb

            try:
                batch = service.new_batch_http_request(callback=_make_callback(current_errors, results_map))
                for mid in pending_ids:
                    req = service.users().messages().get(
                        userId="me",
                        id=mid,
                        format="metadata",
                        metadataHeaders=["From", "To", "Cc", "Subject", "Date"]
                    )
                    batch.add(req, request_id=mid)

                api_calls += 1
                batch.execute()

                # Check if any items in this batch hit rate limits or 5xx
                retryable_ids = []
                for mid, err_str in current_errors.items():
                    err_lower = err_str.lower()
                    if any(term in err_lower for term in ("429", "ratelimit", "concurrent", "500", "503", "backenderror")):
                        retryable_ids.append(mid)
                    else:
                        errors_map[mid] = err_str

                if retryable_ids and attempt < 3:
                    retry_count += 1
                    sleep_dur = 0.5 * (2 ** (attempt - 1))
                    time.sleep(sleep_dur)
                    pending_ids = retryable_ids
                else:
                    for mid in retryable_ids:
                        errors_map[mid] = current_errors[mid]
                    break

            except HttpError as http_err:
                status_code = getattr(http_err.resp, "status", None)
                if status_code in (429, 500, 503):
                    retry_count += 1
                    sleep_dur = 1.0 * (2 ** (attempt - 1))
                    time.sleep(sleep_dur)
                    if attempt == 3:
                        for mid in pending_ids:
                            errors_map[mid] = str(http_err)
                else:
                    for mid in pending_ids:
                        errors_map[mid] = str(http_err)
                    break
            except Exception as ex:
                retry_count += 1
                if attempt == 3:
                    for mid in pending_ids:
                        errors_map[mid] = str(ex)
                time.sleep(0.5)

        time.sleep(0.01)

    parsed_messages: List[Dict[str, Any]] = []
    failed_items: List[Dict[str, Any]] = []

    for mid in message_ids:
        if mid in results_map:
            try:
                parsed = parse_message(results_map[mid])
                if "internalDate" in results_map[mid]:
                    try:
                        parsed["internal_date"] = int(results_map[mid]["internalDate"])
                    except (ValueError, TypeError):
                        pass
                parsed["content_hash"] = compute_content_hash(parsed.get("subject"), parsed.get("snippet"), parsed.get("body"))
                parsed_messages.append(parsed)
            except Exception as parse_err:
                failed_items.append({
                    "message_id": mid,
                    "error": str(parse_err),
                    "timestamp": time.time()
                })
        else:
            err = errors_map.get(mid)
            failed_items.append({
                "message_id": mid,
                "error": str(err) if err else "Not returned by Gmail API batch",
                "timestamp": time.time()
            })

    return parsed_messages, failed_items, api_calls, retry_count


class MailboxScanJob:
    """
    Executes a complete mailbox analysis job for a specific user.
    Can be run directly synchronously (ideal for testing) or in a background thread.
    """

    def __init__(
        self,
        user_id: str,
        service,
        scope: str = "mailbox",
        mode: str = "incremental",
        query: Optional[str] = None,
        force_rescan: bool = False,
        batch_size: int = 100,
        scans_dir: str = SCANS_DIR,
        on_progress: Optional[Any] = None
    ):
        self.user_id = user_id
        self.service = service
        self.scope = scope
        self.mode = "full" if force_rescan else mode
        self.query = query
        self.force_rescan = force_rescan
        self.batch_size = batch_size
        self.scans_dir = scans_dir
        self.on_progress = on_progress
        self.stop_event = threading.Event()
        self._lock = threading.RLock()

        now_iso = datetime.now(timezone.utc).isoformat()
        self.state: Dict[str, Any] = {
            "user_id": user_id,
            "status": ScanJobState.QUEUED,
            "scope": self.scope,
            "mode": self.mode,
            "query": self.query,
            "discovered": 0,
            "analyzed": 0,
            "cached": 0,
            "newly_analyzed": 0,
            "failed": 0,
            "failed_details": [],
            "total": 0,
            "progress_percent": 0.0,
            "started_at": now_iso,
            "updated_at": now_iso,
            "completed_at": None,
            "scan_duration_sec": 0.0,
            "throughput_emails_per_sec": 0.0,
            "api_calls": 0,
            "retry_count": 0,
            "cache_hit_rate": 0.0,
            "pages_scanned": 0,
            "remaining_ids": [],
            "discovered_ids": [],
            "processed_ids": [],
            "error": None
        }

    def cancel(self):
        self.stop_event.set()
        with self._lock:
            self.state["status"] = ScanJobState.CANCELLED

    def _checkpoint_path(self) -> str:
        safe_uid = "".join(c for c in self.user_id if c.isalnum() or c in ("-", "_"))
        return os.path.join(self.scans_dir, f"scan_{safe_uid}.json")

    def _persist(self):
        try:
            os.makedirs(self.scans_dir, exist_ok=True)
            with open(self._checkpoint_path(), "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not persist scan checkpoint: {e}")

    def execute(self) -> Dict[str, Any]:
        t0 = time.perf_counter()

        def _update(**kwargs):
            with self._lock:
                self.state.update(kwargs)
                self.state["updated_at"] = datetime.now(timezone.utc).isoformat()
                cur_dur = max(0.001, time.perf_counter() - t0)
                self.state["scan_duration_sec"] = round(cur_dur, 2)
                self.state["elapsed_seconds"] = round(cur_dur, 2)
                tot_done = self.state["cached"] + self.state["newly_analyzed"]
                if self.state["total"] > 0:
                    self.state["progress_percent"] = round((tot_done / self.state["total"]) * 100, 2)
                if self.state["newly_analyzed"] > 0:
                    self.state["throughput_emails_per_sec"] = round(self.state["newly_analyzed"] / cur_dur, 1)
            self._persist()
            if self.on_progress:
                try:
                    self.on_progress(dict(self.state))
                except Exception:
                    pass

        try:
            # Check for existing checkpoint to resume
            cp_file = self._checkpoint_path()
            resumed_discovered = []
            resumed_processed = set()
            if os.path.exists(cp_file):
                try:
                    with open(cp_file, "r", encoding="utf-8") as fp:
                        cp_data = json.load(fp)
                    # Only resume if previous scan was interrupted while in progress (QUEUED, SCANNING, ANALYZING)
                    if cp_data.get("status") in (ScanJobState.QUEUED, ScanJobState.SCANNING, ScanJobState.ANALYZING) and not self.force_rescan:
                        if cp_data.get("discovered_ids"):
                            resumed_discovered = cp_data["discovered_ids"]
                        if cp_data.get("processed_ids"):
                            resumed_processed = set(cp_data["processed_ids"])
                except Exception:
                    pass


            if resumed_discovered and not self.force_rescan:
                discovered_ids = resumed_discovered
                tot_discovered = len(discovered_ids)
                _update(
                    status=ScanJobState.SCANNING,
                    discovered=tot_discovered,
                    total=tot_discovered,
                    discovered_ids=discovered_ids
                )
            else:
                _update(status=ScanJobState.SCANNING)

                def _on_page(pages, count):
                    _update(pages_scanned=pages, discovered=count, total=count)

                discovered_ids, disc_stats = discover_mailbox_message_ids(
                    service=self.service,
                    scope=self.scope,
                    query=self.query,
                    stop_event=self.stop_event,
                    on_page_discovered=_on_page,
                    return_stats=True
                )

                if self.stop_event.is_set():
                    _update(status=ScanJobState.CANCELLED)
                    return dict(self.state)

                tot_discovered = len(discovered_ids)
                _update(
                    discovered=tot_discovered,
                    total=tot_discovered,
                    pages_scanned=disc_stats["pages_scanned"],
                    api_calls=disc_stats["api_calls"],
                    retry_count=disc_stats["retry_count"],
                    discovered_ids=discovered_ids
                )

            if tot_discovered == 0:
                _update(
                    status=ScanJobState.COMPLETE,
                    completed_at=datetime.now(timezone.utc).isoformat(),
                    progress_percent=100.0,
                    cache_hit_rate=100.0
                )
                return dict(self.state)

            # STAGE 2: CACHE COMPARISON
            if self.force_rescan:
                cached_ids = set()
                to_analyze_ids = [mid for mid in discovered_ids if mid not in resumed_processed]
            else:
                active_ver = model_registry.get_active_version()
                cached_ids = user_email_cache.get_all_cached_ids(self.user_id, active_model_version=active_ver)
                to_analyze_ids = [mid for mid in discovered_ids if mid not in cached_ids and mid not in resumed_processed]

            already_cached_count = len(discovered_ids) - len(to_analyze_ids)
            cache_hit_rate = round((already_cached_count / tot_discovered * 100), 2) if tot_discovered > 0 else 0.0

            _update(
                status=ScanJobState.ANALYZING,
                cached=already_cached_count,
                analyzed=already_cached_count,
                cache_hit_rate=cache_hit_rate,
                remaining_ids=list(to_analyze_ids),
                processed_ids=list(resumed_processed)
            )

            # STAGE 3: BATCH METADATA & ML INFERENCE
            pipeline = load_model()
            batch_size = self.batch_size
            total_to_analyze = len(to_analyze_ids)

            for i in range(0, total_to_analyze, batch_size):
                if self.stop_event.is_set():
                    _update(status=ScanJobState.CANCELLED)
                    return dict(self.state)

                batch_ids = to_analyze_ids[i:i + batch_size]

                # Fetch metadata
                fetch_res = fetch_message_metadata_batch(
                    service=self.service,
                    message_ids=batch_ids,
                    stop_event=self.stop_event
                )
                if isinstance(fetch_res, tuple) and len(fetch_res) == 4:
                    parsed_messages, failed_items, api_calls, retries = fetch_res
                elif isinstance(fetch_res, list):
                    parsed_messages, failed_items, api_calls, retries = fetch_res, [], 1, 0
                else:
                    parsed_messages, failed_items, api_calls, retries = [], [], 0, 0


                with self._lock:
                    self.state["api_calls"] += api_calls
                    self.state["retry_count"] += retries
                    if failed_items:
                        self.state["failed"] += len(failed_items)
                        self.state["failed_details"].extend(failed_items[:20])

                if parsed_messages:
                    # Filter out any corrupt items that don't have minimum required fields
                    valid_parsed = [p for p in parsed_messages if isinstance(p, dict) and "subject" in p and "body" in p]
                    invalid_count = len(parsed_messages) - len(valid_parsed)
                    if invalid_count > 0:
                        with self._lock:
                            self.state["failed"] += invalid_count

                    if valid_parsed:
                        predictions = predict_batch(valid_parsed, pipeline=pipeline)
                        for orig, pred in zip(valid_parsed, predictions):
                            if "content_hash" in orig:
                                pred["content_hash"] = orig["content_hash"]
                            if "internal_date" in orig:
                                pred["internal_date"] = orig["internal_date"]
                        user_email_cache.store_batch(self.user_id, predictions)


                        with self._lock:
                            self.state["newly_analyzed"] += len(predictions)
                            self.state["analyzed"] = self.state["cached"] + self.state["newly_analyzed"]
                            self.state["remaining_ids"] = to_analyze_ids[i + batch_size:]
                            self.state["processed_ids"].extend([p["email_id"] for p in predictions])

                if failed_items:
                    with self._lock:
                        self.state["processed_ids"].extend([f.get("message_id") for f in failed_items if f.get("message_id")])

                if self.stop_event.is_set():
                    _update(status=ScanJobState.CANCELLED)
                    return dict(self.state)

                _update()
                del parsed_messages
                gc.collect()

            if self.stop_event.is_set():
                _update(status=ScanJobState.CANCELLED)
                return dict(self.state)

            # STAGE 4: FINALIZING
            _update(status=ScanJobState.FINALIZING)

            total_dur = max(0.001, time.perf_counter() - t0)
            now_iso = datetime.now(timezone.utc).isoformat()

            with self._lock:
                self.state["status"] = ScanJobState.COMPLETE
                self.state["completed_at"] = now_iso
                self.state["progress_percent"] = 100.0
                self.state["scan_duration_sec"] = round(total_dur, 2)
                self.state["elapsed_seconds"] = round(total_dur, 2)
                self.state["remaining_ids"] = []

            _update()
            return dict(self.state)

        except Exception as e:
            logger.error(f"Fatal error in scan job for {self.user_id}: {e}", exc_info=True)
            with self._lock:
                self.state["status"] = ScanJobState.FAILED
                self.state["error"] = str(e)
                self.state["completed_at"] = datetime.now(timezone.utc).isoformat()
            self._persist()
            return dict(self.state)


class ScanManager:
    """
    Manages long-running complete mailbox analysis jobs per authenticated user.
    Enforces strict multi-user isolation, resume capability across restarts,
    safe rate-limit backoff, and progressive metrics reporting.
    """

    def __init__(self, scans_dir: str = SCANS_DIR):
        self.scans_dir = scans_dir
        self._lock = threading.RLock()
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._active_scan_jobs: Dict[str, MailboxScanJob] = {}
        self._worker_threads: Dict[str, threading.Thread] = {}
        os.makedirs(self.scans_dir, exist_ok=True)
        self._load_persisted_jobs()

    def _job_file_path(self, user_id: str) -> str:
        safe_uid = "".join(c for c in user_id if c.isalnum() or c in ("-", "_"))
        return os.path.join(self.scans_dir, f"scan_{safe_uid}.json")

    def _load_persisted_jobs(self):
        """Loads existing jobs on server startup to enable resuming interrupted scans."""
        try:
            for fname in os.listdir(self.scans_dir):
                if fname.startswith("scan_") and fname.endswith(".json"):
                    fpath = os.path.join(self.scans_dir, fname)
                    try:
                        with open(fpath, "r", encoding="utf-8") as fp:
                            data = json.load(fp)
                        uid = data.get("user_id")
                        if uid:
                            if data.get("status") in (ScanJobState.SCANNING, ScanJobState.ANALYZING, ScanJobState.QUEUED):
                                data["status"] = ScanJobState.QUEUED
                                data["note"] = "Scan interrupted by server restart; ready to resume."
                            self._jobs[uid] = data
                    except Exception as err:
                        logger.warning(f"Failed to load scan job file {fname}: {err}")
        except Exception as e:
            logger.warning(f"Could not load persisted scan jobs: {e}")

    def _persist_job(self, user_id: str):
        """Writes scan job state to disk for restart tolerance."""
        with self._lock:
            job = self._jobs.get(user_id)
            if not job:
                return
            fpath = self._job_file_path(user_id)
            try:
                snapshot = dict(job)
                with open(fpath, "w", encoding="utf-8") as fp:
                    json.dump(snapshot, fp, indent=2)
            except Exception as e:
                logger.warning(f"Could not persist scan job for {user_id}: {e}")

    def set_status(self, user_id: str, status_dict: Dict[str, Any]):
        """Sets status directly for a user (used in testing and explicit overrides)."""
        with self._lock:
            self._jobs[user_id] = status_dict
            self._persist_job(user_id)

    def get_status(self, user_id: str) -> Dict[str, Any]:
        """
        Returns authenticated user's current scan status.
        User-scoped: User A can NEVER view User B's scan status.
        """
        if not user_id:
            return self._empty_status()

        with self._lock:
            # Check active scan job if running
            active_job = self._active_scan_jobs.get(user_id)
            if active_job:
                res = dict(active_job.state)
                res.pop("remaining_ids", None)
                res.pop("discovered_ids", None)
                res.pop("processed_ids", None)
                return res

            job = self._jobs.get(user_id)
            if not job:
                stats = user_email_cache.get_mailbox_stats(user_id)
                cached_count = stats.get("total_analyzed", 0)
                return {
                    "status": ScanJobState.COMPLETE if cached_count > 0 else "IDLE",
                    "scope": "mailbox",
                    "mode": "incremental",
                    "discovered": cached_count,
                    "analyzed": cached_count,
                    "cached": cached_count,
                    "newly_analyzed": 0,
                    "failed": 0,
                    "total": cached_count,
                    "progress_percent": 100.0 if cached_count > 0 else 0.0,
                    "started_at": stats.get("last_synced"),
                    "updated_at": stats.get("last_synced"),
                    "completed_at": stats.get("last_synced") if cached_count > 0 else None,
                    "scan_duration_sec": 0.0,
                    "throughput_emails_per_sec": 0.0,
                    "api_calls": 0,
                    "retry_count": 0,
                    "cache_hit_rate": 100.0 if cached_count > 0 else 0.0,
                    "pages_scanned": 0
                }

            res = dict(job)
            res.pop("remaining_ids", None)
            res.pop("discovered_ids", None)
            res.pop("processed_ids", None)
            return res

    def is_scanning(self, user_id: str) -> bool:
        with self._lock:
            active_job = self._active_scan_jobs.get(user_id)
            if active_job:
                return active_job.state.get("status") in (
                    ScanJobState.QUEUED, ScanJobState.SCANNING, ScanJobState.ANALYZING, ScanJobState.FINALIZING
                )
            job = self._jobs.get(user_id)
            if not job:
                return False
            return job.get("status") in (
                ScanJobState.QUEUED, ScanJobState.SCANNING, ScanJobState.ANALYZING, ScanJobState.FINALIZING
            )

    def cancel_scan(self, user_id: str) -> bool:
        """Signals active scan to stop cleanly and marks status CANCELLED."""
        with self._lock:
            active_job = self._active_scan_jobs.get(user_id)
            if active_job:
                active_job.cancel()
                self._jobs[user_id] = active_job.state
                self._persist_job(user_id)
                return True
            job = self._jobs.get(user_id)
            if job and job.get("status") in (ScanJobState.QUEUED, ScanJobState.SCANNING, ScanJobState.ANALYZING):
                job["status"] = ScanJobState.CANCELLED
                job["updated_at"] = datetime.now(timezone.utc).isoformat()
                self._persist_job(user_id)
                return True
            return False

    def start_scan(
        self,
        user_id: str,
        service,
        scope: str = "mailbox",
        mode: str = "incremental",
        query: Optional[str] = None,
        force_rescan: bool = False
    ) -> Dict[str, Any]:
        """
        Initiates a background complete mailbox scan or incremental sync for user_id.
        """
        with self._lock:
            if self.is_scanning(user_id):
                return self.get_status(user_id)

            job = MailboxScanJob(
                user_id=user_id,
                service=service,
                scope=scope,
                mode=mode,
                query=query,
                force_rescan=force_rescan,
                scans_dir=self.scans_dir
            )
            self._active_scan_jobs[user_id] = job
            self._jobs[user_id] = job.state
            self._persist_job(user_id)

            def _worker():
                try:
                    final_state = job.execute()
                    with self._lock:
                        self._jobs[user_id] = final_state
                        self._persist_job(user_id)
                finally:
                    with self._lock:
                        self._active_scan_jobs.pop(user_id, None)
                        self._worker_threads.pop(user_id, None)

            worker = threading.Thread(
                target=_worker,
                daemon=True,
                name=f"MailMindScanWorker-{user_id[:8]}"
            )
            self._worker_threads[user_id] = worker
            worker.start()

            return self.get_status(user_id)

    def _empty_status(self) -> Dict[str, Any]:
        return {
            "status": "IDLE",
            "scope": "mailbox",
            "mode": "incremental",
            "discovered": 0,
            "analyzed": 0,
            "cached": 0,
            "newly_analyzed": 0,
            "failed": 0,
            "total": 0,
            "progress_percent": 0.0,
            "started_at": None,
            "updated_at": None,
            "completed_at": None,
            "scan_duration_sec": 0.0,
            "throughput_emails_per_sec": 0.0,
            "api_calls": 0,
            "retry_count": 0,
            "cache_hit_rate": 0.0,
            "pages_scanned": 0
        }


# Global scan manager instance
scan_manager = ScanManager()
