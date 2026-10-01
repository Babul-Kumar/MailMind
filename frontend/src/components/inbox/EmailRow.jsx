import React from 'react';
import { PriorityBadge } from '../priority/PriorityBadge';
import { formatEmailDate, cleanSenderName, extractSnippet, getDeadlineState } from '../../utils/formatting';

function EmailRowComponent({ email, isSelected, onClick }) {
  const senderDisplay = cleanSenderName(email.sender);
  const dateDisplay = formatEmailDate(email.date);
  const snippet = extractSnippet(email.body, email.subject);
  const priority = email.final_priority || email.predicted_priority;
  const actionRequired = Boolean(email.action_required);
  const deadlineState = getDeadlineState(email);

  // Color/style for the deadline pill based on state
  const deadlinePillStyle = deadlineState
    ? deadlineState.state === 'overdue'
      ? { color: 'var(--p1-color)', bg: 'rgba(239, 68, 68, 0.12)', border: 'rgba(239, 68, 68, 0.3)' }
      : deadlineState.state === 'today'
      ? { color: 'var(--p2-color)', bg: 'rgba(245, 158, 11, 0.15)', border: 'rgba(245, 158, 11, 0.4)' }
      : { color: 'var(--p2-color)', bg: 'rgba(245, 158, 11, 0.10)', border: 'rgba(245, 158, 11, 0.28)' }
    : null;

  return (
    <div
      onClick={onClick}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          onClick();
        }
      }}
      role="button"
      tabIndex={0}
      style={{
        backgroundColor: isSelected ? 'var(--bg-surface-selected)' : 'transparent',
        borderLeft: isSelected ? '3px solid var(--accent)' : '3px solid transparent',
        boxShadow: 'none',
      }}
      className="email-row"
    >
      {/* Priority Pill & Mobile Top Row Date */}
      <div className="email-row-col-badge">
        <PriorityBadge priority={priority} showLabel={false} size="sm" />
        <span className="email-row-mobile-date" style={{ display: 'none' }}>
          {dateDisplay}
        </span>
      </div>

      {/* Sender Name */}
      <div
        className="email-row-col-sender"
        style={{
          fontSize: '0.85rem',
          fontWeight: 600,
          color: 'var(--text-main)',
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}
        title={email.sender}
      >
        {senderDisplay}
      </div>

      {/* Subject + Snippet Preview + Action Status */}
      <div
        className="email-row-col-main"
        style={{ display: 'flex', flexDirection: 'column', gap: '0.2rem', overflow: 'hidden' }}
      >
        <div
          className="email-row-subject-line"
          style={{
            display: 'flex',
            alignItems: 'baseline',
            gap: '0.45rem',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            fontSize: '0.85rem',
          }}
        >
          <span
            className="email-row-subject"
            style={{
              fontWeight: 700,
              color: 'var(--text-main)',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
              flexShrink: 0,
              maxWidth: '55%',
            }}
          >
            {email.subject || '(No Subject)'}
          </span>
          <span className="email-row-dash" style={{ color: 'var(--text-dim)', flexShrink: 0 }}>&mdash;</span>
          <span
            className="email-row-snippet"
            style={{
              color: 'var(--text-muted)',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
              fontSize: '0.82rem',
              flex: 1,
            }}
          >
            {snippet}
          </span>
        </div>

        {/* Action + Deadline Status line */}
        <div
          className="email-row-action-line"
          style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem', fontSize: '0.72rem' }}
        >
          {deadlineState && deadlinePillStyle && (
            <span
              style={{
                color: deadlinePillStyle.color,
                fontWeight: 600,
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.25rem',
                backgroundColor: deadlinePillStyle.bg,
                border: `1px solid ${deadlinePillStyle.border}`,
                padding: '0.08rem 0.45rem',
                borderRadius: 'var(--radius-xs)',
              }}
            >
              <span>{deadlineState.icon}</span> {deadlineState.label}
            </span>
          )}

          {actionRequired ? (
            <span
              style={{
                color: email.action_reason === 'Account security action' ? 'var(--p1-color)' : 'var(--accent)',
                fontWeight: 600,
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.25rem',
                backgroundColor: email.action_reason === 'Account security action' ? 'rgba(239, 68, 68, 0.12)' : 'rgba(99, 102, 241, 0.12)',
                border: `1px solid ${email.action_reason === 'Account security action' ? 'rgba(239, 68, 68, 0.28)' : 'rgba(99, 102, 241, 0.28)'}`,
                padding: '0.08rem 0.45rem',
                borderRadius: 'var(--radius-xs)',
              }}
            >
              <span>●</span> {email.action_reason || 'Action required'}
            </span>
          ) : (
            !deadlineState && (
              <span style={{ color: 'var(--text-muted)', opacity: 0.55, display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
                <span>○</span> No action required
              </span>
            )
          )}
        </div>
      </div>

      {/* Desktop Date — lower emphasis, visually subdued when deadline is shown */}
      <div
        className="email-row-col-date"
        style={{
          color: deadlineState ? 'var(--text-dim)' : 'var(--text-muted)',
          opacity: deadlineState ? 0.45 : 0.85,
          fontSize: '0.74rem',
        }}
      >
        {dateDisplay}
      </div>
    </div>
  );
}

export const EmailRow = React.memo(EmailRowComponent, (prevProps, nextProps) => {
  return (
    prevProps.isSelected === nextProps.isSelected &&
    prevProps.email.email_id === nextProps.email.email_id &&
    prevProps.email.predicted_priority === nextProps.email.predicted_priority &&
    prevProps.email.final_priority === nextProps.email.final_priority &&
    prevProps.email.action_required === nextProps.email.action_required &&
    prevProps.email.deadline_detected === nextProps.email.deadline_detected &&
    prevProps.email.deadline_display === nextProps.email.deadline_display
  );
});
