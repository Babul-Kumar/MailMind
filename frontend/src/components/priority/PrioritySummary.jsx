import React from 'react';
import { Mail, Zap, ArrowRight } from 'lucide-react';
import { isNeedsAttention } from '../../utils/priority';

export function PrioritySummary({ emails = [], stats = null, onSelectFilter }) {
  const totalAnalyzed = stats?.total_analyzed ?? emails.length;
  if (!totalAnalyzed) return null;

  const count = stats?.needs_attention_count ?? emails.filter(isNeedsAttention).length;
  const counts = stats?.counts || { P1: 0, P2: 0, P3: 0, P4: 0 };

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))',
        gap: '0.75rem',
        marginBottom: '1.25rem',
      }}
    >
      {/* Card 1: Total Mailbox */}
      <div
        onClick={() => onSelectFilter?.('ALL')}
        style={{
          padding: '0.85rem 1rem',
          backgroundColor: 'var(--bg-surface)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-md)',
          cursor: 'pointer',
          transition: 'all var(--transition-fast)',
        }}
        title="Complete mailbox analyzed across all folders"
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
          <span style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Total Analyzed
          </span>
          <Mail size={15} color="var(--text-muted)" />
        </div>
        <div style={{ fontSize: '1.35rem', fontWeight: 700, color: 'var(--text-main)', letterSpacing: '-0.02em' }}>
          {totalAnalyzed.toLocaleString()}
        </div>
        <div style={{ fontSize: '0.74rem', color: '#22c55e', marginTop: '0.2rem', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
          <span>✓</span> Complete mailbox synchronized
        </div>
      </div>

      {/* Card 2: Needs Attention */}
      <div
        onClick={() => onSelectFilter?.('NEEDS_ATTENTION')}
        style={{
          padding: '0.85rem 1rem',
          backgroundColor: count > 0 ? 'rgba(99, 102, 241, 0.06)' : 'var(--bg-surface)',
          border: `1px solid ${count > 0 ? 'rgba(99, 102, 241, 0.25)' : 'var(--border-subtle)'}`,
          borderRadius: 'var(--radius-md)',
          cursor: 'pointer',
          transition: 'all var(--transition-fast)',
        }}
        title="Click to view emails requiring immediate action or with deadlines"
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
          <span style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--accent)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Needs Attention
          </span>
          <Zap size={15} color="var(--accent)" />
        </div>
        <div style={{ fontSize: '1.35rem', fontWeight: 700, color: count > 0 ? 'var(--accent)' : 'var(--text-main)', letterSpacing: '-0.02em' }}>
          {count.toLocaleString()}
        </div>
        <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
          Action required or active deadline
        </div>
      </div>

      {/* Card 3: Critical (P1) */}
      <div
        onClick={() => onSelectFilter?.('P1')}
        style={{
          padding: '0.85rem 1rem',
          backgroundColor: (counts.P1 || 0) > 0 ? 'rgba(239, 68, 68, 0.05)' : 'var(--bg-surface)',
          border: `1px solid ${(counts.P1 || 0) > 0 ? 'rgba(239, 68, 68, 0.22)' : 'var(--border-subtle)'}`,
          borderRadius: 'var(--radius-md)',
          cursor: 'pointer',
          transition: 'all var(--transition-fast)',
        }}
        title="Click to filter Critical Priority (P1) emails"
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
          <span style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--p1-color)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Critical (P1)
          </span>
          <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: 'var(--p1-color)' }} />
        </div>
        <div style={{ fontSize: '1.35rem', fontWeight: 700, color: (counts.P1 || 0) > 0 ? 'var(--p1-color)' : 'var(--text-main)', letterSpacing: '-0.02em' }}>
          {(counts.P1 || 0).toLocaleString()}
        </div>
        <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
          Immediate operational urgency
        </div>
      </div>

      {/* Card 4: Important (P2) */}
      <div
        onClick={() => onSelectFilter?.('P2')}
        style={{
          padding: '0.85rem 1rem',
          backgroundColor: 'var(--bg-surface)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-md)',
          cursor: 'pointer',
          transition: 'all var(--transition-fast)',
        }}
        title="Click to filter Important (P2) emails"
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
          <span style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--p2-color)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Important (P2)
          </span>
          <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: 'var(--p2-color)' }} />
        </div>
        <div style={{ fontSize: '1.35rem', fontWeight: 700, color: 'var(--text-main)', letterSpacing: '-0.02em' }}>
          {(counts.P2 || 0).toLocaleString()}
        </div>
        <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
          Model priority · Filter by action
        </div>
      </div>
    </div>
  );
}
