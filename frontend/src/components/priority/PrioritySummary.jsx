import React from 'react';
import { Zap } from 'lucide-react';
import { isNeedsAttention } from '../../utils/priority';

export function PrioritySummary({ emails = [], stats = null, onSelectFilter }) {
  const totalAnalyzed = stats?.total_analyzed ?? emails.length;
  if (!totalAnalyzed) return null;

  const count = stats?.needs_attention_count ?? emails.filter(isNeedsAttention).length;
  const counts = stats?.counts || { P1: 0, P2: 0, P3: 0, P4: 0 };

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '0.75rem',
        padding: '0.75rem 1.15rem',
        backgroundColor: 'var(--bg-surface)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--radius-lg)',
        marginBottom: '1rem',
        boxShadow: 'var(--shadow-sm)',
      }}
    >
      {/* Primary Hero: Needs Attention */}
      <div
        onClick={() => onSelectFilter?.('NEEDS_ATTENTION')}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.75rem',
          cursor: 'pointer',
          padding: '0.2rem 0.4rem',
          borderRadius: 'var(--radius-md)',
          transition: 'opacity var(--transition-fast)',
          flex: '1 1 260px',
        }}
        onMouseEnter={(e) => (e.currentTarget.style.opacity = '0.85')}
        onMouseLeave={(e) => (e.currentTarget.style.opacity = '1')}
        title="View emails requiring action or with active deadlines"
      >
        <div
          style={{
            width: '34px',
            height: '34px',
            borderRadius: 'var(--radius-md)',
            backgroundColor: 'var(--accent-light)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--accent)',
            flexShrink: 0,
          }}
        >
          <Zap size={17} />
        </div>
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.45rem' }}>
            <span style={{ fontSize: '0.86rem', fontWeight: 700, color: 'var(--text-main)' }}>
              Needs Attention
            </span>
            <span
              style={{
                fontSize: '1.2rem',
                fontWeight: 700,
                color: 'var(--accent)',
                letterSpacing: '-0.02em',
                lineHeight: 1,
              }}
            >
              {count.toLocaleString()}
            </span>
          </div>
          <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>
            Action required or active deadline
          </span>
        </div>
      </div>

      {/* Secondary & Tertiary Stats: P1, P2, Total Analyzed */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.55rem',
          flexWrap: 'wrap',
          flex: '1 1 auto',
          justifyContent: 'flex-end',
        }}
      >
        {/* P1 Pill */}
        <button
          onClick={() => onSelectFilter?.('P1')}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.45rem',
            padding: '0.35rem 0.7rem',
            backgroundColor: (counts.P1 || 0) > 0 ? 'rgba(244, 63, 94, 0.06)' : 'var(--bg-card)',
            border: `1px solid ${(counts.P1 || 0) > 0 ? 'rgba(244, 63, 94, 0.22)' : 'var(--border-subtle)'}`,
            borderRadius: 'var(--radius-md)',
            cursor: 'pointer',
            transition: 'all var(--transition-fast)',
          }}
          title="Filter P1 Critical emails"
          onMouseEnter={(e) => (e.currentTarget.style.borderColor = 'var(--p1-color)')}
          onMouseLeave={(e) =>
            (e.currentTarget.style.borderColor =
              (counts.P1 || 0) > 0 ? 'rgba(244, 63, 94, 0.22)' : 'var(--border-subtle)')
          }
        >
          <span
            style={{
              width: '7px',
              height: '7px',
              borderRadius: '50%',
              backgroundColor: 'var(--p1-color)',
            }}
          />
          <span style={{ fontSize: '0.76rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
            P1 Critical
          </span>
          <span style={{ fontSize: '0.84rem', fontWeight: 700, color: 'var(--p1-color)' }}>
            {(counts.P1 || 0).toLocaleString()}
          </span>
        </button>

        {/* P2 Pill */}
        <button
          onClick={() => onSelectFilter?.('P2')}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.45rem',
            padding: '0.35rem 0.7rem',
            backgroundColor: (counts.P2 || 0) > 0 ? 'rgba(245, 158, 11, 0.06)' : 'var(--bg-card)',
            border: `1px solid ${(counts.P2 || 0) > 0 ? 'rgba(245, 158, 11, 0.22)' : 'var(--border-subtle)'}`,
            borderRadius: 'var(--radius-md)',
            cursor: 'pointer',
            transition: 'all var(--transition-fast)',
          }}
          title="Filter P2 Important emails"
          onMouseEnter={(e) => (e.currentTarget.style.borderColor = 'var(--p2-color)')}
          onMouseLeave={(e) =>
            (e.currentTarget.style.borderColor =
              (counts.P2 || 0) > 0 ? 'rgba(245, 158, 11, 0.22)' : 'var(--border-subtle)')
          }
        >
          <span
            style={{
              width: '7px',
              height: '7px',
              borderRadius: '50%',
              backgroundColor: 'var(--p2-color)',
            }}
          />
          <span style={{ fontSize: '0.76rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
            P2 Important
          </span>
          <span style={{ fontSize: '0.84rem', fontWeight: 700, color: 'var(--p2-color)' }}>
            {(counts.P2 || 0).toLocaleString()}
          </span>
        </button>

        {/* Tertiary: Total Mailbox Analyzed */}
        <div
          onClick={() => onSelectFilter?.('ALL')}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.35rem',
            padding: '0.35rem 0.6rem',
            borderRadius: 'var(--radius-md)',
            fontSize: '0.75rem',
            color: 'var(--text-muted)',
            cursor: 'pointer',
            transition: 'color var(--transition-fast)',
          }}
          title="View all emails in mailbox"
          onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--text-main)')}
          onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--text-muted)')}
        >
          <span style={{ color: '#22c55e', fontWeight: 700 }}>✓</span>
          <span>
            <strong style={{ color: 'var(--text-secondary)' }}>
              {totalAnalyzed.toLocaleString()}
            </strong>{' '}
            analyzed
          </span>
        </div>
      </div>
    </div>
  );
}
