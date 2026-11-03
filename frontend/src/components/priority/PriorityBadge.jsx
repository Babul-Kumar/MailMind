import React from 'react';
import { getPriorityMeta } from '../../utils/priority';

export function PriorityBadge({ priority, showLabel = true, size = 'md' }) {
  const meta = getPriorityMeta(priority);
  const isSm = size === 'sm';
  const isP1 = priority === 'P1';
  const isP2 = priority === 'P2';
  const isP3 = priority === 'P3';
  const isP4 = priority === 'P4';

  const badgeBg = isP4 ? 'rgba(148, 163, 184, 0.08)' : meta.bg;
  const badgeColor = isP4 ? 'var(--text-muted)' : meta.color;
  const badgeBorder = isP4 ? 'rgba(148, 163, 184, 0.20)' : meta.border;
  const dotColor = isP4 ? 'var(--text-dim)' : meta.color;

  const glowShadow = isP1
    ? '0 0 10px rgba(255, 51, 102, 0.3)'
    : isP2
    ? '0 0 8px rgba(245, 158, 11, 0.2)'
    : isP3
    ? '0 0 8px rgba(56, 189, 248, 0.18)'
    : 'none';

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '0.35rem',
        padding: isSm ? '0.12rem 0.45rem' : '0.22rem 0.55rem',
        borderRadius: 'var(--radius-xs)',
        fontSize: isSm ? '0.68rem' : '0.74rem',
        fontWeight: isP4 ? 600 : 700,
        letterSpacing: '0.02em',
        backgroundColor: badgeBg,
        color: badgeColor,
        border: `1px solid ${badgeBorder}`,
        boxShadow: glowShadow,
        width: 'fit-content',
        whiteSpace: 'nowrap',
        opacity: isP4 ? 0.82 : 1,
        transition: 'all var(--transition-fast)',
      }}
    >
      <span
        className={isP1 ? 'animate-pulse-p1' : ''}
        style={{
          width: isSm ? '5px' : '6px',
          height: isSm ? '5px' : '6px',
          borderRadius: '50%',
          backgroundColor: dotColor,
          display: 'inline-block',
          flexShrink: 0,
        }}
      />
      <span>{priority}</span>
      {showLabel && <span style={{ opacity: isP4 ? 0.75 : 0.9, fontWeight: 500 }}>{meta.label}</span>}
    </span>
  );
}

export default PriorityBadge;
