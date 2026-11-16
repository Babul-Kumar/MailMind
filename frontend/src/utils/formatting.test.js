import test from 'node:test';
import assert from 'node:assert/strict';
import { getDeadlineState } from './formatting.js';

test('1. future deadline (general)', () => {
  const email = {
    deadline_detected: true,
    deadline_datetime: '2026-10-05T23:59:00',
    deadline_precision: 'DATETIME',
  };
  const now = new Date(2026, 8, 30, 12, 0, 0); // Sep 30, 2026
  const state = getDeadlineState(email, now);
  assert.equal(state?.state, 'upcoming');
  assert.equal(state?.icon, '⏰');
  assert.equal(state?.label, 'Oct 5 · 5 days');
});

test('2. deadline today', () => {
  const email = {
    deadline_detected: true,
    deadline_datetime: '2026-09-30T23:59:00',
    deadline_precision: 'DATETIME',
  };
  const now = new Date(2026, 8, 30, 15, 0, 0); // Sep 30, 2026 at 3 PM
  const state = getDeadlineState(email, now);
  assert.equal(state?.state, 'today');
  assert.equal(state?.icon, '⏰');
  assert.equal(state?.label, 'Today · 11:59 PM');
  assert.equal(state?.timeStr, '11:59 PM');
});

test('3. past deadline (general overdue)', () => {
  const email = {
    deadline_detected: true,
    deadline_datetime: '2026-09-30T23:59:00',
    deadline_precision: 'DATETIME',
  };
  const now = new Date(2026, 9, 1, 9, 0, 0); // Oct 1, 2026 at 9 AM
  const state = getDeadlineState(email, now);
  assert.equal(state?.state, 'overdue');
  assert.equal(state?.icon, '⚠');
  assert.equal(state?.label, 'Overdue · Sep 30 · 11:59 PM');
});

test('4. date-only future deadline', () => {
  const email = {
    deadline_detected: true,
    deadline_datetime: '2026-10-05',
    deadline_precision: 'DATE',
  };
  const now = new Date(2026, 8, 30, 10, 0, 0); // Sep 30, 2026
  const state = getDeadlineState(email, now);
  assert.equal(state?.state, 'upcoming');
  assert.equal(state?.icon, '⏰');
  assert.equal(state?.label, 'Oct 5 · 5 days');
  assert.equal(state?.isDateOnly, true);
  assert.equal(state?.timeStr, null);
});

test('5. date-only past deadline', () => {
  const email = {
    deadline_detected: true,
    deadline_datetime: '2026-09-25',
    deadline_precision: 'DATE',
  };
  const now = new Date(2026, 9, 1, 12, 0, 0); // Oct 1, 2026
  const state = getDeadlineState(email, now);
  assert.equal(state?.state, 'overdue');
  assert.equal(state?.icon, '⚠');
  assert.equal(state?.label, 'Overdue · Sep 25');
  assert.equal(state?.isDateOnly, true);
  assert.equal(state?.timeStr, null);
});

test('6. datetime future', () => {
  const email = {
    deadline_detected: true,
    deadline_datetime: '2026-10-10T17:00:00',
    deadline_precision: 'DATETIME',
  };
  const now = new Date(2026, 8, 30, 12, 0, 0); // Sep 30, 2026
  const state = getDeadlineState(email, now);
  assert.equal(state?.state, 'upcoming');
  assert.equal(state?.icon, '⏰');
  assert.equal(state?.label, 'Oct 10 · 10 days');
  assert.equal(state?.timeStr, '5:00 PM');
  assert.equal(state?.longLabel, 'Oct 10, 2026 at 5:00 PM');
});

test('7. datetime past', () => {
  const email = {
    deadline_detected: true,
    deadline_datetime: '2026-09-30T23:59:00',
    deadline_precision: 'DATETIME',
  };
  const now = new Date(2026, 9, 1, 8, 30, 0); // Oct 1, 2026
  const state = getDeadlineState(email, now);
  assert.equal(state?.state, 'overdue');
  assert.equal(state?.icon, '⚠');
  assert.equal(state?.label, 'Overdue · Sep 30 · 11:59 PM');
  assert.equal(state?.longLabel, 'Sep 30, 2026 at 11:59 PM');
  assert.equal(state?.timeStr, '11:59 PM');
});

test('8. historical deadline (date-only)', () => {
  const email = {
    deadline_detected: true,
    deadline_datetime: '2024-05-15',
    deadline_precision: 'DATE',
    deadline_status: 'HISTORICAL',
  };
  const now = new Date(2026, 9, 1, 12, 0, 0);
  const state = getDeadlineState(email, now);
  assert.equal(state?.state, 'historical');
  assert.equal(state?.icon, '📅');
  assert.equal(state?.label, 'Past · May 15');
});

test('9. historical deadline (datetime)', () => {
  const email = {
    deadline_detected: true,
    deadline_datetime: '2023-11-20T18:00:00',
    deadline_precision: 'DATETIME',
    deadline_status: 'HISTORICAL',
  };
  const now = new Date(2026, 9, 1, 12, 0, 0);
  const state = getDeadlineState(email, now);
  assert.equal(state?.state, 'historical');
  assert.equal(state?.icon, '📅');
  assert.equal(state?.label, 'Past · Nov 20 · 6:00 PM');
});

test('10. cleanSenderName cleans display name, quotes, and addresses', () => {
  import('./formatting.js').then(({ cleanSenderName, extractSnippet }) => {
    assert.equal(cleanSenderName('"NPTEL Exam Cell" <exams@nptel.iitm.ac.in>'), 'NPTEL Exam Cell');
    assert.equal(cleanSenderName('Google Security Team <no-reply@accounts.google.com>'), 'Google Security Team');
    assert.equal(cleanSenderName('user@domain.com'), 'user@domain.com');
    assert.equal(cleanSenderName(''), 'Unknown Sender');
    assert.equal(cleanSenderName(null), 'Unknown Sender');

    assert.equal(extractSnippet('First line of text that is short', 'Subj'), 'First line of text that is short');
    assert.equal(extractSnippet('   Lots of   spaces and newlines   ', 'Subj'), 'Lots of spaces and newlines');
  });
});

test('11. isItemInWindow strictly filters this_month and last_3_months', async () => {
  const { isItemInWindow } = await import('./formatting.js');
  const now = new Date(2026, 10, 16, 12, 0, 0); // Nov 16, 2026

  // Item from Nov 5, 2026 (this month)
  const itemThisMonth = {
    date: '2026-11-05T10:00:00Z',
    daysAgo: 11
  };
  assert.equal(isItemInWindow(itemThisMonth, 'this_month', now), true);
  assert.equal(isItemInWindow(itemThisMonth, 'last_3_months', now), true);

  // Item from Oct 10, 2026 (last month / 37 days ago)
  const itemLastMonth = {
    date: '2026-10-10T10:00:00Z',
    daysAgo: 37
  };
  assert.equal(isItemInWindow(itemLastMonth, 'this_month', now), false);
  assert.equal(isItemInWindow(itemLastMonth, 'last_3_months', now), true);

  // Item from June 1, 2026 (> 5 months ago)
  const itemOld = {
    date: '2026-06-01T10:00:00Z',
    daysAgo: 168
  };
  assert.equal(isItemInWindow(itemOld, 'this_month', now), false);
  assert.equal(isItemInWindow(itemOld, 'last_3_months', now), false);
});

