import React, { useState, useEffect, useCallback } from 'react';
import {
  MessageSquare, CheckCircle2, XCircle, AlertTriangle, Clock,
  Shield, Activity, Calendar, Database, Loader, RefreshCw,
  ChevronDown, ChevronRight, Info
} from 'lucide-react';

/* -------------------------------------------------------------------------
 * FeedbackReviewPanel — Phase 52
 * Settings → Feedback Review tab
 *
 * Shows:
 *   1. Overview (raw events, unique cases, adjudication breakdown)
 *   2. Priority correction matrix
 *   3. P2/P3 boundary review queue
 *   4. Safety review queue
 *   5. Deadline review queue
 *   6. Accepted training candidates (count + list)
 *   7. Dataset-v5.2 readiness
 *
 * Design invariants:
 *   - No raw email body shown
 *   - No model training triggered
 *   - No cross-user data exposed
 *   - Adjudication status shown clearly
 * -------------------------------------------------------------------------*/

const STATUS_COLOUR = {
  PENDING_REVIEW: '#f59e0b',
  ACCEPTED: '#10b981',
  REJECTED: '#ef4444',
  NEEDS_CONTEXT: '#8b5cf6',
  DUPLICATE: '#6b7280',
};

const PRIORITY_COLOUR = {
  P1: '#ef4444',
  P2: '#f97316',
  P3: '#3b82f6',
  P4: '#6b7280',
};

const PRIORITY_LABEL = {
  P1: 'Critical',
  P2: 'Action Required',
  P3: 'Informational',
  P4: 'Low / Routine',
};

function PriorityBadge({ priority }) {
  if (!priority) return null;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: '0.25rem',
      padding: '0.15rem 0.5rem', borderRadius: 'var(--radius-sm)',
      fontSize: '0.72rem', fontWeight: 700,
      backgroundColor: `${PRIORITY_COLOUR[priority] || '#6b7280'}22`,
      color: PRIORITY_COLOUR[priority] || '#6b7280',
      border: `1px solid ${PRIORITY_COLOUR[priority] || '#6b7280'}44`,
    }}>
      {priority}
    </span>
  );
}

function StatusBadge({ status }) {
  if (!status) return null;
  const colour = STATUS_COLOUR[status] || '#6b7280';
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center',
      padding: '0.15rem 0.5rem', borderRadius: 'var(--radius-sm)',
      fontSize: '0.72rem', fontWeight: 600,
      backgroundColor: `${colour}22`, color: colour,
      border: `1px solid ${colour}44`,
    }}>
      {status.replace('_', ' ')}
    </span>
  );
}

function StatCard({ label, value, icon: Icon, colour = 'var(--accent)', sub }) {
  return (
    <div style={{
      padding: '0.75rem 1rem', borderRadius: 'var(--radius-sm)',
      border: '1px solid var(--border-subtle)',
      backgroundColor: 'var(--bg-card)',
      display: 'flex', alignItems: 'center', gap: '0.75rem', flex: '1 1 130px',
    }}>
      {Icon && <Icon size={18} color={colour} />}
      <div>
        <div style={{ fontSize: '1.35rem', fontWeight: 800, color: 'var(--text-primary)', lineHeight: 1 }}>
          {value ?? '—'}
        </div>
        <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>{label}</div>
        {sub && <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', marginTop: '0.1rem' }}>{sub}</div>}
      </div>
    </div>
  );
}

function Section({ title, icon: Icon, children, defaultOpen = true }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div style={{ border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-sm)', overflow: 'hidden' }}>
      <button
        onClick={() => setOpen(!open)}
        style={{
          width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '0.65rem 0.9rem', backgroundColor: 'var(--bg-card)',
          border: 'none', cursor: 'pointer', color: 'var(--text-primary)', fontWeight: 600,
          fontSize: '0.82rem',
        }}
      >
        <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          {Icon && <Icon size={14} color="var(--accent)" />}
          {title}
        </span>
        {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
      </button>
      {open && (
        <div style={{ padding: '0.75rem 0.9rem', backgroundColor: 'var(--bg-base)', borderTop: '1px solid var(--border-subtle)' }}>
          {children}
        </div>
      )}
    </div>
  );
}

function FeedbackRow({ record }) {
  const orig = record.predicted_priority || record.original_priority || '—';
  const corr = record.corrected_priority || record.user_priority || '—';
  const msgId = record.message_id || record.email_id || '—';
  const ts = record.created_at || record.feedback_timestamp || '—';
  const status = record.adjudication_status || 'PENDING_REVIEW';
  const topic = record.original_topic || record.topic || '';

  return (
    <div style={{
      display: 'grid', gridTemplateColumns: '1fr 80px 80px 120px 140px',
      alignItems: 'center', gap: '0.5rem',
      padding: '0.4rem 0.5rem', borderBottom: '1px solid var(--border-subtle)',
      fontSize: '0.75rem', color: 'var(--text-secondary)',
    }}>
      <span title={msgId} style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: 'var(--text-muted)', fontFamily: 'monospace', fontSize: '0.68rem' }}>
        {msgId.length > 28 ? `${msgId.slice(0, 28)}…` : msgId}
      </span>
      <PriorityBadge priority={orig} />
      <PriorityBadge priority={corr} />
      <span style={{ color: 'var(--text-muted)', fontSize: '0.68rem' }}>{topic}</span>
      <StatusBadge status={status} />
    </div>
  );
}

function TableHeader() {
  return (
    <div style={{
      display: 'grid', gridTemplateColumns: '1fr 80px 80px 120px 140px',
      gap: '0.5rem', padding: '0.3rem 0.5rem',
      fontSize: '0.68rem', fontWeight: 700, color: 'var(--text-muted)',
      borderBottom: '1px solid var(--border-subtle)',
    }}>
      <span>Message ID</span>
      <span>Original</span>
      <span>Corrected</span>
      <span>Topic</span>
      <span>Status</span>
    </div>
  );
}

function EmptyState({ message = 'No records found.' }) {
  return (
    <div style={{ padding: '1.5rem', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.8rem' }}>
      <Info size={18} style={{ marginBottom: '0.4rem', color: 'var(--text-muted)' }} />
      <div>{message}</div>
    </div>
  );
}

function CorrectionMatrix({ matrix }) {
  const priorities = ['P1', 'P2', 'P3', 'P4'];
  if (!matrix) return <EmptyState message="No correction matrix data." />;
  const hasData = priorities.some(r => priorities.some(c => (matrix[r]?.[c] || 0) > 0));
  if (!hasData) return <EmptyState message="No priority corrections adjudicated yet." />;
  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.75rem' }}>
        <thead>
          <tr>
            <th style={{ padding: '0.4rem', color: 'var(--text-muted)', textAlign: 'left', fontSize: '0.7rem' }}>
              Original↓ / Corrected→
            </th>
            {priorities.map(p => (
              <th key={p} style={{ padding: '0.4rem', textAlign: 'center' }}>
                <PriorityBadge priority={p} />
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {priorities.map(r => (
            <tr key={r}>
              <td style={{ padding: '0.4rem' }}><PriorityBadge priority={r} /></td>
              {priorities.map(c => {
                const count = matrix[r]?.[c] || 0;
                const isDiag = r === c;
                return (
                  <td key={c} style={{
                    padding: '0.4rem', textAlign: 'center', fontWeight: count > 0 ? 700 : 400,
                    color: count > 0 ? (isDiag ? '#6b7280' : PRIORITY_COLOUR[c]) : 'var(--text-muted)',
                    backgroundColor: count > 0 && !isDiag ? `${PRIORITY_COLOUR[c]}11` : 'transparent',
                    borderRadius: 'var(--radius-sm)',
                  }}>
                    {count || '—'}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ReadinessIndicator({ readiness }) {
  if (!readiness) return null;
  const { state, reason, accepted_candidates, minimum_threshold } = readiness;

  const stateColour = {
    'READY FOR OFFLINE TRAINING REVIEW': '#10b981',
    'EVIDENCE COLLECTING': '#f59e0b',
    'NOT READY': '#ef4444',
  }[state] || '#6b7280';

  return (
    <div style={{
      padding: '0.75rem 1rem', borderRadius: 'var(--radius-sm)',
      border: `1px solid ${stateColour}44`,
      backgroundColor: `${stateColour}11`,
    }}>
      <div style={{ fontWeight: 700, fontSize: '0.85rem', color: stateColour, marginBottom: '0.3rem' }}>
        {state}
      </div>
      <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
        {reason}
      </div>
      <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
        <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
          Accepted: <strong>{accepted_candidates ?? 0}</strong>
        </span>
        <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
          Threshold: <strong>{minimum_threshold ?? 50}</strong>
        </span>
      </div>
      <div style={{ marginTop: '0.5rem', fontSize: '0.68rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>
        ⚠ Training may only begin after explicit offline human review. No automatic training.
      </div>
    </div>
  );
}


export function FeedbackReviewPanel() {
  const [dedupStats, setDedupStats] = useState(null);
  const [cases, setCases] = useState(null);
  const [p2p3Queue, setP2p3Queue] = useState(null);
  const [safetyQueue, setSafetyQueue] = useState(null);
  const [deadlineQueue, setDeadlineQueue] = useState(null);
  const [accepted, setAccepted] = useState(null);
  const [v52, setV52] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [lastRefresh, setLastRefresh] = useState(null);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [
        dedupRes,
        casesRes,
        p2p3Res,
        safetyRes,
        deadlineRes,
        acceptedRes,
        v52Res,
      ] = await Promise.all([
        fetch('/api/adjudication/dedup-stats').then(r => r.json()).catch(() => null),
        fetch('/api/adjudication/cases').then(r => r.json()).catch(() => null),
        fetch('/api/adjudication/p2-p3-review').then(r => r.json()).catch(() => null),
        fetch('/api/adjudication/safety-queue').then(r => r.json()).catch(() => null),
        fetch('/api/adjudication/deadline-queue').then(r => r.json()).catch(() => null),
        fetch('/api/adjudication/accepted').then(r => r.json()).catch(() => null),
        fetch('/api/adjudication/v52-candidate').then(r => r.json()).catch(() => null),
      ]);

      if (dedupRes?.status === 'success') setDedupStats(dedupRes.dedup_stats);
      if (casesRes?.status === 'success') setCases(casesRes.cases);
      if (p2p3Res?.status === 'success') setP2p3Queue(p2p3Res.queue || []);
      if (safetyRes?.status === 'success') setSafetyQueue(safetyRes.queue || []);
      if (deadlineRes?.status === 'success') setDeadlineQueue(deadlineRes.queue || []);
      if (acceptedRes?.status === 'success') setAccepted(acceptedRes.accepted || []);
      if (v52Res?.status === 'success') setV52(v52Res.v52_candidate);
      setLastRefresh(new Date().toLocaleTimeString());
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.8rem', fontSize: '0.82rem' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <div style={{ fontWeight: 700, color: 'var(--text-primary)' }}>Feedback Review Dashboard</div>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
            Production feedback evidence pipeline — human adjudication required before training
          </div>
        </div>
        <button
          onClick={fetchAll}
          disabled={loading}
          style={{
            display: 'flex', alignItems: 'center', gap: '0.3rem',
            padding: '0.4rem 0.75rem', borderRadius: 'var(--radius-sm)',
            border: '1px solid var(--border-subtle)', backgroundColor: 'var(--bg-card)',
            color: 'var(--text-secondary)', cursor: loading ? 'not-allowed' : 'pointer',
            fontSize: '0.75rem', fontWeight: 600,
          }}
        >
          {loading ? <Loader size={13} className="spin" /> : <RefreshCw size={13} />}
          {loading ? 'Loading…' : 'Refresh'}
        </button>
      </div>

      {lastRefresh && (
        <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>
          Last updated: {lastRefresh}
        </div>
      )}

      {error && (
        <div style={{ padding: '0.5rem 0.75rem', borderRadius: 'var(--radius-sm)', backgroundColor: '#ef444422', color: '#ef4444', fontSize: '0.75rem' }}>
          ⚠ Error loading data: {error}
        </div>
      )}

      {/* Governance banner */}
      <div style={{
        padding: '0.5rem 0.75rem', borderRadius: 'var(--radius-sm)',
        backgroundColor: 'var(--bg-card)', border: '1px solid var(--border-subtle)',
        fontSize: '0.72rem', color: 'var(--text-muted)',
      }}>
        <strong style={{ color: 'var(--text-primary)' }}>Phase 52 Governance</strong>
        {' · '}priority-v5.1 is ACTIVE PRODUCTION
        {' · '}No automated training
        {' · '}No model promotion
        {' · '}Feedback = evidence only (not automatic ground truth)
      </div>

      {/* Section 1 — Overview */}
      <Section title="Feedback Overview" icon={MessageSquare}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
          <StatCard
            label="Raw Feedback Events" value={dedupStats?.raw_feedback_events ?? '—'}
            icon={MessageSquare} colour="#6b7280"
            sub="Total rows in feedback.jsonl"
          />
          <StatCard
            label="Unique Cases" value={dedupStats?.unique_feedback_cases ?? '—'}
            icon={Activity} colour="var(--accent)"
            sub="Deduped by (user, message)"
          />
          <StatCard
            label="Pending Review" value={cases?.pending_adjudication ?? '—'}
            icon={Clock} colour="#f59e0b"
          />
          <StatCard
            label="Accepted" value={cases?.accepted ?? '—'}
            icon={CheckCircle2} colour="#10b981"
          />
          <StatCard
            label="Rejected" value={cases?.rejected ?? '—'}
            icon={XCircle} colour="#ef4444"
          />
          <StatCard
            label="Needs Context" value={cases?.needs_context ?? '—'}
            icon={AlertTriangle} colour="#8b5cf6"
          />
        </div>
        {dedupStats && (
          <div style={{ marginTop: '0.5rem', fontSize: '0.72rem', color: 'var(--text-muted)' }}>
            {dedupStats.duplicate_submissions > 0 && (
              <span>
                ⓘ {dedupStats.duplicate_submissions} duplicate submission{dedupStats.duplicate_submissions !== 1 ? 's' : ''} collapsed
                (same user+message submitted {Math.round((dedupStats.raw_feedback_events || 1) / Math.max(dedupStats.unique_feedback_cases || 1, 1))}× on average)
              </span>
            )}
          </div>
        )}
      </Section>

      {/* Section 2 — Priority correction matrix */}
      <Section title="Priority Corrections (Accepted)" icon={Activity} defaultOpen={false}>
        <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
          Rows: original model priority. Columns: human-confirmed correct priority.
        </div>
        <CorrectionMatrix matrix={cases?.correction_matrix} />
      </Section>

      {/* Section 3 — P2/P3 Boundary */}
      <Section title={`P2/P3 Boundary Review (${p2p3Queue?.length ?? '…'})`} icon={Activity} defaultOpen={false}>
        <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
          Feedback cases involving P2↔P3 transitions. Requires careful review — not all corrections indicate model error.
        </div>
        {p2p3Queue?.length === 0 ? (
          <EmptyState message="No pending P2/P3 boundary cases." />
        ) : (
          <>
            <TableHeader />
            {p2p3Queue?.map((r, i) => <FeedbackRow key={r.feedback_id || i} record={r} />)}
          </>
        )}
      </Section>

      {/* Section 4 — Safety queue */}
      <Section title={`Safety Cases (${safetyQueue?.length ?? '…'})`} icon={Shield} defaultOpen>
        <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
          OTP, MFA, password reset, security alerts, account compromise, authentication failures.
          Invariant: 0 critical P1 downgrades permitted.
        </div>
        {safetyQueue?.length === 0 ? (
          <EmptyState message="No pending safety cases. ✅" />
        ) : (
          <>
            <TableHeader />
            {safetyQueue?.map((r, i) => <FeedbackRow key={r.feedback_id || i} record={r} />)}
          </>
        )}
      </Section>

      {/* Section 5 — Deadline queue */}
      <Section title={`Deadline Cases (${deadlineQueue?.length ?? '…'})`} icon={Calendar} defaultOpen={false}>
        <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
          Feedback involving deadline detection or correction.
        </div>
        {deadlineQueue?.length === 0 ? (
          <EmptyState message="No pending deadline review cases." />
        ) : (
          <>
            <TableHeader />
            {deadlineQueue?.map((r, i) => <FeedbackRow key={r.feedback_id || i} record={r} />)}
          </>
        )}
      </Section>

      {/* Section 6 — Accepted training candidates */}
      <Section title={`Accepted Training Candidates (${accepted?.length ?? '…'})`} icon={Database} defaultOpen={false}>
        <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
          Only ACCEPTED adjudicated records may enter dataset-v5.2. No raw email content is stored.
        </div>
        {accepted?.length === 0 ? (
          <EmptyState message="No accepted training candidates yet. Evidence collecting — insufficient adjudicated production feedback." />
        ) : (
          <>
            <TableHeader />
            {accepted?.map((r, i) => <FeedbackRow key={r.adjudication_id || i} record={r} />)}
          </>
        )}
      </Section>

      {/* Section 7 — Dataset-v5.2 readiness */}
      <Section title="Dataset-v5.2 Readiness" icon={Database} defaultOpen>
        {v52 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            <ReadinessIndicator readiness={v52.readiness} />
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginTop: '0.25rem' }}>
              <StatCard
                label="Candidates (pre-filter)" value={v52.pool_size_before_leakage_filter ?? 0}
                icon={Database} colour="var(--accent)"
              />
              <StatCard
                label="Leaked (removed)" value={v52.leaked_examples ?? 0}
                icon={AlertTriangle} colour={v52.leaked_examples > 0 ? '#ef4444' : '#10b981'}
              />
              <StatCard
                label="Clean Candidates" value={v52.accepted_candidates ?? 0}
                icon={CheckCircle2} colour="#10b981"
              />
            </div>
            {v52.leakage_audit && (
              <div style={{
                padding: '0.4rem 0.6rem', borderRadius: 'var(--radius-sm)',
                backgroundColor: v52.leakage_audit.leakage_free ? '#10b98111' : '#ef444411',
                border: `1px solid ${v52.leakage_audit.leakage_free ? '#10b98144' : '#ef444444'}`,
                fontSize: '0.72rem',
                color: v52.leakage_audit.leakage_free ? '#10b981' : '#ef4444',
              }}>
                Leakage audit: {v52.leakage_audit.leakage_free ? '✅ Leakage-free' : `❌ ${v52.leakage_audit.leakage_count} leaked examples detected`}
              </div>
            )}
          </div>
        ) : (
          loading ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--text-muted)', fontSize: '0.75rem' }}>
              <Loader size={13} className="spin" /> Building candidate report…
            </div>
          ) : (
            <EmptyState message="Candidate report unavailable." />
          )
        )}
      </Section>
    </div>
  );
}
