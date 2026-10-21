/**
 * MailMind API Service
 * Centralized HTTP client for all MailMind backend communication.
 * Handles API base URL resolution, cross-origin cookies, and error parsing.
 */

/**
 * Resolves the backend API base URL.
 * In both production (Vercel same-origin reverse proxy) and local development (Vite dev proxy):
 * Returns empty string '' so all API calls route through the same-origin /api reverse proxy.
 * This ensures session cookies are strictly FIRST-PARTY and never blocked by browser tracking protections.
 * An explicit external URL can still be configured via VITE_USE_DIRECT_API=true if needed.
 */
export function getApiBaseUrl() {
  if (typeof import.meta !== 'undefined' && import.meta.env?.VITE_USE_DIRECT_API === 'true') {
    const envUrl = import.meta.env.VITE_API_BASE_URL;
    if (envUrl && typeof envUrl === 'string' && envUrl.trim()) {
      return envUrl.trim().replace(/\/+$/, '');
    }
  }

  // Same-origin relative URLs (/api/*) route through Vercel or Vite reverse proxy
  return '';
}

/**
 * Exported constant base URL for convenience.
 */
export const API_BASE_URL = getApiBaseUrl();

/**
 * Centralized fetch wrapper ensuring:
 * 1. Base URL prefixing.
 * 2. credentials: 'include' for cross-origin HttpOnly session cookies.
 * 3. Default header merging.
 */
export async function apiFetch(endpoint, options = {}) {
  const baseUrl = getApiBaseUrl();
  const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  const fullUrl = `${baseUrl}${cleanEndpoint}`;

  const defaultHeaders = {};
  if (options.body && typeof options.body === 'string' && !options.headers?.['Content-Type']) {
    defaultHeaders['Content-Type'] = 'application/json';
  }

  const mergedOptions = {
    ...options,
    credentials: 'include',
    headers: {
      ...defaultHeaders,
      ...(options.headers || {}),
    },
  };

  return fetch(fullUrl, mergedOptions);
}

export async function fetchHealth() {
  const res = await apiFetch('/api/health');
  if (!res.ok) throw new Error(`Health check failed: HTTP ${res.status}`);
  return res.json();
}

export async function fetchAuthStatus() {
  const res = await apiFetch('/api/auth/status');
  if (!res.ok) throw new Error(`Auth status failed: HTTP ${res.status}`);
  return res.json();
}

export async function fetchAuthLogin(prompt = 'select_account') {
  const origin = typeof window !== 'undefined' ? window.location.origin : '';
  const originParam = origin ? `&origin=${encodeURIComponent(origin)}` : '';
  const res = await apiFetch(`/api/auth/login?prompt=${encodeURIComponent(prompt)}${originParam}`);
  if (!res.ok) throw new Error(`Login initiation failed: HTTP ${res.status}`);
  return res.json();
}

const _pendingExchanges = new Map();

export async function fetchAuthExchange(handoff) {
  if (!handoff) throw new Error('Missing handoff code');

  if (_pendingExchanges.has(handoff)) {
    return _pendingExchanges.get(handoff);
  }

  const exchangePromise = (async () => {
    try {
      const res = await apiFetch('/api/auth/exchange', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ handoff }),
      });
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || errorData.message || `Exchange failed: HTTP ${res.status}`);
      }
      return await res.json();
    } finally {
      // Clear from pending cache after 15s to allow future logins if needed
      setTimeout(() => {
        _pendingExchanges.delete(handoff);
      }, 15000);
    }
  })();

  _pendingExchanges.set(handoff, exchangePromise);
  return exchangePromise;
}

export async function logout() {
  const res = await apiFetch('/api/auth/logout', { method: 'POST' });
  if (!res.ok) throw new Error(`Logout failed: HTTP ${res.status}`);
  return res.json();
}

export async function fetchProfile() {
  const res = await apiFetch('/api/profile');
  if (!res.ok) {
    if (res.status === 401) throw new Error('Authentication required');
    throw new Error(`Profile fetch failed: HTTP ${res.status}`);
  }
  return res.json();
}

export async function fetchModelInfo() {
  const res = await apiFetch('/api/model-info');
  if (!res.ok) throw new Error(`Model info fetch failed: HTTP ${res.status}`);
  return res.json();
}

export async function fetchEmails({ page = 1, pageSize = 50, priority = '', query = '', actionRequired = null, maxEmails } = {}) {
  const params = new URLSearchParams();
  if (page) params.append('page', String(page));
  if (pageSize) params.append('page_size', String(pageSize));
  if (priority) params.append('priority', priority);
  if (query) params.append('query', query);
  if (actionRequired !== null && actionRequired !== undefined) {
    params.append('action_required', String(actionRequired));
  }
  if (maxEmails !== undefined) params.append('max_emails', String(maxEmails));

  const res = await apiFetch(`/api/emails?${params.toString()}`);
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    const err = new Error(errorData.message || errorData.detail || `HTTP ${res.status} error`);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

export async function fetchEmailDetail(emailId) {
  const res = await apiFetch(`/api/emails/${encodeURIComponent(emailId)}`);
  if (!res.ok) throw new Error(`Failed to fetch email detail: HTTP ${res.status}`);
  return res.json();
}

export async function submitFeedback(payload) {
  const res = await apiFetch('/api/feedback', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`Feedback submission failed: HTTP ${res.status}`);
  return res.json();
}

export async function fetchScanStatus() {
  const res = await apiFetch('/api/scan/status');
  if (!res.ok) {
    if (res.status === 401) throw new Error('Authentication required');
    throw new Error(`Failed to fetch scan status: HTTP ${res.status}`);
  }
  return res.json();
}

export async function startScan({ scope = 'mailbox', mode = 'incremental', query = '', forceRescan = false } = {}) {
  const params = new URLSearchParams();
  if (scope) params.append('scope', scope);
  if (mode) params.append('mode', mode);
  if (query) params.append('query', query);
  if (forceRescan) params.append('force_rescan', 'true');

  const res = await apiFetch(`/api/scan/start?${params.toString()}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      scope,
      mode,
      query,
      force_rescan: forceRescan,
    }),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || errorData.message || `Failed to start scan: HTTP ${res.status}`);
  }
  return res.json();
}

export async function cancelScan() {
  const res = await apiFetch('/api/scan/cancel', {
    method: 'POST',
  });
  if (!res.ok) throw new Error(`Failed to cancel scan: HTTP ${res.status}`);
  return res.json();
}

export async function rescanMailbox({ scope = 'mailbox' } = {}) {
  const res = await apiFetch('/api/scan/rescan', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ scope }),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || errorData.message || `Failed to trigger rescan: HTTP ${res.status}`);
  }
  return res.json();
}

// -----------------------------------------------------------------------------
// Smart Action Queue & Resolution Endpoints
// -----------------------------------------------------------------------------

export async function resolveAction(messageId, threadId = null, note = null) {
  const res = await apiFetch('/api/actions/resolve', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message_id: messageId,
      thread_id: threadId,
      note,
    }),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || errorData.message || `Failed to resolve action: HTTP ${res.status}`);
  }
  return res.json();
}

export async function unresolveAction(messageId) {
  const res = await apiFetch('/api/actions/unresolve', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message_id: messageId }),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || errorData.message || `Failed to undo resolution: HTTP ${res.status}`);
  }
  return res.json();
}

export async function snoozeAction(messageId, snoozeUntil, threadId = null, snoozeReason = null) {
  const res = await apiFetch('/api/actions/snooze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message_id: messageId,
      thread_id: threadId,
      snooze_until: snoozeUntil,
      snooze_reason: snoozeReason,
    }),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || errorData.message || `Failed to snooze action: HTTP ${res.status}`);
  }
  return res.json();
}

export async function unsnoozeAction(messageId) {
  const res = await apiFetch('/api/actions/unsnooze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message_id: messageId }),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || errorData.message || `Failed to unsnooze: HTTP ${res.status}`);
  }
  return res.json();
}

export async function fetchActionQueue({ sortBy = 'urgent', olderSortBy = 'oldest', thresholdDays = 8.0 } = {}) {
  const params = new URLSearchParams();
  if (sortBy) params.append('sort_by', sortBy);
  if (olderSortBy) params.append('older_sort_by', olderSortBy);
  if (thresholdDays) params.append('threshold_days', String(thresholdDays));

  const res = await apiFetch(`/api/actions/queue?${params.toString()}`);
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || errorData.message || `Failed to fetch action queue: HTTP ${res.status}`);
  }
  return res.json();
}

export async function fetchActionSummary(thresholdDays = 8.0) {
  const params = new URLSearchParams();
  if (thresholdDays) params.append('threshold_days', String(thresholdDays));

  const res = await apiFetch(`/api/actions/summary?${params.toString()}`);
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || errorData.message || `Failed to fetch action summary: HTTP ${res.status}`);
  }
  return res.json();
}

