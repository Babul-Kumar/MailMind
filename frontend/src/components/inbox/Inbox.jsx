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

      {/* Background Mailbox Scan Notification Banner */}
      {isScanning && scanStatus && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '0.75rem 1.1rem',
            backgroundColor: 'rgba(99, 102, 241, 0.08)',
            border: '1px solid rgba(99, 102, 241, 0.25)',
            borderRadius: 'var(--radius-lg)',
            marginBottom: '1rem',
            color: 'var(--accent)',
            fontSize: '0.84rem',
            fontWeight: 500,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ display: 'inline-block', width: '8px', height: '8px', borderRadius: '50%', backgroundColor: 'var(--accent)' }} className="animate-pulse" />
            <span>
              {scanStatus.status === 'SCANNING'
                ? `Scanning Gmail... Discovered ${scanStatus.discovered?.toLocaleString() || 0} messages so far.`
                : scanStatus.status === 'ANALYZING'
                ? `Analyzing complete mailbox: ${scanStatus.analyzed?.toLocaleString() || 0} / ${scanStatus.total?.toLocaleString() || 0} analyzed (${scanStatus.progress_percent}%) · ${scanStatus.cached?.toLocaleString() || 0} reused from cache.`
                : 'Finalizing complete mailbox analysis...'}
            </span>
          </div>
          <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>
            You can browse cached emails while background scan continues.
          </span>
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

      {/* Unified View Header & Control Bar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '0.8rem',
          padding: '0.5rem 0',
          marginBottom: '0.75rem',
        }}
      >
        {/* Left: View title & email count & contextual filter chips */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
            <h3 style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--text-main)', margin: 0, letterSpacing: '-0.01em' }}>
              {viewTitle}
            </h3>
            <span
              style={{
                fontSize: '0.76rem',
                color: 'var(--text-secondary)',
                backgroundColor: 'var(--bg-surface-hover)',
                border: '1px solid var(--border-subtle)',
                padding: '0.15rem 0.55rem',
                borderRadius: 'var(--radius-full)',
                fontWeight: 600,
              }}
            >
              {totalCount.toLocaleString()} {totalCount === 1 ? 'email' : 'emails'} analyzed
            </span>
            {totalCount > 0 && (
              <span style={{ fontSize: '0.76rem', color: 'var(--text-muted)' }}>
                Showing {startIdx}–{endIdx} of {totalCount.toLocaleString()}
              </span>
            )}
          </div>

          {viewDescription && (
            <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', margin: '0.15rem 0 0' }}>
              {viewDescription}
            </p>
          )}

          {/* Secondary Action Filter for P2 */}
          {activeFilter === 'P2' && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', marginTop: '0.45rem' }}>
              <button
                onClick={() => onSelectActionFilter?.('ALL')}
                style={{
                  padding: '0.22rem 0.65rem',
                  borderRadius: 'var(--radius-full)',
                  fontSize: '0.76rem',
                  fontWeight: actionFilter === 'ALL' ? 600 : 500,
                  backgroundColor: actionFilter === 'ALL' ? 'var(--bg-surface-selected)' : 'transparent',
                  color: actionFilter === 'ALL' ? 'var(--text-main)' : 'var(--text-muted)',
                  border: `1px solid ${actionFilter === 'ALL' ? 'var(--border-subtle)' : 'var(--border-subtle)'}`,
                  cursor: 'pointer',
                  transition: 'all var(--transition-fast)',
                }}
              >
                All Important ({(stats?.counts?.P2 || totalCount).toLocaleString()})
              </button>
              <button
                onClick={() => onSelectActionFilter?.('ACTION_REQUIRED')}
                style={{
                  padding: '0.22rem 0.65rem',
                  borderRadius: 'var(--radius-full)',
                  fontSize: '0.76rem',
                  fontWeight: actionFilter === 'ACTION_REQUIRED' ? 600 : 500,
                  backgroundColor: actionFilter === 'ACTION_REQUIRED' ? 'var(--accent-light)' : 'transparent',
                  color: actionFilter === 'ACTION_REQUIRED' ? 'var(--accent)' : 'var(--text-muted)',
                  border: `1px solid ${actionFilter === 'ACTION_REQUIRED' ? 'var(--accent)' : 'var(--border-subtle)'}`,
                  cursor: 'pointer',
                  transition: 'all var(--transition-fast)',
                }}
              >
                ● Action Required
              </button>
              <button
                onClick={() => onSelectActionFilter?.('NO_ACTION')}
                style={{
                  padding: '0.22rem 0.65rem',
                  borderRadius: 'var(--radius-full)',
                  fontSize: '0.76rem',
                  fontWeight: actionFilter === 'NO_ACTION' ? 600 : 500,
                  backgroundColor: actionFilter === 'NO_ACTION' ? 'var(--bg-surface-selected)' : 'transparent',
                  color: actionFilter === 'NO_ACTION' ? 'var(--text-main)' : 'var(--text-muted)',
                  border: `1px solid ${actionFilter === 'NO_ACTION' ? 'var(--border-subtle)' : 'var(--border-subtle)'}`,
                  cursor: 'pointer',
                  transition: 'all var(--transition-fast)',
                }}
              >
                ○ No Action
              </button>
            </div>
          )}
        </div>

        {/* Right: Focus Mode toggle & Sort Select */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <button
            onClick={() => onToggleFocusMode(!focusMode)}
            title="Show only emails that require action or have a meaningful deadline."
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.35rem',
              padding: '0.28rem 0.65rem',
              borderRadius: 'var(--radius-sm)',
              fontSize: '0.78rem',
              fontWeight: 600,
              backgroundColor: focusMode ? 'rgba(245, 158, 11, 0.15)' : 'var(--bg-surface)',
              color: focusMode ? 'var(--p2-color)' : 'var(--text-secondary)',
              border: `1px solid ${focusMode ? 'rgba(245, 158, 11, 0.3)' : 'var(--border-subtle)'}`,
              cursor: 'pointer',
            }}
          >
            <Zap size={13} />
            <span>{focusMode ? 'Exit Focus Mode' : 'Focus Mode'}</span>
          </button>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>Sort:</span>
            <select
              value={sortBy}
              onChange={(e) => onSortChange(e.target.value)}
              style={{
                backgroundColor: 'var(--bg-surface)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--radius-sm)',
                color: 'var(--text-secondary)',
                fontSize: '0.78rem',
                padding: '0.25rem 0.55rem',
                outline: 'none',
                cursor: 'pointer',
              }}
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

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
              <button
                onClick={() => onPageChange?.(pagination.page - 1)}
                disabled={!pagination.has_prev || isLoading}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.35rem',
                  padding: '0.35rem 0.75rem',
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

              <span style={{ padding: '0 0.4rem', color: 'var(--text-muted)', fontSize: '0.78rem' }}>
                Page <strong style={{ color: 'var(--text-main)' }}>{pagination.page}</strong> of {pagination.total_pages}
              </span>

              <button
                onClick={() => onPageChange?.(pagination.page + 1)}
                disabled={!pagination.has_next || isLoading}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.35rem',
                  padding: '0.35rem 0.75rem',
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
