/**
 * MailMind API Service
 * Centralized HTTP client for all MailMind backend communication.
 * Handles API base URL resolution, cross-origin cookies, and error parsing.
 */

/**
 * Resolves the backend API base URL.
 * In production (Vercel): Requires VITE_API_BASE_URL. Fails explicitly if missing.
 * In development: Falls back to empty string '' (which routes through Vite proxy)
 * or local dev backend.
 */
export function getApiBaseUrl() {
  const isProd = typeof import.meta !== 'undefined' && import.meta.env ? import.meta.env.PROD : false;
  const envUrl = typeof import.meta !== 'undefined' && import.meta.env ? import.meta.env.VITE_API_BASE_URL : undefined;

  if (envUrl && typeof envUrl === 'string' && envUrl.trim()) {
    return envUrl.trim().replace(/\/+$/, '');
  }

  if (isProd) {
    throw new Error(
      'MailMind Configuration Error: VITE_API_BASE_URL environment variable is required in production deployment. ' +
      'Please configure VITE_API_BASE_URL in your Vercel project settings pointing to your Render backend URL.'
    );
  }

  // Local development fallback (relative URLs use Vite dev proxy)
  return '';
}

/**
 * Exported constant base URL for convenience.
 */
export const API_BASE_URL = typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_BASE_URL
  ? import.meta.env.VITE_API_BASE_URL.trim().replace(/\/+$/, '')
  : '';

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
  const res = await apiFetch(`/api/auth/login?prompt=${encodeURIComponent(prompt)}`);
  if (!res.ok) throw new Error(`Login initiation failed: HTTP ${res.status}`);
  return res.json();
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
