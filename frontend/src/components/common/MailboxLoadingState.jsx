import React from 'react';
import { MailMindLogo } from '../brand/MailMindLogo';
import { CheckCircle2, RefreshCw } from 'lucide-react';

/**
 * MailMind Staged Loading State
 * Renders meaningful progress across 6 explicit stages with real telemetry:
 * 1. Connecting to Gmail
 * 2. Discovering your mailbox
 * 3. Preparing emails
 * 4. Analyzing new messages
 * 5. Finalizing your inbox
 * 6. Mailbox ready ✓
 */
export function MailboxLoadingState({ scanStatus, stepText = 'Connecting to Gmail...' }) {
  const status = scanStatus?.status || 'SCANNING';
  const discovered = scanStatus?.discovered || 0;
  const analyzed = scanStatus?.analyzed || 0;
  const total = scanStatus?.total || 0;
  const percent = scanStatus?.progress_percent ?? (total > 0 ? Math.min(100, Math.round((analyzed / total) * 100)) : 0);

  // Determine active stage
  let stageIndex = 1;
  let stageTitle = 'Connecting to Gmail';
  let stageSubtitle = 'Establishing secure, read-only session...';

  if (status === 'QUEUED') {
    stageIndex = 1;
    stageTitle = 'Connecting to Gmail';
    stageSubtitle = 'Initializing mailbox queue...';
  } else if (status === 'SCANNING' || (discovered > 0 && analyzed === 0)) {
    stageIndex = 2;
    stageTitle = 'Discovering your mailbox';
    stageSubtitle = discovered > 0
      ? `Discovered ${discovered.toLocaleString()} messages across all labels...`
      : 'Indexing message identifiers...';
  } else if (status === 'ANALYZING') {
    if (analyzed < 200) {
      stageIndex = 3;
      stageTitle = 'Preparing emails';
      stageSubtitle = 'Extracting headers, timestamps, and thread signals...';
    } else {
      stageIndex = 4;
      stageTitle = 'Analyzing new messages';
      stageSubtitle = total > 0
        ? `Classifying priorities and extracting deadlines (${analyzed.toLocaleString()} / ${total.toLocaleString()})...`
        : `Classifying ${analyzed.toLocaleString()} messages...`;
    }
  } else if (status === 'FINALIZING') {
    stageIndex = 5;
    stageTitle = 'Finalizing your inbox';
    stageSubtitle = 'Committing secure index cache and updating priorities...';
  } else if (status === 'COMPLETE') {
    stageIndex = 6;
    stageTitle = 'Mailbox ready';
    stageSubtitle = 'Your intelligent inbox is fully prepared.';
  } else if (stepText) {
    stageSubtitle = stepText;
  }

  const STAGES = [
    { id: 1, label: 'Connecting' },
    { id: 2, label: 'Discovering' },
    { id: 3, label: 'Preparing' },
    { id: 4, label: 'Analyzing' },
    { id: 5, label: 'Finalizing' },
    { id: 6, label: 'Ready' },
  ];

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '55vh',
        padding: '2.5rem 1.5rem',
        textAlign: 'center',
      }}
    >
      <div
        style={{
          maxWidth: '460px',
          width: '100%',
          backgroundColor: 'var(--bg-surface)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-lg)',
          padding: '2.25rem 2rem',
          boxShadow: 'var(--shadow-md)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: '1.25rem',
        }}
      >
        {/* Brand Mark with Pulse */}
        <div
          style={{
            width: '60px',
            height: '60px',
            borderRadius: 'var(--radius-md)',
            backgroundColor: 'var(--bg-card)',
            border: '1px solid var(--border-subtle)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 4px 14px rgba(99, 102, 241, 0.15)',
          }}
        >
          <MailMindLogo size={36} isScanning={status !== 'COMPLETE'} />
        </div>

        {/* Heading & Subtitle */}
        <div>
          <h3
            style={{
              fontSize: '1.25rem',
              fontWeight: 700,
              color: 'var(--text-main)',
              letterSpacing: '-0.02em',
              margin: '0 0 0.35rem 0',
            }}
          >
            {stageTitle}
          </h3>
          <p
            style={{
              fontSize: '0.84rem',
              color: 'var(--text-muted)',
              lineHeight: 1.45,
              margin: 0,
            }}
          >
            {stageSubtitle}
          </p>
        </div>

        {/* Progress Bar & Real Counts */}
        <div style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          <div
            style={{
              width: '100%',
              height: '6px',
              backgroundColor: 'var(--border-subtle)',
              borderRadius: 'var(--radius-full)',
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                width: status === 'COMPLETE' ? '100%' : `${Math.max(5, percent)}%`,
                height: '100%',
                backgroundColor: 'var(--accent)',
                borderRadius: 'var(--radius-full)',
                transition: 'width 0.35s cubic-bezier(0.16, 1, 0.3, 1)',
              }}
            />
          </div>

          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              fontSize: '0.76rem',
              color: 'var(--text-muted)',
            }}
          >
            <span>
              {total > 0
                ? `${analyzed.toLocaleString()} / ${total.toLocaleString()} emails`
                : discovered > 0
                ? `${discovered.toLocaleString()} discovered`
                : 'Processing...'}
            </span>
            <span style={{ fontWeight: 600, color: 'var(--text-secondary)' }}>
              {status === 'COMPLETE' ? '100%' : `${percent}%`}
            </span>
          </div>
        </div>

        {/* 6 Stage Stepper Dots */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            width: '100%',
            paddingTop: '0.75rem',
            borderTop: '1px solid var(--border-subtle)',
          }}
        >
          {STAGES.map((s) => {
            const isCompleted = s.id < stageIndex || (s.id === 6 && status === 'COMPLETE');
            const isCurrent = s.id === stageIndex && status !== 'COMPLETE';
            return (
              <div
                key={s.id}
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: '0.25rem',
                  opacity: isCompleted || isCurrent ? 1 : 0.45,
                }}
              >
                <div
                  style={{
                    width: '8px',
                    height: '8px',
                    borderRadius: '50%',
                    backgroundColor: isCompleted ? '#22c55e' : isCurrent ? 'var(--accent)' : 'var(--border-subtle)',
                    boxShadow: isCurrent ? '0 0 8px rgba(99, 102, 241, 0.5)' : 'none',
                    transition: 'all 0.2s ease',
                  }}
                />
                <span style={{ fontSize: '0.66rem', color: isCurrent ? 'var(--text-main)' : 'var(--text-dim)', fontWeight: isCurrent ? 600 : 400 }}>
                  {s.label}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export default MailboxLoadingState;
