import React, { useState, useEffect, useCallback } from 'react';

/* ─── Status badge ─── */
function StatusBadge({ severity }) {
  const colors = {
    NORMAL: { bg: '#064e3b', fg: '#34d399', label: 'NORMAL' },
    WATCH: { bg: '#78350f', fg: '#fbbf24', label: 'WATCH' },
    ALERT: { bg: '#7f1d1d', fg: '#f87171', label: 'ALERT' },
  };
  const c = colors[severity] || colors.NORMAL;
  return (
    <span
      style={{
        display: 'inline-flex', alignItems: 'center', gap: '0.3rem',
        padding: '0.15rem 0.55rem', borderRadius: '999px',
        fontSize: '0.7rem', fontWeight: 700, letterSpacing: '0.04em',
        background: c.bg, color: c.fg,
      }}
    >
      <span style={{ width: 6, height: 6, borderRadius: '50%', background: c.fg, display: 'inline-block' }} />
      {c.label}
    </span>
  );
}

/* ─── Section card ─── */
function Section({ title, severity, children }) {
  return (
    <div
      style={{
        background: 'var(--bg-secondary, #1e293b)', border: '1px solid var(--border-subtle, #334155)',
        borderRadius: 'var(--radius-md, 8px)', padding: '1rem', marginBottom: '0.75rem',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.6rem' }}>
        <h4 style={{ margin: 0, fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-main, #f1f5f9)' }}>{title}</h4>
        {severity && <StatusBadge severity={severity} />}
      </div>
      {children}
    </div>
  );
}

/* ─── Stat row ─── */
function Stat({ label, value, sub }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', padding: '0.2rem 0' }}>
      <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary, #94a3b8)' }}>{label}</span>
      <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-main, #e2e8f0)' }}>
        {value}
        {sub && <span style={{ fontSize: '0.68rem', fontWeight: 400, color: 'var(--text-muted, #64748b)', marginLeft: '0.3rem' }}>{sub}</span>}
      </span>
    </div>
  );
}

/* ─── Tiny matrix for P→P ─── */
function CorrectionMatrix({ matrix }) {
  const keys = ['P1', 'P2', 'P3', 'P4'];
  return (
    <table style={{ fontSize: '0.7rem', borderCollapse: 'collapse', width: '100%', marginTop: '0.4rem' }}>
      <thead>
        <tr>
          <th style={{ padding: '0.2rem', color: 'var(--text-muted)', textAlign: 'left' }}>From ↓ To →</th>
          {keys.map((k) => <th key={k} style={{ padding: '0.2rem', color: 'var(--text-secondary)', textAlign: 'center' }}>{k}</th>)}
        </tr>
      </thead>
      <tbody>
        {keys.map((from) => (
          <tr key={from}>
            <td style={{ padding: '0.2rem', fontWeight: 600, color: 'var(--text-secondary)' }}>{from}</td>
            {keys.map((to) => {
              const v = matrix?.[from]?.[to] ?? 0;
              const highlight = from !== to && v > 0;
              return (
                <td
                  key={to}
                  style={{
                    padding: '0.2rem', textAlign: 'center',
                    color: highlight ? '#fbbf24' : 'var(--text-muted)',
                    fontWeight: highlight ? 700 : 400,
                  }}
                >
                  {v}
                </td>
              );
            })}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/* ─── Main Panel ─── */
export function SystemHealthPanel() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expanded, setExpanded] = useState('production');

  const fetchData = useCallback(() => {
    setLoading(true);
    setError(null);
    fetch('/api/monitoring/phase51/summary')
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then((json) => { if (json.status === 'success') setData(json.phase51); else throw new Error('Failed'); })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  if (loading) return <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>Loading monitoring data…</div>;
  if (error) return <div style={{ padding: '1rem', color: '#f87171' }}>Error: {error}</div>;
  if (!data) return null;

  const pm = data.production_model || {};
  const rb = data.rollback_model || {};
  const dist = data.distribution || {};
  const conf = data.confidence || {};
  const fb = data.feedback || {};
  const boundary = data.p2_p3_boundary || {};
  const safety = data.safety || {};
  const ad = data.action_deadline || {};
  const na = data.needs_attention || {};
  const drift = data.drift || {};
  const ce = data.cache_errors || {};
  const alerts = data.alerts || {};
  const v52 = data.v52_readiness || {};

  const sections = [
    { id: 'production', label: '1. Production Model' },
    { id: 'distribution', label: '2. Distribution' },
    { id: 'confidence', label: '3. Confidence' },
    { id: 'feedback', label: '4. Feedback' },
    { id: 'boundary', label: '5. P2/P3 Boundary' },
    { id: 'safety', label: '6. Safety' },
    { id: 'action', label: '7. Action & Deadline' },
    { id: 'attention', label: '8. Needs Attention' },
    { id: 'drift', label: '9. Drift' },
    { id: 'cache', label: '10. Cache & Errors' },
    { id: 'alerts', label: '11. Alerts' },
    { id: 'v52', label: '12. v5.2 Readiness' },
  ];

  return (
    <div style={{ maxHeight: '55vh', overflowY: 'auto', paddingRight: '0.3rem' }}>
      {/* Nav pills */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.3rem', marginBottom: '0.75rem' }}>
        {sections.map((s) => (
          <button
            key={s.id}
            onClick={() => setExpanded(s.id)}
            style={{
              padding: '0.25rem 0.5rem', borderRadius: '999px', border: 'none', cursor: 'pointer',
              fontSize: '0.68rem', fontWeight: expanded === s.id ? 700 : 500,
              background: expanded === s.id ? 'var(--accent-primary, #3b82f6)' : 'var(--bg-tertiary, #334155)',
              color: expanded === s.id ? '#fff' : 'var(--text-secondary, #94a3b8)',
            }}
          >
            {s.label}
          </button>
        ))}
        <button
          onClick={fetchData}
          style={{
            padding: '0.25rem 0.5rem', borderRadius: '999px', border: 'none', cursor: 'pointer',
            fontSize: '0.68rem', fontWeight: 600, marginLeft: 'auto',
            background: '#064e3b', color: '#34d399',
          }}
        >
          ↻ Refresh
        </button>
      </div>

      {/* 1. Production */}
      {expanded === 'production' && (
        <Section title="Production Model">
          <Stat label="Active Model" value={pm.model_version} />
          <Stat label="Status" value={pm.status} />
          <Stat label="Dataset" value={pm.dataset_version} />
          <Stat label="SHA-256" value={pm.artifact_sha256?.slice(0, 16) + '…'} />
          <Stat label="Promoted" value={pm.promoted_at} />
          <div style={{ borderTop: '1px solid var(--border-subtle)', marginTop: '0.5rem', paddingTop: '0.5rem' }}>
            <Stat label="Rollback Model" value={rb.model_version} />
            <Stat label="Rollback Status" value={rb.status} />
          </div>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '0.5rem', fontStyle: 'italic' }}>
            {data.governance}
          </div>
        </Section>
      )}

      {/* 2. Distribution */}
      {expanded === 'distribution' && (
        <Section title="Prediction Distribution" severity={dist.severity}>
          <Stat label="Total Messages" value={dist.total_messages?.toLocaleString()} />
          {['P1', 'P2', 'P3', 'P4'].map((p) => (
            <Stat key={p} label={p} value={`${dist.counts?.[p] ?? 0} (${dist.percentages?.[p] ?? 0}%)`}
              sub={`drift: ${dist.drift_pp?.[p] >= 0 ? '+' : ''}${dist.drift_pp?.[p] ?? 0}pp`}
            />
          ))}
          <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', marginTop: '0.4rem' }}>{dist.note}</div>
        </Section>
      )}

      {/* 3. Confidence */}
      {expanded === 'confidence' && (
        <Section title="Confidence Monitoring" severity={conf.severity}>
          <Stat label="Overall Mean" value={conf.overall?.mean ?? '—'} />
          <Stat label="Overall Median" value={conf.overall?.median ?? '—'} />
          <Stat label="Low Confidence Rate" value={`${conf.low_confidence_rate_pct ?? 0}%`} />
          <Stat label="High Confidence Rate" value={`${conf.high_confidence_rate_pct ?? 0}%`} />
          {['P1', 'P2', 'P3', 'P4'].map((p) => (
            <Stat key={p} label={`${p} Median`} value={conf.by_priority?.[p]?.median ?? '—'}
              sub={`n=${conf.by_priority?.[p]?.count ?? 0}`}
            />
          ))}
          <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', marginTop: '0.4rem' }}>{conf.note}</div>
        </Section>
      )}

      {/* 4. Feedback */}
      {expanded === 'feedback' && (
        <Section title="User Feedback" severity={fb.severity}>
          <Stat label="Total Events" value={fb.total_feedback_events} />
          <Stat label="Unique Pairs" value={fb.unique_user_message_pairs} />
          <Stat label="Duplicates" value={fb.duplicate_retries} />
          <Stat label="Correction Rate" value={`${fb.correction_rate_pct}%`} />
          <Stat label="Total Corrections" value={fb.total_priority_corrections} />
          {fb.correction_matrix && <CorrectionMatrix matrix={fb.correction_matrix} />}
          <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', marginTop: '0.4rem' }}>{fb.note}</div>
        </Section>
      )}

      {/* 5. P2/P3 Boundary */}
      {expanded === 'boundary' && (
        <Section title="P2/P3 Boundary Diagnostic" severity={boundary.severity}>
          <Stat label="P2 → P3 Corrections" value={boundary.p2_to_p3_count} />
          <Stat label="P3 → P2 Corrections" value={boundary.p3_to_p2_count} />
          <Stat label="Boundary Total" value={boundary.boundary_total} />
          <Stat label="% of All Feedback" value={`${boundary.pct_of_all_feedback}%`} />
          <Stat label="% of Corrections" value={`${boundary.pct_of_all_corrections}%`} />
          <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', marginTop: '0.4rem' }}>{boundary.note}</div>
        </Section>
      )}

      {/* 6. Safety */}
      {expanded === 'safety' && (
        <Section title="Safety Monitoring" severity={safety.severity}>
          <Stat label="P1 Count" value={safety.p1_count} />
          <Stat label="P1 Retention" value={`${safety.p1_retention_pct}%`} />
          <Stat label="P1 Downgrades" value={safety.p1_downgrade_count} />
          <Stat label="Safety Escalations" value={safety.safety_escalation_count} />
          <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', marginTop: '0.4rem' }}>{safety.requirement}</div>
        </Section>
      )}

      {/* 7. Action & Deadline */}
      {expanded === 'action' && (
        <Section title="Action & Deadline" severity={ad.severity}>
          <Stat label="Action Required" value={`${ad.action_required?.count ?? 0} (${ad.action_required?.rate_pct ?? 0}%)`} />
          <Stat label="Deadline Detected" value={`${ad.deadline_detected?.count ?? 0} (${ad.deadline_detected?.rate_pct ?? 0}%)`} />
          {ad.deadline_status && Object.entries(ad.deadline_status).map(([k, v]) => (
            <Stat key={k} label={`  ${k}`} value={v} />
          ))}
          <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', marginTop: '0.4rem' }}>{ad.decoupling_note}</div>
        </Section>
      )}

      {/* 8. Needs Attention */}
      {expanded === 'attention' && (
        <Section title="Needs Attention" severity={na.severity}>
          <Stat label="Needs Attention" value={`${na.needs_attention_count} (${na.needs_attention_pct}%)`} />
          <Stat label="P1 Contribution" value={na.breakdown?.p1_contribution} />
          <Stat label="P2 + Action" value={na.breakdown?.p2_action_contribution} />
          <Stat label="Deadline" value={na.breakdown?.deadline_contribution} />
          <Stat label="Active Deadline" value={na.breakdown?.active_deadline_contribution} />
          <Stat label="Overdue" value={na.breakdown?.overdue_contribution} />
          <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', marginTop: '0.4rem' }}>{na.definition_note}</div>
        </Section>
      )}

      {/* 9. Drift */}
      {expanded === 'drift' && (
        <Section title="Domain / Distribution Drift" severity={drift.severity}>
          <Stat label="Total Messages" value={drift.total_messages} />
          {drift.topic_distribution && Object.entries(drift.topic_distribution).slice(0, 10).map(([k, v]) => (
            <Stat key={k} label={k} value={`${v}%`} sub={`n=${drift.topic_counts?.[k] ?? 0}`} />
          ))}
          {drift.subject_length_stats && (
            <>
              <div style={{ borderTop: '1px solid var(--border-subtle)', marginTop: '0.4rem', paddingTop: '0.3rem' }} />
              <Stat label="Subject Length (mean)" value={drift.subject_length_stats.mean} />
              <Stat label="Subject Length (median)" value={drift.subject_length_stats.median} />
            </>
          )}
          <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', marginTop: '0.4rem' }}>{drift.sender_domain_note}</div>
        </Section>
      )}

      {/* 10. Cache & Errors */}
      {expanded === 'cache' && (
        <Section title="Cache & Error Monitoring" severity={ce.severity}>
          <Stat label="Total Cached" value={ce.total_cached_predictions} />
          <Stat label="Stale Entries" value={ce.stale_entries} />
          <Stat label="Cache Key" value={ce.cache_key} />
          <Stat label="Isolation Verified" value={ce.isolation_verified ? '✓ Yes' : '✗ No'} />
          {ce.by_model_version && Object.entries(ce.by_model_version).map(([k, v]) => (
            <Stat key={k} label={`  ${k}`} value={v} />
          ))}
          <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', marginTop: '0.4rem' }}>{ce.v41_v51_contamination_risk}</div>
        </Section>
      )}

      {/* 11. Alerts */}
      {expanded === 'alerts' && (
        <Section title={`Alerts (${alerts.alert_count ?? 0})`}>
          {(alerts.alerts || []).length === 0 ? (
            <div style={{ fontSize: '0.78rem', color: '#34d399', padding: '0.4rem 0' }}>✓ No active alerts.</div>
          ) : (
            (alerts.alerts || []).map((a, i) => (
              <div key={i} style={{ padding: '0.4rem', marginBottom: '0.3rem', background: '#7f1d1d33', borderRadius: '4px', fontSize: '0.75rem' }}>
                <StatusBadge severity={a.severity} />{' '}
                <strong>{a.metric}</strong> — {a.evidence}
              </div>
            ))
          )}
          <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', marginTop: '0.4rem' }}>{alerts.note}</div>
        </Section>
      )}

      {/* 12. v5.2 Readiness */}
      {expanded === 'v52' && (
        <Section title="v5.2 Readiness Report">
          <Stat label="State" value={v52.state} />
          {v52.criteria && Object.entries(v52.criteria).map(([k, v]) => (
            <Stat key={k} label={k.replace(/_/g, ' ')} value={
              v.met !== undefined ? (v.met ? `✓ ${v.current}/${v.target}` : `✗ ${v.current}/${v.target}`)
                : v.present !== undefined ? (v.present ? `⚠ ${v.current}` : `— ${v.current}`)
                : JSON.stringify(v)
            } />
          ))}
          <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', marginTop: '0.4rem' }}>{v52.recommendation}</div>
          {v52.forbidden && (
            <div style={{ fontSize: '0.68rem', color: '#f87171', marginTop: '0.3rem' }}>
              {v52.forbidden.map((f, i) => <div key={i}>⛔ {f}</div>)}
            </div>
          )}
        </Section>
      )}
    </div>
  );
}
