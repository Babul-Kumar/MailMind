import React from 'react';

function PrioritySummaryComponent({ emails = [], stats = null, onSelectFilter }) {
  const totalAnalyzed = stats?.total_analyzed ?? emails.length;
  if (!totalAnalyzed) return null;

  const counts = stats?.counts || { P1: 0, P2: 0, P3: 0, P4: 0 };

  return (
    <div className="priority-summary-card">
      {/* Priority Breakdown: P1 to P4 */}
      <div className="priority-summary-breakdown" style={{ display: 'flex', gap: '0.65rem', flexWrap: 'wrap', flex: 1 }}>
        <button
          type="button"
          onClick={() => onSelectFilter?.('P1')}
          className="priority-breakdown-chip p1-chip"
          title="Filter P1 Critical emails"
        >
          <span className="priority-chip-dot p1-dot" />
          <span className="priority-chip-title">P1 Critical</span>
          <span className="priority-chip-num p1-num">{(counts.P1 || 0).toLocaleString()}</span>
        </button>

        <button
          type="button"
          onClick={() => onSelectFilter?.('P2')}
          className="priority-breakdown-chip p2-chip"
          title="Filter P2 Important emails"
        >
          <span className="priority-chip-dot p2-dot" />
          <span className="priority-chip-title">P2 Important</span>
          <span className="priority-chip-num p2-num">{(counts.P2 || 0).toLocaleString()}</span>
        </button>

        <button
          type="button"
          onClick={() => onSelectFilter?.('P3')}
          className="priority-breakdown-chip"
          title="Filter P3 Routine emails"
        >
          <span className="priority-chip-dot" style={{ backgroundColor: 'var(--p3-color, #3b82f6)' }} />
          <span className="priority-chip-title">P3 Routine</span>
          <span className="priority-chip-num">{(counts.P3 || 0).toLocaleString()}</span>
        </button>

        <button
          type="button"
          onClick={() => onSelectFilter?.('P4')}
          className="priority-breakdown-chip"
          title="Filter P4 Low priority emails"
        >
          <span className="priority-chip-dot" style={{ backgroundColor: 'var(--p4-color, #64748b)' }} />
          <span className="priority-chip-title">P4 Low</span>
          <span className="priority-chip-num">{(counts.P4 || 0).toLocaleString()}</span>
        </button>
      </div>

      {/* Background Processing Metadata */}
      <div
        className="priority-summary-meta"
        onClick={() => onSelectFilter?.('ALL')}
        role="button"
        tabIndex={0}
        title="View all emails in mailbox"
      >
        <span className="priority-meta-check">✓</span>
        <span>{totalAnalyzed.toLocaleString()} emails analyzed</span>
      </div>
    </div>
  );
}

export const PrioritySummary = React.memo(PrioritySummaryComponent);
