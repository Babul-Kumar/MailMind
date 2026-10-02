import React, { useState, useEffect, useCallback } from 'react';
import {
  MessageSquare, CheckCircle2, XCircle, AlertTriangle, Clock,
  Shield, Activity, Calendar, Database, Loader, RefreshCw,
  ChevronDown, ChevronRight, Info, Layers, Tag
} from 'lucide-react';

/* -------------------------------------------------------------------------
 * FeedbackReviewPanel — Phase 53 Production Feedback Review Dashboard
 * Settings → Feedback Review tab
 *
 * Dedicated Observability Sections:
 *   1. Production v5.1 Evidence (v5.1 specific counts & metrics)
 *   2. Historical vs Production Model Separation (v5.1 vs v4.1 vs older)
 *   3. P2/P3 Boundary Diagnostic Review
 *   4. Safety Feedback Queue (OTP, MFA, security alerts)
 *   5. Deadline Feedback Queue (decoupled tracking)
 *   6. Human Adjudication Queue
 *   7. Dataset-v5.2 Readiness & Candidate Evidence
 *
 * Governance:
 *   - No ML retraining triggered
 *   - Clear distinction between historical and production evidence
 *   - "No feedback does not imply no model errors"
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

function Section({ title, icon: Icon, children, defaultOpen = true, badge = null }) {
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
        <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          {badge && (
            <span style={{
              fontSize: '0.68rem', padding: '0.1rem 0.4rem', borderRadius: 'var(--radius-xs)',
              backgroundColor: 'var(--bg-surface-hover)', color: 'var(--text-muted)', border: '1px solid var(--border-subtle)',
            }}>
              {badge}
            </span>
          )}
          {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </span>
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
  const corr = record.corrected_priority || record.user_priority || (record.feedback_type === 'ACCEPT' ? 'Confirmed' : '—');
  const msgId = record.message_id || record.email_id || '—';
  const status = record.adjudication_status || 'PENDING_REVIEW';
  const topic = record.original_topic || record.topic || '';
  const mVer = record.model_version || 'historical';

  return (
    <div style={{
      display: 'grid', gridTemplateColumns: '1fr 90px 70px 80px 100px 120px',
      alignItems: 'center', gap: '0.5rem',
      padding: '0.4rem 0.5rem', borderBottom: '1px solid var(--border-subtle)',
      fontSize: '0.75rem', color: 'var(--text-secondary)',
    }}>
      <span title={msgId} style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: 'var(--text-muted)', fontFamily: 'monospace', fontSize: '0.68rem' }}>
        {msgId.length > 26 ? `${msgId.slice(0, 26)}…` : msgId}
      </span>
      <span style={{ fontSize: '0.68rem', color: mVer === 'priority-v5.1' ? 'var(--accent)' : 'var(--text-muted)' }}>
        {mVer}
      </span>
      <PriorityBadge priority={orig} />
      {corr === 'Confirmed' ? (
        <span style={{ color: '#10b981', fontWeight: 600, fontSize: '0.7rem' }}>✓ Accept</span>
      ) : (
        <PriorityBadge priority={corr} />
      )}
      <span style={{ color: 'var(--text-muted)', fontSize: '0.68rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{topic}</span>
      <StatusBadge status={status} />
    </div>
  );
}

function TableHeader() {
  return (
    <div style={{
      display: 'grid', gridTemplateColumns: '1fr 90px 70px 80px 100px 120px',
      gap: '0.5rem', padding: '0.3rem 0.5rem',
      fontSize: '0.68rem', fontWeight: 700, color: 'var(--text-muted)',
      borderBottom: '1px solid var(--border-subtle)',
    }}>
      <span>Message ID</span>
      <span>Model</span>
      <span>Original</span>
      <span>Correction</span>
      <span>Topic</span>
      <span>Status</span>
    </div>
  );
}

function EmptyState({ message = 'No records found.' }) {
  return (
    <div style={{ padding: '1.25rem', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.78rem' }}>
      <Info size={16} style={{ marginBottom: '0.3rem', color: 'var(--text-muted)' }} />
      <div>{message}</div>
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
        ⚠ Human adjudication is mandatory. No automated model retraining or promotion.
      </div>
    </div>
  );
}

export function FeedbackReviewPanel() {
  const [v51Metrics, setV51Metrics] = useState(null);
  const [modelSeparation, setModelSeparation] = useState(null);
  const [qualityMetrics, setQualityMetrics] = useState(null);
  const [boundaryAnalysis, setBoundaryAnalysis] = useState(null);
  const [safetyAnalysis, setSafetyAnalysis] = useState(null);
  const [deadlineAnalysis, setDeadlineAnalysis] = useState(null);
  const [cases, setCases] = useState(null);
  const [accepted, setAccepted] = useState(null);
  const [v52, setV52] = useState(null);
  const [recentQueue, setRecentQueue] = useState([]);
  const [filterModel, setFilterModel] = useState('all'); // 'all' | 'v5.1' | 'historical'
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [lastRefresh, setLastRefresh] = useState(null);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [
        v51Res,
        sepRes,
        qualRes,
        boundRes,
        safeRes,
        dlRes,
        casesRes,
        accRes,
        v52Res,
        queueRes,
      ] = await Promise.all([
        fetch('/api/adjudication/v51-metrics').then(r => r.json()).catch(() => null),
        fetch('/api/adjudication/model-separation').then(r => r.json()).catch(() => null),
        fetch('/api/adjudication/quality-metrics').then(r => r.json()).catch(() => null),
        fetch('/api/adjudication/p2-p3-boundary').then(r => r.json()).catch(() => null),
        fetch('/api/adjudication/safety-feedback').then(r => r.json()).catch(() => null),
        fetch('/api/adjudication/deadline-feedback').then(r => r.json()).catch(() => null),
        fetch('/api/adjudication/cases').then(r => r.json()).catch(() => null),
        fetch('/api/adjudication/accepted').then(r => r.json()).catch(() => null),
        fetch('/api/adjudication/v52-candidate').then(r => r.json()).catch(() => null),
        fetch('/api/adjudication/queue').then(r => r.json()).catch(() => null),
      ]);

      if (v51Res?.status === 'success') setV51Metrics(v51Res.v51_metrics);
      if (sepRes?.status === 'success') setModelSeparation(sepRes.model_separation);
      if (qualRes?.status === 'success') setQualityMetrics(qualRes.quality_metrics);
      if (boundRes?.status === 'success') setBoundaryAnalysis(boundRes.boundary_analysis);
      if (safeRes?.status === 'success') setSafetyAnalysis(safeRes.safety_analysis);
      if (dlRes?.status === 'success') setDeadlineAnalysis(dlRes.deadline_analysis);
      if (casesRes?.status === 'success') setCases(casesRes.cases);
      if (accRes?.status === 'success') setAccepted(accRes.accepted || []);
      if (v52Res?.status === 'success') setV52(v52Res.v52_candidate);
      if (queueRes?.status === 'success') setRecentQueue(queueRes.queue || []);

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

  // Filter recent queue by model
  const filteredQueue = recentQueue.filter(r => {
    if (filterModel === 'v5.1') return r.model_version === 'priority-v5.1';
    if (filterModel === 'historical') return r.model_version !== 'priority-v5.1';
    return true;
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem', fontSize: '0.82rem' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <div style={{ fontWeight: 700, color: 'var(--text-primary)' }}>Production Feedback Review Dashboard</div>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
            Phase 53 Production Evidence Pipeline · Human Adjudication Required Before Dataset Inclusion
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
          {loading ? 'Refreshing…' : 'Refresh'}
        </button>
      </div>

      {lastRefresh && (
        <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>
          Last refreshed: {lastRefresh}
        </div>
      )}

      {error && (
        <div style={{ padding: '0.5rem 0.75rem', borderRadius: 'var(--radius-sm)', backgroundColor: '#ef444422', color: '#ef4444', fontSize: '0.75rem' }}>
          ⚠ Error loading dashboard data: {error}
        </div>
      )}

      {/* Governance & Core Rule */}
      <div style={{
        padding: '0.55rem 0.85rem', borderRadius: 'var(--radius-sm)',
        backgroundColor: 'var(--bg-card)', border: '1px solid var(--border-subtle)',
        fontSize: '0.72rem', color: 'var(--text-muted)', display: 'flex', flexDirection: 'column', gap: '0.2rem'
      }}>
        <div>
          <strong style={{ color: 'var(--text-primary)' }}>Phase 53 Governance:</strong>
          {' '}priority-v5.1 ACTIVE PRODUCTION · priority-v4.1 ROLLBACK BASELINE · No automatic retraining · No model promotion
        </div>
        <div style={{ color: 'var(--text-secondary)', fontStyle: 'italic' }}>
          "No feedback does not imply no model errors. Feedback is evidence for human adjudication."
        </div>
      </div>

      {/* SECTION 1 — Production v5.1 Evidence */}
      <Section title="1. Production v5.1 Evidence" icon={Activity} defaultOpen={true} badge="Active Model">
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
          <StatCard
            label="v5.1 Raw Events"
            value={v51Metrics?.raw_feedback_events ?? 0}
            icon={MessageSquare}
            colour="var(--accent)"
            sub="Events on priority-v5.1"
          />
          <StatCard
            label="v5.1 Unique Cases"
            value={v51Metrics?.unique_feedback_cases ?? 0}
            icon={Activity}
            colour="#10b981"
            sub="Deduped by (user, message)"
          />
          <StatCard
            label="Unique Corrections"
            value={v51Metrics?.unique_corrections ?? 0}
            icon={AlertTriangle}
            colour="#f59e0b"
            sub={`Rate: ${v51Metrics?.correction_rate_pct ?? 0}%`}
          />
          <StatCard
            label="Acceptances"
            value={v51Metrics?.accept_count ?? 0}
            icon={CheckCircle2}
            colour="#10b981"
            sub="Confirmed correct"
          />
          <StatCard
            label="Not Sure"
            value={v51Metrics?.not_sure_count ?? 0}
            icon={Info}
            colour="#8b5cf6"
            sub="Ambiguous cases"
          />
        </div>

        <div style={{ marginTop: '0.65rem', padding: '0.5rem 0.75rem', backgroundColor: 'var(--bg-card)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)', fontSize: '0.72rem' }}>
          <strong>Production Status:</strong>{' '}
          <span style={{ color: (v51Metrics?.unique_feedback_cases || 0) === 0 ? 'var(--text-muted)' : 'var(--text-primary)' }}>
            {v51Metrics?.status_statement || '0 genuine v5.1 feedback cases observed.'}
          </span>
        </div>
      </Section>

      {/* SECTION 2 — Historical vs Production Separation */}
      <Section title="2. Historical vs Production Breakdown" icon={Layers} defaultOpen={false}>
        <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: '0.6rem' }}>
          Historical feedback (priority-v1 / priority-v4.1) is strictly isolated and never mixed into v5.1 production metrics.
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.6rem' }}>
          <div style={{ padding: '0.65rem', backgroundColor: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-sm)' }}>
            <div style={{ fontWeight: 700, color: 'var(--accent)', marginBottom: '0.3rem' }}>Production: priority-v5.1</div>
            <div style={{ fontSize: '0.74rem' }}>Raw Events: <strong>{modelSeparation?.v51_feedback?.raw_count ?? 0}</strong></div>
            <div style={{ fontSize: '0.74rem' }}>Unique Cases: <strong>{modelSeparation?.v51_feedback?.unique_cases ?? 0}</strong></div>
            <div style={{ fontSize: '0.74rem' }}>Corrections: <strong>{modelSeparation?.v51_feedback?.corrections ?? 0}</strong></div>
          </div>
          <div style={{ padding: '0.65rem', backgroundColor: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-sm)' }}>
            <div style={{ fontWeight: 700, color: '#f59e0b', marginBottom: '0.3rem' }}>Rollback: priority-v4.1</div>
            <div style={{ fontSize: '0.74rem' }}>Raw Events: <strong>{modelSeparation?.v41_feedback?.raw_count ?? 0}</strong></div>
            <div style={{ fontSize: '0.74rem' }}>Unique Cases: <strong>{modelSeparation?.v41_feedback?.unique_cases ?? 0}</strong></div>
            <div style={{ fontSize: '0.74rem' }}>Corrections: <strong>{modelSeparation?.v41_feedback?.corrections ?? 0}</strong></div>
          </div>
          <div style={{ padding: '0.65rem', backgroundColor: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-sm)' }}>
            <div style={{ fontWeight: 700, color: '#6b7280', marginBottom: '0.3rem' }}>Historical (v1 / Legacy)</div>
            <div style={{ fontSize: '0.74rem' }}>Raw Events: <strong>{modelSeparation?.older_feedback?.raw_count ?? 0}</strong></div>
            <div style={{ fontSize: '0.74rem' }}>Unique Cases: <strong>{modelSeparation?.older_feedback?.unique_cases ?? 0}</strong></div>
            <div style={{ fontSize: '0.74rem' }}>Corrections: <strong>{modelSeparation?.older_feedback?.corrections ?? 0}</strong></div>
          </div>
        </div>
      </Section>

      {/* SECTION 3 — Recent Feedback Queue */}
      <Section title={`3. Recent Feedback Submissions (${filteredQueue.length})`} icon={Clock} defaultOpen={false}>
        {/* Model Filter Pills */}
        <div style={{ display: 'flex', gap: '0.4rem', marginBottom: '0.6rem' }}>
          {['all', 'v5.1', 'historical'].map(f => (
            <button
              key={f}
              onClick={() => setFilterModel(f)}
              style={{
                padding: '0.2rem 0.55rem', borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border-subtle)',
                backgroundColor: filterModel === f ? 'var(--accent)' : 'var(--bg-card)',
                color: filterModel === f ? '#fff' : 'var(--text-muted)',
                fontSize: '0.7rem', fontWeight: 600, cursor: 'pointer',
              }}
            >
              {f === 'all' ? 'All Feedback' : f === 'v5.1' ? 'priority-v5.1 Only' : 'Historical Only'}
            </button>
          ))}
        </div>

        {filteredQueue.length === 0 ? (
          <EmptyState message={`No feedback submissions found for filter '${filterModel}'.`} />
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <TableHeader />
            {filteredQueue.slice(0, 15).map((r, i) => (
              <FeedbackRow key={r.feedback_id || i} record={r} />
            ))}
          </div>
        )}
      </Section>

      {/* SECTION 4 — P2/P3 Boundary Diagnostic Review */}
      <Section title={`4. P2/P3 Boundary Diagnostics (${boundaryAnalysis?.pending_boundary_cases ?? 0} Pending)`} icon={Activity} defaultOpen={false}>
        <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
          Diagnostic monitoring of P2↔P3 transitions. Topics and domains are diagnostic categories only, not classification rules.
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '0.6rem' }}>
          <StatCard label="P2 → P3 Corrections" value={boundaryAnalysis?.p2_to_p3_pending ?? 0} colour="#3b82f6" />
          <StatCard label="P3 → P2 Corrections" value={boundaryAnalysis?.p3_to_p2_pending ?? 0} colour="#f97316" />
          <StatCard label="Adjudicated Boundary" value={boundaryAnalysis?.adjudicated_boundary_cases ?? 0} colour="#10b981" />
          <StatCard label="Accepted Boundary" value={boundaryAnalysis?.accepted_boundary_corrections ?? 0} colour="#10b981" />
        </div>
        {boundaryAnalysis?.breakdown_by_topic && Object.keys(boundaryAnalysis.breakdown_by_topic).length > 0 && (
          <div style={{ padding: '0.5rem', backgroundColor: 'var(--bg-card)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)', fontSize: '0.72rem' }}>
            <strong>Breakdown by Topic:</strong>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', marginTop: '0.3rem' }}>
              {Object.entries(boundaryAnalysis.breakdown_by_topic).map(([topic, cnt]) => (
                <span key={topic} style={{ padding: '0.15rem 0.45rem', backgroundColor: 'var(--bg-surface-hover)', borderRadius: 'var(--radius-xs)', border: '1px solid var(--border-subtle)' }}>
                  {topic}: <strong>{cnt}</strong>
                </span>
              ))}
            </div>
          </div>
        )}
      </Section>

      {/* SECTION 5 — Safety Feedback Queue */}
      <Section title={`5. Safety Feedback Queue (${safetyAnalysis?.total_safety_feedback ?? 0})`} icon={Shield} defaultOpen={true}>
        <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
          OTP, MFA, password reset, security alerts, account compromise, infrastructure incidents.
          Invariant: 0 critical P1 downgrades. Any report indicating critical email classified below P1 appears here immediately.
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '0.5rem' }}>
          <StatCard
            label="Critical P1 Escalations"
            value={safetyAnalysis?.critical_p1_escalations ?? 0}
            icon={Shield}
            colour={safetyAnalysis?.critical_p1_escalations > 0 ? '#ef4444' : '#10b981'}
            sub="Classified below P1"
          />
          <StatCard
            label="P1 Downgrades"
            value={safetyAnalysis?.p1_downgrades ?? 0}
            icon={AlertTriangle}
            colour={safetyAnalysis?.p1_downgrades > 0 ? '#f59e0b' : '#10b981'}
            sub="P1 → P2/P3/P4"
          />
        </div>
        {safetyAnalysis?.safety_queue?.length === 0 ? (
          <EmptyState message="No pending safety cases. Zero critical safety incidents detected. ✅" />
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <TableHeader />
            {safetyAnalysis?.safety_queue?.map((r, i) => (
              <FeedbackRow key={r.feedback_id || i} record={r} />
            ))}
          </div>
        )}
      </Section>

      {/* SECTION 6 — Deadline Feedback Queue */}
      <Section title={`6. Deadline Feedback Queue (${deadlineAnalysis?.total_deadline_feedback ?? 0})`} icon={Calendar} defaultOpen={false}>
        <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
          Missed deadline, false deadline, wrong deadline date, historical deadline, deadline not detected.
          Deadlines are evaluated independently from priority.
        </div>
        {deadlineAnalysis?.deadline_queue?.length === 0 ? (
          <EmptyState message="No pending deadline review cases." />
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <TableHeader />
            {deadlineAnalysis?.deadline_queue?.map((r, i) => (
              <FeedbackRow key={r.feedback_id || i} record={r} />
            ))}
          </div>
        )}
      </Section>

      {/* SECTION 7 — Dataset-v5.2 Readiness */}
      <Section title="7. Dataset-v5.2 Evidence & Readiness" icon={Database} defaultOpen={true}>
        {v52 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            <ReadinessIndicator readiness={v52.readiness} />
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginTop: '0.25rem' }}>
              <StatCard
                label="Accepted Candidates" value={v52.accepted_candidates ?? 0}
                icon={CheckCircle2} colour="#10b981"
                sub="Eligible for dataset-v5.2"
              />
              <StatCard
                label="Leakage Check" value={v52.leakage_audit?.leakage_free ? '0 Leaks' : 'Leaked'}
                icon={Shield} colour={v52.leakage_audit?.leakage_free ? '#10b981' : '#ef4444'}
                sub="Frozen holdouts checked"
              />
            </div>
          </div>
        ) : (
          <EmptyState message="v5.2 candidate report loading..." />
        )}
      </Section>
    </div>
  );
}
