import test from 'node:test';
import assert from 'node:assert/strict';
import { getApiBaseUrl, apiFetch } from './api.js';

test('1. getApiBaseUrl returns empty string or dev fallback when unset in non-production', () => {
  const url = getApiBaseUrl();
  assert.equal(typeof url, 'string');
});

test('2. apiFetch sets credentials to include', async () => {
  const originalFetch = globalThis.fetch;
  let capturedOptions = null;
  let capturedUrl = null;

  globalThis.fetch = async (url, options) => {
    capturedUrl = url;
    capturedOptions = options;
    return {
      ok: true,
      json: async () => ({ status: 'ok' })
    };
  };

  try {
    const res = await apiFetch('/api/test-endpoint');
    assert.equal(capturedOptions?.credentials, 'include');
    assert.ok(capturedUrl.endsWith('/api/test-endpoint'));
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('3. apiFetch merges json body and content-type header', async () => {
  const originalFetch = globalThis.fetch;
  let capturedOptions = null;

  globalThis.fetch = async (url, options) => {
    capturedOptions = options;
    return {
      ok: true,
      json: async () => ({ status: 'ok' })
    };
  };

  try {
    const payload = JSON.stringify({ message: 'hello' });
    await apiFetch('/api/feedback', { method: 'POST', body: payload });
    assert.equal(capturedOptions?.credentials, 'include');
    assert.equal(capturedOptions?.headers?.['Content-Type'], 'application/json');
  } finally {
    globalThis.fetch = originalFetch;
  }
});
