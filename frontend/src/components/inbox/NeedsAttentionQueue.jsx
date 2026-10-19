import React, { useState } from 'react';
import {
  Zap,
  Flame,
  Clock,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  RotateCcw,
  ExternalLink,
  Calendar,
  AlertTriangle,
  Inbox,
  Filter,
  Check,
} from 'lucide-react';
import { PriorityBadge } from '../priority/PriorityBadge';
import { cleanSenderName, formatEmailDate } from '../../utils/formatting';
import { SnoozeModal } from './SnoozeModal';

export function NeedsAttentionQueue({
  actionQueue,
  isLoading,
  sortBy,
  onSortChange,
  olderSortBy,
  onOlderSortChange,
  onSelectEmail,
  onResolve,
  onUnresolve,
  onSnooze,
  onUnsnooze,
  recentlyResolved,
  onClearRecentlyResolved,
  onNavigateAllMail,
}) {
  const [olderExpanded, setOlderExpanded] = useState(false);
  const [showSnoozed, setShowSnoozed] = useState(false);
  const [snoozeModalEmail, setSnoozeModalEmail] = useState(null);

  const counts = actionQueue?.counts || {
    urgent: 0,
    due_soon: 0,
    other_active: 0,
    total_active: 0,
    older: 0,
    snoozed: 0,
    resolved: 0,
  };

  const activeQueue = actionQueue?.active_queue || [];
  const olderActions = actionQueue?.older_actions || [];
  const snoozedItems = actionQueue?.snoozed_items || [];

  return (
    <div style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* Undo Toast Notification */}
      {recentlyResolved && (
        <div
          className="animate-fade-in"
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            backgroundColor: 'rgba(34, 197, 94, 0.12)',
            border: '1px solid rgba(34, 197, 94, 0.3)',
            borderRadius: 'var(--radius-md, 8px)',
            padding: '0.65rem 1rem',
            fontSize: '0.86rem',
            color: '#4ade80',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <CheckCircle2 size={16} />
            <span>Action marked as resolved.</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <button
              onClick={() => onUnresolve(recentlyResolved.messageId)}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.35rem',
                backgroundColor: 'rgba(34, 197, 94, 0.2)',
                border: '1px solid rgba(34, 197, 94, 0.4)',
                borderRadius: '6px',
                color: '#4ade80',
                fontSize: '0.8rem',
                fontWeight: 600,
                padding: '0.25rem 0.65rem',
                cursor: 'pointer',
              }}
            >
              <RotateCcw size={13} />
              <span>Undo</span>
            </button>
            <button
              onClick={onClearRecentlyResolved}
              style={{
                background: 'transparent',
                border: 'none',
                color: 'var(--text-muted)',
                fontSize: '1rem',
                cursor: 'pointer',
              }}
            >
              ×
            </button>
          </div>
        </div>
      )}

      {/* Header & Metric Summary Bar */}
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: '1rem',
          backgroundColor: 'var(--bg-surface)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-lg, 12px)',
          padding: '1.25rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.55rem' }}>
              <div
                style={{
                  width: '28px',
                  height: '28px',
                  borderRadius: '6px',
                  backgroundColor: 'rgba(245, 158, 11, 0.15)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'var(--accent, #f59e0b)',
                }}
              >
                <Zap size={16} />
              </div>
              <h2 style={{ fontSize: '1.25rem', fontWeight: 700, margin: 0, color: 'var(--text-main)', letterSpacing: '-0.02em' }}>
                Smart Action Queue
              </h2>
            </div>
            <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', margin: '0.3rem 0 0 0' }}>
              Tasks and announcements needing attention right now, bounded by the 8-day policy.
            </p>
          </div>

          {/* Sort Control */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>Sort queue:</span>
            <select
              value={sortBy}
              onChange={(e) => onSortChange?.(e.target.value)}
              aria-label="Sort queue"
              style={{
                padding: '0.4rem 0.75rem',
                borderRadius: '6px',
                border: '1px solid var(--border-subtle)',
                backgroundColor: 'var(--bg-card, #1e293b)',
                color: 'var(--text-main)',
                fontSize: '0.8rem',
                cursor: 'pointer',
              }}
            >
              <option value="urgent">Most urgent first</option>
              <option value="deadline">Deadline soonest</option>
              <option value="newest">Newest first</option>
              <option value="oldest">Oldest first</option>
            </select>
          </div>
        </div>

        {/* Derived Metric Counts (Urgent, Due Soon, Other Active) */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
            gap: '0.75rem',
            paddingTop: '0.5rem',
            borderTop: '1px solid var(--border-subtle)',
          }}
        >
          {/* Urgent Count */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.65rem',
              padding: '0.65rem 0.85rem',
              borderRadius: '8px',
              backgroundColor: 'rgba(239, 68, 68, 0.08)',
              border: '1px solid rgba(239, 68, 68, 0.2)',
            }}
          >
            <div
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '6px',
                backgroundColor: 'rgba(239, 68, 68, 0.15)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#ef4444',
              }}
            >
              <Flame size={16} />
            </div>
            <div>
              <span style={{ display: 'block', fontSize: '1.15rem', fontWeight: 700, color: 'var(--text-main)', lineHeight: 1.1 }}>
                {counts.urgent}
              </span>
              <span style={{ fontSize: '0.72rem', color: '#f87171', fontWeight: 500 }}>
                Urgent
              </span>
            </div>
          </div>

          {/* Due Soon Count */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.65rem',
              padding: '0.65rem 0.85rem',
              borderRadius: '8px',
              backgroundColor: 'rgba(245, 158, 11, 0.08)',
              border: '1px solid rgba(245, 158, 11, 0.2)',
            }}
          >
            <div
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '6px',
                backgroundColor: 'rgba(245, 158, 11, 0.15)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#f59e0b',
              }}
            >
              <Clock size={16} />
            </div>
            <div>
              <span style={{ display: 'block', fontSize: '1.15rem', fontWeight: 700, color: 'var(--text-main)', lineHeight: 1.1 }}>
                {counts.due_soon}
              </span>
              <span style={{ fontSize: '0.72rem', color: '#fbbf24', fontWeight: 500 }}>
                Due soon
              </span>
            </div>
          </div>

          {/* Other Active Count */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.65rem',
              padding: '0.65rem 0.85rem',
              borderRadius: '8px',
              backgroundColor: 'rgba(59, 130, 246, 0.08)',
              border: '1px solid rgba(59, 130, 246, 0.2)',
            }}
          >
            <div
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '6px',
                backgroundColor: 'rgba(59, 130, 246, 0.15)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#3b82f6',
              }}
            >
              <Zap size={16} />
            </div>
            <div>
              <span style={{ display: 'block', fontSize: '1.15rem', fontWeight: 700, color: 'var(--text-main)', lineHeight: 1.1 }}>
                {counts.other_active}
              </span>
              <span style={{ fontSize: '0.72rem', color: '#60a5fa', fontWeight: 500 }}>
                Other active
              </span>
            </div>
          </div>

          {/* Total Active Summary */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.65rem',
              padding: '0.65rem 0.85rem',
              borderRadius: '8px',
              backgroundColor: 'var(--bg-main, #0f172a)',
              border: '1px solid var(--border-subtle)',
            }}
          >
            <div>
              <span style={{ display: 'block', fontSize: '1.15rem', fontWeight: 700, color: 'var(--text-main)', lineHeight: 1.1 }}>
                {counts.total_active}
              </span>
              <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                Total in active queue
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Main Active Queue List */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
        {activeQueue.length > 0 ? (
          activeQueue.map((item) => (
            <ActionQueueRow
              key={item.email_id || item.id || item.message_id}
              email={item}
              onOpen={() => onSelectEmail(item)}
              onResolve={() => onResolve(item.email_id || item.id || item.message_id, item.thread_id)}
              onSnoozeClick={() => setSnoozeModalEmail(item)}
            />
          ))
        ) : !isLoading ? (
          /* Clean Empty State */
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '3rem 1.5rem',
              borderRadius: 'var(--radius-lg, 12px)',
              border: '1px dashed var(--border-subtle)',
              backgroundColor: 'var(--bg-surface)',
              textAlign: 'center',
            }}
          >
            <div
              style={{
                width: '48px',
                height: '48px',
                borderRadius: '50%',
                backgroundColor: 'rgba(34, 197, 94, 0.12)',
                color: '#22c55e',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                marginBottom: '0.85rem',
              }}
            >
              <CheckCircle2 size={24} />
            </div>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--text-main)', margin: '0 0 0.35rem 0' }}>
              You're all caught up.
            </h3>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', margin: 0, maxWidth: '420px', lineHeight: 1.4 }}>
              No pending tasks require your immediate attention in the active queue.
            </p>
            <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1.25rem' }}>
              {counts.older > 0 && (
                <button
                  onClick={() => setOlderExpanded(true)}
                  style={{
                    fontSize: '0.82rem',
                    padding: '0.45rem 0.85rem',
                    borderRadius: '6px',
                    backgroundColor: 'var(--bg-card, #1e293b)',
                    border: '1px solid var(--border-subtle)',
                    color: 'var(--text-secondary)',
                    cursor: 'pointer',
                  }}
                >
                  View Older actions ({counts.older})
                </button>
              )}
              {counts.snoozed > 0 && (
                <button
                  onClick={() => setShowSnoozed(true)}
                  style={{
                    fontSize: '0.82rem',
                    padding: '0.45rem 0.85rem',
                    borderRadius: '6px',
                    backgroundColor: 'var(--bg-card, #1e293b)',
                    border: '1px solid var(--border-subtle)',
                    color: 'var(--text-secondary)',
                    cursor: 'pointer',
                  }}
                >
                  View Snoozed ({counts.snoozed})
                </button>
              )}
              <button
                onClick={onNavigateAllMail}
                style={{
                  fontSize: '0.82rem',
                  padding: '0.45rem 0.85rem',
                  borderRadius: '6px',
                  backgroundColor: 'transparent',
                  border: '1px solid var(--border-subtle)',
                  color: 'var(--text-muted)',
                  cursor: 'pointer',
                }}
              >
                Go to All Mail
              </button>
            </div>
          </div>
        ) : (
          <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
            Synchronizing smart action queue...
          </div>
        )}
      </div>

      {/* Collapsible Older Actions Section */}
      {olderActions.length > 0 && (
        <div
          style={{
            marginTop: '0.75rem',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-lg, 12px)',
            backgroundColor: 'var(--bg-surface)',
            overflow: 'hidden',
          }}
        >
          {/* Collapsible Header */}
          <div
            onClick={() => setOlderExpanded(!olderExpanded)}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '0.85rem 1.15rem',
              cursor: 'pointer',
              backgroundColor: 'var(--bg-card, rgba(255,255,255,0.02))',
              userSelect: 'none',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.55rem' }}>
              {olderExpanded ? <ChevronDown size={18} color="var(--text-muted)" /> : <ChevronRight size={18} color="var(--text-muted)" />}
              <span style={{ fontSize: '0.92rem', fontWeight: 600, color: 'var(--text-main)' }}>
                Older actions
              </span>
              <span
                style={{
                  fontSize: '0.72rem',
                  fontWeight: 600,
                  padding: '0.15rem 0.5rem',
                  borderRadius: '10px',
                  backgroundColor: 'rgba(255, 255, 255, 0.08)',
                  color: 'var(--text-secondary)',
                }}
              >
                {olderActions.length}
              </span>
              <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                (Unresolved items older than 8 days)
              </span>
            </div>

            {olderExpanded && (
              <div
                onClick={(e) => e.stopPropagation()}
                style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}
              >
                <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>Sort:</span>
                <select
                  value={olderSortBy}
                  onChange={(e) => onOlderSortChange?.(e.target.value)}
                  style={{
                    padding: '0.25rem 0.55rem',
                    borderRadius: '4px',
                    border: '1px solid var(--border-subtle)',
                    backgroundColor: 'var(--bg-main, #0f172a)',
                    color: 'var(--text-main)',
                    fontSize: '0.75rem',
                    cursor: 'pointer',
                  }}
                >
                  <option value="oldest">Oldest first</option>
                  <option value="newest">Newest first</option>
                  <option value="urgent">Most urgent</option>
                </select>
              </div>
            )}
          </div>

          {/* Collapsible Content */}
          {olderExpanded && (
            <div style={{ padding: '0.85rem', display: 'flex', flexDirection: 'column', gap: '0.65rem', borderTop: '1px solid var(--border-subtle)' }}>
              {olderActions.map((item) => (
                <ActionQueueRow
                  key={item.email_id || item.id || item.message_id}
                  email={item}
                  isOlderSection={true}
                  onOpen={() => onSelectEmail(item)}
                  onResolve={() => onResolve(item.email_id || item.id || item.message_id, item.thread_id)}
                  onSnoozeClick={() => setSnoozeModalEmail(item)}
                />
              ))}
            </div>
          )}
        </div>
      )}

      {/* Snoozed Items Collapsible / Review */}
      {snoozedItems.length > 0 && (
        <div
          style={{
            marginTop: '0.5rem',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-lg, 12px)',
            backgroundColor: 'var(--bg-surface)',
            overflow: 'hidden',
          }}
        >
          <div
            onClick={() => setShowSnoozed(!showSnoozed)}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '0.85rem 1.15rem',
              cursor: 'pointer',
              backgroundColor: 'var(--bg-card, rgba(255,255,255,0.02))',
              userSelect: 'none',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.55rem' }}>
              <Clock size={16} color="#3b82f6" />
              <span style={{ fontSize: '0.92rem', fontWeight: 600, color: 'var(--text-main)' }}>
                Snoozed actions
              </span>
              <span
                style={{
                  fontSize: '0.72rem',
                  fontWeight: 600,
                  padding: '0.15rem 0.5rem',
                  borderRadius: '10px',
                  backgroundColor: 'rgba(59, 130, 246, 0.12)',
                  color: '#60a5fa',
                }}
              >
                {snoozedItems.length}
              </span>
            </div>
            {showSnoozed ? <ChevronDown size={18} color="var(--text-muted)" /> : <ChevronRight size={18} color="var(--text-muted)" />}
          </div>

          {showSnoozed && (
            <div style={{ padding: '0.85rem', display: 'flex', flexDirection: 'column', gap: '0.65rem', borderTop: '1px solid var(--border-subtle)' }}>
              {snoozedItems.map((item) => (
                <div
                  key={item.email_id || item.id || item.message_id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '0.75rem 0.95rem',
                    borderRadius: '8px',
                    border: '1px solid var(--border-subtle)',
                    backgroundColor: 'var(--bg-card, #1e293b)',
                    gap: '0.75rem',
                  }}
                >
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.2rem' }}>
                      <span style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-main)' }}>
                        {cleanSenderName(item.sender)}
                      </span>
                      <span style={{ fontSize: '0.72rem', color: '#60a5fa' }}>
                        ● Snoozed until {item.snoozed_until ? new Date(item.snoozed_until * 1000).toLocaleString() : 'scheduled time'}
                      </span>
                    </div>
                    <div style={{ fontSize: '0.84rem', color: 'var(--text-secondary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {item.subject}
                    </div>
                  </div>

                  <button
                    onClick={() => onUnsnooze(item.email_id || item.id || item.message_id)}
                    style={{
                      padding: '0.35rem 0.75rem',
                      borderRadius: '6px',
                      border: '1px solid var(--border-subtle)',
                      backgroundColor: 'transparent',
                      color: 'var(--text-main)',
                      fontSize: '0.78rem',
                      fontWeight: 600,
                      cursor: 'pointer',
                      flexShrink: 0,
                    }}
                  >
                    Unsnooze
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Snooze Modal */}
      {snoozeModalEmail && (
        <SnoozeModal
          email={snoozeModalEmail}
          isOpen={Boolean(snoozeModalEmail)}
          onClose={() => setSnoozeModalEmail(null)}
          onSnooze={onSnooze}
        />
      )}
    </div>
  );
}

/**
 * Action Queue Item Row Component
 * Displays concise actionable card with clear reason, next step, and 1-click actions.
 */
function ActionQueueRow({ email, isOlderSection = false, onOpen, onResolve, onSnoozeClick }) {
  const policy = email.action_policy || {};
  const priority = email.final_priority || email.predicted_priority || 'P4';
  const reason = email.action_reason || policy.reason || 'Action required';
  const nextStep = email.next_step || policy.next_step;
  const isCritical = email.is_critical_incident || policy.is_critical_incident || priority === 'P1';
  const dlStatus = policy.deadline_status || email.deadline_status;
  const dlDisp = policy.deadline_display || email.deadline_display;

  return (
    <div
      className="action-queue-row"
      style={{
        display: 'flex',
        flexDirection: 'column',
        padding: '0.9rem 1.1rem',
        borderRadius: 'var(--radius-md, 8px)',
        border: `1px solid ${isCritical ? 'rgba(239, 68, 68, 0.35)' : 'var(--border-subtle)'}`,
        backgroundColor: isCritical ? 'rgba(239, 68, 68, 0.03)' : 'var(--bg-card, #1e293b)',
        transition: 'all 0.15s ease',
        gap: '0.65rem',
      }}
    >
      {/* Top Line: Sender, Priority, Age, Deadline Pill */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.65rem', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.55rem', minWidth: 0 }}>
          <PriorityBadge priority={priority} size="sm" showLabel={true} />
          <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-main)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {cleanSenderName(email.sender)}
          </span>
          <span style={{ fontSize: '0.76rem', color: 'var(--text-muted)' }}>
            · {formatEmailDate(email.date)}
          </span>
        </div>

        {/* Status Pills */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
          {isCritical && (
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.25rem',
                fontSize: '0.72rem',
                fontWeight: 600,
                padding: '0.15rem 0.45rem',
                borderRadius: '4px',
                backgroundColor: 'rgba(239, 68, 68, 0.15)',
                color: '#ef4444',
              }}
            >
              <AlertTriangle size={12} />
              Critical
            </span>
          )}

          {dlDisp && (
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.25rem',
                fontSize: '0.72rem',
                fontWeight: 600,
                padding: '0.15rem 0.45rem',
                borderRadius: '4px',
                backgroundColor: dlStatus === 'OVERDUE' ? 'rgba(239, 68, 68, 0.12)' : 'rgba(245, 158, 11, 0.12)',
                color: dlStatus === 'OVERDUE' ? '#ef4444' : '#f59e0b',
              }}
            >
              <Clock size={12} />
              {dlDisp}
            </span>
          )}

          {isOlderSection && (
            <span
              style={{
                fontSize: '0.7rem',
                padding: '0.12rem 0.4rem',
                borderRadius: '4px',
                backgroundColor: 'rgba(255, 255, 255, 0.06)',
                color: 'var(--text-muted)',
              }}
            >
              &gt;8 days old
            </span>
          )}
        </div>
      </div>

      {/* Middle: Subject & Meaningful Action Reason */}
      <div
        onClick={onOpen}
        style={{ cursor: 'pointer', display: 'flex', flexDirection: 'column', gap: '0.25rem' }}
      >
        <h4
          style={{
            fontSize: '0.94rem',
            fontWeight: 600,
            margin: 0,
            color: 'var(--text-main)',
            lineHeight: 1.3,
          }}
        >
          {email.subject || '(No Subject)'}
        </h4>

        {/* Meaningful Reason Pill */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', flexWrap: 'wrap' }}>
          <span
            style={{
              fontSize: '0.76rem',
              fontWeight: 500,
              color: isCritical ? '#f87171' : 'var(--accent, #f59e0b)',
            }}
          >
            ● {reason}
          </span>
          {nextStep && (
            <span style={{ fontSize: '0.76rem', color: 'var(--text-secondary)' }}>
              — Next: <em>{nextStep}</em>
            </span>
          )}
        </div>
      </div>

      {/* Bottom: Quick Actions Bar (Open, Mark Resolved, Snooze) */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          paddingTop: '0.45rem',
          borderTop: '1px solid rgba(255, 255, 255, 0.05)',
        }}
      >
        <button
          onClick={onOpen}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.35rem',
            background: 'transparent',
            border: 'none',
            color: '#3b82f6',
            fontSize: '0.78rem',
            fontWeight: 600,
            cursor: 'pointer',
            padding: '0.2rem 0',
          }}
        >
          <span>Open email</span>
          <ExternalLink size={12} />
        </button>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          {/* Snooze Button */}
          <button
            onClick={onSnoozeClick}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.3rem',
              padding: '0.35rem 0.65rem',
              borderRadius: '6px',
              border: '1px solid var(--border-subtle)',
              backgroundColor: 'transparent',
              color: 'var(--text-secondary)',
              fontSize: '0.76rem',
              fontWeight: 500,
              cursor: 'pointer',
              transition: 'background-color 0.15s ease',
            }}
            title="Postpone this action"
          >
            <Clock size={13} />
            <span>Snooze</span>
          </button>

          {/* Mark Resolved Button */}
          <button
            onClick={onResolve}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.35rem',
              padding: '0.35rem 0.75rem',
              borderRadius: '6px',
              border: '1px solid rgba(34, 197, 94, 0.35)',
              backgroundColor: 'rgba(34, 197, 94, 0.1)',
              color: '#4ade80',
              fontSize: '0.76rem',
              fontWeight: 600,
              cursor: 'pointer',
              transition: 'all 0.15s ease',
            }}
            title="Mark this action completed or resolved"
          >
            <Check size={13} />
            <span>Mark resolved</span>
          </button>
        </div>
      </div>
    </div>
  );
}
