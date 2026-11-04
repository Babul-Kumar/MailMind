import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import {
  Search,
  Check,
  Clock,
  Sun,
  Moon,
  ChevronDown,
  Paperclip,
  RefreshCw,
  Copy,
  RotateCcw,
  ArrowLeft,
  LogOut
} from 'lucide-react';
import { useAuth } from './hooks/useAuth';
import { useEmails } from './hooks/useEmails';
import { AuthCallback } from './components/auth/AuthCallback';
import { cleanSenderName, formatEmailDate } from './utils/formatting';
import { submitFeedback } from './services/api';

// ============================================================================
// PRIORITY DEFINITIONS (NATURAL COLORS, SHORT LABELS)
// ============================================================================

const PRIORITIES = {
  P1: { id: 'P1', name: 'Urgent', color: '#E11D48' },
  P2: { id: 'P2', name: 'Important', color: '#D97706' },
  P3: { id: 'P3', name: 'Routine', color: '#2563EB' },
  P4: { id: 'P4', name: 'Low', color: '#A1A1AA' }
};

const WINDOWS = [
  { id: 'this_month', label: 'This month', days: 30 },
  { id: 'last_3_months', label: 'Last 3 months', days: 90 },
  { id: 'last_year', label: 'Last year', days: 365 },
  { id: 'all_time', label: 'All time', days: 9999 }
];

// ============================================================================
// CONCISE, NATURAL EMAIL DATASET (FALLBACK / DEMO / SAMPLE)
// ============================================================================

const INITIAL_EMAILS = [
  {
    id: 'e1',
    sender: 'AWS CloudWatch',
    email: 'no-reply@amazonaws.com',
    initials: 'AW',
    avatarBg: 'bg-stone-200/80 text-stone-700 dark-avatar-stone',
    subject: 'Elevated 5xx latency on production API',
    time: '10:42 AM',
    fullDate: 'Nov 5, 10:42 AM',
    daysAgo: 0,
    unread: true,
    analyzed: true,
    priority: 'P1',
    needsAttention: true,
    matched: '5xx, production, immediate',
    note: 'Security alert stays pinned',
    otp: null,
    attachment: null,
    paragraphs: [
      'CloudWatch detected an elevated 5xx error rate (4.8%) on your primary API service in ap-south-1 over the last 10 minutes.',
      'Database connection pool saturation reached 92% during peak sync traffic. Scaling the read replica or recycling idle workers will restore normal latency.',
      'This alert remains active in your queue until marked done.'
    ]
  },
  {
    id: 'e2',
    sender: 'GitHub',
    email: 'noreply@github.com',
    initials: 'GH',
    avatarBg: 'bg-zinc-200/80 text-zinc-700',
    subject: '849201 is your device verification code',
    time: '10:38 AM',
    fullDate: 'Nov 5, 10:38 AM',
    daysAgo: 0,
    unread: true,
    analyzed: true,
    priority: 'P1',
    needsAttention: true,
    matched: 'verification code, expires',
    note: 'Expires in 10 min',
    otp: '849201',
    attachment: null,
    paragraphs: [
      'A sign-in attempt from Ludhiana, IN requires verification before granting SSH access to Babul-Kumar/MailMind.',
      'Enter code 849201 within the next 10 minutes to authorize this session. Once expired, this message automatically steps down to Routine.'
    ]
  },
  {
    id: 'e3',
    sender: 'Prof. R. Sharma',
    email: 'rajesh.sharma@lpu.co.in',
    initials: 'RS',
    avatarBg: 'bg-amber-100/70 text-amber-900',
    subject: 'CSE472 final viva slot confirmation',
    time: '9:15 AM',
    fullDate: 'Nov 5, 9:15 AM',
    daysAgo: 0,
    unread: true,
    analyzed: true,
    priority: 'P2',
    needsAttention: true,
    matched: 'viva, confirm by Friday',
    note: 'Due Nov 8',
    otp: null,
    attachment: null,
    paragraphs: [
      'Hi Babul, the panel schedule for CSE472 Applied AI project evaluations has been finalized for next week.',
      'Please confirm your 15-minute live demonstration slot by Friday, November 8, and ensure your repository README and test suite are up to date.'
    ]
  },
  {
    id: 'e4',
    sender: 'LPU Examinations',
    email: 'examinations@lpu.co.in',
    initials: 'LP',
    avatarBg: 'bg-emerald-100/60 text-emerald-900',
    subject: 'Download provisional hall ticket for Autumn term',
    time: 'Yesterday',
    fullDate: 'Nov 4, 4:20 PM',
    daysAgo: 1,
    unread: false,
    analyzed: true,
    priority: 'P3',
    needsAttention: true,
    matched: 'download, hall ticket',
    note: 'Document action detected',
    otp: null,
    attachment: { name: 'Hall_Ticket_2026.pdf', size: '240 KB' },
    paragraphs: [
      'Provisional admit cards for the November end-term practical and theory examinations are now ready.',
      'Download the attached PDF and carry a printed copy along with your university ID card to the examination venue.'
    ]
  },
  {
    id: 'e5',
    sender: 'Stripe',
    email: 'receipts@stripe.com',
    initials: 'ST',
    avatarBg: 'bg-slate-200/80 text-slate-700',
    subject: 'October cloud invoice #4829 ready for approval',
    time: 'Nov 3',
    fullDate: 'Nov 3, 2:10 PM',
    daysAgo: 2,
    unread: false,
    analyzed: true,
    priority: 'P2',
    needsAttention: true,
    matched: 'invoice, approval, due',
    note: 'Due Nov 10',
    otp: null,
    attachment: { name: 'Invoice_4829.pdf', size: '118 KB' },
    paragraphs: [
      'Your October infrastructure statement (#4829) for $19.00 USD has been generated.',
      'Please verify your billing card on file before November 10 so automatic settlement completes without interruption.'
    ]
  },
  {
    id: 'e6',
    sender: 'Linear',
    email: 'changelog@linear.app',
    initials: 'LN',
    avatarBg: 'bg-zinc-200/80 text-zinc-700',
    subject: 'Changelog: Faster sync and keyboard triage',
    time: 'Nov 2',
    fullDate: 'Nov 2, 11:00 AM',
    daysAgo: 3,
    unread: false,
    analyzed: true,
    priority: 'P3',
    needsAttention: false,
    matched: 'changelog, release notes',
    note: 'Informational update',
    otp: null,
    attachment: null,
    paragraphs: [
      'This week we shipped sub-millisecond local cache hydration and cleaner keyboard navigation across inbox views.',
      'No action is needed—your workspace has already been updated automatically.'
    ]
  },
  {
    id: 'e7',
    sender: 'Figma',
    email: 'notifications@figma.com',
    initials: 'FG',
    avatarBg: 'bg-stone-200/80 text-stone-700',
    subject: 'Weekly activity digest on MailMind Design System',
    time: 'Oct 30',
    fullDate: 'Oct 30, 6:00 PM',
    daysAgo: 6,
    unread: false,
    analyzed: true,
    priority: 'P3',
    needsAttention: false,
    matched: 'weekly digest, activity',
    note: 'Routine summary',
    otp: null,
    attachment: null,
    paragraphs: [
      'Aarav and 2 teammates left resolved notes on the typography and color token frames earlier this week.',
      'Open Figma anytime if you would like to review the archived version history.'
    ]
  },
  {
    id: 'e8',
    sender: 'Coursera',
    email: 'no-reply@coursera.org',
    initials: 'CR',
    avatarBg: 'bg-zinc-200/80 text-zinc-600',
    subject: 'Save 40% on Applied Machine Learning specializations',
    time: 'Oct 26',
    fullDate: 'Oct 26, 9:00 AM',
    daysAgo: 10,
    unread: false,
    analyzed: true,
    priority: 'P4',
    needsAttention: false,
    matched: 'save 40%, promotional',
    note: 'Filtered low priority',
    otp: null,
    attachment: null,
    paragraphs: [
      'Advance your career this autumn with hands-on courses from leading university partners at a seasonal discount.',
      'You are receiving this email because you enrolled in an NLP course last semester.'
    ]
  },
  {
    id: 'e9',
    sender: 'Dr. Vikram Sen',
    email: 'vikram.sen@lpu.co.in',
    initials: 'VS',
    avatarBg: 'bg-emerald-100/60 text-emerald-900',
    subject: 'Approved: Capstone proposal on email priority intelligence',
    time: 'May 18',
    fullDate: 'May 18, 2026',
    daysAgo: 171,
    unread: false,
    analyzed: false,
    priority: 'P2',
    needsAttention: false,
    matched: 'approved, capstone proposal',
    note: 'Historical archive',
    otp: null,
    attachment: { name: 'Proposal_Approval.pdf', size: '190 KB' },
    paragraphs: [
      'Dear Babul, the department committee has approved your CSE472 capstone topic proposal for the 2026 academic term.',
      'Keep a copy of the signed approval memo attached below for your final thesis submission.'
    ]
  },
  {
    id: 'e10',
    sender: 'Vercel',
    email: 'updates@vercel.com',
    initials: 'VC',
    avatarBg: 'bg-zinc-200/80 text-zinc-700',
    subject: 'Spring platform update and edge region expansion',
    time: 'Feb 12',
    fullDate: 'Feb 12, 2026',
    daysAgo: 266,
    unread: false,
    analyzed: false,
    priority: 'P4',
    needsAttention: false,
    matched: 'platform update, newsletter',
    note: 'Historical archive',
    otp: null,
    attachment: null,
    paragraphs: [
      'Explore faster static builds and new edge caching regions across South Asia in our seasonal platform roundup.',
      'Thank you for building and deploying with Vercel.'
    ]
  }
];

// ============================================================================
// MINIMAL BRAND MARK
// ============================================================================

function BrandMark() {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="none"
      className="w-4 h-4 shrink-0"
      aria-hidden="true"
    >
      <rect
        x="2"
        y="3.5"
        width="16"
        height="13"
        rx="3"
        stroke="currentColor"
        strokeWidth="1.6"
      />
      <path
        d="M3.5 6L10 10.5L16.5 6"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function getSenderInitials(name) {
  if (!name) return 'M';
  const clean = name.replace(/<[^>]+>/g, '').trim();
  const parts = clean.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) {
    return (parts[0][0] + parts[1][0]).toUpperCase();
  }
  return clean.slice(0, 2).toUpperCase() || 'M';
}

function formatRealEmail(item, index) {
  const senderDisplay = cleanSenderName(item.sender);
  const senderEmail = (item.sender?.match(/<([^>]+)>/)?.[1]) || (item.sender?.includes('@') ? item.sender : '');
  const initials = getSenderInitials(senderDisplay);
  const priority = item.effective_priority || item.final_priority || item.predicted_priority || 'P3';
  const time = formatEmailDate(item.date);
  const fullDate = item.date
    ? new Date(item.date).toLocaleString([], { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })
    : time;

  // Detect OTP from subject or body
  const text = `${item.subject || ''} ${item.body || ''}`;
  let otp = null;
  const otpMatch = text.match(/\b([0-9]{6})\b/);
  if (otpMatch && /verification|code|otp|one-time|password|authorize/i.test(text)) {
    otp = otpMatch[1];
  }

  // Paragraphs
  const paragraphs = item.body
    ? item.body.split(/\r?\n\s*\r?\n/).map((p) => p.trim()).filter(Boolean)
    : [item.snippet || item.subject || 'No textual content found in message payload.'];

  // Matched / Signals
  const matched =
    (item.salient_tokens || item.salient_keywords || []).slice(0, 4).join(', ') ||
    item.action_reason ||
    (priority === 'P1' ? 'urgent operational alert' : 'important correspondence');
  const note = item.deadline_display || item.action_reason || '';

  // Attachment
  const attachment =
    item.has_attachment && item.attachments?.[0]
      ? { name: item.attachments[0].filename || 'Document.pdf', size: item.attachments[0].size || '240 KB' }
      : item.subject && /invoice|bill|statement|receipt|hall ticket/i.test(item.subject)
      ? { name: `${item.subject.slice(0, 20)}.pdf`, size: '180 KB' }
      : null;

  // Days ago calculation
  let daysAgo = 0;
  if (item.date) {
    const diffMs = Date.now() - new Date(item.date).getTime();
    daysAgo = Math.max(0, Math.floor(diffMs / (1000 * 60 * 60 * 24)));
  }

  const needsAttention = Boolean(
    item.action_required ||
    item.deadline_detected ||
    priority === 'P1' ||
    (priority === 'P2' && item.action_required !== false)
  );

  return {
    id: item.email_id || item.id || `real-${index}`,
    sender: senderDisplay,
    email: senderEmail || 'user@example.com',
    initials,
    avatarBg: 'bg-zinc-200/80 text-zinc-700',
    subject: item.subject || '(No Subject)',
    time,
    fullDate,
    daysAgo,
    unread: Boolean(item.is_unread || item.unread),
    analyzed: Boolean(item.predicted_priority || item.final_priority),
    priority,
    needsAttention,
    matched,
    note,
    otp,
    attachment,
    paragraphs: paragraphs.length ? paragraphs : ['(No message body)'],
    raw: item,
  };
}

// ============================================================================
// MAIN APPLICATION
// ============================================================================

export default function App() {
  const [dark, setDark] = useState(() => {
    return localStorage.getItem('mailmind_theme') === 'dark';
  });

  // Auth & Backend Integration
  const auth = useAuth();
  const emailsHook = useEmails(auth.isAuthenticated, auth.user);

  // Sync theme with document class and localStorage
  useEffect(() => {
    if (dark) {
      document.documentElement.classList.add('dark');
      document.documentElement.setAttribute('data-theme', 'dark');
      localStorage.setItem('mailmind_theme', 'dark');
    } else {
      document.documentElement.classList.remove('dark');
      document.documentElement.setAttribute('data-theme', 'light');
      localStorage.setItem('mailmind_theme', 'light');
    }
  }, [dark]);

  // OAuth Callback Route Check
  const [currentPath, setCurrentPath] = useState(() => {
    if (typeof window !== 'undefined') {
      const pathname = window.location.pathname;
      const search = window.location.search;
      if (pathname.includes('/auth/callback') || search.includes('handoff=') || search.includes('auth_error=')) {
        return '/auth/callback';
      }
      return pathname;
    }
    return '/';
  });

  useEffect(() => {
    const handlePopState = () => {
      const pathname = window.location.pathname;
      const search = window.location.search;
      if (pathname.includes('/auth/callback') || search.includes('handoff=') || search.includes('auth_error=')) {
        setCurrentPath('/auth/callback');
      } else {
        setCurrentPath(pathname);
      }
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  // Navigation & Filters
  const [view, setView] = useState('attention'); // 'attention' | 'recent' | 'all'
  const [subTab, setSubTab] = useState('active'); // 'active' | 'snoozed' | 'done'
  const [priorityFilter, setPriorityFilter] = useState(null); // null | 'P1' | 'P2' | 'P3' | 'P4'
  const [windowId, setWindowId] = useState('last_3_months');
  const [search, setSearch] = useState('');
  const [mobileReading, setMobileReading] = useState(false);

  // Mailbox Data & Triage Status
  const [selectedId, setSelectedId] = useState('e1');
  const [statusMap, setStatusMap] = useState({}); // { [id]: { state: 'done' | 'snoozed', until?: string } }

  // Overrides map for user-set priorities
  const [overridesMap, setOverridesMap] = useState({});

  // Floating Popovers & Feedback
  const [syncing, setSyncing] = useState(false);
  const [priorityMenuOpen, setPriorityMenuOpen] = useState(false);
  const [snoozeMenuOpen, setSnoozeMenuOpen] = useState(false);
  const [windowMenuOpen, setWindowMenuOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [copiedId, setCopiedId] = useState(null);
  const [toast, setToast] = useState(null);

  const rootRef = useRef(null);

  // Sync background progress
  useEffect(() => {
    if (emailsHook.isScanning || emailsHook.isRefreshing) {
      setSyncing(true);
    } else {
      setSyncing(false);
    }
  }, [emailsHook.isScanning, emailsHook.isRefreshing]);

  // Combine real backend emails or fallback to concise INITIAL_EMAILS
  const emails = useMemo(() => {
    if (emailsHook.emails && emailsHook.emails.length > 0) {
      return emailsHook.emails.map((m, idx) => {
        const formatted = formatRealEmail(m, idx);
        if (overridesMap[formatted.id]) {
          formatted.priority = overridesMap[formatted.id];
          formatted.needsAttention = overridesMap[formatted.id] === 'P1' || overridesMap[formatted.id] === 'P2';
        }
        return formatted;
      });
    }
    return INITIAL_EMAILS.map((m) => {
      const copy = { ...m };
      if (overridesMap[copy.id]) {
        copy.priority = overridesMap[copy.id];
        copy.needsAttention = overridesMap[copy.id] === 'P1' || overridesMap[copy.id] === 'P2';
      }
      return copy;
    });
  }, [emailsHook.emails, overridesMap]);

  // Select first email on load
  useEffect(() => {
    if (emails.length > 0 && (!selectedId || !emails.find((e) => e.id === selectedId))) {
      setSelectedId(emails[0].id);
    }
  }, [emails, selectedId]);

  const triggerToast = useCallback((message, undo = null) => {
    setToast({ id: Date.now(), message, undo });
  }, []);

  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 4000);
    return () => clearTimeout(timer);
  }, [toast]);

  // Close floating menus on Escape
  useEffect(() => {
    const onKeyDown = (e) => {
      if (e.key === 'Escape') {
        setPriorityMenuOpen(false);
        setSnoozeMenuOpen(false);
        setWindowMenuOpen(false);
        setUserMenuOpen(false);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  const closeAllMenus = () => {
    setPriorityMenuOpen(false);
    setSnoozeMenuOpen(false);
    setWindowMenuOpen(false);
    setUserMenuOpen(false);
  };

  // Active Window Cutoff
  const cutoffDays = useMemo(() => {
    return WINDOWS.find((w) => w.id === windowId)?.days ?? 90;
  }, [windowId]);

  // Attention Counter
  const attentionCount = useMemo(() => {
    return emails.filter((e) => e.needsAttention && !statusMap[e.id]).length;
  }, [emails, statusMap]);

  // Filtered List Items
  const visibleEmails = useMemo(() => {
    return emails.filter((item) => {
      const st = statusMap[item.id]?.state;

      if (view === 'attention') {
        if (subTab === 'active' && (!item.needsAttention || st)) return false;
        if (subTab === 'snoozed' && st !== 'snoozed') return false;
        if (subTab === 'done' && st !== 'done') return false;
      } else if (view === 'recent') {
        if (item.daysAgo > cutoffDays) return false;
        if (st === 'done') return false;
      }
      // 'all' shows everything in mailbox

      if (priorityFilter) {
        if (!item.analyzed || item.priority !== priorityFilter) return false;
      }

      if (search.trim()) {
        const q = search.toLowerCase();
        return (
          item.sender.toLowerCase().includes(q) ||
          item.subject.toLowerCase().includes(q)
        );
      }

      return true;
    });
  }, [emails, view, subTab, statusMap, cutoffDays, priorityFilter, search]);

  const currentEmail = useMemo(() => {
    return (
      visibleEmails.find((e) => e.id === selectedId) ||
      visibleEmails[0] ||
      null
    );
  }, [visibleEmails, selectedId]);

  // ============================================================================
  // INTERACTIVE HANDLERS
  // ============================================================================

  const selectEmail = (item) => {
    setSelectedId(item.id);
    setMobileReading(true);
    closeAllMenus();
  };

  const advanceSelection = (actingId) => {
    const idx = visibleEmails.findIndex((e) => e.id === actingId);
    if (idx === -1) return;
    const nextItem = visibleEmails[idx + 1] || visibleEmails[idx - 1];
    if (nextItem) setSelectedId(nextItem.id);
  };

  const markDone = (item, e = null) => {
    if (e) e.stopPropagation();
    if (!item) return;
    const prev = statusMap[item.id];
    advanceSelection(item.id);
    setStatusMap((map) => ({ ...map, [item.id]: { state: 'done' } }));
    closeAllMenus();

    // Trigger backend resolve if real email
    if (item.raw?.email_id || item.raw?.id) {
      emailsHook.resolveEmail?.(item.raw.email_id || item.raw.id);
    }

    triggerToast('Marked done', () => {
      setStatusMap((map) => {
        const next = { ...map };
        if (prev) next[item.id] = prev;
        else delete next[item.id];
        return next;
      });
      setSelectedId(item.id);
      if (item.raw?.email_id || item.raw?.id) {
        emailsHook.unresolveEmail?.(item.raw.email_id || item.raw.id);
      }
    });
  };

  const snoozeItem = (item, untilLabel, e = null) => {
    if (e) e.stopPropagation();
    if (!item) return;
    const prev = statusMap[item.id];
    advanceSelection(item.id);
    setStatusMap((map) => ({
      ...map,
      [item.id]: { state: 'snoozed', until: untilLabel }
    }));
    closeAllMenus();

    if (item.raw?.email_id || item.raw?.id) {
      const ms = untilLabel === 'Tomorrow' ? 86400000 : 7 * 86400000;
      emailsHook.snoozeEmail?.(item.raw.email_id || item.raw.id, Date.now() + ms);
    }

    triggerToast(`Snoozed · ${untilLabel}`, () => {
      setStatusMap((map) => {
        const next = { ...map };
        if (prev) next[item.id] = prev;
        else delete next[item.id];
        return next;
      });
      setSelectedId(item.id);
      if (item.raw?.email_id || item.raw?.id) {
        emailsHook.unsnoozeEmail?.(item.raw.email_id || item.raw.id);
      }
    });
  };

  const restoreItem = (item, e = null) => {
    if (e) e.stopPropagation();
    setStatusMap((map) => {
      const next = { ...map };
      delete next[item.id];
      return next;
    });
    closeAllMenus();
    if (item.raw?.email_id || item.raw?.id) {
      emailsHook.unresolveEmail?.(item.raw.email_id || item.raw.id);
    }
    triggerToast('Moved to Active');
  };

  const changePriority = (item, newPriority) => {
    setPriorityMenuOpen(false);
    if (item.priority === newPriority) return;
    const oldPriority = item.priority;

    setOverridesMap((prev) => ({ ...prev, [item.id]: newPriority }));

    // Send feedback override to backend
    if (item.raw) {
      submitFeedback({
        message_id: item.raw.email_id || item.raw.id,
        user_priority: newPriority,
        predicted_priority: item.raw.predicted_priority || item.raw.final_priority || oldPriority,
        confidence: item.raw.confidence || 0.9,
        thread_id: item.raw.thread_id,
        feedback_type: 'OVERRIDE',
      }).catch(() => {});
    }

    triggerToast(`Set to ${PRIORITIES[newPriority].name}`, () => {
      setOverridesMap((prev) => {
        const next = { ...prev };
        next[item.id] = oldPriority;
        return next;
      });
    });
  };

  const analyzeSingle = (item) => {
    setSyncing(true);
    setTimeout(() => {
      setSyncing(false);
      triggerToast(`Classified · ${PRIORITIES[item.priority]?.name || 'Urgent'}`);
    }, 450);
  };

  const selectWindow = (nextId) => {
    setWindowId(nextId);
    setWindowMenuOpen(false);
    setSyncing(true);

    if (emailsHook.changeAnalysisPeriod) {
      emailsHook.changeAnalysisPeriod(nextId);
    }

    setTimeout(() => {
      setSyncing(false);
    }, 600);
  };

  const handleCopyOtp = (code, id) => {
    if (navigator.clipboard?.writeText) {
      navigator.clipboard.writeText(code).catch(() => {});
    }
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  // OAuth Callback Route
  if (currentPath === '/auth/callback') {
    return (
      <AuthCallback
        exchangeHandoff={auth.exchangeHandoff}
        onAuthenticationComplete={() => {
          auth.refreshStatus?.();
        }}
        onSuccess={() => {
          window.history.replaceState({}, document.title, '/');
          setCurrentPath('/');
          auth.refreshStatus?.();
        }}
        onCancel={() => {
          window.history.replaceState({}, document.title, '/');
          setCurrentPath('/');
        }}
      />
    );
  }

  // ============================================================================
  // MINIMAL CARDLESS GOOGLE SIGN-IN SCREEN
  // ============================================================================

  const signedIn = auth.isAuthenticated || (!auth.isLoading && emails.length > 0);

  if (!signedIn && !auth.isLoading) {
    return (
      <div
        className={`h-screen w-full flex flex-col items-center justify-center px-6 transition-colors duration-200 ${
          dark ? 'bg-[#18181B] text-[#F4F4F5]' : 'bg-[#FFFFFF] text-[#18181B]'
        }`}
      >
        <button
          onClick={() => setDark((d) => !d)}
          className={`fixed top-6 right-6 p-2 rounded-full transition cursor-pointer ${
            dark
              ? 'text-[#A1A1AA] hover:text-[#F4F4F5] hover:bg-zinc-800'
              : 'text-[#71717A] hover:text-[#18181B] hover:bg-zinc-100'
          }`}
          aria-label="Toggle theme"
        >
          {dark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
        </button>

        <div className="flex flex-col items-center text-center max-w-xs">
          <div
            className={`w-10 h-10 rounded-xl flex items-center justify-center mb-6 ${
              dark ? 'bg-zinc-800 text-[#F4F4F5]' : 'bg-[#F5F5F4] text-[#18181B]'
            }`}
          >
            <BrandMark />
          </div>

          <h1 className="text-xl font-semibold tracking-tight mb-2">
            Calm priority for Gmail
          </h1>
          <p
            className={`text-sm mb-8 ${
              dark ? 'text-[#A1A1AA]' : 'text-[#71717A]'
            }`}
          >
            Read-only triage. Zero clutter.
          </p>

          <button
            onClick={() => auth.login()}
            className={`px-5 py-2.5 rounded-lg text-sm font-medium transition cursor-pointer ${
              dark
                ? 'bg-[#F4F4F5] text-[#18181B] hover:bg-zinc-200'
                : 'bg-[#18181B] text-white hover:bg-zinc-800'
            }`}
          >
            Continue with Google
          </button>
        </div>
      </div>
    );
  }

  // ============================================================================
  // SEAMLESS 3-COLUMN WORKSPACE (ZERO BOX-IN-BOX)
  // ============================================================================

  const activeWindowLabel =
    WINDOWS.find((w) => w.id === windowId)?.label || 'Last 3 months';
  const currentPriority = currentEmail
    ? PRIORITIES[currentEmail.priority] || PRIORITIES.P3
    : null;
  const currentTriage = currentEmail ? statusMap[currentEmail.id] : null;

  const userName = auth.user?.name || (auth.user?.email ? auth.user.email.split('@')[0] : 'Babul Kumar');
  const userInitials = auth.user?.name ? getSenderInitials(auth.user.name) : 'BK';

  return (
    <div
      ref={rootRef}
      onClick={closeAllMenus}
      className={`h-screen w-full overflow-hidden flex relative select-none transition-colors duration-200 ${
        dark ? 'bg-[#18181B] text-[#F4F4F5]' : 'bg-[#FFFFFF] text-[#18181B]'
      }`}
    >
      {/* Sleek 2px Top Sync Progress Line */}
      <div className="fixed top-0 left-0 right-0 h-[2px] z-50 pointer-events-none overflow-hidden">
        <div
          className={`h-full bg-[#2563EB] transition-all duration-500 ease-out ${
            syncing ? 'w-full opacity-100' : 'w-0 opacity-0'
          }`}
        />
      </div>

      {/* ==================================================================== */}
      {/* 1. LEFT SIDEBAR (w-56, SINGLE HAIRLINE BORDER, NO BOXED CARDS)       */}
      {/* ==================================================================== */}
      <aside
        className={`w-56 hidden md:flex flex-col justify-between shrink-0 border-r px-3 py-4 ${
          dark
            ? 'bg-[#121214] border-[#27272A]'
            : 'bg-[#F5F5F4] border-[#E4E4E7]'
        }`}
      >
        <div className="space-y-6">
          {/* Brand + Theme Toggle */}
          <div className="flex items-center justify-between px-2.5">
            <div className="flex items-center gap-2 font-semibold text-[14px] tracking-tight">
              <BrandMark />
              <span>MailMind</span>
            </div>

            <button
              onClick={(e) => {
                e.stopPropagation();
                setDark((d) => !d);
              }}
              className={`p-1.5 rounded-md transition cursor-pointer ${
                dark
                  ? 'text-[#A1A1AA] hover:text-[#F4F4F5] hover:bg-zinc-800/70'
                  : 'text-[#71717A] hover:text-[#18181B] hover:bg-zinc-200/60'
              }`}
              aria-label="Toggle theme"
            >
              {dark ? <Sun className="w-3.5 h-3.5" /> : <Moon className="w-3.5 h-3.5" />}
            </button>
          </div>

          {/* Primary Views */}
          <nav className="space-y-0.5">
            {[
              { id: 'attention', label: 'Needs Attention', count: attentionCount },
              { id: 'recent', label: 'Recent Mail', count: null },
              { id: 'all', label: 'All Mail', count: null }
            ].map((nav) => {
              const active = view === nav.id;
              return (
                <button
                  key={nav.id}
                  onClick={() => {
                    setView(nav.id);
                    setMobileReading(false);
                  }}
                  className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg text-[13px] transition cursor-pointer ${
                    active
                      ? dark
                        ? 'bg-zinc-800/80 text-[#F4F4F5] font-medium'
                        : 'bg-zinc-200/70 text-[#18181B] font-medium'
                      : dark
                      ? 'text-[#A1A1AA] hover:text-[#F4F4F5] hover:bg-zinc-800/40'
                      : 'text-[#71717A] hover:text-[#18181B] hover:bg-zinc-200/40'
                  }`}
                >
                  <span>{nav.label}</span>
                  {nav.count !== null && nav.count > 0 && (
                    <span
                      className={`text-xs tabular-nums ${
                        active
                          ? dark
                            ? 'text-[#F4F4F5]'
                            : 'text-[#18181B]'
                          : 'text-[#71717A]'
                      }`}
                    >
                      {nav.count}
                    </span>
                  )}
                </button>
              );
            })}
          </nav>

          {/* Subtle Priority Filter Dots */}
          <div className="space-y-0.5 pt-2">
            <div className="px-2.5 pb-1.5 text-[11px] font-medium text-[#71717A]">
              Priority
            </div>
            {Object.values(PRIORITIES).map((tier) => {
              const active = priorityFilter === tier.id;
              return (
                <button
                  key={tier.id}
                  onClick={() =>
                    setPriorityFilter((cur) => (cur === tier.id ? null : tier.id))
                  }
                  className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg text-[13px] transition cursor-pointer ${
                    active
                      ? dark
                        ? 'bg-zinc-800/80 text-[#F4F4F5] font-medium'
                        : 'bg-zinc-200/70 text-[#18181B] font-medium'
                      : dark
                      ? 'text-[#A1A1AA] hover:text-[#F4F4F5] hover:bg-zinc-800/40'
                      : 'text-[#71717A] hover:text-[#18181B] hover:bg-zinc-200/40'
                  }`}
                >
                  <span className="flex items-center gap-2.5">
                    <span
                      className="w-[7px] h-[7px] rounded-full shrink-0"
                      style={{ backgroundColor: tier.color }}
                    />
                    <span>{tier.name}</span>
                  </span>
                  {active && (
                    <span className="text-[11px] text-[#71717A]">Clear</span>
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {/* Quiet Bottom Footer: Analysis Window + User Row */}
        <div className="space-y-1 pt-4">
          {/* Minimal Borderless Window Menu */}
          <div className="relative" onClick={(e) => e.stopPropagation()}>
            <button
              onClick={() => {
                setWindowMenuOpen((o) => !o);
                setUserMenuOpen(false);
              }}
              className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg text-xs transition cursor-pointer ${
                dark
                  ? 'text-[#A1A1AA] hover:text-[#F4F4F5] hover:bg-zinc-800/50'
                  : 'text-[#71717A] hover:text-[#18181B] hover:bg-zinc-200/50'
              }`}
            >
              <span className="flex items-center gap-2">
                <RefreshCw
                  className={`w-3 h-3 ${syncing ? 'animate-spin' : ''}`}
                />
                <span>{activeWindowLabel}</span>
              </span>
              <ChevronDown className="w-3 h-3 opacity-60" />
            </button>

            {windowMenuOpen && (
              <div
                className={`absolute bottom-9 left-0 w-48 rounded-xl p-1 shadow-lg border z-30 ${
                  dark
                    ? 'bg-[#1F1F23] border-[#27272A] text-[#F4F4F5]'
                    : 'bg-[#FFFFFF] border-[#E4E4E7] text-[#18181B]'
                }`}
              >
                {WINDOWS.map((w) => (
                  <button
                    key={w.id}
                    onClick={() => selectWindow(w.id)}
                    className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg text-xs transition cursor-pointer ${
                      windowId === w.id
                        ? dark
                          ? 'bg-zinc-800 font-medium'
                          : 'bg-zinc-100 font-medium'
                        : dark
                        ? 'hover:bg-zinc-800/60 text-[#A1A1AA]'
                        : 'hover:bg-zinc-50 text-[#71717A]'
                    }`}
                  >
                    <span>{w.label}</span>
                    {windowId === w.id && <Check className="w-3 h-3" />}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Simple User Row */}
          <div className="relative" onClick={(e) => e.stopPropagation()}>
            <button
              onClick={() => {
                setUserMenuOpen((o) => !o);
                setWindowMenuOpen(false);
              }}
              className={`w-full flex items-center gap-2.5 px-2.5 py-1.5 rounded-lg text-[13px] transition cursor-pointer ${
                dark
                  ? 'text-[#A1A1AA] hover:text-[#F4F4F5] hover:bg-zinc-800/50'
                  : 'text-[#52525B] hover:text-[#18181B] hover:bg-zinc-200/50'
              }`}
            >
              <span
                className={`w-6 h-6 rounded-full text-[10px] font-medium flex items-center justify-center shrink-0 ${
                  dark
                    ? 'bg-zinc-800 text-[#F4F4F5]'
                    : 'bg-zinc-200/90 text-[#18181B]'
                }`}
              >
                {userInitials}
              </span>
              <span className="truncate text-xs font-medium">{userName}</span>
            </button>

            {userMenuOpen && (
              <div
                className={`absolute bottom-10 left-0 w-44 rounded-xl p-1 shadow-lg border z-30 ${
                  dark
                    ? 'bg-[#1F1F23] border-[#27272A] text-[#F4F4F5]'
                    : 'bg-[#FFFFFF] border-[#E4E4E7] text-[#18181B]'
                }`}
              >
                <button
                  onClick={() => {
                    setUserMenuOpen(false);
                    auth.logout();
                  }}
                  className={`w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-xs transition cursor-pointer ${
                    dark
                      ? 'hover:bg-zinc-800 text-[#A1A1AA] hover:text-[#F4F4F5]'
                      : 'hover:bg-zinc-100 text-[#52525B] hover:text-[#18181B]'
                  }`}
                >
                  <LogOut className="w-3.5 h-3.5" />
                  <span>Sign out</span>
                </button>
              </div>
            )}
          </div>
        </div>
      </aside>

      {/* ==================================================================== */}
      {/* 2. MIDDLE COLUMN — EMAIL LIST (w-[360px], TWO-LINE ROWS, NO CARDS)   */}
      {/* ==================================================================== */}
      <section
        className={`${
          mobileReading ? 'hidden md:flex' : 'flex'
        } w-full md:w-[360px] shrink-0 flex-col border-r ${
          dark
            ? 'bg-[#18181B] border-[#27272A]'
            : 'bg-[#FFFFFF] border-[#E4E4E7]'
        }`}
      >
        {/* Minimal Mobile Nav Strip (Only visible on small screens) */}
        <div
          className={`flex md:hidden items-center justify-between px-5 pt-3 pb-1 text-xs ${
            dark ? 'text-[#A1A1AA]' : 'text-[#71717A]'
          }`}
        >
          <div className="flex items-center gap-3">
            {[
              { id: 'attention', label: 'Attention' },
              { id: 'recent', label: 'Recent' },
              { id: 'all', label: 'All Mail' }
            ].map((m) => (
              <button
                key={m.id}
                onClick={() => setView(m.id)}
                className={
                  view === m.id
                    ? dark
                      ? 'text-[#F4F4F5] font-medium'
                      : 'text-[#18181B] font-medium'
                    : ''
                }
              >
                {m.label}
              </button>
            ))}
          </div>
          <button onClick={() => setDark((d) => !d)}>
            {dark ? <Sun className="w-3.5 h-3.5" /> : <Moon className="w-3.5 h-3.5" />}
          </button>
        </div>

        {/* Borderless Top Search Header */}
        <div
          className={`h-14 px-5 flex items-center gap-2.5 border-b shrink-0 ${
            dark ? 'border-[#27272A]' : 'border-[#E4E4E7]'
          }`}
        >
          <Search className="w-4 h-4 text-[#71717A] shrink-0" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search..."
            className={`w-full bg-transparent text-[13px] focus:outline-none ${
              dark
                ? 'text-[#F4F4F5] placeholder-[#71717A]'
                : 'text-[#18181B] placeholder-[#A1A1AA]'
            }`}
          />
          {search && (
            <button
              onClick={() => setSearch('')}
              className="text-xs text-[#71717A] hover:text-current cursor-pointer"
            >
              Clear
            </button>
          )}
        </div>

        {/* Quiet Underline Tabs (ONLY in Needs Attention) */}
        {view === 'attention' && (
          <div
            className={`px-5 flex items-center gap-5 border-b text-xs shrink-0 ${
              dark ? 'border-[#27272A]' : 'border-[#E4E4E7]'
            }`}
          >
            {[
              { id: 'active', label: 'Active' },
              { id: 'snoozed', label: 'Snoozed' },
              { id: 'done', label: 'Done' }
            ].map((t) => {
              const active = subTab === t.id;
              return (
                <button
                  key={t.id}
                  onClick={() => setSubTab(t.id)}
                  className={`py-2.5 border-b-2 -mb-px transition cursor-pointer ${
                    active
                      ? dark
                        ? 'border-[#F4F4F5] text-[#F4F4F5] font-medium'
                        : 'border-[#18181B] text-[#18181B] font-medium'
                      : 'border-transparent text-[#71717A] hover:text-current'
                  }`}
                >
                  {t.label}
                </button>
              );
            })}
          </div>
        )}

        {/* Strictly Two-Line Clean Email Rows */}
        <div
          className={`flex-1 overflow-y-auto divide-y ${
            dark ? 'divide-[#27272A]' : 'divide-[#E4E4E7]'
          }`}
        >
          {visibleEmails.length === 0 ? (
            <div className="px-6 py-16 text-center text-[13px] text-[#71717A]">
              All clear
            </div>
          ) : (
            visibleEmails.map((item) => {
              const isSelected = currentEmail?.id === item.id;
              const tier = PRIORITIES[item.priority] || PRIORITIES.P3;
              const st = statusMap[item.id]?.state;

              return (
                <div
                  key={item.id}
                  onClick={() => selectEmail(item)}
                  className={`group relative py-3.5 px-5 cursor-pointer transition-colors ${
                    isSelected
                      ? dark
                        ? 'bg-zinc-800/60'
                        : 'bg-zinc-100/80'
                      : dark
                      ? 'hover:bg-zinc-800/30'
                      : 'hover:bg-zinc-50'
                  }`}
                >
                  {/* Subtle 2px Left Selection Accent */}
                  {isSelected && (
                    <div
                      className={`absolute left-0 top-0 bottom-0 w-[2px] ${
                        dark ? 'bg-[#F4F4F5]' : 'bg-[#18181B]'
                      }`}
                    />
                  )}

                  {/* Line 1: 7px Dot + Sender Name + Timestamp */}
                  <div className="flex items-center justify-between gap-3 mb-1">
                    <div className="flex items-center gap-2.5 min-w-0">
                      {item.analyzed ? (
                        <span
                          className="w-[7px] h-[7px] rounded-full shrink-0"
                          style={{ backgroundColor: tier.color }}
                        />
                      ) : (
                        <span
                          className={`w-[7px] h-[7px] rounded-full border shrink-0 ${
                            dark ? 'border-zinc-500' : 'border-zinc-400'
                          }`}
                        />
                      )}

                      <span
                        className={`text-sm truncate ${
                          item.unread ? 'font-semibold' : 'font-medium'
                        }`}
                      >
                        {item.sender}
                      </span>
                    </div>

                    <span
                      className={`text-xs shrink-0 tabular-nums transition-opacity group-hover:opacity-0 ${
                        dark ? 'text-[#71717A]' : 'text-[#71717A]'
                      }`}
                    >
                      {item.time}
                    </span>
                  </div>

                  {/* Line 2: Concise Subject Only (Zero 3rd Line Snippet) */}
                  <div
                    className={`pl-[17px] text-[13px] truncate ${
                      item.unread
                        ? dark
                          ? 'text-[#E4E4E7]'
                          : 'text-[#3F3F46]'
                        : dark
                        ? 'text-[#A1A1AA]'
                        : 'text-[#71717A]'
                    }`}
                  >
                    {item.subject}
                  </div>

                  {/* Zero-Layout-Shift Floating Hover Actions */}
                  <div
                    onClick={(e) => e.stopPropagation()}
                    className={`absolute right-4 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1 pl-4 py-1 ${
                      isSelected
                        ? dark
                          ? 'bg-gradient-to-l from-zinc-800 via-zinc-800 to-transparent'
                          : 'bg-gradient-to-l from-zinc-100 via-zinc-100 to-transparent'
                        : dark
                        ? 'bg-gradient-to-l from-[#1E1E22] via-[#1E1E22] to-transparent'
                        : 'bg-gradient-to-l from-zinc-50 via-zinc-50 to-transparent'
                    }`}
                  >
                    {st ? (
                      <button
                        onClick={(e) => restoreItem(item, e)}
                        className={`p-1.5 rounded-md transition cursor-pointer ${
                          dark
                            ? 'text-[#A1A1AA] hover:text-[#F4F4F5] hover:bg-zinc-700/60'
                            : 'text-[#71717A] hover:text-[#18181B] hover:bg-zinc-200/70'
                        }`}
                        title="Restore"
                      >
                        <RotateCcw className="w-3.5 h-3.5" />
                      </button>
                    ) : (
                      <>
                        <button
                          onClick={(e) => snoozeItem(item, 'Tomorrow', e)}
                          className={`p-1.5 rounded-md transition cursor-pointer ${
                            dark
                              ? 'text-[#A1A1AA] hover:text-[#F4F4F5] hover:bg-zinc-700/60'
                              : 'text-[#71717A] hover:text-[#18181B] hover:bg-zinc-200/70'
                          }`}
                          title="Snooze"
                        >
                          <Clock className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={(e) => markDone(item, e)}
                          className={`p-1.5 rounded-md transition cursor-pointer ${
                            dark
                              ? 'text-[#A1A1AA] hover:text-[#F4F4F5] hover:bg-zinc-700/60'
                              : 'text-[#71717A] hover:text-[#18181B] hover:bg-zinc-200/70'
                          }`}
                          title="Done"
                        >
                          <Check className="w-3.5 h-3.5" />
                        </button>
                      </>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>
      </section>

      {/* ==================================================================== */}
      {/* 3. RIGHT COLUMN — OPEN READING CANVAS (PURE PAGE, NO INNER BOXES)    */}
      {/* ==================================================================== */}
      <main
        className={`${
          mobileReading ? 'flex' : 'hidden md:flex'
        } flex-1 flex-col overflow-y-auto ${
          dark ? 'bg-[#18181B]' : 'bg-[#FFFFFF]'
        }`}
      >
        {currentEmail ? (
          <>
            {/* Clean Top Action Strip */}
            <header
              className={`h-14 px-6 lg:px-12 border-b flex items-center justify-between shrink-0 ${
                dark ? 'border-[#27272A]' : 'border-[#E4E4E7]'
              }`}
            >
              {/* Left: Mobile Back + Floating Priority Popover Pill */}
              <div className="flex items-center gap-3">
                <button
                  onClick={() => setMobileReading(false)}
                  className="md:hidden p-1.5 -ml-1.5 text-[#71717A] hover:text-current cursor-pointer"
                >
                  <ArrowLeft className="w-4 h-4" />
                </button>

                {!currentEmail.analyzed ? (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      analyzeSingle(currentEmail);
                    }}
                    className={`inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium transition cursor-pointer ${
                      dark
                        ? 'bg-zinc-800 text-[#F4F4F5] hover:bg-zinc-700'
                        : 'bg-zinc-100 text-[#18181B] hover:bg-zinc-200/70'
                    }`}
                  >
                    <span className="w-[7px] h-[7px] rounded-full border border-current opacity-60" />
                    <span>Analyze</span>
                  </button>
                ) : (
                  <div
                    className="relative"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <button
                      onClick={() => {
                        setPriorityMenuOpen((o) => !o);
                        setSnoozeMenuOpen(false);
                      }}
                      className={`inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium transition cursor-pointer ${
                        dark
                          ? 'bg-zinc-800/80 text-[#F4F4F5] hover:bg-zinc-800'
                          : 'bg-[#F5F5F4] text-[#18181B] hover:bg-zinc-200/60'
                      }`}
                    >
                      <span
                        className="w-[7px] h-[7px] rounded-full"
                        style={{ backgroundColor: currentPriority.color }}
                      />
                      <span>
                        {currentPriority.id} · {currentPriority.name}
                      </span>
                      <ChevronDown className="w-3 h-3 opacity-60" />
                    </button>

                    {/* Floating Popover (Zero Accordion Layout Shift) */}
                    {priorityMenuOpen && (
                      <div
                        className={`absolute left-0 top-9 z-30 w-64 rounded-xl p-3.5 shadow-lg border space-y-3 ${
                          dark
                            ? 'bg-[#1F1F23] border-[#27272A] text-[#F4F4F5]'
                            : 'bg-[#FFFFFF] border-[#E4E4E7] text-[#18181B]'
                        }`}
                      >
                        <div className="space-y-1 text-xs">
                          <p
                            className={
                              dark ? 'text-[#E4E4E7]' : 'text-[#18181B]'
                            }
                          >
                            Matched:{' '}
                            <span className="text-[#71717A]">
                              {currentEmail.matched}
                            </span>
                          </p>
                          {currentEmail.note && (
                            <p className="text-[#71717A]">
                              {currentEmail.note}
                            </p>
                          )}
                        </div>

                        <div
                          className={`pt-2.5 border-t grid grid-cols-4 gap-1 ${
                            dark ? 'border-[#27272A]' : 'border-[#E4E4E7]'
                          }`}
                        >
                          {Object.values(PRIORITIES).map((tier) => {
                            const active = currentEmail.priority === tier.id;
                            return (
                              <button
                                key={tier.id}
                                onClick={() =>
                                  changePriority(currentEmail, tier.id)
                                }
                                className={`py-1.5 rounded-lg text-xs font-medium flex items-center justify-center gap-1.5 transition cursor-pointer ${
                                  active
                                    ? dark
                                      ? 'bg-zinc-700 text-[#F4F4F5]'
                                      : 'bg-zinc-200/80 text-[#18181B]'
                                    : dark
                                    ? 'hover:bg-zinc-800 text-[#A1A1AA]'
                                    : 'hover:bg-zinc-100 text-[#71717A]'
                                }`}
                              >
                                <span
                                  className="w-1.5 h-1.5 rounded-full"
                                  style={{ backgroundColor: tier.color }}
                                />
                                {tier.id}
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Right: OTP Copy + Snooze Popover + Done */}
              <div className="flex items-center gap-2">
                {currentEmail.otp && (
                  <button
                    onClick={() =>
                      handleCopyOtp(currentEmail.otp, currentEmail.id)
                    }
                    className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition cursor-pointer ${
                      dark
                        ? 'bg-zinc-800 text-[#F4F4F5] hover:bg-zinc-700'
                        : 'bg-[#F5F5F4] text-[#18181B] hover:bg-zinc-200/70'
                    }`}
                  >
                    {copiedId === currentEmail.id ? (
                      <>
                        <Check className="w-3.5 h-3.5 text-emerald-500" />
                        <span>Copied</span>
                      </>
                    ) : (
                      <>
                        <Copy className="w-3.5 h-3.5 text-[#71717A]" />
                        <span>Copy {currentEmail.otp}</span>
                      </>
                    )}
                  </button>
                )}

                {currentTriage ? (
                  <button
                    onClick={() => restoreItem(currentEmail)}
                    className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition cursor-pointer ${
                      dark
                        ? 'text-[#A1A1AA] hover:text-[#F4F4F5] hover:bg-zinc-800'
                        : 'text-[#52525B] hover:text-[#18181B] hover:bg-zinc-100'
                    }`}
                  >
                    <RotateCcw className="w-3.5 h-3.5" />
                    <span>Restore</span>
                  </button>
                ) : (
                  <>
                    <div
                      className="relative"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <button
                        onClick={() => {
                          setSnoozeMenuOpen((o) => !o);
                          setPriorityMenuOpen(false);
                        }}
                        className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition cursor-pointer ${
                          dark
                            ? 'text-[#A1A1AA] hover:text-[#F4F4F5] hover:bg-zinc-800'
                            : 'text-[#52525B] hover:text-[#18181B] hover:bg-zinc-100'
                        }`}
                      >
                        <Clock className="w-3.5 h-3.5" />
                        <span>Snooze</span>
                      </button>

                      {snoozeMenuOpen && (
                        <div
                          className={`absolute right-0 top-9 z-30 w-40 rounded-xl p-1 shadow-lg border text-xs ${
                            dark
                              ? 'bg-[#1F1F23] border-[#27272A] text-[#F4F4F5]'
                              : 'bg-[#FFFFFF] border-[#E4E4E7] text-[#18181B]'
                          }`}
                        >
                          {['Later today', 'Tomorrow', 'Next week'].map(
                            (option) => (
                              <button
                                key={option}
                                onClick={() => snoozeItem(currentEmail, option)}
                                className={`w-full text-left px-3 py-1.5 rounded-lg transition cursor-pointer ${
                                  dark
                                    ? 'hover:bg-zinc-800 text-[#E4E4E7]'
                                    : 'hover:bg-zinc-100 text-[#18181B]'
                                }`}
                              >
                                {option}
                              </button>
                            )
                          )}
                        </div>
                      )}
                    </div>

                    <button
                      onClick={() => markDone(currentEmail)}
                      className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition cursor-pointer ${
                        dark
                          ? 'bg-[#F4F4F5] text-[#18181B] hover:bg-zinc-200'
                          : 'bg-[#18181B] text-white hover:bg-zinc-800'
                      }`}
                    >
                      <Check className="w-3.5 h-3.5" />
                      <span>Done</span>
                    </button>
                  </>
                )}
              </div>
            </header>

            {/* Open Reading Canvas (Generous Whitespace, Zero Inner Cards) */}
            <article className="px-6 lg:px-12 py-10 max-w-2xl w-full select-text">
              <h1 className="text-xl font-semibold tracking-tight leading-snug mb-5">
                {currentEmail.subject}
              </h1>

              {/* Clean Sender Row */}
              <div className="flex items-center justify-between gap-4 mb-8">
                <div className="flex items-center gap-3 min-w-0">
                  <div
                    className={`w-9 h-9 rounded-full text-xs font-medium flex items-center justify-center shrink-0 ${
                      dark
                        ? 'bg-zinc-800 text-[#E4E4E7]'
                        : currentEmail.avatarBg
                    }`}
                  >
                    {currentEmail.initials}
                  </div>
                  <div className="min-w-0 truncate">
                    <span className="text-sm font-medium">
                      {currentEmail.sender}
                    </span>
                    <span className="text-xs text-[#71717A] ml-2">
                      &lt;{currentEmail.email}&gt;
                    </span>
                  </div>
                </div>

                <span className="text-xs text-[#71717A] shrink-0">
                  {currentEmail.fullDate}
                </span>
              </div>

              {/* Crisp Natural Paragraphs */}
              <div
                className={`text-[15px] leading-relaxed space-y-4 ${
                  dark ? 'text-[#E4E4E7]' : 'text-[#27272A]'
                }`}
              >
                {currentEmail.paragraphs.map((para, idx) => (
                  <p key={idx}>{para}</p>
                ))}
              </div>

              {/* Single Subtle Inline Attachment Pill */}
              {currentEmail.attachment && (
                <div className="mt-8">
                  <button
                    onClick={() =>
                      triggerToast(`Downloaded ${currentEmail.attachment.name}`)
                    }
                    className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs transition cursor-pointer ${
                      dark
                        ? 'bg-zinc-800/80 text-[#E4E4E7] hover:bg-zinc-800'
                        : 'bg-[#F5F5F4] text-[#3F3F46] hover:bg-zinc-200/70'
                    }`}
                  >
                    <Paperclip className="w-3.5 h-3.5 text-[#71717A]" />
                    <span className="font-medium">
                      {currentEmail.attachment.name}
                    </span>
                    <span className="text-[#71717A]">
                      · {currentEmail.attachment.size}
                    </span>
                  </button>
                </div>
              )}
            </article>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-sm text-[#71717A]">
            No message selected
          </div>
        )}
      </main>

      {/* ==================================================================== */}
      {/* MINIMAL BOTTOM-RIGHT TOAST                                           */}
      {/* ==================================================================== */}
      {toast && (
        <div
          onClick={(e) => e.stopPropagation()}
          className={`fixed bottom-5 right-5 z-50 px-3.5 py-2 rounded-lg shadow-md border text-xs flex items-center gap-3 ${
            dark
              ? 'bg-[#1F1F23] border-[#27272A] text-[#F4F4F5]'
              : 'bg-[#18181B] border-[#18181B] text-white'
          }`}
        >
          <span>{toast.message}</span>
          {toast.undo && (
            <button
              onClick={() => {
                toast.undo();
                setToast(null);
              }}
              className="font-medium underline underline-offset-2 opacity-90 hover:opacity-100 cursor-pointer"
            >
              Undo
            </button>
          )}
        </div>
      )}
    </div>
  );
}
