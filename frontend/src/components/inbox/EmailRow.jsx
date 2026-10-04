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

  const isOtpOrVerification = Boolean(
    email.action_reason === 'Immediate verification required' ||
    email.action_reason === 'Account security action' ||
    (email.subject && /otp|verification\s*code|one-time\s*password|login\s*code/i.test(email.subject))
  );

  let deadlineLabel = deadlineState?.label;
  let deadlinePillStyle = null;

  if (deadlineState) {
    if (deadlineState.state === 'historical' || email.deadline_status === 'HISTORICAL') {
      deadlineLabel = deadlineState.label.startsWith('Overdue · ')
        ? deadlineState.label.replace('Overdue · ', 'Past · ')
        : deadlineState.label;
      deadlinePillStyle = {
        color: 'var(--text-muted)',
        bg: 'var(--bg-surface-hover)',
        border: 'var(--border-subtle)',
        icon: '📅',
      };
    } else if (deadlineState.state === 'overdue') {
      if (isOtpOrVerification || email.deadline_status === 'EXPIRED') {
        deadlineLabel = 'Expired verification code';
        deadlinePillStyle = {
          color: 'var(--text-muted)',
          bg: 'var(--bg-surface-hover)',
          border: 'var(--border-subtle)',
          icon: '⌛',
        };
      } else {
        deadlineLabel = deadlineState.label;
        deadlinePillStyle = {
          color: 'var(--p1-color)',
          bg: 'rgba(239, 68, 68, 0.08)',
          border: 'rgba(239, 68, 68, 0.22)',
          icon: '⚠',
        };
      }
    } else if (deadlineState.state === 'today') {
      deadlineLabel = deadlineState.label;
      deadlinePillStyle = {
        color: 'var(--p2-color)',
        bg: 'rgba(245, 158, 11, 0.12)',
        border: 'rgba(245, 158, 11, 0.35)',
        icon: '⏰',
      };
    } else {
      deadlineLabel = deadlineState.label;
      deadlinePillStyle = {
        color: 'var(--p2-color)',
        bg: 'rgba(245, 158, 11, 0.08)',
        border: 'rgba(245, 158, 11, 0.22)',
        icon: '⏰',
      };
    }
  }

  const isP4 = priority === 'P4';
  const hasActionLine = Boolean(deadlineState || actionRequired);

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
      className={`email-row ${isP4 ? 'p4-row' : ''} ${isSelected ? 'is-selected' : ''}`}
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
          fontSize: '0.84rem',
          fontWeight: isP4 ? 500 : 600,
          color: isP4 ? 'var(--text-muted)' : 'var(--text-main)',
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
        style={{ display: 'flex', flexDirection: 'column', gap: hasActionLine ? '0.2rem' : '0', overflow: 'hidden' }}
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
              fontWeight: isP4 ? 500 : 600,
              color: isP4 ? 'var(--text-secondary)' : 'var(--text-main)',
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

        {/* Action + Deadline Status line (Only rendered when meaningful signals exist) */}
        {hasActionLine && (
          <div
            className="email-row-action-line"
            style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: '0.45rem', fontSize: '0.72rem' }}
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
                  padding: '0.06rem 0.45rem',
                  borderRadius: 'var(--radius-xs)',
                }}
              >
                <span>{deadlinePillStyle.icon}</span> {deadlineLabel}
              </span>
            )}

            {actionRequired && (
              <span
                style={{
                  color: email.action_reason === 'Account security action' || email.action_reason === 'Immediate verification required' ? 'var(--p1-color)' : 'var(--accent)',
                  fontWeight: 600,
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.25rem',
                  backgroundColor: email.action_reason === 'Account security action' || email.action_reason === 'Immediate verification required' ? 'rgba(244, 63, 94, 0.08)' : 'rgba(99, 102, 241, 0.08)',
                  border: `1px solid ${email.action_reason === 'Account security action' || email.action_reason === 'Immediate verification required' ? 'rgba(244, 63, 94, 0.22)' : 'rgba(99, 102, 241, 0.22)'}`,
                  padding: '0.06rem 0.45rem',
                  borderRadius: 'var(--radius-xs)',
                }}
              >
                <span>●</span> {email.action_reason || 'Action required'}
              </span>
            )}
          </div>
        )}
      </div>

      {/* Desktop Date */}
      <div
        className="email-row-col-date"
        style={{
          color: deadlineState ? 'var(--text-dim)' : 'var(--text-muted)',
          opacity: deadlineState ? 0.6 : 0.85,
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
    prevProps.email.action_reason === nextProps.email.action_reason &&
    prevProps.email.deadline_detected === nextProps.email.deadline_detected &&
    prevProps.email.deadline_display === nextProps.email.deadline_display &&
    prevProps.email.deadline_status === nextProps.email.deadline_status
  );
});
