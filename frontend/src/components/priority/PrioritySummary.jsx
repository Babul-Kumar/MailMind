import React from 'react';
import { Sparkles, ArrowRight, CheckCircle2 } from 'lucide-react';
import { isNeedsAttention, hasGenuineDeadline } from '../../utils/priority';

export function PrioritySummary({ emails = [], onSelectFilter }) {
  if (!emails || emails.length === 0) return null;

  const attentionEmails = emails.filter(isNeedsAttention);
  const count = attentionEmails.length;
  const hasAttention = count > 0;

  // Breakdown of attention reasons for clean secondary summary
  const secCount = attentionEmails.filter((e) => e.action_reason === 'Account security action').length;
  const serviceCount = attentionEmails.filter((e) => e.action_reason === 'Service action').length;
  const deadlineCount = attentionEmails.filter((e) => Boolean(e.deadline_detected && e.action_reason !== 'Service action')).length;
  const otherActionCount = attentionEmails.filter(
    (e) => e.action_required && e.action_reason !== 'Account security action' && e.action_reason !== 'Service action'
  ).length;

  const detailParts = [];
  if (serviceCount > 0) detailParts.push(`${serviceCount} service action${serviceCount > 1 ? 's' : ''}`);
  if (secCount > 0) detailParts.push(`${secCount} security alert${secCount > 1 ? 's' : ''}`);
  if (deadlineCount > 0) detailParts.push(`${deadlineCount} deadline${deadlineCount > 1 ? 's' : ''}`);
  if (otherActionCount > 0) detailParts.push(`${otherActionCount} response required`);

  const secondaryText = detailParts.join(' · ') || (count === 1 ? '1 actionable email' : `${count} actionable emails`);

  if (!hasAttention) {
    return (
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.75rem',
          padding: '0.75rem 1.15rem',
          backgroundColor: 'rgba(34, 197, 94, 0.08)',
          border: '1px solid rgba(34, 197, 94, 0.22)',
          borderRadius: 'var(--radius-lg)',
          marginBottom: '1rem',
        }}
      >
        <CheckCircle2 size={18} color="var(--p3-color)" />
        <div>
          <div style={{ fontSize: '0.72rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--p3-color)' }}>
            ✓ You're all caught up
          </div>
          <p style={{ fontSize: '0.84rem', color: 'var(--text-secondary)', margin: '0.1rem 0 0' }}>
            No emails currently require your attention.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '0.85rem',
        padding: '0.85rem 1.25rem',
        backgroundColor: 'rgba(99, 102, 241, 0.08)',
        border: '1px solid rgba(99, 102, 241, 0.22)',
        borderRadius: 'var(--radius-lg)',
        marginBottom: '1rem',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.75rem' }}>
        <div style={{ marginTop: '0.15rem', color: 'var(--accent)' }}>
          <Sparkles size={18} />
        </div>
        <div>
          <div style={{ fontSize: '0.72rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--accent)', marginBottom: '0.15rem' }}>
            ✦ Inbox at a glance
          </div>
          <h4 style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--text-main)', margin: 0, lineHeight: 1.3 }}>
            {count} email{count === 1 ? '' : 's'} need attention
          </h4>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', margin: '0.2rem 0 0', lineHeight: 1.3 }}>
            {secondaryText}
          </p>
        </div>
      </div>

      <button
        onClick={() => onSelectFilter('NEEDS_ATTENTION')}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '0.35rem',
          padding: '0.38rem 0.85rem',
          backgroundColor: 'var(--accent)',
          color: '#fff',
          fontSize: '0.8rem',
          fontWeight: 600,
          borderRadius: 'var(--radius-sm)',
          border: 'none',
          cursor: 'pointer',
          whiteSpace: 'nowrap',
          transition: 'opacity 150ms ease',
        }}
      >
        <span>View attention</span>
        <ArrowRight size={13} />
      </button>
    </div>
  );
}
