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
