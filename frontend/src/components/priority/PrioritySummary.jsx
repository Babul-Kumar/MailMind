import React, { useMemo } from 'react';
import { Sparkles, Layers } from 'lucide-react';

function PrioritySummaryComponent({ emails = [], stats = null, onSelectFilter, activeFilter = 'ALL' }) {
  const totalAnalyzed = stats?.total_analyzed ?? emails.length;
  if (!totalAnalyzed) return null;

  const counts = stats?.counts || { P1: 0, P2: 0, P3: 0, P4: 0 };
  const p1 = counts.P1 || 0;
  const p2 = counts.P2 || 0;
  const p3 = counts.P3 || 0;
  const p4 = counts.P4 || 0;
  const sum = p1 + p2 + p3 + p4 || totalAnalyzed || 1;

  const p1Pct = ((p1 / sum) * 100).toFixed(1);
  const p2Pct = ((p2 / sum) * 100).toFixed(1);
  const p3Pct = ((p3 / sum) * 100).toFixed(1);
  const p4Pct = ((p4 / sum) * 100).toFixed(1);

  return (
    <div
      className="priority-summary-card"
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '0.85rem',
        padding: '0.95rem 1.25rem',
        backgroundColor: 'var(--bg-surface)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--radius-lg)',
        boxShadow: 'var(--shadow-sm)',
        marginBottom: '1rem',
        transition: 'all var(--transition-fast)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
        {/* Priority Breakdown Chips */}
        <div className="priority-summary-breakdown" style={{ display: 'flex', gap: '0.55rem', flexWrap: 'wrap', flex: 1, alignItems: 'center' }}>
          {/* P1 Critical */}
          <button
            type="button"
            onClick={() => onSelectFilter?.(activeFilter === 'P1' ? 'ALL' : 'P1')}
            className={`priority-breakdown-chip ${activeFilter === 'P1' ? 'active-chip' : ''}`}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.45rem',
              padding: '0.35rem 0.75rem',
              borderRadius: 'var(--radius-sm)',
              fontSize: '0.8rem',
              fontWeight: 600,
              cursor: 'pointer',
              border: activeFilter === 'P1' ? '1px solid var(--p1-color)' : '1px solid var(--p1-border)',
              backgroundColor: activeFilter === 'P1' ? 'var(--p1-bg)' : 'var(--bg-card)',
              color: 'var(--p1-color)',
              boxShadow: activeFilter === 'P1' ? '0 0 12px var(--p1-glow)' : 'none',
              transition: 'all var(--transition-fast)',
            }}
            title="Filter P1 Critical emails"
          >
            <span
              className={p1 > 0 ? 'animate-pulse-p1' : ''}
              style={{
                width: '7px',
                height: '7px',
                borderRadius: '50%',
                backgroundColor: 'var(--p1-color)',
                display: 'inline-block',
              }}
            />
            <span>P1 Critical</span>
            <span
              style={{
                marginLeft: '0.2rem',
                padding: '0.05rem 0.4rem',
                borderRadius: 'var(--radius-xs)',
                backgroundColor: 'rgba(255, 51, 102, 0.15)',
                fontWeight: 700,
                fontSize: '0.74rem',
              }}
            >
              {p1.toLocaleString()}
            </span>
          </button>

          {/* P2 Important */}
          <button
            type="button"
            onClick={() => onSelectFilter?.(activeFilter === 'P2' ? 'ALL' : 'P2')}
            className={`priority-breakdown-chip ${activeFilter === 'P2' ? 'active-chip' : ''}`}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.45rem',
              padding: '0.35rem 0.75rem',
              borderRadius: 'var(--radius-sm)',
              fontSize: '0.8rem',
              fontWeight: 600,
              cursor: 'pointer',
              border: activeFilter === 'P2' ? '1px solid var(--p2-color)' : '1px solid var(--p2-border)',
              backgroundColor: activeFilter === 'P2' ? 'var(--p2-bg)' : 'var(--bg-card)',
              color: 'var(--p2-color)',
              boxShadow: activeFilter === 'P2' ? '0 0 12px var(--p2-glow)' : 'none',
              transition: 'all var(--transition-fast)',
            }}
            title="Filter P2 Important emails"
          >
            <span
              style={{
                width: '7px',
                height: '7px',
                borderRadius: '50%',
                backgroundColor: 'var(--p2-color)',
                display: 'inline-block',
              }}
            />
            <span>P2 Important</span>
            <span
              style={{
                marginLeft: '0.2rem',
                padding: '0.05rem 0.4rem',
                borderRadius: 'var(--radius-xs)',
                backgroundColor: 'rgba(245, 158, 11, 0.15)',
                fontWeight: 700,
                fontSize: '0.74rem',
              }}
            >
              {p2.toLocaleString()}
            </span>
          </button>

          {/* P3 Routine */}
          <button
            type="button"
            onClick={() => onSelectFilter?.(activeFilter === 'P3' ? 'ALL' : 'P3')}
            className={`priority-breakdown-chip ${activeFilter === 'P3' ? 'active-chip' : ''}`}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.45rem',
              padding: '0.35rem 0.75rem',
              borderRadius: 'var(--radius-sm)',
              fontSize: '0.8rem',
              fontWeight: 600,
              cursor: 'pointer',
              border: activeFilter === 'P3' ? '1px solid var(--p3-color)' : '1px solid var(--p3-border)',
              backgroundColor: activeFilter === 'P3' ? 'var(--p3-bg)' : 'var(--bg-card)',
              color: 'var(--p3-color)',
              boxShadow: activeFilter === 'P3' ? '0 0 12px var(--p3-glow)' : 'none',
              transition: 'all var(--transition-fast)',
            }}
            title="Filter P3 Routine emails"
          >
            <span
              style={{
                width: '7px',
                height: '7px',
                borderRadius: '50%',
                backgroundColor: 'var(--p3-color)',
                display: 'inline-block',
              }}
            />
            <span>P3 Routine</span>
            <span
              style={{
                marginLeft: '0.2rem',
                padding: '0.05rem 0.4rem',
                borderRadius: 'var(--radius-xs)',
                backgroundColor: 'rgba(56, 189, 248, 0.15)',
                fontWeight: 700,
                fontSize: '0.74rem',
              }}
            >
              {p3.toLocaleString()}
            </span>
          </button>

          {/* P4 Low */}
          <button
            type="button"
            onClick={() => onSelectFilter?.(activeFilter === 'P4' ? 'ALL' : 'P4')}
            className={`priority-breakdown-chip ${activeFilter === 'P4' ? 'active-chip' : ''}`}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.45rem',
              padding: '0.35rem 0.75rem',
              borderRadius: 'var(--radius-sm)',
              fontSize: '0.8rem',
              fontWeight: 600,
              cursor: 'pointer',
              border: activeFilter === 'P4' ? '1px solid var(--p4-color)' : '1px solid var(--p4-border)',
              backgroundColor: activeFilter === 'P4' ? 'var(--p4-bg)' : 'var(--bg-card)',
              color: 'var(--p4-color)',
              boxShadow: activeFilter === 'P4' ? '0 0 10px var(--p4-glow)' : 'none',
              transition: 'all var(--transition-fast)',
            }}
            title="Filter P4 Low priority emails"
          >
            <span
              style={{
                width: '7px',
                height: '7px',
                borderRadius: '50%',
                backgroundColor: 'var(--p4-color)',
                display: 'inline-block',
              }}
            />
            <span>P4 Low</span>
            <span
              style={{
                marginLeft: '0.2rem',
                padding: '0.05rem 0.4rem',
                borderRadius: 'var(--radius-xs)',
                backgroundColor: 'rgba(148, 163, 184, 0.15)',
                fontWeight: 700,
                fontSize: '0.74rem',
              }}
            >
              {p4.toLocaleString()}
            </span>
          </button>
        </div>

        {/* Total Analyzed Status Badge */}
        <div
          onClick={() => onSelectFilter?.('ALL')}
          role="button"
          tabIndex={0}
          title="Reset filter to view all emails in mailbox"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.45rem',
            padding: '0.3rem 0.65rem',
            borderRadius: 'var(--radius-sm)',
            backgroundColor: activeFilter === 'ALL' ? 'var(--accent-light)' : 'var(--bg-card)',
            border: activeFilter === 'ALL' ? '1px solid var(--accent)' : '1px solid var(--border-subtle)',
            color: activeFilter === 'ALL' ? 'var(--accent)' : 'var(--text-muted)',
            fontSize: '0.76rem',
            fontWeight: 600,
            cursor: 'pointer',
            transition: 'all var(--transition-fast)',
          }}
        >
          <Sparkles size={13} style={{ color: 'var(--accent)' }} />
          <span>{totalAnalyzed.toLocaleString()} emails analyzed</span>
          {activeFilter !== 'ALL' && (
            <span style={{ fontSize: '0.7rem', color: 'var(--accent)', marginLeft: '0.2rem' }}>
              (Show all)
            </span>
          )}
        </div>
      </div>

      {/* Visual Priority Distribution Bar */}
      <div
        style={{
          display: 'flex',
          height: '4px',
          width: '100%',
          borderRadius: 'var(--radius-full)',
          overflow: 'hidden',
          backgroundColor: 'var(--border-divider)',
          gap: '1px',
        }}
        title={`Distribution: P1 ${p1Pct}% · P2 ${p2Pct}% · P3 ${p3Pct}% · P4 ${p4Pct}%`}
      >
        {p1 > 0 && (
          <div
            style={{
              width: `${p1Pct}%`,
              backgroundColor: 'var(--p1-color)',
              transition: 'width 0.4s ease',
            }}
          />
        )}
        {p2 > 0 && (
          <div
            style={{
              width: `${p2Pct}%`,
              backgroundColor: 'var(--p2-color)',
              transition: 'width 0.4s ease',
            }}
          />
        )}
        {p3 > 0 && (
          <div
            style={{
              width: `${p3Pct}%`,
              backgroundColor: 'var(--p3-color)',
              transition: 'width 0.4s ease',
            }}
          />
        )}
        {p4 > 0 && (
          <div
            style={{
              width: `${p4Pct}%`,
              backgroundColor: 'var(--p4-color)',
              transition: 'width 0.4s ease',
            }}
          />
        )}
      </div>
    </div>
  );
}

export const PrioritySummary = React.memo(PrioritySummaryComponent);
export default PrioritySummary;
