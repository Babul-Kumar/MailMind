export const PRIORITY_CONFIG = {
  P1: {
    label: 'Critical',
    fullLabel: 'Critical / Urgent',
    color: 'var(--p1-color)',
    bg: 'var(--p1-bg)',
    border: 'var(--p1-border)',
    badgeClass: 'badge-p1',
    rank: 4,
  },
  P2: {
    label: 'Important',
    fullLabel: 'Important / Actionable',
    color: 'var(--p2-color)',
    bg: 'var(--p2-bg)',
    border: 'var(--p2-border)',
    badgeClass: 'badge-p2',
    rank: 3,
  },
  P3: {
    label: 'Routine',
    fullLabel: 'Routine / Informational',
    color: 'var(--p3-color)',
    bg: 'var(--p3-bg)',
    border: 'var(--p3-border)',
    badgeClass: 'badge-p3',
    rank: 2,
  },
  P4: {
    label: 'Low',
    fullLabel: 'Low / Promotional / Noise',
    color: 'var(--p4-color)',
    bg: 'var(--p4-bg)',
    border: 'var(--p4-border)',
    badgeClass: 'badge-p4',
    rank: 1,
  },
};

export function getPriorityMeta(priority) {
  return PRIORITY_CONFIG[priority] || PRIORITY_CONFIG.P4;
}

export function hasGenuineDeadline(email) {
  if (!email) return false;
  if (email.deadline_detected) return true;
  const text = `${email.subject || ''} ${email.body || ''}`;
  return /\b((?:submission |assignment |registration |application |payment |competition )?deadline|due (?:date|on|by|before)|closes (?:on|at|by)|expires (?:on|in|at)|last date (?:to|for)|valid (?:until|till|through)|before (?:midnight|[0-9]{1,2}:[0-9]{2})|action required (?:by|before))\b/i.test(text);
}

export function isNeedsAttention(email) {
  if (!email) return false;
  const p = email.final_priority || email.predicted_priority;
  if (p === 'P1') return true;
  if (p === 'P2' && email.action_required) return true;
  if (email.action_required && hasGenuineDeadline(email)) return true;
  return false;
}
