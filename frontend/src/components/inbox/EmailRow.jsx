import React, { useMemo, useCallback, useState } from 'react';
import { formatEmailDate, cleanSenderName, extractSnippet, getDeadlineState } from '../../utils/formatting';

const PRIORITY_DOT_COLORS = {
  P1: 'var(--p1-color)',
  P2: 'var(--p2-color)',
  P3: 'var(--p3-color)',
  P4: 'var(--p4-color)',
};

function EmailRowComponent({ email, isSelected, onClick }) {
  const [isHovered, setIsHovered] = useState(false);
  const senderDisplay = useMemo(() => cleanSenderName(email.sender), [email.sender]);
  const dateDisplay = useMemo(() => formatEmailDate(email.date), [email.date]);
  const snippet = useMemo(() => extractSnippet(email.body, email.subject), [email.body, email.subject]);
  const priority = email.effective_priority || email.final_priority || email.predicted_priority || 'P3';
  const actionRequired = Boolean(email.action_required);
  const deadlineState = useMemo(() => getDeadlineState(email), [email.deadline_status, email.deadline_datetime, email.date]);

  const dotColor = PRIORITY_DOT_COLORS[priority] || 'var(--p3-color)';
  const isP1 = priority === 'P1';
  const isP4 = priority === 'P4';

  const handleClick = useCallback(() => {
    onClick?.(email);
  }, [onClick, email]);

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
        display: 'flex',
        flexDirection: 'column',
        gap: '4px',
        padding: '10px 14px',
        borderBottom: '1px solid var(--border-divider)',
        cursor: 'pointer',
        transition: 'background-color var(--transition-fast), border-color var(--transition-fast)',
        userSelect: 'none',
        position: 'relative',
        backgroundColor: isSelected ? 'var(--bg-surface-selected)' : isHovered ? 'var(--bg-surface-hover)' : 'transparent',
      }}
    >
      {/* Line 1: Priority Dot + Sender Name + Timestamp */}
      <div
        className="email-row-line-1"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '8px',
          width: '100%',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0, flex: 1 }}>
          <span
            className={`priority-dot ${isP1 ? 'animate-pulse-p1' : ''}`}
            title={`Priority ${priority}`}
            style={{
              width: '6px',
              height: '6px',
              borderRadius: '50%',
              backgroundColor: dotColor,
              flexShrink: 0,
              boxShadow: isP1 ? '0 0 6px var(--p1-color)' : 'none',
            }}
          />
          <span
            className="email-row-sender"
            style={{
              fontSize: '0.85rem',
              fontWeight: isP4 ? 500 : 600,
              color: isP4 ? 'var(--text-secondary)' : 'var(--text-main)',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
              letterSpacing: '-0.01em',
            }}
          >
            {senderDisplay}
          </span>
        </div>

        <span
          className="email-row-date"
          style={{
            fontSize: '0.74rem',
            color: 'var(--text-muted)',
            whiteSpace: 'nowrap',
            flexShrink: 0,
            fontVariantNumeric: 'tabular-nums',
          }}
        >
          {dateDisplay}
        </span>
      </div>

      {/* Line 2: Subject + Snippet Preview + Action Indicator */}
      <div
        className="email-row-line-2"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          fontSize: '0.82rem',
          overflow: 'hidden',
          whiteSpace: 'nowrap',
          textOverflow: 'ellipsis',
          lineHeight: 1.4,
        }}
      >
        <span
          className="email-row-subject"
          style={{
            fontWeight: 500,
            color: isP4 ? 'var(--text-muted)' : 'var(--text-main)',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            flexShrink: 0,
            maxWidth: snippet ? '55%' : '100%',
          }}
        >
          {email.subject || '(No Subject)'}
        </span>

        {snippet && (
          <>
            <span style={{ color: 'var(--text-dim)', flexShrink: 0, fontSize: '0.78rem' }}>—</span>
            <span
              className="email-row-snippet"
              style={{
                color: 'var(--text-muted)',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                flex: 1,
                fontSize: '0.8rem',
              }}
            >
              {snippet}
            </span>
          </>
        )}

        {/* Discreet Action/Deadline Tag if urgent */}
        {actionRequired && (
          <span
            style={{
              fontSize: '0.68rem',
              fontWeight: 600,
              padding: '1px 5px',
              borderRadius: 'var(--radius-xs)',
              backgroundColor: isP1 ? 'var(--p1-bg)' : 'var(--accent-light)',
              color: isP1 ? 'var(--p1-color)' : 'var(--accent)',
              border: `1px solid ${isP1 ? 'var(--p1-border)' : 'var(--border-subtle)'}`,
              flexShrink: 0,
              marginLeft: 'auto',
            }}
          >
            Action
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
