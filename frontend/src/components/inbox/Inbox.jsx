import React, { useState, useEffect } from 'react';
import { PrioritySummary } from '../priority/PrioritySummary';
import { EmailList } from './EmailList';
import { EmailDetail } from './EmailDetail';
import { Zap } from 'lucide-react';

export function Inbox({
  emails,
  allEmails = [],
  stats,
  isLoading,
  isRefreshing = false,
  isInitialLoading = false,
  searchQuery,
  activeFilter,
  onSelectFilter,
  actionFilter = 'ALL',
  onSelectActionFilter,
  focusMode,
  onToggleFocusMode,
  sortBy,
  onSortChange,
  onRefresh,
  pagination,
  onPageChange,
  scanStatus,
  isScanning,
}) {

  const [selectedEmail, setSelectedEmail] = useState(null);
  const [highlightedIndex, setHighlightedIndex] = useState(-1);

  // Reset keyboard highlight when filtered emails change
  useEffect(() => {
    setHighlightedIndex(-1);
  }, [emails]);

  // Keyboard navigation: ArrowUp, ArrowDown, Enter, /
  useEffect(() => {
    const handleKeyDown = (e) => {
      // Do not trigger if user is actively in a form field
      const activeTag = document.activeElement?.tagName?.toLowerCase();
      if (activeTag === 'input' || activeTag === 'textarea' || activeTag === 'select') {
        return;
      }

      if (e.key === '/') {
        e.preventDefault();
        const searchInput = document.querySelector('input[aria-label="Search emails"]') || document.querySelector('input[type="text"]');
        if (searchInput) {
          searchInput.focus();
          searchInput.select();
        }
        return;
      }

      if (!emails || emails.length === 0) return;

      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setHighlightedIndex((prev) => (prev < emails.length - 1 ? prev + 1 : 0));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setHighlightedIndex((prev) => (prev > 0 ? prev - 1 : emails.length - 1));
      } else if (e.key === 'Enter') {
        if (highlightedIndex >= 0 && highlightedIndex < emails.length) {
          e.preventDefault();
          setSelectedEmail(emails[highlightedIndex]);
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [emails, highlightedIndex]);

  const totalCount = pagination?.total_emails ?? emails.length;
  const pageNum = pagination?.page || 1;
  const pageSize = pagination?.page_size || 50;
  const startIdx = totalCount > 0 ? (pageNum - 1) * pageSize + 1 : 0;
  const endIdx = totalCount > 0 ? Math.min(pageNum * pageSize, totalCount) : 0;

  // Title and description for active view
  let viewTitle = 'All Mail';
  let viewDescription = '';
  if (focusMode) {
    viewTitle = 'Focus Mode';
    viewDescription = 'Emails that require action or have an active deadline.';
  } else if (activeFilter === 'NEEDS_ATTENTION') {
    viewTitle = 'Needs Attention';
    viewDescription = 'Emails that need action or have an active deadline.';
  } else if (activeFilter === 'IMPORTANT') {
    viewTitle = 'Important';
    viewDescription = 'High-importance emails classified by the priority model.';
  } else if (activeFilter === 'P1') {
    viewTitle = 'P1 · Critical';
    viewDescription = 'Immediate operational urgency or critical consequence.';
  } else if (activeFilter === 'P2') {
    viewTitle = 'P2 · Important';
    viewDescription = 'Important emails classified by the priority model.';
  } else if (activeFilter === 'P3') {
    viewTitle = 'P3 · Routine';
    viewDescription = 'Informational or routine correspondence.';
  } else if (activeFilter === 'P4') {
    viewTitle = 'P4 · Low';
    viewDescription = 'Bulk notifications, updates, or low priority.';
  } else if (activeFilter === 'ALL') {
    viewTitle = 'All Mail';
    viewDescription = '';
  }

  return (
    <div style={{ width: '100%' }}>
      {/* Mailbox Intelligence Overview (Only in All Mail) */}
      {!focusMode && !searchQuery && activeFilter === 'ALL' && (
        <PrioritySummary emails={allEmails.length ? allEmails : emails} stats={stats} onSelectFilter={onSelectFilter} />
      )}

      {/* Background Mailbox Scan Notification Card */}
      {isScanning && scanStatus && (
        <div className="scan-status-card">
          <div className="scan-status-header">
            <div className="scan-status-title-group">
              <span className="scan-status-pulse-dot animate-pulse" />
              <span className="scan-status-title">
                {scanStatus.status === 'SCANNING'
                  ? 'Scanning Gmail Mailbox'
                  : scanStatus.status === 'ANALYZING'
                  ? 'Analyzing Complete Mailbox'
                  : 'Analysis Complete'}
              </span>
            </div>
            {scanStatus.status === 'ANALYZING' && (
              <span className="scan-status-counter">
                {scanStatus.analyzed?.toLocaleString() || 0} / {scanStatus.total?.toLocaleString() || 0}
              </span>
            )}
          </div>

          {/* Smooth Progress Track */}
          {scanStatus.status === 'ANALYZING' && (
            <div className="scan-status-track">
              <div
                className="scan-status-fill"
                style={{ width: `${Math.min(100, Math.max(0, scanStatus.progress_percent || 0))}%` }}
              />
            </div>
          )}

          <div className="scan-status-meta-line">
            {scanStatus.status === 'ANALYZING' ? (
              <>
                <span>{scanStatus.progress_percent}% analyzed</span>
                <span className="meta-dot">·</span>
                <span>{scanStatus.cached?.toLocaleString() || 0} reused from cache</span>
              </>
            ) : scanStatus.status === 'SCANNING' ? (
              <span>Discovered {scanStatus.discovered?.toLocaleString() || 0} messages so far</span>
            ) : (
              <span>100% analyzed · All priority classes active</span>
            )}
          </div>

          <div className="scan-status-subnote">
            You can browse cached emails while background analysis continues.
          </div>
        </div>
      )}

      {/* Focus Mode Notification Banner */}
      {focusMode && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '0.65rem 1rem',
            backgroundColor: 'rgba(245, 158, 11, 0.08)',
            border: '1px solid rgba(245, 158, 11, 0.22)',
            borderRadius: 'var(--radius-md)',
            marginBottom: '1rem',
            color: 'var(--p2-color)',
            fontSize: '0.82rem',
            fontWeight: 500,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
            <Zap size={15} />
            <span>Focus Mode · Showing emails that require action or have an active deadline.</span>
          </div>
          <button
            onClick={() => onToggleFocusMode(false)}
            style={{
              fontSize: '0.78rem',
              color: 'var(--p2-color)',
              fontWeight: 600,
              padding: '0.2rem 0.55rem',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid rgba(245, 158, 11, 0.3)',
              backgroundColor: 'rgba(245, 158, 11, 0.1)',
              cursor: 'pointer',
              transition: 'background-color var(--transition-fast)',
            }}
          >
            Exit Focus Mode
          </button>
        </div>
      )}

      {/* Mobile Horizontal Priority Filter Bar */}
      <div className="mobile-priority-bar" role="tablist" aria-label="Filter by priority">
        {[
          { key: 'ALL', label: 'All', count: totalCount },
          { key: 'NEEDS_ATTENTION', label: 'Needs Attention', count: stats?.needs_attention_count || 0, isAttention: true },
          { key: 'P1', label: 'P1', count: stats?.counts?.P1 || 0, dotColor: 'var(--p1-color)' },
          { key: 'P2', label: 'P2', count: stats?.counts?.P2 || 0, dotColor: 'var(--p2-color)' },
          { key: 'P3', label: 'P3', count: stats?.counts?.P3 || 0, dotColor: 'var(--p3-color)' },
          { key: 'P4', label: 'P4', count: stats?.counts?.P4 || 0, dotColor: 'var(--p4-color)' },
        ].map((tab) => {
          const isActive = !focusMode && activeFilter === tab.key;
          return (
            <button
              key={tab.key}
              role="tab"
              aria-selected={isActive}
              onClick={() => {
                onToggleFocusMode(false);
                onSelectFilter(tab.key);
              }}
              className={`mobile-priority-chip ${isActive ? 'is-active' : ''}`}
            >
              {tab.dotColor && (
                <span className="mobile-chip-dot" style={{ backgroundColor: tab.dotColor }} />
              )}
              {tab.isAttention && (
                <Zap size={14} color="var(--accent)" style={{ flexShrink: 0 }} />
              )}
              <span>{tab.label}</span>
              <span className="mobile-chip-separator">·</span>
              <span className="mobile-chip-count">
                {typeof tab.count === 'number' ? tab.count.toLocaleString() : tab.count}
              </span>
            </button>
          );
        })}
      </div>

      {/* Unified View Header & Control Bar */}
      <div className="inbox-section-header">
        {/* Top Line: View Title & Counts */}
        <div className="inbox-header-top-line">
          <div className="inbox-header-title-group">
            <h2 className="inbox-view-title">{viewTitle}</h2>
            <span className="inbox-view-count-badge">
              {totalCount.toLocaleString()} {totalCount === 1 ? 'email' : 'emails'}
            </span>
          </div>
          {totalCount > 0 && (
            <span className="inbox-view-pagination-info">
              Showing {startIdx}–{endIdx} of {totalCount.toLocaleString()}
            </span>
          )}
        </div>

        {viewDescription && (
          <p className="inbox-view-description">
            {viewDescription}
          </p>
        )}

        {/* Secondary Action Filter for P2 */}
        {activeFilter === 'P2' && (
          <div className="inbox-p2-filter-row">
            <button
              type="button"
              onClick={() => onSelectActionFilter?.('ALL')}
              className={`inbox-sub-chip ${actionFilter === 'ALL' ? 'is-active' : ''}`}
            >
              All Important ({(stats?.counts?.P2 || totalCount).toLocaleString()})
            </button>
            <button
              type="button"
              onClick={() => onSelectActionFilter?.('ACTION_REQUIRED')}
              className={`inbox-sub-chip action-required ${actionFilter === 'ACTION_REQUIRED' ? 'is-active' : ''}`}
            >
              ● Action Required
            </button>
            <button
              type="button"
              onClick={() => onSelectActionFilter?.('NO_ACTION')}
              className={`inbox-sub-chip ${actionFilter === 'NO_ACTION' ? 'is-active' : ''}`}
            >
              ○ No Action
            </button>
          </div>
        )}

        {/* Controls Row: Focus Mode Toggle & Sort Dropdown */}
        <div className="inbox-controls-row">
          <button
            type="button"
            onClick={() => onToggleFocusMode(!focusMode)}
            className={`inbox-focus-btn ${focusMode ? 'is-active' : ''}`}
            title="Show only emails that require action or have an active deadline."
          >
            <Zap size={14} />
            <span>{focusMode ? 'Exit Focus Mode' : 'Focus Mode'}</span>
          </button>

          <div className="inbox-sort-group">
            <span className="inbox-sort-label">Sort:</span>
            <select
              value={sortBy}
              onChange={(e) => onSortChange(e.target.value)}
              className="inbox-sort-select"
              aria-label="Sort emails"
            >
              <option value="date_desc">Newest</option>
              <option value="date_asc">Oldest</option>
              <option value="priority_desc">Priority</option>
              <option value="confidence_desc">Confidence</option>
              <option value="deadline_asc">Deadline (earliest first)</option>
              <option value="sender_asc">Sender (A-Z)</option>
            </select>
          </div>
        </div>
      </div>

      {/* Main Email Feed */}
      <div>
        <EmailList
          emails={emails}
          selectedEmailId={selectedEmail?.email_id || (highlightedIndex >= 0 ? emails[highlightedIndex]?.email_id : null)}
          onSelectEmail={setSelectedEmail}
          isLoading={isLoading}
          isRefreshing={isRefreshing}
          isInitialLoading={isInitialLoading}
          emptyType={searchQuery.trim() ? 'search' : (focusMode ? 'focus' : 'inbox')}
          onRefresh={onRefresh}
        />

        {/* Modern Pagination Controls */}
        {pagination && pagination.total_emails > 0 && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '0.85rem 0.5rem',
              marginTop: '0.75rem',
              borderTop: '1px solid var(--border-subtle)',
              fontSize: '0.82rem',
              color: 'var(--text-secondary)',
              flexWrap: 'wrap',
              gap: '0.6rem',
            }}
          >
            <div>
              Showing{' '}
              <strong style={{ color: 'var(--text-main)' }}>
                {Math.min((pagination.page - 1) * pagination.page_size + 1, pagination.total_emails)}–
                {Math.min(pagination.page * pagination.page_size, pagination.total_emails)}
              </strong>{' '}
              of{' '}
              <strong style={{ color: 'var(--text-main)' }}>
                {pagination.total_emails.toLocaleString()}
              </strong>{' '}
              analyzed messages
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', flexWrap: 'wrap' }}>
              <button
                onClick={() => onPageChange?.(pagination.page - 1)}
                disabled={!pagination.has_prev || isLoading}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.35rem',
                  padding: '0.4rem 0.8rem',
                  minHeight: '38px',
                  borderRadius: 'var(--radius-sm)',
                  backgroundColor: 'var(--bg-surface)',
                  border: '1px solid var(--border-subtle)',
                  color: !pagination.has_prev || isLoading ? 'var(--text-muted)' : 'var(--text-main)',
                  cursor: !pagination.has_prev || isLoading ? 'default' : 'pointer',
                  fontSize: '0.8rem',
                  fontWeight: 500,
                  opacity: !pagination.has_prev || isLoading ? 0.5 : 1,
                  transition: 'all var(--transition-fast)',
                }}
              >
                ← Previous
              </button>

              <span style={{ padding: '0 0.4rem', color: 'var(--text-muted)', fontSize: '0.78rem', whiteSpace: 'nowrap' }}>
                Page <strong style={{ color: 'var(--text-main)' }}>{pagination.page}</strong> of {pagination.total_pages}
              </span>

              <button
                onClick={() => onPageChange?.(pagination.page + 1)}
                disabled={!pagination.has_next || isLoading}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.35rem',
                  padding: '0.4rem 0.8rem',
                  minHeight: '38px',
                  borderRadius: 'var(--radius-sm)',
                  backgroundColor: 'var(--bg-surface)',
                  border: '1px solid var(--border-subtle)',
                  color: !pagination.has_next || isLoading ? 'var(--text-muted)' : 'var(--text-main)',
                  cursor: !pagination.has_next || isLoading ? 'default' : 'pointer',
                  fontSize: '0.8rem',
                  fontWeight: 500,
                  opacity: !pagination.has_next || isLoading ? 0.5 : 1,
                  transition: 'all var(--transition-fast)',
                }}
              >
                Next →
              </button>
            </div>
          </div>
        )}
      </div>


      {/* Detail Drawer */}
      {selectedEmail && (
        <EmailDetail email={selectedEmail} onClose={() => setSelectedEmail(null)} />
      )}
    </div>
  );
}
