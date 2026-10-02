import React, { useState } from 'react';
import { Sparkles, ChevronDown } from 'lucide-react';
import { getDeadlineState } from '../../utils/formatting';
import { getPriorityMeta } from '../../utils/priority';

export function AIInsight({ email }) {
  const [techOpen, setTechOpen] = useState(false);
  if (!email) return null;

  const finalPriority = email.final_priority || email.predicted_priority;
  const modelPriority = email.model_priority || email.predicted_priority;
  const isRefined = Boolean(email.refinement_applied);
  const actionRequired = email.action_required;
  const deadlineState = getDeadlineState(email);
  const pct = Math.round((email.confidence || 0) * 100);

  const textLower = `${email.subject || ''} ${email.body || ''}`.toLowerCase();

  // Grounded insight — deadline-state-aware & metadata-driven
  let insightTitle = '';
  let insightBody = '';
  const isHistorical = email.deadline_status === 'HISTORICAL' || deadlineState?.state === 'historical';
  if (deadlineState?.state === 'overdue' || isHistorical) {
    if (email.action_reason === 'Immediate verification required' || email.deadline_status === 'EXPIRED' || textLower.includes('verification') || textLower.includes('otp')) {
      insightTitle = 'Expired verification code';
      insightBody = 'This one-time passcode or verification code has expired and is no longer valid.';
    } else if (isHistorical) {
      insightTitle = `Past ${(email.action_reason || 'deadline').toLowerCase()}`;
      insightBody = `The deadline passed on ${deadlineState.longLabel}.`;
    } else if (email.action_reason === 'Submission deadline' || textLower.includes('competition') || textLower.includes('submission')) {
      insightTitle = 'Overdue submission deadline';
      if (textLower.includes('competition')) {
        insightBody = `The competition deadline passed on ${deadlineState.longLabel}.`;
      } else if (textLower.includes('assignment')) {
        insightBody = `The assignment deadline passed on ${deadlineState.longLabel}.`;
      } else {
        insightBody = `The submission deadline passed on ${deadlineState.longLabel}.`;
      }
    } else if (email.action_reason === 'Service action' || textLower.includes('deletion') || textLower.includes('project')) {
      insightTitle = 'Overdue service action';
      insightBody = `The service action deadline passed on ${deadlineState.longLabel}.`;
    } else {
      insightTitle = `Overdue ${(email.action_reason || 'deadline').toLowerCase()}`;
      insightBody = `The deadline passed on ${deadlineState.longLabel}.`;
    }
  } else if (deadlineState?.state === 'today') {
    insightTitle = `${email.action_reason || 'Deadline'} — due today`;
    const timeDetail = deadlineState.timeStr ? ` at ${deadlineState.timeStr}` : '';
    if (textLower.includes('competition')) {
      insightBody = `The competition closes today${timeDetail}.`;
    } else if (textLower.includes('assignment')) {
      insightBody = `The assignment deadline is today${timeDetail}.`;
    } else {
      insightBody = `This deadline expires today${timeDetail}.`;
    }
  } else if (deadlineState?.state === 'upcoming') {
    if (email.action_reason === 'Service action' || ((textLower.includes('inactive') || textLower.includes('project')) && textLower.includes('delete'))) {
      insightTitle = 'Service action';
      const targetDate = deadlineState.dateStr || deadlineState.fullDateStr;
      insightBody = `Your inactive project is scheduled for deletion after ${targetDate}.`;
    } else if (email.action_reason === 'Submission deadline' || textLower.includes('competition')) {
      insightTitle = 'Submission deadline';
      const targetDate = deadlineState.dateStr || deadlineState.fullDateStr;
      if (textLower.includes('competition')) {
        insightBody = `The competition closes on ${targetDate}.`;
      } else if (textLower.includes('assignment')) {
        insightBody = `The assignment submission closes on ${targetDate}.`;
      } else {
        insightBody = `Submissions close on ${targetDate}.`;
      }
    } else {
      insightTitle = email.action_reason || 'Upcoming deadline';
      insightBody = `This deadline closes on ${deadlineState.dateStr || deadlineState.longLabel}.`;
    }
  } else if (actionRequired === true) {
    if (email.action_reason === 'Account security action') {
      insightTitle = 'Account security action';
      if (textLower.includes('google drive')) {
        insightBody = 'Review the recent Google Drive access activity.';
      } else if (textLower.includes('sign-in') || textLower.includes('device') || textLower.includes('activity')) {
        insightBody = 'Review the recent sign-in or device access activity.';
      } else {
        insightBody = 'Review the recent security activity on your account.';
      }
    } else if (email.action_reason === 'Service action') {
      insightTitle = 'Service action';
      insightBody = email.refinement_reason || 'Action is required to prevent service interruption.';
    } else {
      insightTitle = email.action_reason || 'Action required';
      insightBody = email.refinement_reason || 'Action or response is required for this message.';
    }
  } else {
    insightTitle = 'No action required';
    insightBody = 'No explicit action or deadline was detected for this email.';
  }

  return (
    <div
      style={{
        backgroundColor: 'var(--bg-card)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--radius-lg)',
        padding: '1.1rem',
        display: 'flex',
        flexDirection: 'column',
        gap: '0.75rem',
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
        <Sparkles size={15} color="var(--sparkle-color)" />
        <h4 style={{ fontSize: '0.88rem', fontWeight: 600, color: 'var(--text-main)', margin: 0 }}>
          ✦ Why this matters
        </h4>
      </div>

      {/* Primary insight card */}
      <div
        style={{
          padding: '0.85rem 1rem',
          backgroundColor: 'var(--bg-surface)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-md)',
          display: 'flex',
          flexDirection: 'column',
          gap: '0.35rem',
        }}
      >
        {deadlineState && (
          <span style={{
            fontSize: '0.75rem',
            fontWeight: 700,
            color: isHistorical
              ? 'var(--text-muted)'
              : deadlineState.state === 'overdue'
                ? 'var(--p1-color)'
                : 'var(--p2-color)',
            display: 'flex',
            alignItems: 'center',
            gap: '0.3rem',
          }}>
            <span>{isHistorical ? '📅' : deadlineState.icon}</span>{' '}
            {isHistorical && deadlineState.label.startsWith('Overdue · ')
              ? deadlineState.label.replace('Overdue · ', 'Past · ')
              : deadlineState.label}
          </span>
        )}
        {!deadlineState && actionRequired === true && (
          <span style={{ fontSize: '0.75rem', fontWeight: 700, color: email.action_reason === 'Account security action' ? 'var(--p1-color)' : 'var(--accent)' }}>
            ● {email.action_reason || 'Action required'}
          </span>
        )}
        <p style={{ fontSize: '0.88rem', fontWeight: 700, color: 'var(--text-main)', margin: 0, lineHeight: 1.3 }}>
          {insightTitle}
        </p>
        <p style={{ fontSize: '0.84rem', color: 'var(--text-secondary)', lineHeight: 1.5, margin: 0 }}>
          {insightBody}
        </p>
        {isRefined && (
          <div style={{ marginTop: '0.25rem', paddingTop: '0.35rem', borderTop: '1px solid var(--border-divider)', fontSize: '0.73rem', color: 'var(--text-muted)' }}>
            Priority adjusted &bull; Model: {modelPriority} &rarr; Final: {finalPriority}
          </div>
        )}
      </div>

      {/* Collapsible: Technical classification details */}
      <div>
        <button
          onClick={() => setTechOpen((o) => !o)}
          style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.74rem', color: 'var(--text-muted)', fontWeight: 500, cursor: 'pointer', background: 'none', border: 'none', padding: 0 }}
          aria-expanded={techOpen}
        >
          <ChevronDown size={13} style={{ transform: techOpen ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.15s' }} />
          <span>Technical classification details</span>
        </button>

        {techOpen && (
          <div
            style={{
              marginTop: '0.5rem',
              padding: '0.75rem',
              backgroundColor: 'var(--bg-surface)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-sm)',
              fontSize: '0.76rem',
              color: 'var(--text-secondary)',
              lineHeight: 1.6,
              display: 'flex',
              flexDirection: 'column',
              gap: '0.35rem',
            }}
          >
            <div><strong style={{ color: 'var(--text-main)' }}>Model:</strong> TF-IDF + Logistic Regression</div>
            <div><strong style={{ color: 'var(--text-main)' }}>Priority:</strong> {finalPriority} · {getPriorityMeta(finalPriority).label}</div>
            <div>
              <strong style={{ color: 'var(--text-main)' }}>Confidence:</strong>{' '}
              <span style={{ color: pct < 60 ? 'var(--p2-color)' : 'var(--accent)', fontWeight: 600 }}>{pct}%</span>
            </div>
            {email.top_signals && email.top_signals.length > 0 && (
              <div>
                <div style={{ fontWeight: 600, color: 'var(--text-muted)', marginBottom: '0.3rem' }}>Top text features:</div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem' }}>
                  {email.top_signals.map((sig, idx) => (
                    <span key={idx} title={`weight: +${sig.weight}`} style={{ padding: '0.12rem 0.45rem', backgroundColor: 'var(--bg-surface-hover)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-sm)', fontSize: '0.73rem', color: 'var(--text-main)' }}>
                      <span style={{ color: 'var(--accent)', fontWeight: 700 }}>+</span> {sig.term}
                    </span>
                  ))}
                </div>
              </div>
            )}
            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', borderTop: '1px solid var(--border-divider)', paddingTop: '0.35rem' }}>
              Action, deadline, and topic are evaluated separately from the model score.
            </div>
          </div>
        )}
      </div>
    </div>
  );
}


