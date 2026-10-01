import React from 'react';
import { getPriorityMeta } from '../../utils/priority';

export function PriorityBadge({ priority, showLabel = true, size = 'md' }) {
  const meta = getPriorityMeta(priority);
  const isSm = size === 'sm';
  const isP4 = priority === 'P4';

  const badgeBg = isP4 ? 'rgba(148, 163, 184, 0.06)' : meta.bg;
  const badgeColor = isP4 ? 'var(--text-muted)' : meta.color;
  const badgeBorder = isP4 ? 'rgba(148, 163, 184, 0.16)' : meta.border;
  const dotColor = isP4 ? 'var(--text-dim)' : meta.color;

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '0.35rem',
        padding: isSm ? '0.12rem 0.4rem' : '0.2rem 0.5rem',
        borderRadius: 'var(--radius-xs)',
        fontSize: isSm ? '0.68rem' : '0.74rem',
        fontWeight: isP4 ? 600 : 700,
        letterSpacing: '0.02em',
        backgroundColor: badgeBg,
        color: badgeColor,
        border: `1px solid ${badgeBorder}`,
        width: 'fit-content',
        whiteSpace: 'nowrap',
        opacity: isP4 ? 0.82 : 1,
      }}
    >
      <span
        style={{
          width: '5px',
          height: '5px',
          borderRadius: '50%',
          backgroundColor: dotColor,
          display: 'inline-block',
          opacity: isP4 ? 0.6 : 1,
        }}
      />
      <span>{priority}</span>
      {showLabel && <span style={{ opacity: isP4 ? 0.75 : 0.9, fontWeight: 500 }}>{meta.label}</span>}
    </span>
  );
}
