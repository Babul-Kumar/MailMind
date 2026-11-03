# MAILMIND — API CONTRACTS SPECIFICATION
**Document Version:** 1.0.0  
**Specification Date:** 2026-11-03  
**Status:** Approved Architecture Contract  
**Protocol:** REST over HTTPS / JSON / OpenAPI 3.1 Compliant

---

## 1. Overview & Authentication Standard

All endpoints described herein require an active, authenticated user session established via MailMind's existing Google OAuth flow. 
- **Browser Clients (React/Vite):** Authenticate using secure, HTTP-only session cookies (`session_id`).
- **Server-Side Clients (React):** Authenticate by passing either the session cookie in HTTP requests or using the secure single-use session handoff token exchange (`X-Session-ID` header or authenticated session cookie).
- **Security Invariant:** Every request is authenticated on the server side. User A can never inspect, query, or mutate User B's preferences, jobs, emails, or actions. Cross-user data leakage returns HTTP 401 Unauthorized or HTTP 403 Forbidden.

---

## 2. Analysis Configuration Endpoints

### 2.1 GET `/api/analysis/config`
Retrieves the user's persisted date-analysis preference for their connected Gmail account.

- **Method:** `GET`
- **Headers:** `Cookie: session_id=<token>`
- **Response `200 OK`:**
```json
{
  "status": "success",
  "data": {
    "period": "last_3_months",
    "timezone": "Asia/Kolkata",
    "custom_start_date": null,
    "custom_end_date": null,
    "updated_at": "2026-11-03T10:00:00Z"
  }
}
```
- **Error Responses:**
  - `401 Unauthorized`: Missing or expired session cookie.

---

### 2.2 PUT `/api/analysis/config`
Updates the user's persisted date-analysis preference.

- **Method:** `PUT`
- **Headers:** `Content-Type: application/json`, `Cookie: session_id=<token>`
- **Request Body (Preset Period):**
```json
{
  "period": "this_month",
  "timezone": "Asia/Kolkata"
}
```
- **Request Body (Custom Range):**
```json
{
  "period": "custom",
  "timezone": "Asia/Kolkata",
  "custom_start_date": "2026-08-01",
  "custom_end_date": "2026-10-31"
}
```
- **Validation Rules:**
  - `period` must be one of: `this_month`, `last_3_months`, `last_1_year`, `all_time`, `custom`.
  - If `period == "custom"`, `custom_start_date` and `custom_end_date` must be valid `YYYY-MM-DD` strings.
  - `custom_start_date` $\le$ `custom_end_date`.
  - `custom_end_date` must not be in the future (relative to today in the specified timezone).
  - `timezone` must be a recognized IANA timezone identifier (e.g., `UTC`, `Asia/Kolkata`, `America/New_York`).
- **Response `200 OK`:**
```json
{
  "status": "success",
  "message": "Analysis configuration updated successfully.",
  "data": {
    "period": "custom",
    "timezone": "Asia/Kolkata",
    "custom_start_date": "2026-08-01",
    "custom_end_date": "2026-10-31",
    "updated_at": "2026-11-03T10:15:00Z",
    "analysis_required": true
  }
}
```
- **Error Responses:**
  - `400 Bad Request` or `422 Unprocessable Entity`: Invalid date format, future date, start after end, or unrecognized period.

---

## 3. Analysis Progress & Execution Endpoints

### 3.1 GET `/api/analysis/summary`
Returns high-level analysis metrics and coverage for the selected analysis period (or a requested period).

- **Method:** `GET`
- **Query Parameters:**
  - `period` (optional, string): Scope override. Defaults to user's saved preference.
- **Response `200 OK`:**
```json
{
  "status": "success",
  "data": {
    "period": "last_3_months",
    "timezone": "Asia/Kolkata",
    "date_boundaries": {
      "start_iso": "2026-08-03T21:15:00Z",
      "end_iso": "2026-11-03T21:15:00Z",
      "start_ts_ms": 1785791700000,
      "end_ts_ms": 1793740500000
    },
    "total_eligible": 1850,
    "analyzed": 1850,
    "pending": 0,
    "failed": 0,
    "reused_from_cache": 1850,
    "progress_percentage": 100.0,
    "status": "completed",
    "last_analyzed_at": "2026-11-03T10:00:00Z"
  }
}
```

---

### 3.2 POST `/api/analysis/start`
Initiates or resumes incremental background ML analysis for the specified or current period.

- **Method:** `POST`
- **Headers:** `Content-Type: application/json`, `Cookie: session_id=<token>`
- **Request Body:**
```json
{
  "period": "last_3_months",
  "start_date": null,
  "end_date": null,
  "force_reanalysis": false
}
```
- **Behavior & Idempotency:**
  - If a job for the same user and scope is already in progress (`RUNNING` or `QUEUED`), the API returns the active job descriptor immediately without launching duplicate background tasks.
  - If all eligible emails in the date scope already have valid cache entries for the active model version (`priority-v5.1`), the job completes immediately with `already_analyzed == total_eligible` and `status == "completed"`.
  - Does not retrain the frozen model.
- **Response `200 OK` (or `202 Accepted`):**
```json
{
  "status": "success",
  "data": {
    "job_id": "job_9a8b7c6d5e",
    "status": "running",
    "period": "last_3_months",
    "total_eligible": 1850,
    "already_analyzed": 620,
    "pending": 1230,
    "reused_from_cache": 620,
    "created_at": "2026-11-03T10:20:00Z"
  }
}
```

---

### 3.3 GET `/api/analysis/status`
Returns the status and live progress metrics for the current or specified analysis job.

- **Method:** `GET`
- **Query Parameters:**
  - `job_id` (optional, string): Job ID to check. If omitted, returns current/latest job for user.
- **Response `200 OK`:**
```json
{
  "status": "success",
  "data": {
    "job_id": "job_9a8b7c6d5e",
    "status": "running",
    "period": "last_3_months",
    "total_eligible": 1850,
    "processed_count": 900,
    "already_analyzed": 620,
    "pending": 950,
    "failed_count": 0,
    "progress_percentage": 48.65,
    "started_at": "2026-11-03T10:20:00Z",
    "updated_at": "2026-11-03T10:23:45Z",
    "completed_at": null,
    "error": null
  }
}
```
- **Possible `status` values:** `queued`, `running`, `completed`, `partially_completed`, `failed`, `cancelled`.

---

## 4. Mailbox & Email Query Endpoints

### 4.1 GET `/api/emails/recent`
Retrieves paginated emails situated strictly within the selected (or requested) analysis date scope.

- **Method:** `GET`
- **Query Parameters:**
  - `page` (int, default: 1, $\ge 1$)
  - `page_size` (int, default: 50, $1 \le \text{page\_size} \le 100$)
  - `period` (optional string): Defaults to user's saved preference
  - `priority` (optional string): `ALL`, `P1`, `P2`, `P3`, `P4`, `NEEDS_ATTENTION`
  - `search` (optional string, max 200 chars): Search across sender, subject, snippet, body
  - `action_required` (optional bool)
  - `sort` (optional string: `desc` [default, newest first] or `asc`)
- **Response `200 OK`:**
```json
{
  "status": "success",
  "data": {
    "items": [
      {
        "id": "1894a8f9c02d1234",
        "thread_id": "1894a8f9c02d1234",
        "sender": "security@company.com",
        "subject": "New sign-in detected on Windows",
        "snippet": "We noticed a new login to your account...",
        "date": "2026-11-02T14:30:00Z",
        "internal_date": 1793639400000,
        "original_priority": "P1",
        "effective_priority": "P1",
        "action_status": "ACTIVE",
        "is_demoted": false,
        "demotion_reason": null,
        "action_required": true,
        "deadline_status": "NONE",
        "deadline_display": null,
        "model_version": "priority-v5.1",
        "confidence": 0.942
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 50,
      "total_items": 1850,
      "total_pages": 37,
      "has_next": true,
      "has_prev": false
    },
    "period": "last_3_months",
    "date_boundaries": {
      "start_iso": "2026-08-03T21:15:00Z",
      "end_iso": "2026-11-03T21:15:00Z"
    }
  }
}
```

---

### 4.2 GET `/api/emails/history`
Provides browsing access to all historical synchronized mailbox messages independently of the selected analysis period.

- **Method:** `GET`
- **Query Parameters:**
  - `page` (int, default: 1, $\ge 1$)
  - `page_size` (int, default: 50, $1 \le \text{page\_size} \le 100$)
  - `start_date` (optional string, `YYYY-MM-DD`)
  - `end_date` (optional string, `YYYY-MM-DD`)
  - `search` (optional string, max 200 chars)
  - `priority` (optional string: `ALL`, `P1`, `P2`, `P3`, `P4`)
  - `analyzed` (optional bool): If `true`, returns only emails with ML predictions; if `false`, returns only unanalyzed messages; if omitted, returns both.
  - `sort` (optional string: `desc` [default] or `asc`)
- **Response `200 OK`:**
```json
{
  "status": "success",
  "data": {
    "items": [
      {
        "id": "17e5b2c1d3456789",
        "thread_id": "17e5b2c1d3456789",
        "sender": "newsletter@techcrunch.com",
        "subject": "TechCrunch Daily Briefing",
        "snippet": "Here is today's top tech news...",
        "date": "2024-05-12T08:00:00Z",
        "internal_date": 1715497200000,
        "is_analyzed": false,
        "original_priority": null,
        "effective_priority": null,
        "action_status": null,
        "model_version": null
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 50,
      "total_items": 18009,
      "total_pages": 361,
      "has_next": true,
      "has_prev": false
    }
  }
}
```
- **Invariant:** Opening or browsing *All History* does NOT trigger automatic full-mailbox ML inference.

---

### 4.3 GET `/api/emails/{message_id}`
Retrieves full details for a single email, downloading the full body on-demand if deferred.

- **Method:** `GET`
- **Path Parameters:**
  - `message_id` (string, required): Gmail message ID
- **Response `200 OK`:**
```json
{
  "status": "success",
  "email": {
    "id": "1894a8f9c02d1234",
    "thread_id": "1894a8f9c02d1234",
    "sender": "security@company.com",
    "recipients": "user@example.com",
    "subject": "New sign-in detected on Windows",
    "snippet": "We noticed a new login...",
    "body": "Detailed login alert: IP 192.168.1.1 on Windows 11...",
    "date": "2026-11-02T14:30:00Z",
    "internal_date": 1793639400000,
    "original_priority": "P1",
    "effective_priority": "P1",
    "action_status": "ACTIVE",
    "is_demoted": false,
    "demotion_reason": null,
    "is_resolved": false,
    "is_snoozed": false,
    "snoozed_until": null,
    "model_version": "priority-v5.1",
    "confidence": 0.942,
    "action_policy": {
      "original_priority": "P1",
      "effective_priority": "P1",
      "action_status": "ACTIVE",
      "is_demoted": false,
      "demotion_reason": null,
      "placement": "URGENT",
      "reason": "Security Alert: Active critical login notification"
    }
  }
}
```
- **Error Responses:**
  - `404 Not Found`: Message does not exist or does not belong to the authenticated user.

---

## 5. Smart Action Queue Endpoints

### 5.1 GET `/api/actions/attention`
Retrieves outstanding actionable messages. 
- **CRITICAL REQUIREMENT:** This endpoint is completely **independent of the selected date analysis period**. It evaluates all un-resolved, non-expired actionable items across the entire mailbox history.

- **Method:** `GET`
- **Query Parameters:**
  - `threshold_days` (float, default: 7.0)
  - `sort_by` (string, default: `deadline`)
- **Response `200 OK`:**
```json
{
  "status": "success",
  "data": {
    "counts": {
      "urgent": 2,
      "due_soon": 1,
      "other_active": 3,
      "older": 5,
      "snoozed": 1,
      "resolved": 14
    },
    "urgent": [...],
    "due_soon": [...],
    "other_active": [...],
    "older": [...]
  }
}
```

---

## 6. Error & Status Code Summary

| Status Code | Reason | Description |
| :--- | :--- | :--- |
| `200 OK` | Request Succeeded | Normal query response |
| `202 Accepted` | Async Job Started | Background analysis queued or running |
| `400 Bad Request` | Invalid Parameters | Malformed date range or parameter out of bounds |
| `401 Unauthorized` | Auth Required | Missing or invalid session |
| `403 Forbidden` | Access Denied | Attempting to access another user's message/job |
| `404 Not Found` | Resource Missing | Email or job not found |
| `422 Unprocessable` | Validation Error | Start date after end date, future date, etc. |
| `502 Bad Gateway` | Gmail API Error | Upstream Gmail failure / rate limit exhausted |

