import React from 'react';
import { Sparkles, CheckCircle2 } from 'lucide-react';

export function AIProcessingState({ isLoading, stepText }) {
  if (!isLoading && !stepText) return null;

  return (
    <div
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '0.45rem',
        fontSize: '0.78rem',
        color: isLoading ? 'var(--sparkle-color)' : 'var(--text-secondary)',
        backgroundColor: 'var(--accent-light)',
        padding: '0.25rem 0.65rem',
        borderRadius: 'var(--radius-full)',
      }}
    >
      {isLoading ? (
        <>
          <Sparkles size={13} className="animate-spin" />
          <span>{stepText || 'Organizing inbox...'}</span>
        </>
      ) : (
        <>
          <CheckCircle2 size={13} color="var(--accent)" />
          <span>{stepText || '✨ Inbox organized'}</span>
        </>
      )}
    </div>
  );
}
