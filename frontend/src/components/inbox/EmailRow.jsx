import React, { useMemo, useCallback, useState } from 'react';
import { PriorityBadge } from '../priority/PriorityBadge';
import { formatEmailDate, cleanSenderName, extractSnippet, getDeadlineState } from '../../utils/formatting';
import { ExternalLink, Eye, Clock, AlertTriangle, Check } from 'lucide-react';

function getSenderInitials(name) {
  if (!name) return 'M';
  const clean = name.replace(/<[^>]+>/g, '').trim();
  const parts = clean.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) {
    return (parts[0][0] + parts[1][0]).toUpperCase();
  }
  return clean.slice(0, 2).toUpperCase() || 'M';
}

const AVATAR_GRADIENTS = [
  'linear-gradient(135deg, #6366f1, #8b5cf6)',
  'linear-gradient(135deg, #ec4899, #f43f5e)',
  'linear-gradient(135deg, #06b6d4, #3b82f6)',
  'linear-gradient(135deg, #10b981, #059669)',
  'linear-gradient(135deg, #f59e0b, #d97706)',
  'linear-gradient(135deg, #8b5cf6, #d946ef)',
  'linear-gradient(135deg, #0ea5e9, #2563eb)',
];

function getAvatarGradient(str) {
  let hash = 0;
  for (let i = 0; i < (str || '').length; i++) {
    hash = (hash << 5) - hash + str.charCodeAt(i);
    hash |= 0;
  }
  return AVATAR_GRADIENTS[Math.abs(hash) % AVATAR_GRADIENTS.length];
}

function EmailRowComponent({ email, isSelected, onClick }) {
  const [isHovered, setIsHovered] = useState(false);
  const senderDisplay = useMemo(() => cleanSenderName(email.sender), [email.sender]);
  const senderInitials = useMemo(() => getSenderInitials(senderDisplay), [senderDisplay]);
  const avatarBg = useMemo(() => getAvatarGradient(email.sender || senderDisplay), [email.sender, senderDisplay]);
  const dateDisplay = useMemo(() => formatEmailDate(email.date), [email.date]);
  const snippet = useMemo(() => extractSnippet(email.body, email.subject), [email.body, email.subject]);
  const priority = email.effective_priority || email.final_priority || email.predicted_priority;
  const actionRequired = Boolean(email.action_required);
  const deadlineState = useMemo(() => getDeadlineState(email), [email.deadline_status, email.deadline_datetime, email.date]);

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
          bg: 'rgba(255, 51, 102, 0.10)',
          border: 'rgba(255, 51, 102, 0.28)',
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

  const isP1 = priority === 'P1';
  const isP4 = priority === 'P4';
  const hasActionLine = Boolean(deadlineState || actionRequired);

  const handleClick = useCallback(() => {
    onClick?.(email);
  }, [onClick, email]);

  const handleOpenGmail = (e) => {
    e.stopPropagation();
    window.open(`https://mail.google.com/mail/u/0/#all/${email.email_id || ''}`, '_blank', 'noopener,noreferrer');
  };

  return (
    <div
      onClick={handleClick}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          handleClick();
        }
      }}
      role="button"
      tabIndex={0}
      className={`email-row ${isP1 ? 'p1-row' : ''} ${isP4 ? 'p4-row' : ''} ${isSelected ? 'is-selected' : ''}`}
      style={{
        position: 'relative',
        borderLeft: isP1 ? '3px solid var(--p1-color)' : isSelected ? '3px solid var(--accent)' : '3px solid transparent',
        backgroundColor: isSelected ? 'var(--bg-surface-selected)' : isHovered ? 'var(--bg-surface-hover)' : 'transparent',
      }}
    >
      {/* Mobile Top Row */}
      <div className="email-row-mobile-top-line" style={{ display: 'none' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', minWidth: 0, flex: 1 }}>
          <div
            style={{
              width: '26px',
              height: '26px',
              borderRadius: '50%',
              background: avatarBg,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#ffffff',
              fontSize: '0.68rem',
              fontWeight: 700,
              flexShrink: 0,
            }}
          >
            {senderInitials}
          </div>
          <PriorityBadge priority={priority} showLabel={false} size="sm" />
          <span
            style={{
              fontSize: '0.88rem',
              fontWeight: isP4 ? 600 : 700,
              color: isP4 ? 'var(--text-secondary)' : 'var(--text-main)',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {senderDisplay}
          </span>
        </div>
        <span className="email-row-mobile-date">
          {dateDisplay}
        </span>
      </div>

      {/* Desktop Column 1: Priority Pill */}
      <div className="email-row-col-badge">
        <PriorityBadge priority={priority} showLabel={false} size="sm" />
      </div>

      {/* Desktop Column 2: Sender Avatar */}
      <div
        className="email-row-col-avatar"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <div
          style={{
            width: '30px',
            height: '30px',
            borderRadius: '50%',
            background: avatarBg,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#ffffff',
            fontSize: '0.72rem',
            fontWeight: 700,
            boxShadow: '0 2px 6px rgba(0,0,0,0.18)',
            letterSpacing: '0.02em',
            flexShrink: 0,
          }}
          title={senderDisplay}
        >
          {senderInitials}
        </div>
      </div>

      {/* Desktop Column 3: Sender Name */}
      <div
        className="email-row-col-sender"
        style={{
          fontSize: '0.86rem',
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
        style={{ display: 'flex', flexDirection: 'column', gap: hasActionLine ? '0.2rem' : '0', overflow: 'hidden', minWidth: 0 }}
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
            fontSize: '0.86rem',
            minWidth: 0,
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
              maxWidth: '52%',
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
                  padding: '0.08rem 0.5rem',
                  borderRadius: 'var(--radius-xs)',
                  boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
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
                  backgroundColor: email.action_reason === 'Account security action' || email.action_reason === 'Immediate verification required' ? 'rgba(255, 51, 102, 0.10)' : 'rgba(99, 102, 241, 0.10)',
                  border: `1px solid ${email.action_reason === 'Account security action' || email.action_reason === 'Immediate verification required' ? 'rgba(255, 51, 102, 0.28)' : 'rgba(99, 102, 241, 0.28)'}`,
                  padding: '0.08rem 0.5rem',
                  borderRadius: 'var(--radius-xs)',
                }}
              >
                <span>●</span> {email.action_reason || 'Action required'}
              </span>
            )}
          </div>
        )}
      </div>

      {/* Desktop Column 5: Date OR Quick Action Buttons on Hover */}
      <div
        className="email-row-col-date"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'flex-end',
          minWidth: '85px',
        }}
      >
        {isHovered ? (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.35rem',
            }}
          >
            <button
              type="button"
              onClick={handleOpenGmail}
              title="Open message in Gmail"
              aria-label="Open in Gmail"
              style={{
                background: 'var(--bg-surface)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--radius-sm)',
                color: 'var(--text-muted)',
                padding: '4px',
                cursor: 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                transition: 'all var(--transition-fast)',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.color = 'var(--text-main)';
                e.currentTarget.style.borderColor = 'var(--accent)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.color = 'var(--text-muted)';
                e.currentTarget.style.borderColor = 'var(--border-subtle)';
              }}
            >
              <ExternalLink size={13} />
            </button>
            <button
              type="button"
              onClick={handleClick}
              title="View Priority Intelligence"
              aria-label="View Intelligence"
              style={{
                background: 'var(--accent-light)',
                border: '1px solid var(--accent)',
                borderRadius: 'var(--radius-sm)',
                color: 'var(--accent)',
                padding: '4px 6px',
                cursor: 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '2px',
                fontSize: '0.72rem',
                fontWeight: 600,
                transition: 'all var(--transition-fast)',
              }}
            >
              <Eye size={12} />
              <span>AI</span>
            </button>
          </div>
        ) : (
          <span
            style={{
              color: deadlineState ? 'var(--text-dim)' : 'var(--text-muted)',
              fontSize: '0.75rem',
              whiteSpace: 'nowrap',
            }}
          >
            {dateDisplay}
          </span>
        )}
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

export default EmailRow;
