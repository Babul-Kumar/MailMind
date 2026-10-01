import React from 'react';

export function AIConfidence({ confidence }) {
  const pct = Math.round((confidence || 0) * 100);
  const isLow = pct < 60;

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
      <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>Confidence:</span>
      <span
        style={{
          fontSize: '0.78rem',
          fontWeight: 700,
          padding: '0.12rem 0.45rem',
          borderRadius: 'var(--radius-xs)',
          backgroundColor: isLow ? 'rgba(245, 158, 11, 0.12)' : 'var(--accent-light)',
          color: isLow ? 'var(--p2-color)' : 'var(--accent)',
        }}
      >
        {pct}%
      </span>
    </div>
  );
}
