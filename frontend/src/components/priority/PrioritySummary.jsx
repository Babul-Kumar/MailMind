import React, { useState } from 'react';
import { Sparkles, BarChart3 } from 'lucide-react';

function PrioritySummaryComponent({ emails = [], stats = null, activeFilter = 'ALL' }) {
  const totalAnalyzed = stats?.total_analyzed ?? emails.length;
  if (!totalAnalyzed) return null;

  const counts = stats?.counts || { P1: 0, P2: 0, P3: 0, P4: 0 };
  const p1 = counts.P1 || 0;
  const p2 = counts.P2 || 0;
  const p3 = counts.P3 || 0;
  const p4 = counts.P4 || 0;
  const sum = p1 + p2 + p3 + p4 || totalAnalyzed || 1;

  const p1Pct = Number(((p1 / sum) * 100).toFixed(1));
  const p2Pct = Number(((p2 / sum) * 100).toFixed(1));
  const p3Pct = Number(((p3 / sum) * 100).toFixed(1));
  const p4Pct = Number(((p4 / sum) * 100).toFixed(1));

  const [hoveredTier, setHoveredTier] = useState(null);

  const tiers = [
    { key: 'P1', label: 'Critical', count: p1, pct: p1Pct, color: 'var(--p1-color)', desc: 'Immediate action or deadline' },
    { key: 'P2', label: 'Important', count: p2, pct: p2Pct, color: 'var(--p2-color)', desc: 'Important business correspondence' },
    { key: 'P3', label: 'Routine', count: p3, pct: p3Pct, color: 'var(--p3-color)', desc: 'Informational & standard operations' },
    { key: 'P4', label: 'Low', count: p4, pct: p4Pct, color: 'var(--p4-color)', desc: 'Promotional, bulk updates & newsletters' },
  ];

  return (
    <div
      className="priority-summary-card"
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '0.75rem',
        padding: '0.85rem 1.25rem',
        backgroundColor: 'var(--bg-surface)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--radius-lg)',
        boxShadow: 'var(--shadow-sm)',
        marginBottom: '1rem',
        transition: 'border-color var(--transition-fast)',
      }}
    >
      {/* Top Header: Title & Total Analyzed */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.55rem' }}>
          <div
            style={{
              width: '26px',
              height: '26px',
              borderRadius: 'var(--radius-md)',
              background: 'linear-gradient(135deg, rgba(99, 102, 241, 0.18), rgba(168, 85, 247, 0.18))',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--accent)',
            }}
          >
            <Sparkles size={14} />
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ fontSize: '0.84rem', fontWeight: 700, color: 'var(--text-main)', letterSpacing: '-0.01em' }}>
              Priority Distribution
            </span>
            <span
              style={{
                fontSize: '0.68rem',
                padding: '0.1rem 0.45rem',
                borderRadius: 'var(--radius-full)',
                background: 'rgba(99, 102, 241, 0.10)',
                color: 'var(--accent)',
                fontWeight: 600,
                border: '1px solid rgba(99, 102, 241, 0.22)',
              }}
            >
              Model v5.1
            </span>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span
            style={{
              fontSize: '0.74rem',
              color: 'var(--text-muted)',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.35rem',
              backgroundColor: 'var(--bg-card)',
              border: '1px solid var(--border-subtle)',
              padding: '0.2rem 0.55rem',
              borderRadius: 'var(--radius-sm)',
              fontWeight: 500,
            }}
          >
            <BarChart3 size={12} style={{ color: 'var(--accent)' }} />
            <strong style={{ color: 'var(--text-main)' }}>{totalAnalyzed.toLocaleString()}</strong> analyzed
          </span>
        </div>
      </div>

      {/* Visual Continuous Priority Distribution Spectrum Bar */}
      <div
        style={{
          display: 'flex',
          height: '6px',
          width: '100%',
          borderRadius: 'var(--radius-full)',
          overflow: 'hidden',
          backgroundColor: 'var(--border-divider)',
          gap: '2px',
        }}
        title={`Distribution: P1 ${p1Pct}% · P2 ${p2Pct}% · P3 ${p3Pct}% · P4 ${p4Pct}%`}
      >
        {tiers.map((t) => (
          t.pct > 0 && (
            <div
              key={t.key}
              onMouseEnter={() => setHoveredTier(t.key)}
              onMouseLeave={() => setHoveredTier(null)}
              style={{
                width: `${t.pct}%`,
                backgroundColor: t.color,
                opacity: hoveredTier === null || hoveredTier === t.key ? 1 : 0.45,
                transition: 'opacity 0.2s ease, transform 0.2s ease, filter 0.2s ease',
                transform: hoveredTier === t.key ? 'scaleY(1.4)' : 'scaleY(1)',
                filter: hoveredTier === t.key ? `drop-shadow(0 0 4px ${t.color})` : 'none',
              }}
            />
          )
        ))}
      </div>

      {/* Clean Descriptive Metrics (Clear display without duplicating filter buttons) */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '0.75rem',
          paddingTop: '0.1rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem', flexWrap: 'wrap' }}>
          {tiers.map((t) => {
            const isHovered = hoveredTier === t.key;
            return (
              <div
                key={t.key}
                onMouseEnter={() => setHoveredTier(t.key)}
                onMouseLeave={() => setHoveredTier(null)}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.4rem',
                  fontSize: '0.76rem',
                  color: isHovered ? 'var(--text-main)' : 'var(--text-muted)',
                  transition: 'all var(--transition-fast)',
                }}
              >
                <span
                  style={{
                    width: '6px',
                    height: '6px',
                    borderRadius: '50%',
                    backgroundColor: t.color,
                    boxShadow: isHovered ? `0 0 6px ${t.color}` : 'none',
                    transition: 'box-shadow var(--transition-fast)',
                  }}
                />
                <span style={{ fontWeight: 600 }}>{t.key} · {t.label}</span>
                <span
                  style={{
                    fontWeight: 700,
                    color: isHovered ? t.color : 'var(--text-secondary)',
                  }}
                >
                  {t.count.toLocaleString()}
                </span>
                <span style={{ fontSize: '0.70rem', color: 'var(--text-dim)' }}>
                  ({t.pct}%)
                </span>
              </div>
            );
          })}
        </div>

        <div
          style={{
            fontSize: '0.72rem',
            color: 'var(--text-dim)',
            display: 'flex',
            alignItems: 'center',
            gap: '0.4rem',
          }}
        >
          {hoveredTier ? (
            <span style={{ color: 'var(--text-secondary)', fontWeight: 500 }}>
              {tiers.find((t) => t.key === hoveredTier)?.desc}
            </span>
          ) : (
            <span>Continuous intelligence triage</span>
          )}
        </div>
      </div>
    </div>
  );
}

export const PrioritySummary = React.memo(PrioritySummaryComponent);
export default PrioritySummary;
