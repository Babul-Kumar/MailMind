import React, { useState } from 'react';
import { ThumbsUp, ThumbsDown, ChevronDown, Loader, Check, AlertCircle } from 'lucide-react';

/* -------------------------------------------------------------------------
 * FeedbackWidget — Phase 52 (52-I: Production feedback collection UI)
 *
 * Inline priority correction widget for email cards.
 * Renders a lightweight "Correct this priority?" affordance.
 *
 * Design constraints:
 *   - No ML terminology exposed to users ("model", "training", "dataset")
 *   - No required input — all fields optional to avoid feedback fatigue
 *   - No raw email body submitted
 *   - Submits to POST /api/feedback
 *   - Non-blocking: UI responds immediately, submission is fire-and-forget
 * -------------------------------------------------------------------------*/

const PRIORITY_OPTIONS = [
  { value: 'P1', label: 'P1 — Urgent / Critical' },
  { value: 'P2', label: 'P2 — Action Required' },
  { value: 'P3', label: 'P3 — Informational' },
  { value: 'P4', label: 'P4 — Low Priority' },
];

const REASON_OPTIONS = [
  { value: 'too_high', label: 'Ranked too high' },
  { value: 'too_low', label: 'Ranked too low' },
  { value: 'action_wrong', label: 'Action required misread' },
  { value: 'deadline_wrong', label: 'Deadline misunderstood' },
  { value: 'context_missing', label: 'Missing context' },
  { value: 'other', label: 'Other' },
];

const PRIORITY_COLOUR = {
  P1: '#ef4444',
  P2: '#f97316',
  P3: '#3b82f6',
  P4: '#6b7280',
};

/**
 * FeedbackWidget
 *
 * Props:
 *   messageId     {string}  required — the email's unique message ID
 *   modelVersion  {string}  optional — current model version (for audit trail)
 *   currentPriority {string} optional — the currently displayed priority (P1-P4)
 *   confidence    {number}  optional — model confidence (0-1)
 *   topic         {string}  optional — model-assigned topic label
 *   threadId      {string}  optional — thread identifier
 *   deadlineDetected {bool} optional — whether model detected a deadline
 *   actionRequired {bool}   optional — whether model flagged action required
 *   compact       {bool}    optional — compact mode (icon only, no label)
 */
export function FeedbackWidget({
  messageId,
  modelVersion = 'priority-v5.1',
  currentPriority,
  confidence,
  topic,
  threadId,
  deadlineDetected = false,
  actionRequired = false,
  compact = false,
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [selected, setSelected] = useState('');
  const [reason, setReason] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState(null); // 'success' | 'error' | null

  if (!messageId) return null;

  const handleSubmit = async () => {
    if (!selected) return;

    setSubmitting(true);
    try {
      const body = {
        message_id: messageId,
        model_version: modelVersion || 'priority-v5.1',
        thread_id: threadId || null,
        feedback_type: 'CORRECT',
        predicted_priority: currentPriority || '',
        predicted_action_required: actionRequired,
        original_confidence: typeof confidence === 'number' ? confidence : null,
        original_topic: topic || null,
        original_deadline_detected: deadlineDetected,
        corrected_priority: selected,
        notes: reason || null,
      };

      const res = await fetch('/api/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (res.ok) {
        setResult('success');
        setTimeout(() => {
          setIsOpen(false);
          setResult(null);
          setSelected('');
          setReason('');
        }, 1500);
      } else {
        setResult('error');
      }
    } catch {
      setResult('error');
    } finally {
      setSubmitting(false);
    }
  };

  const priorityColour = PRIORITY_COLOUR[currentPriority] || '#6b7280';

  // Compact trigger button
  const TriggerButton = () => (
    <button
      onClick={(e) => { e.stopPropagation(); setIsOpen(!isOpen); }}
      title="Correct this priority"
      aria-label="Correct priority"
      aria-expanded={isOpen}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: '0.25rem',
        padding: compact ? '0.2rem 0.35rem' : '0.25rem 0.5rem',
        borderRadius: 'var(--radius-sm)',
        border: '1px solid var(--border-subtle)',
        backgroundColor: isOpen ? 'var(--bg-card)' : 'transparent',
        color: 'var(--text-muted)',
        cursor: 'pointer',
        fontSize: '0.7rem',
        fontWeight: 500,
        transition: 'all 0.15s',
        opacity: 0.7,
      }}
      onMouseEnter={e => { e.currentTarget.style.opacity = '1'; e.currentTarget.style.borderColor = priorityColour; }}
      onMouseLeave={e => { e.currentTarget.style.opacity = '0.7'; e.currentTarget.style.borderColor = 'var(--border-subtle)'; }}
    >
      {result === 'success' ? (
        <Check size={11} color="#10b981" />
      ) : result === 'error' ? (
        <AlertCircle size={11} color="#ef4444" />
      ) : (
        <ThumbsDown size={11} />
      )}
      {!compact && <span>Wrong?</span>}
      {!compact && <ChevronDown size={10} style={{ transform: isOpen ? 'rotate(180deg)' : 'none', transition: 'transform 0.15s' }} />}
    </button>
  );

  const dropdown = isOpen && result !== 'success' && (
    <div
      role="dialog"
      aria-label="Priority correction"
      onClick={e => e.stopPropagation()}
      style={{
        position: 'absolute', right: 0, top: '100%', marginTop: '0.3rem',
        zIndex: 200, minWidth: '220px',
        backgroundColor: 'var(--bg-card)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--radius-md)',
        boxShadow: '0 4px 16px rgba(0,0,0,0.25)',
        padding: '0.75rem',
        display: 'flex', flexDirection: 'column', gap: '0.5rem',
      }}
    >
      <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.1rem' }}>
        What should this be?
      </div>

      {/* Priority selector */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
        {PRIORITY_OPTIONS.map(opt => {
          const isSelected = selected === opt.value;
          const isCurrent = opt.value === currentPriority;
          return (
            <button
              key={opt.value}
              onClick={() => setSelected(isSelected ? '' : opt.value)}
              disabled={isCurrent}
              style={{
                display: 'flex', alignItems: 'center', gap: '0.5rem',
                padding: '0.3rem 0.5rem', borderRadius: 'var(--radius-sm)',
                border: `1px solid ${isSelected ? PRIORITY_COLOUR[opt.value] : 'var(--border-subtle)'}`,
                backgroundColor: isSelected ? `${PRIORITY_COLOUR[opt.value]}18` : 'transparent',
                color: isCurrent ? 'var(--text-muted)' : 'var(--text-secondary)',
                cursor: isCurrent ? 'default' : 'pointer',
                fontSize: '0.73rem', textAlign: 'left',
                opacity: isCurrent ? 0.45 : 1,
              }}
            >
              <span style={{
                width: '8px', height: '8px', borderRadius: '50%',
                backgroundColor: PRIORITY_COLOUR[opt.value],
                flexShrink: 0,
              }} />
              {opt.label}
              {isCurrent && <span style={{ marginLeft: 'auto', fontSize: '0.65rem', color: 'var(--text-muted)' }}>current</span>}
              {isSelected && <Check size={10} color={PRIORITY_COLOUR[opt.value]} style={{ marginLeft: 'auto' }} />}
            </button>
          );
        })}
      </div>

      {/* Optional reason */}
      {selected && (
        <select
          value={reason}
          onChange={e => setReason(e.target.value)}
          aria-label="Reason for correction (optional)"
          style={{
            padding: '0.3rem 0.5rem', borderRadius: 'var(--radius-sm)',
            border: '1px solid var(--border-subtle)',
            backgroundColor: 'var(--bg-input)',
            color: 'var(--text-secondary)',
            fontSize: '0.72rem',
          }}
        >
          <option value="">Why? (optional)</option>
          {REASON_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      )}

      {/* Submit row */}
      <div style={{ display: 'flex', gap: '0.4rem', justifyContent: 'flex-end' }}>
        <button
          onClick={() => { setIsOpen(false); setSelected(''); setReason(''); }}
          style={{
            padding: '0.3rem 0.6rem', borderRadius: 'var(--radius-sm)',
            border: '1px solid var(--border-subtle)', backgroundColor: 'transparent',
            color: 'var(--text-muted)', cursor: 'pointer', fontSize: '0.72rem',
          }}
        >
          Cancel
        </button>
        <button
          onClick={handleSubmit}
          disabled={!selected || submitting}
          style={{
            padding: '0.3rem 0.75rem', borderRadius: 'var(--radius-sm)',
            border: 'none',
            backgroundColor: selected && !submitting ? 'var(--accent)' : 'var(--bg-card)',
            color: selected && !submitting ? '#fff' : 'var(--text-muted)',
            cursor: selected && !submitting ? 'pointer' : 'not-allowed',
            fontSize: '0.72rem', fontWeight: 600,
            display: 'flex', alignItems: 'center', gap: '0.3rem',
          }}
        >
          {submitting && <Loader size={11} className="spin" />}
          Send
        </button>
      </div>

      {result === 'error' && (
        <div style={{ fontSize: '0.68rem', color: '#ef4444' }}>
          Could not submit. Please try again.
        </div>
      )}

      <div style={{ fontSize: '0.63rem', color: 'var(--text-muted)', paddingTop: '0.2rem', borderTop: '1px solid var(--border-subtle)' }}>
        Your correction is saved for review — it does not immediately change the AI model.
      </div>
    </div>
  );

  return (
    <div style={{ position: 'relative', display: 'inline-flex' }}>
      <TriggerButton />
      {dropdown}
    </div>
  );
}
