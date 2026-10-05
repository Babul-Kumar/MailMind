import React from 'react';
import { Zap } from 'lucide-react';
import { isNeedsAttention } from '../../utils/priority';

function PrioritySummaryComponent({ emails = [], stats = null, onSelectFilter }) {
  const totalAnalyzed = stats?.total_analyzed ?? emails.length;
  if (!totalAnalyzed) return null;

  const count = stats?.needs_attention_count ?? (emails.length > 0 ? emails.filter(isNeedsAttention).length : 0);
  const counts = stats?.counts || { P1: 0, P2: 0, P3: 0, P4: 0 };

  return (
    <div className="priority-summary-card">
      {/* Primary: Needs Attention Metric */}
      <div
        className="priority-summary-hero"
        onClick={() => onSelectFilter?.('NEEDS_ATTENTION')}
        role="button"
        tabIndex={0}
        title="View emails requiring action or with active deadlines"
      >
        <div className="priority-summary-header-row">
          <div className="priority-summary-icon-badge">
            <Zap size={16} />
          </div>
          <span className="priority-summary-label">Needs Attention</span>
        </div>

        <div className="priority-summary-metric">
          {count.toLocaleString()}
        </div>

        <div className="priority-summary-subtext">
          Action required or active deadline
        </div>
      </div>

      {/* Secondary: Priority Breakdown Chips */}
      <div className="priority-summary-breakdown">
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
      </div>

      {/* Tertiary: Subtle Background Processing Metadata */}
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

