import React, { useState } from 'react';
import { History, Calendar, Search, Filter, Sparkles, CheckCircle2, AlertCircle } from 'lucide-react';
import { PriorityBadge } from '../priority/PriorityBadge';
import { formatEmailDate, cleanSenderName, extractSnippet } from '../../utils/formatting';
import { EmptyState } from '../common/EmptyState';

export function HistoryView({
  emails = [],
  pagination,
  onPageChange,
  isLoading = false,
  startDate = '',
  endDate = '',
  searchQuery = '',
  analyzedOnly = false,
  onFilterChange,
  onSelectEmail,
}) {
  const [localStart, setLocalStart] = useState(startDate);
  const [localEnd, setLocalEnd] = useState(endDate);
  const [localSearch, setLocalSearch] = useState(searchQuery);
  const [localAnalyzed, setLocalAnalyzed] = useState(analyzedOnly);

  const handleApplyFilter = (e) => {
    e?.preventDefault();
    onFilterChange?.({
      startDate: localStart,
      endDate: localEnd,
      query: localSearch,
      analyzedOnly: localAnalyzed,
    });
  };

  const handleResetFilter = () => {
    setLocalStart('');
    setLocalEnd('');
    setLocalSearch('');
    setLocalAnalyzed(false);
    onFilterChange?.({
      startDate: '',
      endDate: '',
      query: '',
      analyzedOnly: false,
    });
  };

  const totalCount = pagination?.total_items ?? emails.length;
  const pageNum = pagination?.page || 1;
  const pageSize = pagination?.page_size || 50;
  const startIdx = totalCount > 0 ? (pageNum - 1) * pageSize + 1 : 0;
  const endIdx = totalCount > 0 ? Math.min(pageNum * pageSize, totalCount) : 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', width: '100%' }}>
      {/* Header Banner */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          padding: '1rem 1.25rem',
          backgroundColor: 'var(--bg-surface)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-md)',
          gap: '1rem',
          flexWrap: 'wrap',
        }}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <History size={18} color="var(--accent)" />
            <h2 style={{ fontSize: '1.05rem', fontWeight: 700, color: 'var(--text-main)', margin: 0 }}>
              All Mailbox History
            </h2>
            <span
              style={{
                fontSize: '0.74rem',
                fontWeight: 600,
                padding: '0.15rem 0.5rem',
                borderRadius: '999px',
                backgroundColor: 'var(--badge-bg)',
                color: 'var(--text-secondary)',
              }}
            >
              {totalCount.toLocaleString()} {totalCount === 1 ? 'message' : 'messages'}
            </span>
          </div>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', margin: 0 }}>
            Browse older synchronized messages beyond your current analysis window. Historical browsing does not trigger automatic bulk ML inference.
          </p>
        </div>

        {totalCount > 0 && (
          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
            Showing {startIdx}–{endIdx} of {totalCount.toLocaleString()}
          </div>
        )}
      </div>

      {/* Date & Filter Toolbar */}
      <form
        onSubmit={handleApplyFilter}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.65rem',
          padding: '0.75rem 1rem',
          backgroundColor: 'var(--bg-surface)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-md)',
          flexWrap: 'wrap',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', flex: '1 1 180px' }}>
          <Search size={14} color="var(--text-muted)" />
          <input
            type="text"
            placeholder="Search sender, subject..."
            value={localSearch}
            onChange={(e) => setLocalSearch(e.target.value)}
            style={{
              width: '100%',
              padding: '0.35rem 0.55rem',
              fontSize: '0.8rem',
              borderRadius: 'var(--radius-xs)',
              border: '1px solid var(--border-subtle)',
              backgroundColor: 'var(--bg-card)',
              color: 'var(--text-main)',
            }}
          />
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <span style={{ fontSize: '0.76rem', color: 'var(--text-muted)' }}>From:</span>
          <input
            type="date"
            value={localStart}
            onChange={(e) => setLocalStart(e.target.value)}
            style={{
              padding: '0.35rem 0.45rem',
              fontSize: '0.78rem',
              borderRadius: 'var(--radius-xs)',
              border: '1px solid var(--border-subtle)',
              backgroundColor: 'var(--bg-card)',
              color: 'var(--text-main)',
            }}
          />
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <span style={{ fontSize: '0.76rem', color: 'var(--text-muted)' }}>To:</span>
          <input
            type="date"
            value={localEnd}
            onChange={(e) => setLocalEnd(e.target.value)}
            style={{
              padding: '0.35rem 0.45rem',
              fontSize: '0.78rem',
              borderRadius: 'var(--radius-xs)',
              border: '1px solid var(--border-subtle)',
              backgroundColor: 'var(--bg-card)',
              color: 'var(--text-main)',
            }}
          />
        </div>

        <label style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.78rem', color: 'var(--text-secondary)', cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={localAnalyzed}
            onChange={(e) => setLocalAnalyzed(e.target.checked)}
          />
          <span>Analyzed only</span>
        </label>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginLeft: 'auto' }}>
          <button
            type="submit"
            style={{
              padding: '0.35rem 0.75rem',
              backgroundColor: 'var(--accent)',
              color: '#ffffff',
              fontSize: '0.78rem',
              fontWeight: 600,
              borderRadius: 'var(--radius-xs)',
              border: 'none',
              cursor: 'pointer',
            }}
          >
            Apply
          </button>
          {(localStart || localEnd || localSearch || localAnalyzed) && (
            <button
              type="button"
              onClick={handleResetFilter}
              style={{
                padding: '0.35rem 0.6rem',
                backgroundColor: 'transparent',
                color: 'var(--text-muted)',
                fontSize: '0.78rem',
                borderRadius: 'var(--radius-xs)',
                border: '1px solid var(--border-subtle)',
                cursor: 'pointer',
              }}
            >
              Reset
            </button>
          )}
        </div>
      </form>

      {/* History Emails Feed */}
      {isLoading ? (
        <div style={{ padding: '3rem 1rem', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
          Loading historical messages...
        </div>
      ) : emails.length === 0 ? (
        <EmptyState
          type="history"
          title="No historical emails found"
          description="Try broadening your date filter or search query."
        />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
          {emails.map((email) => {
            const isAnalyzed = email.is_analyzed !== 0 && email.is_analyzed !== false && Boolean(email.effective_priority || email.final_priority || email.predicted_priority);
            const priority = isAnalyzed ? (email.effective_priority || email.final_priority || email.predicted_priority) : null;
            const senderClean = cleanSenderName(email.sender);
            const dateStr = formatEmailDate(email.date);
            const snippet = extractSnippet(email.body, email.subject);

            return (
              <div
                key={email.email_id || email.id}
                onClick={() => onSelectEmail?.(email)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  padding: '0.65rem 0.95rem',
                  backgroundColor: 'var(--bg-surface)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 'var(--radius-sm)',
                  cursor: 'pointer',
                  gap: '0.85rem',
                  transition: 'background-color var(--transition-fast)',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'var(--bg-surface-hover)')}
                onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'var(--bg-surface)')}
              >
                {/* Priority or Unanalyzed Badge */}
                <div style={{ minWidth: '85px', flexShrink: 0 }}>
                  {isAnalyzed ? (
                    <PriorityBadge priority={priority} size="sm" />
                  ) : (
                    <span
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '0.3rem',
                        fontSize: '0.68rem',
                        fontWeight: 600,
                        padding: '0.12rem 0.45rem',
                        borderRadius: 'var(--radius-xs)',
                        backgroundColor: 'var(--bg-surface-hover)',
                        color: 'var(--text-muted)',
                        border: '1px solid var(--border-subtle)',
                      }}
                    >
                      <span style={{ width: '5px', height: '5px', borderRadius: '50%', backgroundColor: 'var(--text-muted)' }} />
                      Unanalyzed
                    </span>
                  )}
                </div>

                {/* Sender */}
                <div
                  style={{
                    minWidth: '150px',
                    maxWidth: '180px',
                    fontSize: '0.82rem',
                    fontWeight: isAnalyzed && priority === 'P1' ? 700 : 600,
                    color: 'var(--text-main)',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                    flexShrink: 0,
                  }}
                >
                  {senderClean}
                </div>

                {/* Subject & Snippet */}
                <div style={{ flex: 1, minWidth: 0, display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
                  <span
                    style={{
                      fontSize: '0.82rem',
                      fontWeight: 600,
                      color: 'var(--text-main)',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {email.subject || '(No subject)'}
                  </span>
                  {snippet && (
                    <span
                      style={{
                        fontSize: '0.78rem',
                        color: 'var(--text-muted)',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      — {snippet}
                    </span>
                  )}
                </div>

                {/* Date */}
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', flexShrink: 0, textAlign: 'right' }}>
                  {dateStr}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Pagination Controls */}
      {pagination && pagination.total_pages > 1 && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '0.75rem 0.5rem',
            borderTop: '1px solid var(--border-subtle)',
            fontSize: '0.82rem',
            color: 'var(--text-secondary)',
          }}
        >
          <div>
            Page <strong>{pagination.page}</strong> of <strong>{pagination.total_pages}</strong>
          </div>
          <div style={{ display: 'flex', gap: '0.45rem' }}>
            <button
              onClick={() => onPageChange?.(pagination.page - 1)}
              disabled={!pagination.has_prev || isLoading}
              style={{
                padding: '0.35rem 0.75rem',
                fontSize: '0.78rem',
                borderRadius: 'var(--radius-xs)',
                border: '1px solid var(--border-subtle)',
                backgroundColor: 'var(--bg-surface)',
                color: pagination.has_prev ? 'var(--text-main)' : 'var(--text-muted)',
                cursor: pagination.has_prev ? 'pointer' : 'not-allowed',
              }}
            >
              Previous
            </button>
            <button
              onClick={() => onPageChange?.(pagination.page + 1)}
              disabled={!pagination.has_next || isLoading}
              style={{
                padding: '0.35rem 0.75rem',
                fontSize: '0.78rem',
                borderRadius: 'var(--radius-xs)',
                border: '1px solid var(--border-subtle)',
                backgroundColor: 'var(--bg-surface)',
                color: pagination.has_next ? 'var(--text-main)' : 'var(--text-muted)',
                cursor: pagination.has_next ? 'pointer' : 'not-allowed',
              }}
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

