import React from 'react';
import { Sparkles, CheckCircle2 } from 'lucide-react';

export function AIProcessingState({ isLoading, stepText }) {
  if (!isLoading) return null;

  return (
    <div
      className="topbar-ai-status"
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '0.45rem',
        fontSize: '0.78rem',
        color: 'var(--sparkle-color)',
        backgroundColor: 'var(--accent-light)',
        padding: '0.25rem 0.65rem',
        borderRadius: 'var(--radius-full)',
        whiteSpace: 'nowrap',
      }}
    >
      <Sparkles size={13} className="animate-spin" />
      <span>{stepText || 'Organizing inbox...'}</span>
    </div>
  );
}
