export async function fetchHealth() {
  const res = await fetch('/api/health');
  if (!res.ok) throw new Error(`Health check failed: HTTP ${res.status}`);
  return res.json();
}

export async function fetchAuthStatus() {
  const res = await fetch('/api/auth/status');
  if (!res.ok) throw new Error(`Auth status failed: HTTP ${res.status}`);
  return res.json();
}

export async function fetchAuthLogin(prompt = 'select_account') {
  const res = await fetch(`/api/auth/login?prompt=${encodeURIComponent(prompt)}`);
  if (!res.ok) throw new Error(`Login initiation failed: HTTP ${res.status}`);
  return res.json();
}

export async function logout() {
  const res = await fetch('/api/auth/logout', { method: 'POST' });
  if (!res.ok) throw new Error(`Logout failed: HTTP ${res.status}`);
  return res.json();
}

export async function fetchProfile() {
  const res = await fetch('/api/profile');
  if (!res.ok) {
    if (res.status === 401) throw new Error('Authentication required');
    throw new Error(`Profile fetch failed: HTTP ${res.status}`);
  }
  return res.json();
}

export async function fetchModelInfo() {
  const res = await fetch('/api/model-info');
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

  const res = await fetch(`/api/emails?${params.toString()}`);
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    const err = new Error(errorData.message || errorData.detail || `HTTP ${res.status} error`);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

export async function fetchEmailDetail(emailId) {
  const res = await fetch(`/api/emails/${encodeURIComponent(emailId)}`);
  if (!res.ok) throw new Error(`Failed to fetch email detail: HTTP ${res.status}`);
  return res.json();
}

export async function submitFeedback(payload) {
  const res = await fetch('/api/feedback', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`Feedback submission failed: HTTP ${res.status}`);
  return res.json();
}

export async function fetchScanStatus() {
  const res = await fetch('/api/scan/status');
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

  const res = await fetch(`/api/scan/start?${params.toString()}`, {
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
  const res = await fetch('/api/scan/cancel', {
    method: 'POST',
  });
  if (!res.ok) throw new Error(`Failed to cancel scan: HTTP ${res.status}`);
  return res.json();
}

export async function rescanMailbox({ scope = 'mailbox' } = {}) {
  const res = await fetch('/api/scan/rescan', {
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

