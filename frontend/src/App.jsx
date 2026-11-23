import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import {
  Menu,
  Search,
  SlidersHorizontal,
  Sun,
  Moon,
  RefreshCw,
  Inbox,
  AlertCircle,
  Star,
  Clock,
  Archive,
  Tag,
  Users,
  Info,
  Check,
  CheckSquare,
  Square,
  MinusSquare,
  RotateCcw,
  ArrowLeft,
  ExternalLink,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Paperclip,
  Copy,
  LogOut,
  Columns,
  X,
  Mail,
  MailOpen,
  Trash2
} from 'lucide-react';
import { useAuth } from './hooks/useAuth';
import { useEmails } from './hooks/useEmails';
import { AuthCallback } from './components/auth/AuthCallback';
import { cleanSenderName, formatEmailDate, isItemInWindow } from './utils/formatting';
import { submitFeedback, fetchEmailDetail } from './services/api';

// ============================================================================
// PRIORITY DEFINITIONS (NATURAL COLORS, SHORT LABELS)
// ============================================================================

const PRIORITIES = {
  P1: { id: 'P1', name: 'Urgent', color: '#E11D48' },
  P2: { id: 'P2', name: 'Important', color: '#F59E0B' },
  P3: { id: 'P3', name: 'Routine', color: '#7E22CE' },
  P4: { id: 'P4', name: 'Low', color: '#94A3B8' }
};

const WINDOWS = [
  { id: 'this_month', label: 'This month', days: 30 },
  { id: 'last_3_months', label: 'Last 3 months', days: 90 }
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
    avatarBg: 'bg-stone-200/80 text-stone-700',
    subject: 'Elevated 5xx latency on production API',
    time: '10:42 AM',
    fullDate: 'Nov 5, 10:42 AM',
    date: '2026-11-05T10:42:00Z',
    timestamp: Date.now() - 1000 * 60 * 18,
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
    date: '2026-11-05T10:38:00Z',
    timestamp: Date.now() - 1000 * 60 * 22,
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
    date: '2026-11-05T09:15:00Z',
    timestamp: Date.now() - 1000 * 60 * 105,
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
    date: '2026-11-04T16:20:00Z',
    timestamp: Date.now() - 1000 * 60 * 60 * 20,
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
    sender: 'ByteByteGo',
    email: 'bytebytego@substack.com',
    initials: 'BB',
    avatarBg: 'bg-indigo-100/70 text-indigo-900',
    subject: 'The Hidden Work Behind Every Database Request',
    time: 'Nov 3',
    fullDate: 'Nov 3, 2:10 PM',
    date: '2026-11-03T14:10:00Z',
    timestamp: Date.now() - 1000 * 60 * 60 * 48,
    daysAgo: 2,
    unread: false,
    analyzed: true,
    priority: 'P3',
    needsAttention: false,
    matched: 'newsletter, architecture',
    note: 'Tech digest',
    otp: null,
    attachment: null,
    paragraphs: [
      'When an application executes a simple SQL query, dozens of kernel and storage operations fire in parallel under the hood.',
      'From buffer pool lookups and WAL synchronization to lock managers, understanding execution engine internals helps prevent database brownouts under peak loads.'
    ]
  },
  {
    id: 'e6',
    sender: 'Stripe Billing',
    email: 'invoices@stripe.com',
    initials: 'ST',
    avatarBg: 'bg-violet-100/70 text-violet-900',
    subject: 'Your October subscription invoice and receipt',
    time: 'Oct 12',
    fullDate: 'Oct 12, 11:30 AM',
    date: '2026-10-12T11:30:00Z',
    timestamp: Date.now() - 1000 * 60 * 60 * 24 * 36,
    daysAgo: 36,
    unread: false,
    analyzed: true,
    priority: 'P2',
    needsAttention: false,
    matched: 'invoice, subscription, payment receipt',
    note: 'Paid invoice',
    otp: null,
    attachment: { name: 'Invoice_OCT_2026.pdf', size: '120 KB' },
    paragraphs: [
      'Your monthly invoice for Cloud Pro tier has been processed successfully.',
      'A copy of receipt #INV-2026-10-848 is attached for your accounting records.'
    ]
  },
  {
    id: 'e7',
    sender: 'DeepLearning.AI',
    email: 'certs@deeplearning.ai',
    initials: 'DL',
    avatarBg: 'bg-sky-100/70 text-sky-900',
    subject: 'Certificate of Completion: Applied Generative Models',
    time: 'Sep 24',
    fullDate: 'Sep 24, 4:15 PM',
    date: '2026-09-24T16:15:00Z',
    timestamp: Date.now() - 1000 * 60 * 60 * 24 * 54,
    daysAgo: 54,
    unread: false,
    analyzed: true,
    priority: 'P3',
    needsAttention: false,
    matched: 'certificate, course completion',
    note: 'Course certificate',
    otp: null,
    attachment: null,
    paragraphs: [
      'Congratulations on completing the specialization! Your verified certificate is ready to share on LinkedIn.',
      'Review your capstone score and download your credentials from your learner dashboard.'
    ]
  },
  {
    id: 'e8',
    sender: 'GitHub Security',
    email: 'security-alerts@github.com',
    initials: 'GH',
    avatarBg: 'bg-rose-100/70 text-rose-900',
    subject: 'Security Advisory: Dependabot alert resolved',
    time: 'Aug 29',
    fullDate: 'Aug 29, 3:00 PM',
    date: '2026-08-29T15:00:00Z',
    timestamp: Date.now() - 1000 * 60 * 60 * 24 * 80,
    daysAgo: 80,
    unread: false,
    analyzed: true,
    priority: 'P3',
    needsAttention: false,
    matched: 'dependabot, vulnerability resolved',
    note: 'Advisory resolved',
    otp: null,
    attachment: null,
    paragraphs: [
      'Dependabot detected that advisory CVE-2026-3829 has been mitigated in your repository dependency manifest.',
      'No further remediation steps are required at this time.'
    ]
  }
];

// ============================================================================
// BRAND LOGO ICON
// ============================================================================

function BrandMark() {
  return (
    <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-[#3B0764] via-[#581C87] to-[#1A072A] flex items-center justify-center shadow-sm border border-[#7E22CE]/40 shrink-0">
      <svg
        viewBox="0 0 20 20"
        fill="none"
        className="w-4 h-4 shrink-0 text-[#F59E0B]"
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
          d="M2.5 5.5L10 11.5L17.5 5.5"
          stroke="#FBBF24"
          strokeWidth="1.6"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </div>
  );
}

function getSenderInitials(name) {
  if (!name) return 'M';
  const clean = name.replace(/[^a-zA-Z\s]/g, '').trim();
  const parts = clean.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) {
    return (parts[0][0] + parts[1][0]).toUpperCase();
  }
  return clean.slice(0, 2).toUpperCase() || 'M';
}

// ============================================================================
// RICH GMAIL-STYLE EMAIL CONTENT RENDERERS
// ============================================================================

function HtmlEmailViewer({ html, dark }) {
  const iframeRef = useRef(null);
  const [iframeHeight, setIframeHeight] = useState(500);

  const cleanHtml = useMemo(() => {
    if (!html) return '';

    // Neutralize dangerous inline handlers & scripts
    let processed = html
      .replace(/\s+on\w+\s*=\s*(?:'[^']*'|"[^"]*"|[^\s>]+)/gi, '')
      .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '');

    // Convert all links (double-quote, single-quote, unquoted) to safe external tabs with rel="noopener noreferrer"
    processed = processed.replace(/<a\b([^>]*)>/gi, (match, attrs) => {
      const hrefMatch = attrs.match(/href\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))/i);
      const rawUrl = hrefMatch ? (hrefMatch[1] || hrefMatch[2] || hrefMatch[3] || '') : '';
      const safeUrl = rawUrl.trim().toLowerCase().startsWith('javascript:') ? '#' : rawUrl;
      const cleanAttrs = attrs
        .replace(/\s*target\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+)/gi, '')
        .replace(/\s*rel\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+)/gi, '')
        .replace(/href\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+)/i, `href="${safeUrl}"`);
      return `<a ${cleanAttrs} target="_blank" rel="noopener noreferrer">`;
    });

    const resetStyles = `
      <style>
        html, body {
          margin: 0;
          padding: 16px 20px;
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
          font-size: 14px;
          line-height: 1.6;
          color: ${dark ? '#F8FAFC' : '#1D0B2B'};
          background-color: transparent !important;
          word-break: break-word;
          overflow-wrap: break-word;
        }
        img {
          max-width: 100% !important;
          height: auto !important;
        }
        table {
          max-width: 100% !important;
        }
        a {
          color: ${dark ? '#C084FC' : '#7E22CE'};
        }
        blockquote {
          border-left: 2px solid ${dark ? '#3B1E52' : '#E2E8F0'};
          margin: 8px 0;
          padding-left: 12px;
          color: ${dark ? '#94A3B8' : '#786B84'};
        }
      </style>
    `;

    if (processed.includes('</head>')) {
      return processed.replace('</head>', `${resetStyles}</head>`);
    } else {
      return `${resetStyles}${processed}`;
    }
  }, [html, dark]);

  useEffect(() => {
    const iframe = iframeRef.current;
    if (!iframe) return;

    const measureHeight = () => {
      try {
        const doc = iframe.contentDocument || iframe.contentWindow?.document;
        if (doc && doc.body) {
          const bodyH = doc.body.scrollHeight;
          const docH = doc.documentElement.scrollHeight;
          const h = Math.max(bodyH, docH, 350);
          setIframeHeight(h + 30);
        }
      } catch (err) {
        // Fallback for sandboxed context
      }
    };

    iframe.addEventListener('load', measureHeight);
    const interval = setInterval(measureHeight, 500);
    const stopTimer = setTimeout(() => clearInterval(interval), 3500);

    return () => {
      iframe.removeEventListener('load', measureHeight);
      clearInterval(interval);
      clearTimeout(stopTimer);
    };
  }, [cleanHtml]);

  return (
    <iframe
      ref={iframeRef}
      title="Email Content"
      srcDoc={cleanHtml}
      sandbox="allow-popups allow-popups-to-escape-sandbox allow-same-origin"
      style={{
        width: '100%',
        minHeight: '350px',
        height: `${iframeHeight}px`,
        border: 'none',
        display: 'block',
        backgroundColor: 'transparent',
      }}
    />
  );
}

function FormattedTextEmail({ text, dark }) {
  const urlRegex = /(https?:\/\/[^\s<>()"']+)/g;

  const paragraphs = useMemo(() => {
    if (!text) return [];
    return text.split(/\r?\n\s*\r?\n/).map((p) => p.trim()).filter(Boolean);
  }, [text]);

  const renderWithLinks = (paragraph) => {
    const tokens = paragraph.split(urlRegex);
    return tokens.map((token, idx) => {
      if (token.match(urlRegex)) {
        return (
          <a
            key={idx}
            href={token}
            target="_blank"
            rel="noopener noreferrer"
            className={`${dark ? 'text-[#C084FC] hover:text-[#E9D5FF]' : 'text-[#7E22CE] hover:text-[#581C87]'} font-medium hover:underline break-all`}
          >
            {token}
          </a>
        );
      }
      return token;
    });
  };

  if (!paragraphs.length) {
    return (
      <div className={`italic text-sm ${dark ? 'text-zinc-500' : 'text-zinc-400'}`}>
        (No message content)
      </div>
    );
  }

  return (
    <div className={`space-y-4 text-[14.5px] leading-relaxed select-text break-words overflow-hidden ${
      dark ? 'text-[#F8FAFC]' : 'text-[#1E1231]'
    }`}>
      {paragraphs.map((p, idx) => (
        <p key={idx} className="whitespace-pre-wrap">
          {renderWithLinks(p)}
        </p>
      ))}
    </div>
  );
}

function formatRealEmail(item, index) {
  const senderDisplay = cleanSenderName(item.sender);
  const senderEmail = (item.sender?.match(/<([^>]+)>/)?.[1]) || (item.sender?.includes('@') ? item.sender : '');
  const initials = getSenderInitials(senderDisplay);
  const priority = item.original_priority || item.predicted_priority || item.final_priority || item.effective_priority || 'P3';
  const time = formatEmailDate(item.date);
  const fullDate = item.date
    ? new Date(item.date).toLocaleString([], {
        weekday: 'short',
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: 'numeric',
        minute: '2-digit'
      })
    : time;

  // Detect OTP strictly from authentication context (prevent address/pincode collisions like Bengaluru 560055)
  const fullText = `${item.subject || ''} ${item.body || ''}`;
  let otp = null;
  const isMarketingOrAddress = /\b(?:bengaluru|bangalore|mumbai|delhi|hyderabad|chennai|pincode|pin\s*code|postal|discount|newsletter|unsubscribe|early bird|conference|summit)\b/i.test(fullText);
  if (!isMarketingOrAddress) {
    const authOtpMatch = fullText.match(/(?:verification\s*code|one-time\s*(?:passcode|password)|auth\s*code|\botp\b)(?:[:\s]+is)?[:\s]+([0-9]{4,8})\b/i) ||
                         fullText.match(/\b([0-9]{4,8})\b(?:\s+is\s+(?:your\s+)?(?:verification\s*code|otp|one-time\s*password|security\s*code))/i);
    if (authOtpMatch) {
      otp = authOtpMatch[1];
    }
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

  let timestamp = 0;
  if (item.internal_date) {
    const val = Number(item.internal_date);
    timestamp = val > 1e11 ? val : val * 1000;
  } else if (item.date) {
    const parsed = new Date(item.date).getTime();
    if (!isNaN(parsed)) timestamp = parsed;
  }
  if (!timestamp && item.daysAgo !== undefined) {
    timestamp = Date.now() - item.daysAgo * 86400000;
  }

  let daysAgo = 0;
  if (timestamp) {
    const diffMs = Date.now() - timestamp;
    daysAgo = Math.max(0, Math.floor(diffMs / (1000 * 60 * 60 * 24)));
  }

  // Actionability check:
  // An email needs attention if it is in the active or older queue, requires action,
  // has a deadline, or is P1/P2 actionable, provided it is not expired, resolved, or snoozed.
  const isAgedOut = item.action_status === 'EXPIRED' || item.is_resolved || item.is_snoozed;
  const needsAttention = !isAgedOut && Boolean(
    item.queue_placement === 'ACTIVE' ||
    item.queue_placement === 'OLDER' ||
    item.needs_attention ||
    item.action_policy?.is_actionable ||
    item.action_required ||
    item.deadline_detected ||
    priority === 'P1' ||
    (priority === 'P2' && item.action_required !== false)
  );

  return {
    id: item.email_id || item.id || `real-${index}`,
    thread_id: item.thread_id || item.threadId || item.id,
    sender: senderDisplay,
    email: senderEmail || 'user@example.com',
    recipients: item.recipients || 'me',
    initials,
    avatarBg: 'bg-zinc-200/80 text-zinc-700',
    subject: item.subject || '(No Subject)',
    time,
    fullDate,
    date: item.date,
    timestamp,
    daysAgo,
    unread: Boolean(item.is_unread || item.unread),
    analyzed: Boolean(item.predicted_priority || item.final_priority),
    priority,
    needsAttention,
    matched,
    note,
    otp,
    attachment,
    body: item.body || item.snippet || '',
    body_html: item.body_html || '',
    paragraphs: paragraphs.length ? paragraphs : ['(No message body)'],
    raw: item,
  };
}

export function getEmailCategory(item) {
  const text = `${item.subject || ''} ${item.sender || ''}`.toLowerCase();
  if (/offer|drop|price|sale|discount|deal|free|win|festive|reward|quiz|internship|hiring|coupon|promo/i.test(text)) {
    return 'promotions';
  }
  if (/quora|linkedin|twitter|facebook|connect|network|community|discussion|instagram|threads/i.test(text)) {
    return 'social';
  }
  if (
    item.priority === 'P3' ||
    /update|code|verify|digest|notification|security|system|admit|receipt|alert|statement|billing|invoice|github|gitlab|atcoder|codechef|leetcode/i.test(text)
  ) {
    return 'updates';
  }
  return 'primary';
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

  // Visual Layout & Navigation State
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [layoutMode, setLayoutMode] = useState('table'); // 'table' | 'split'
  const [view, setView] = useState('all'); // 'all' | 'attention' | 'recent'
  const [categoryTab, setCategoryTab] = useState('all'); // 'all' | 'primary' | 'promotions' | 'social' | 'updates'
  const [readingEmailId, setReadingEmailId] = useState(null); // when null: table view; when id: open email view
  const [selectedId, setSelectedId] = useState('e1');
  const [priorityFilter, setPriorityFilter] = useState(null); // null | 'P1' | 'P2' | 'P3' | 'P4'
  const [windowId, setWindowId] = useState('last_3_months');
  const [search, setSearch] = useState('');
  const [mobileReading, setMobileReading] = useState(false);

  // Synchronize windowId with emailsHook.analysisPeriod when restored
  useEffect(() => {
    if (emailsHook.analysisPeriod && emailsHook.analysisPeriod !== windowId) {
      if (WINDOWS.some((w) => w.id === emailsHook.analysisPeriod)) {
        setWindowId(emailsHook.analysisPeriod);
      }
    }
  }, [emailsHook.analysisPeriod, windowId]);

  // Checkbox selection & Starred State
  const [checkedIds, setCheckedIds] = useState(() => new Set());
  const [starredIds, setStarredIds] = useState(() => {
    try {
      const stored = localStorage.getItem('mailmind_starred_ids');
      return stored ? new Set(JSON.parse(stored)) : new Set(['e1', 'e3']);
    } catch {
      return new Set(['e1', 'e3']);
    }
  });

  // Triage and override maps
  const [statusMap, setStatusMap] = useState({}); // { [id]: { state: 'done' | 'snoozed', until?: string } }
  const [overridesMap, setOverridesMap] = useState({});

  // Floating Popovers & Feedback
  const [syncing, setSyncing] = useState(false);
  const [priorityMenuOpen, setPriorityMenuOpen] = useState(false);
  const [windowMenuOpen, setWindowMenuOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [selectMenuOpen, setSelectMenuOpen] = useState(false);
  const [copiedId, setCopiedId] = useState(null);
  const [toast, setToast] = useState(null);

  // Cache for full email details (MIME HTML body, complete headers)
  const [emailDetails, setEmailDetails] = useState({});
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [viewMode, setViewMode] = useState('rich'); // 'rich' | 'plain'

  const rootRef = useRef(null);

  // Save starred state
  useEffect(() => {
    try {
      localStorage.setItem('mailmind_starred_ids', JSON.stringify(Array.from(starredIds)));
    } catch {}
  }, [starredIds]);

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
        setWindowMenuOpen(false);
        setUserMenuOpen(false);
        setSelectMenuOpen(false);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  const closeAllMenus = () => {
    setPriorityMenuOpen(false);
    setWindowMenuOpen(false);
    setUserMenuOpen(false);
    setSelectMenuOpen(false);
  };

  // Active Window Cutoff
  const cutoffDays = useMemo(() => {
    return WINDOWS.find((w) => w.id === windowId)?.days ?? 90;
  }, [windowId]);

  // Attention Counter (global stats from backend or loaded items fallback)
  const attentionCount = useMemo(() => {
    if (view === 'attention' && emailsHook.pagination?.total_emails) {
      return emailsHook.pagination.total_emails;
    }
    if (emailsHook.stats?.needs_attention_count !== undefined && emailsHook.stats.needs_attention_count !== null) {
      return emailsHook.stats.needs_attention_count;
    }
    return emails.filter((e) => e.needsAttention && !statusMap[e.id]).length;
  }, [view, emailsHook.pagination?.total_emails, emailsHook.stats, emails, statusMap]);

  // Category Counts for Gmail Category Tabs
  const categoryCounts = useMemo(() => {
    let primary = 0;
    let updates = 0;
    let promotions = 0;
    let social = 0;

    emails.forEach((item) => {
      const cat = getEmailCategory(item);
      if (cat === 'promotions') {
        promotions++;
      } else if (cat === 'social') {
        social++;
      } else if (cat === 'updates') {
        updates++;
      } else {
        primary++;
      }
    });

    return { primary, updates, promotions, social };
  }, [emails]);

  // Filtered List Items (Meticulous Gmail Tab & Folder Filtering with Timeframe & Strict Time Sorting)
  const visibleEmails = useMemo(() => {
    const filtered = emails.filter((item) => {
      // 1. Timeframe window filter: strictly enforce "This month" or "Last 3 months" for demo items
      // For real synchronized emails, backend query already bounds internal_date strictly
      if (!item.raw && !isItemInWindow(item, windowId)) {
        return false;
      }

      // 2. View filtering
      if (view === 'attention') {
        if (!item.needsAttention) return false;
      } else if (view === 'recent') {
        if (item.daysAgo > 30) return false;
      }

      // 3. Category Tab Filtering (applies only in main mailbox view 'all')
      if (view === 'all' && categoryTab !== 'all') {
        const cat = getEmailCategory(item);
        if (cat !== categoryTab) {
          // Keep critical P1/P2 items in primary so they are never missed
          if (categoryTab === 'primary' && (item.priority === 'P1' || item.priority === 'P2')) {
            // Include in primary
          } else {
            return false;
          }
        }
      }

      if (priorityFilter) {
        if (!item.analyzed || item.priority !== priorityFilter) return false;
      }

      if (search.trim()) {
        const q = search.toLowerCase();
        return (
          item.sender.toLowerCase().includes(q) ||
          item.subject.toLowerCase().includes(q) ||
          (item.paragraphs?.[0] || '').toLowerCase().includes(q)
        );
      }

      return true;
    });

    // 4. Strict chronological sort by time (Newest first)
    return filtered.slice().sort((a, b) => {
      const getEmailTime = (em) => {
        if (!em) return 0;
        if (em.internal_date) {
          const val = Number(em.internal_date);
          if (!isNaN(val) && val > 0) return val > 1e11 ? val : val * 1000;
        }
        if (em.timestamp) {
          const val = Number(em.timestamp);
          if (!isNaN(val) && val > 0) return val;
        }
        if (em.date) {
          const parsed = new Date(em.date).getTime();
          if (!isNaN(parsed) && parsed > 0) return parsed;
        }
        if (em.daysAgo !== undefined) {
          return Date.now() - Number(em.daysAgo) * 86400000;
        }
        return 0;
      };
      return getEmailTime(b) - getEmailTime(a);
    });
  }, [emails, view, categoryTab, statusMap, starredIds, priorityFilter, search, windowId]);

  // Active email
  const currentEmail = useMemo(() => {
    const targetId = readingEmailId || selectedId;
    return (
      visibleEmails.find((e) => e.id === targetId) ||
      emails.find((e) => e.id === targetId) ||
      visibleEmails[0] ||
      null
    );
  }, [visibleEmails, emails, readingEmailId, selectedId]);

  const detailedEmail = currentEmail ? (emailDetails[currentEmail.id] || currentEmail) : null;
  const rawHtml = detailedEmail?.body_html || currentEmail?.body_html || '';
  const rawBody = detailedEmail?.body || currentEmail?.body || '';

  // On-demand fetch of complete MIME content & HTML body when email is selected or opened
  useEffect(() => {
    if (!currentEmail?.id) return;
    const emailId = currentEmail.id;

    // Skip mock static emails
    if (emailId.startsWith('e') && emailId.length <= 3) return;

    // If detail is already cached with full HTML or body, skip
    if (emailDetails[emailId]) return;

    let isMounted = true;
    setLoadingDetail(true);

    fetchEmailDetail(emailId)
      .then((res) => {
        if (!isMounted) return;
        if (res?.email) {
          setEmailDetails((prev) => ({
            ...prev,
            [emailId]: res.email,
          }));
        }
      })
      .catch((err) => {
        if (!isMounted) return;
        console.warn('Could not fetch email detail:', err);
      })
      .finally(() => {
        if (isMounted) setLoadingDetail(false);
      });

    return () => {
      isMounted = false;
    };
  }, [currentEmail?.id]);

  // ============================================================================
  // INTERACTIVE HANDLERS
  // ============================================================================

  const selectEmail = (item) => {
    setSelectedId(item.id);
    if (layoutMode === 'table') {
      setReadingEmailId(item.id);
    }
    setMobileReading(true);
    closeAllMenus();
  };

  const advanceSelection = (actingId) => {
    const idx = visibleEmails.findIndex((e) => e.id === actingId);
    if (idx === -1) return;
    const nextItem = visibleEmails[idx + 1] || visibleEmails[idx - 1];
    if (nextItem) {
      setSelectedId(nextItem.id);
      if (readingEmailId) setReadingEmailId(nextItem.id);
    }
  };

  const markDone = (item, e = null) => {
    if (e) e.stopPropagation();
    if (!item) return;
    const prev = statusMap[item.id];
    advanceSelection(item.id);
    setStatusMap((map) => ({ ...map, [item.id]: { state: 'done' } }));
    closeAllMenus();

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
    });
  };

  const restoreItem = (item, e = null) => {
    if (e) e.stopPropagation();
    if (!item) return;
    setStatusMap((map) => {
      const next = { ...map };
      delete next[item.id];
      return next;
    });
    if (item.raw?.email_id || item.raw?.id) {
      emailsHook.unresolveEmail?.(item.raw.email_id || item.raw.id);
    }
    triggerToast('Restored to inbox');
  };

  const toggleStarEmail = (id, e = null) => {
    if (e) e.stopPropagation();
    setStarredIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleCheckEmail = (id, e = null) => {
    if (e) e.stopPropagation();
    setCheckedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (checkedIds.size === visibleEmails.length && visibleEmails.length > 0) {
      setCheckedIds(new Set());
    } else {
      setCheckedIds(new Set(visibleEmails.map((e) => e.id)));
    }
  };

  const handleBatchDone = () => {
    if (checkedIds.size === 0) return;
    const ids = Array.from(checkedIds);
    setStatusMap((prev) => {
      const next = { ...prev };
      ids.forEach((id) => {
        next[id] = { state: 'done' };
      });
      return next;
    });
    ids.forEach((id) => {
      emailsHook.resolveEmail?.(id);
    });
    setCheckedIds(new Set());
    triggerToast(`Marked ${ids.length} email(s) as done`);
  };

  const handleCopyOtp = (code, id) => {
    if (!code) return;
    navigator.clipboard?.writeText(code);
    setCopiedId(id);
    triggerToast(`Copied ${code}`);
    setTimeout(() => {
      setCopiedId(null);
    }, 2000);
  };

  const changePriority = (item, newPriority) => {
    if (!item || !newPriority) return;
    setOverridesMap((prev) => ({
      ...prev,
      [item.id]: newPriority
    }));
    setPriorityMenuOpen(false);

    submitFeedback({
      message_id: item.raw?.email_id || item.id,
      suggested_priority: newPriority,
      comment: 'User UI priority refinement',
      original_priority: item.priority
    }).catch(() => {});

    triggerToast(`Priority changed to ${newPriority} · ${PRIORITIES[newPriority].name}`);
  };

  const selectWindow = (nextId) => {
    setWindowId(nextId);
    setWindowMenuOpen(false);
    setSyncing(true);

    if (emailsHook.changeAnalysisPeriod) {
      emailsHook.changeAnalysisPeriod(nextId);
    } else if (emailsHook.refresh) {
      emailsHook.refresh(nextId);
    }

    setTimeout(() => {
      setSyncing(false);
    }, 600);
  };

  // Next / Previous email in open view
  const currentIdx = visibleEmails.findIndex((e) => e.id === currentEmail?.id);
  const prevEmail = currentIdx > 0 ? visibleEmails[currentIdx - 1] : null;
  const nextEmail = currentIdx >= 0 && currentIdx < visibleEmails.length - 1 ? visibleEmails[currentIdx + 1] : null;

  // Render OAuth callback
  if (currentPath === '/auth/callback') {
    return <AuthCallback />;
  }

  // Calculate Gmail pagination and counts
  const inboxTotalCount = emailsHook.pagination?.total_emails || emails.length;
  const isPrioritySynced = !priorityFilter || emailsHook.activeFilter === priorityFilter;
  const isCustomFiltered = Boolean((view === 'all' && categoryTab !== 'all') || search.trim());
  const currentViewTotal = isCustomFiltered
    ? visibleEmails.length
    : (view === 'attention'
      ? (emailsHook.pagination?.total_emails || attentionCount || visibleEmails.length)
      : (emailsHook.pagination?.total_emails || visibleEmails.length));

  const currentPage = emailsHook.pagination?.page || 1;
  const pageSize = emailsHook.pagination?.page_size || 50;
  const startNum = visibleEmails.length === 0 ? 0 : ((currentPage - 1) * pageSize) + 1;
  const endNum = visibleEmails.length === 0 ? 0 : Math.min(startNum + visibleEmails.length - 1, currentViewTotal);
  const hasNextPage = (!isCustomFiltered && isPrioritySynced) ? Boolean(emailsHook.pagination?.has_next) : false;

  const activeWindowLabel = WINDOWS.find((w) => w.id === windowId)?.label || 'Last 3 months';
  const currentPriority = currentEmail ? (PRIORITIES[currentEmail.priority] || PRIORITIES.P3) : null;
  const currentTriage = currentEmail ? statusMap[currentEmail.id] : null;

  const userName = auth.user?.name || auth.user?.email?.split('@')[0] || 'User';
  const userInitials = auth.user?.name ? getSenderInitials(auth.user.name) : 'BK';

  return (
    <div
      ref={rootRef}
      onClick={closeAllMenus}
      className={`h-screen w-full overflow-hidden flex flex-col relative select-none transition-colors duration-200 ${
        dark ? 'bg-[#10141D] text-[#F8FAFC]' : 'bg-[#EEF2F7] text-[#1E1231]'
      }`}
    >
      {/* Sleek 2.5px Top Sync Progress Line - Deep Aubergine to Radiant Marigold to Ice Silver */}
      <div className="fixed top-0 left-0 right-0 h-[2.5px] z-50 pointer-events-none overflow-hidden">
        <div
          className={`h-full bg-gradient-to-r from-[#581C87] via-[#F59E0B] to-[#CBD5E1] transition-all duration-500 ease-out ${
            syncing ? 'w-full opacity-100' : 'w-0 opacity-0'
          }`}
        />
      </div>

      {/* ==================================================================== */}
      {/* TOP BAR: CLASSY HEADER WITH EXPANSIVE PILL SEARCH, LOGO, USER AVATAR */}
      {/* ==================================================================== */}
      <header
        className={`h-16 px-4 sm:px-6 flex items-center justify-between border-b shrink-0 z-20 backdrop-blur-md transition-colors duration-200 ${
          dark
            ? 'bg-[#181D29]/95 border-[#2D3648] text-[#F8FAFC]'
            : 'bg-[#F5F8FC]/90 border-[#CBD5E1] text-[#1E1231] shadow-[0_1px_3px_rgba(88,28,135,0.03)]'
        }`}
      >
        {/* Left: Hamburger + Logo */}
        <div className="flex items-center gap-3 w-56 shrink-0">
          <button
            onClick={() => setSidebarOpen((o) => !o)}
            className={`p-2 rounded-full transition cursor-pointer hover:scale-105 active:scale-95 ${
              dark
                ? 'text-[#CBD5E1] hover:text-white hover:bg-[#202737]'
                : 'text-[#4D3A5B] hover:text-[#581C87] hover:bg-white hover:shadow-xs'
            }`}
            title="Main menu"
          >
            <Menu className="w-5 h-5" />
          </button>

          <div
            onClick={() => {
              setReadingEmailId(null);
              setView('all');
              setCategoryTab('all');
              setPriorityFilter(null);
              emailsHook.setActiveFilter?.('ALL');
            }}
            className="flex items-center gap-2.5 font-semibold text-lg tracking-tight cursor-pointer"
          >
            <BrandMark />
            <span className={`font-bold tracking-tight text-lg ${dark ? 'text-[#F8FAFC]' : 'text-[#2E084D]'}`}>
              MailMind<span className="text-[#F59E0B] ml-0.5">•</span>
            </span>
          </div>
        </div>

        {/* Center: Expansive Rounded Pill Search Bar */}
        <div className="flex-1 max-w-2xl px-2 sm:px-6">
          <div
            className={`flex items-center h-11 px-4 rounded-full transition-all border ${
              dark
                ? 'bg-[#141822] border-[#2D3648] focus-within:bg-[#181D29] focus-within:border-[#F59E0B] focus-within:ring-2 focus-within:ring-[#F59E0B]/25 focus-within:shadow-md'
                : 'bg-white border-[#CBD5E1] hover:border-[#94A3B8] focus-within:bg-white focus-within:border-[#581C87] focus-within:ring-2 focus-within:ring-[#581C87]/15 focus-within:shadow-[0_2px_12px_rgba(88,28,135,0.08)]'
            }`}
          >
            <Search className={`w-4 h-4 shrink-0 mr-3 ${dark ? 'text-[#94A3B8]' : 'text-[#581C87]'}`} />
            <input
              type="text"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                emailsHook.setSearchQuery?.(e.target.value);
              }}
              placeholder="Search in emails..."
              className={`w-full bg-transparent text-[13.5px] focus:outline-none ${
                dark
                  ? 'text-[#F8FAFC] placeholder-[#94A3B8]'
                  : 'text-[#1E1231] placeholder-[#786B84]'
              }`}
            />
            {search ? (
              <button
                onClick={() => setSearch('')}
                className={`p-1 transition ${dark ? 'text-[#94A3B8] hover:text-white' : 'text-[#786B84] hover:text-[#1E1231]'}`}
              >
                <X className="w-4 h-4" />
              </button>
            ) : (
              <button
                title="Search options"
                className={`p-1 transition ${dark ? 'text-[#94A3B8] hover:text-white' : 'text-[#786B84] hover:text-[#1E1231]'}`}
              >
                <SlidersHorizontal className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>

        {/* Right: Quick Controls + User Profile */}
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={() => emailsHook.refresh?.(windowId)}
            className={`p-2 rounded-full transition cursor-pointer hover:scale-105 active:scale-95 ${
              dark
                ? 'text-[#CBD5E1] hover:text-white hover:bg-[#202737]'
                : 'text-[#4D3A5B] hover:text-[#581C87] hover:bg-white hover:shadow-xs'
            }`}
            title="Sync mailbox"
          >
            <RefreshCw className={`w-4 h-4 ${syncing ? 'animate-spin text-[#F59E0B]' : ''}`} />
          </button>

          <button
            onClick={() => setDark((d) => !d)}
            className={`p-2 rounded-full transition cursor-pointer hover:scale-105 active:scale-95 ${
              dark
                ? 'text-[#CBD5E1] hover:text-[#F59E0B] hover:bg-[#202737]'
                : 'text-[#4D3A5B] hover:text-[#581C87] hover:bg-white hover:shadow-xs'
            }`}
            title={dark ? 'Switch to light mode' : 'Switch to dark mode'}
          >
            {dark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4 text-[#581C87]" />}
          </button>

          {/* User Profile Avatar Dropdown */}
          <div className="relative ml-2" onClick={(e) => e.stopPropagation()}>
            {auth.isAuthenticated ? (
              <button
                onClick={() => {
                  setUserMenuOpen((o) => !o);
                  setWindowMenuOpen(false);
                }}
                className={`w-8 h-8 rounded-full text-xs font-bold flex items-center justify-center shrink-0 ring-2 cursor-pointer transition ${
                  dark
                    ? 'bg-gradient-to-br from-[#2E084D] to-[#120420] text-[#F8FAFC] ring-[#F59E0B] hover:ring-[#FBBF24]'
                    : 'bg-gradient-to-br from-[#2E084D] to-[#1A042D] text-white ring-[#F59E0B] hover:ring-[#D97706] shadow-sm'
                }`}
                title={auth.user?.email || 'Active Account'}
              >
                {userInitials}
              </button>
            ) : (
              <button
                onClick={() => auth.devLogin ? auth.devLogin() : auth.login()}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold bg-gradient-to-r from-[#2E084D] to-[#581C87] hover:from-[#3B0A63] hover:to-[#6B21A8] text-white shadow-sm border border-[#7E22CE]/40 transition cursor-pointer"
                title="Connect your Gmail account"
              >
                <span>Connect Gmail</span>
              </button>
            )}

            {userMenuOpen && auth.isAuthenticated && (
              <div
                className={`absolute right-0 top-11 w-56 rounded-2xl p-2 shadow-xl border z-50 ${
                  dark
                    ? 'bg-[#1E0F2B] border-[#361A4B] text-[#F8FAFC]'
                    : 'bg-[#FFFFFF] border-[#E2E8F0] text-[#1D0B2B]'
                }`}
              >
                <div className="px-3 py-2 border-b border-[#361A4B]/40 dark:border-[#361A4B] mb-1">
                  <p className="text-xs font-semibold truncate">{userName}</p>
                  <p className="text-[11px] text-[#94A3B8] dark:text-[#94A3B8] truncate">{auth.user?.email || 'Connected'}</p>
                </div>
                <button
                  onClick={() => {
                    setUserMenuOpen(false);
                    auth.logout();
                  }}
                  className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-xs transition cursor-pointer ${
                    dark
                      ? 'hover:bg-[#281438] text-rose-400'
                      : 'hover:bg-[#EDF2F7] text-rose-600'
                  }`}
                >
                  <LogOut className="w-4 h-4" />
                  <span>Sign out</span>
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* ==================================================================== */}
      {/* MAIN CONTAINER: SIDEBAR + CONTENT AREA                                */}
      {/* ==================================================================== */}
      <div className="flex-1 flex overflow-hidden">
        {/* ================================================================== */}
        {/* LEFT SIDEBAR (GMAIL STYLE RAIL & LABELS)                           */}
        {/* ================================================================== */}
        <aside
          className={`${
            sidebarOpen ? 'w-60' : 'w-16'
          } hidden md:flex flex-col justify-between shrink-0 border-r py-3 transition-all duration-200 ${
            dark
              ? 'bg-[#141822] border-[#252D3C]'
              : 'bg-[#F5F8FC]/80 backdrop-blur-md border-[#CBD5E1]'
          }`}
        >
          <div className="space-y-3 px-3">
            {/* Primary Views */}
            <nav className="space-y-1">
              {[
                { id: 'all', label: 'Inbox', icon: Inbox, count: inboxTotalCount },
                { id: 'attention', label: 'Needs Attention', icon: AlertCircle, count: attentionCount },
                { id: 'recent', label: 'Recent Mail', icon: Clock, count: null }
              ].map((nav) => {
                const active = view === nav.id;
                const IconComponent = nav.icon;
                return (
                  <button
                    key={nav.id}
                    onClick={() => {
                      setView(nav.id);
                      setReadingEmailId(null);
                      setMobileReading(false);
                      setPriorityFilter(null);
                      if (nav.id === 'all') {
                        setCategoryTab('all');
                        emailsHook.setActiveFilter?.('ALL');
                      } else if (nav.id === 'attention') {
                        setCategoryTab('all');
                        emailsHook.setActiveFilter?.('NEEDS_ATTENTION');
                      } else if (nav.id === 'recent') {
                        setCategoryTab('all');
                        emailsHook.setActiveFilter?.('ALL');
                      }
                    }}
                    className={`w-full flex items-center justify-between py-2 rounded-xl text-[13.5px] transition cursor-pointer ${
                      sidebarOpen ? 'pl-3.5 pr-3' : 'px-2 justify-center'
                    } ${
                      active
                        ? dark
                          ? 'bg-[#2E1A40] text-[#F8FAFC] font-semibold border-l-4 border-[#F59E0B] shadow-sm'
                          : 'bg-white text-[#3B0764] font-bold shadow-sm border border-[#E2E8F0] shadow-[0_2px_8px_rgba(88,28,135,0.06)] ring-1 ring-[#581C87]/10'
                        : dark
                        ? 'text-[#CBD5E1] hover:text-white hover:bg-[#202737]'
                        : 'text-[#524365] hover:text-[#2E084D] hover:bg-white/70 hover:shadow-xs'
                    }`}
                    title={nav.label}
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      {active && !dark && (
                        <span className="w-1.5 h-4.5 rounded-full bg-gradient-to-b from-[#F59E0B] to-[#D97706] shadow-[0_0_8px_rgba(245,158,11,0.5)] shrink-0" />
                      )}
                      <IconComponent
                        className={`w-4 h-4 shrink-0 transition-colors ${
                          active
                            ? dark ? 'text-[#F59E0B]' : 'text-[#581C87]'
                            : dark ? 'text-[#94A3B8]' : 'text-[#716080]'
                        }`}
                      />
                      {sidebarOpen && <span className="truncate">{nav.label}</span>}
                    </div>

                    {sidebarOpen && nav.count > 0 && (
                      <span
                        className={`text-xs tabular-nums font-bold px-2 py-0.5 rounded-full transition-colors ${
                          active
                            ? dark
                              ? 'bg-[#F59E0B] text-[#1E082B] shadow-sm'
                              : 'bg-[#F59E0B]/20 text-[#B45309] border border-[#F59E0B]/35 shadow-xs'
                            : dark
                            ? 'text-[#94A3B8] bg-[#22293A]'
                            : 'text-[#64748B] bg-[#E2E8F0]/80'
                        }`}
                      >
                        {nav.count.toLocaleString()}
                      </span>
                    )}
                  </button>
                );
              })}
            </nav>

            {/* Priority Section */}
            {sidebarOpen && (
              <div className="pt-3 border-t border-[#CBD5E1] dark:border-[#361A4B]">
                <div className="px-3 pb-1.5 text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider">
                  Priority
                </div>
                {Object.values(PRIORITIES).map((tier) => {
                  const active = priorityFilter === tier.id;
                  return (
                    <button
                      key={tier.id}
                      onClick={() => {
                        const nextPriority = priorityFilter === tier.id ? null : tier.id;
                        setPriorityFilter(nextPriority);
                        setCategoryTab('all');
                        setReadingEmailId(null);
                        emailsHook.setActiveFilter?.(nextPriority || 'ALL');
                      }}
                      className={`w-full flex items-center justify-between px-3 py-1.5 rounded-xl text-[13px] transition cursor-pointer ${
                        active
                          ? dark
                            ? 'bg-[#2E1A40] text-[#F8FAFC] font-semibold'
                            : 'bg-white text-[#3B0764] font-semibold shadow-xs border border-[#E2E8F0]'
                          : dark
                          ? 'text-[#CBD5E1] hover:text-white hover:bg-[#202737]'
                          : 'text-[#524365] hover:text-[#2E084D] hover:bg-white/60'
                      }`}
                    >
                      <span className="flex items-center gap-2.5">
                        <span
                          className="w-2 h-2 rounded-full shrink-0 shadow-sm"
                          style={{ backgroundColor: tier.color }}
                        />
                        <span>{tier.name}</span>
                      </span>
                      {active && (
                        <span className="text-[11px] text-[#F59E0B] hover:text-[#D97706] font-bold">Clear</span>
                      )}
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* Footer of Sidebar: Timeframe Selector */}
          {sidebarOpen && (
            <div className="px-3 pt-3 border-t border-[#CBD5E1] dark:border-[#252D3C]">
              <div className="relative" onClick={(e) => e.stopPropagation()}>
                <button
                  onClick={() => {
                    setWindowMenuOpen((o) => !o);
                    setUserMenuOpen(false);
                  }}
                  className={`w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs transition cursor-pointer border ${
                    dark
                      ? 'text-[#CBD5E1] hover:text-white hover:bg-[#202737] border-[#2D3648]'
                      : 'bg-white/70 hover:bg-white text-[#4D3A5B] hover:text-[#2E084D] hover:border-[#94A3B8] border-[#CBD5E1] shadow-xs hover:shadow-sm'
                  }`}
                >
                  <span className="flex items-center gap-2">
                    <RefreshCw className={`w-3.5 h-3.5 ${syncing ? 'animate-spin text-[#F59E0B]' : 'text-[#F59E0B]'}`} />
                    <span className="font-medium">{activeWindowLabel}</span>
                  </span>
                  <ChevronDown className="w-3.5 h-3.5 opacity-60" />
                </button>

                {windowMenuOpen && (
                  <div
                    className={`absolute bottom-11 left-0 w-48 rounded-2xl p-1.5 shadow-xl border z-50 ${
                      dark
                        ? 'bg-[#181D29] border-[#2D3648] text-[#F8FAFC]'
                        : 'bg-white/95 backdrop-blur-md border-[#CBD5E1] shadow-xl text-[#1E1231]'
                    }`}
                  >
                    {WINDOWS.map((w) => (
                      <button
                        key={w.id}
                        onClick={() => selectWindow(w.id)}
                        className={`w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs transition cursor-pointer ${
                          windowId === w.id
                            ? dark
                              ? 'bg-[#2E1A40] font-semibold text-[#F8FAFC]'
                              : 'bg-[#581C87]/10 font-bold text-[#3B0764] border border-[#581C87]/15'
                            : dark
                            ? 'hover:bg-[#202737] text-[#CBD5E1]'
                            : 'hover:bg-[#F1F5F9] text-[#4D3A5B] hover:text-[#1E1231]'
                        }`}
                      >
                        <span>{w.label}</span>
                        {windowId === w.id && <Check className="w-3 h-3 text-[#F59E0B]" />}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </aside>

        {/* ================================================================== */}
        {/* MAIN MAILBOX WORKSPACE: TOOLBAR + TABS + TABLE ROWS OR READING PANE */}
        {/* ================================================================== */}
        <main
          className={`flex-1 flex flex-col overflow-hidden m-2 sm:m-3 rounded-2xl border shadow-sm transition-colors ${
            dark ? 'bg-[#181D29] border-[#2C3547]' : 'bg-[#FFFFFF] border-[#CBD5E1]/90 shadow-[0_2px_14px_rgba(88,28,135,0.04),0_1px_3px_rgba(0,0,0,0.03)]'
          }`}
        >
          {/* 1. ACTION TOOLBAR */}
          <div
            className={`h-12 px-4 flex items-center justify-between border-b shrink-0 text-xs backdrop-blur-sm ${
              dark ? 'bg-[#161B26]/90 border-[#252D3C]' : 'bg-[#FFFFFF]/95 border-[#E2E8F0]'
            }`}
          >
            {/* Left Controls: Checkbox Dropdown, Refresh, Batch Actions */}
            <div className="flex items-center gap-2">
              {readingEmailId ? (
                /* When in thread view: Back to inbox button */
                <button
                  onClick={() => setReadingEmailId(null)}
                  className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg font-medium transition cursor-pointer ${
                    dark
                      ? 'text-[#CBD5E1] hover:text-white hover:bg-[#202737]'
                      : 'text-[#4D3A5B] hover:text-[#581C87] hover:bg-[#F1F5F9]'
                  }`}
                >
                  <ArrowLeft className="w-4 h-4 text-[#F59E0B]" />
                  <span>Back to all mail</span>
                </button>
              ) : (
                <>
                  {/* Select All Checkbox */}
                  <button
                    onClick={toggleSelectAll}
                    className={`p-1.5 rounded-md transition cursor-pointer hover:scale-105 active:scale-95 ${
                      dark ? 'text-[#94A3B8] hover:text-white hover:bg-[#202737]' : 'text-[#64748B] hover:text-[#581C87] hover:bg-[#F1F5F9]'
                    }`}
                    title="Select all"
                  >
                    {checkedIds.size === visibleEmails.length && visibleEmails.length > 0 ? (
                      <CheckSquare className="w-4 h-4 text-[#F59E0B]" />
                    ) : checkedIds.size > 0 ? (
                      <MinusSquare className="w-4 h-4 text-[#F59E0B]" />
                    ) : (
                      <Square className="w-4 h-4" />
                    )}
                  </button>

                  <button
                    onClick={() => emailsHook.refresh?.(windowId)}
                    className={`p-1.5 rounded-md transition cursor-pointer hover:scale-105 active:scale-95 ${
                      dark ? 'text-[#94A3B8] hover:text-white hover:bg-[#202737]' : 'text-[#64748B] hover:text-[#581C87] hover:bg-[#F1F5F9]'
                    }`}
                    title="Refresh"
                  >
                    <RefreshCw className={`w-4 h-4 ${syncing ? 'animate-spin text-[#F59E0B]' : ''}`} />
                  </button>

                  {/* Batch actions when checkboxes selected */}
                  {checkedIds.size > 0 && (
                    <div className="flex items-center gap-2 ml-2 pl-3 border-l border-[#CBD5E1] dark:border-[#2D3648]">
                      <span className="font-semibold text-xs text-[#F59E0B]">
                        {checkedIds.size} selected
                      </span>

                      <button
                        onClick={() => setCheckedIds(new Set())}
                        className={`px-2 py-1 rounded-md text-xs font-medium transition ${
                          dark ? 'text-[#94A3B8] hover:text-white hover:bg-[#202737]' : 'text-[#64748B] hover:text-[#3B0764] hover:bg-[#F1F5F9]'
                        }`}
                      >
                        Clear
                      </button>
                    </div>
                  )}
                </>
              )}
            </div>

            {/* Right Controls: Pagination 1-50 of 7,044 + Arrow Navigation */}
            <div className="flex items-center gap-3">
              <span className={`tabular-nums ${dark ? 'text-[#94A3B8]' : 'text-[#64748B]'}`}>
                {startNum}–{endNum} of {currentViewTotal.toLocaleString()}
              </span>

              <div className="flex items-center gap-1">
                <button
                  disabled={currentPage <= 1 || !!readingEmailId}
                  onClick={() => emailsHook.setPage?.((p) => Math.max(1, p - 1))}
                  className={`p-1.5 rounded-md transition cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed hover:scale-105 active:scale-95 ${
                    dark ? 'hover:bg-[#202737] text-[#CBD5E1]' : 'hover:bg-[#F1F5F9] text-[#4D3A5B]'
                  }`}
                  title="Newer"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <button
                  disabled={!hasNextPage || !!readingEmailId}
                  onClick={() => emailsHook.setPage?.((p) => p + 1)}
                  className={`p-1.5 rounded-md transition cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed hover:scale-105 active:scale-95 ${
                    dark ? 'hover:bg-[#202737] text-[#CBD5E1]' : 'hover:bg-[#F1F5F9] text-[#4D3A5B]'
                  }`}
                  title="Older"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>

              {/* View Layout Toggle (Table vs Split View) */}
              <button
                onClick={() => {
                  setLayoutMode((m) => (m === 'table' ? 'split' : 'table'));
                  if (layoutMode === 'split') setReadingEmailId(null);
                }}
                className={`p-1.5 rounded-md transition cursor-pointer hover:scale-105 active:scale-95 ${
                  layoutMode === 'split'
                    ? 'bg-[#F59E0B]/15 text-[#92400E] border border-[#F59E0B]/30 font-semibold'
                    : dark
                    ? 'text-[#94A3B8] hover:bg-[#202737] hover:text-white'
                    : 'text-[#64748B] hover:bg-[#F1F5F9] hover:text-[#3B0764]'
                }`}
                title={layoutMode === 'split' ? 'Switch to Full Table View' : 'Switch to Split Reading View'}
              >
                <Columns className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* 2. CATEGORY TABS (Primary, Updates, Promotions, Social, All) - Shown in Main Inbox View */}
          {!readingEmailId && view === 'all' && (
            <div
              className={`flex items-center border-b shrink-0 px-2 sm:px-4 gap-1 ${
                dark ? 'bg-[#161B26] border-[#252D3C]' : 'bg-[#FFFFFF] border-[#E2E8F0]'
              }`}
            >
              {[
                { id: 'primary', label: 'Primary', icon: Inbox, count: categoryCounts.primary },
                { id: 'promotions', label: 'Promotions', icon: Tag, count: categoryCounts.promotions },
                { id: 'social', label: 'Social', icon: Users, count: categoryCounts.social },
                { id: 'updates', label: 'Updates', icon: Info, count: categoryCounts.updates },
                { id: 'all', label: 'All', icon: Archive, count: inboxTotalCount }
              ].map((tab) => {
                const active = categoryTab === tab.id;
                const IconComponent = tab.icon;
                return (
                  <button
                    key={tab.id}
                    onClick={() => setCategoryTab(tab.id)}
                    className={`group flex items-center gap-2 px-3 sm:px-5 py-2.5 text-[13.5px] font-medium transition cursor-pointer border-b-2 -mb-[1px] rounded-t-xl ${
                      active
                        ? dark
                          ? 'border-[#F59E0B] text-[#FBBF24] font-bold bg-[#F59E0B]/5'
                          : 'border-[#581C87] text-[#3B0764] font-bold bg-[#581C87]/6 shadow-[inset_0_-2px_0_0_#581C87]'
                        : dark
                        ? 'border-transparent text-[#94A3B8] hover:text-white hover:bg-[#202737]'
                        : 'border-transparent text-[#64748B] hover:text-[#3B0764] hover:bg-[#F1F5F9]'
                    }`}
                  >
                    <IconComponent
                      className={`w-4 h-4 shrink-0 transition-colors ${
                        active
                          ? dark ? 'text-[#F59E0B]' : 'text-[#581C87]'
                          : dark ? 'text-[#94A3B8] group-hover:text-white' : 'text-[#94A3B8] group-hover:text-[#581C87]'
                      }`}
                    />
                    <span>{tab.label}</span>
                    {tab.count > 0 && (
                      <span
                        className={`text-xs tabular-nums px-2 py-0.5 rounded-full font-bold transition-all ${
                          active
                            ? dark
                              ? 'bg-[#F59E0B] text-[#1E082B] shadow-sm'
                              : 'bg-[#581C87] text-white shadow-xs'
                            : dark
                            ? 'bg-[#252D3C] text-[#94A3B8]'
                            : 'bg-[#F1F5F9] text-[#64748B] border border-[#E2E8F0] group-hover:border-[#CBD5E1]'
                        }`}
                      >
                        {tab.count.toLocaleString()}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          )}

          {/* NEEDS ATTENTION QUEUE HEADER BANNER */}
          {!readingEmailId && view === 'attention' && (
            <div
              className={`flex items-center justify-between border-b shrink-0 px-4 py-2.5 ${
                dark ? 'bg-[#1C1327] border-[#2D1B3E]' : 'bg-[#FAF5FF] border-[#E9D5FF]'
              }`}
            >
              <div className="flex items-center gap-2.5">
                <AlertCircle className="w-4 h-4 text-[#F59E0B]" />
                <span className={`text-xs font-bold ${dark ? 'text-[#F8FAFC]' : 'text-[#581C87]'}`}>
                  Needs Attention Priority Queue
                </span>
                <span className="text-[11px] text-[#94A3B8]">
                  · Operational alerts, tasks requiring action, and upcoming deadlines
                </span>
              </div>
              <span className={`text-xs font-bold px-2.5 py-0.5 rounded-full ${dark ? 'bg-[#F59E0B]/20 text-[#FBBF24]' : 'bg-[#581C87]/10 text-[#581C87]'}`}>
                {currentViewTotal.toLocaleString()} items
              </span>
            </div>
          )}

          {/* RECENT MAIL HEADER BANNER */}
          {!readingEmailId && view === 'recent' && (
            <div
              className={`flex items-center justify-between border-b shrink-0 px-4 py-2.5 ${
                dark ? 'bg-[#181D29] border-[#252D3C]' : 'bg-[#F1F5F9] border-[#CBD5E1]'
              }`}
            >
              <div className="flex items-center gap-2.5">
                <Clock className="w-4 h-4 text-[#F59E0B]" />
                <span className={`text-xs font-bold ${dark ? 'text-[#F8FAFC]' : 'text-[#3B0764]'}`}>
                  Recent Mail
                </span>
                <span className="text-[11px] text-[#94A3B8]">
                  · Synced messages from the last 30 days
                </span>
              </div>
            </div>
          )}

          {/* Offline / Backend Unreachable Banner */}
          {emailsHook.isOfflineMode && (
            <div className={`mx-4 mt-2 mb-1 px-4 py-2.5 rounded-xl text-xs flex items-center justify-between border ${
              dark ? 'bg-amber-500/10 border-amber-500/20 text-amber-400' : 'bg-amber-50 border-amber-200 text-amber-800'
            }`}>
              <div className="flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0 text-amber-500" />
                <span>Backend server unreachable at http://127.0.0.1:8000. Displaying cached local emails.</span>
              </div>
              <button
                onClick={() => emailsHook.refresh?.()}
                className="underline hover:opacity-80 font-medium cursor-pointer"
              >
                Retry Connection
              </button>
            </div>
          )}

          {/* 3. MAIL CONTENT: TABLE VIEW vs FULL THREAD VIEW vs SPLIT VIEW */}
          <div className="flex-1 flex overflow-hidden">
            {/* EMAIL LIST TABLE (Shown when not reading in table mode, or in split mode) */}
            {(!readingEmailId || layoutMode === 'split') && (
              <div
                className={`flex-1 flex flex-col overflow-y-auto ${
                  layoutMode === 'split' ? 'w-full md:w-[420px] lg:w-[480px] shrink-0 border-r' : 'w-full'
                } ${dark ? 'border-[#2D153E]' : 'border-[#E2E8F0]'}`}
              >
                {visibleEmails.length === 0 ? (
                  <div className="flex-1 flex flex-col items-center justify-center p-12 text-center text-[#94A3B8]">
                    <Inbox className="w-12 h-12 stroke-[1.2] mb-3 opacity-40 text-[#7E22CE]" />
                    <p className="text-sm font-semibold text-[#CBD5E1] dark:text-[#CBD5E1]">All caught up</p>
                    <p className="text-xs text-[#94A3B8] mt-1">No messages match the active view or filter</p>
                  </div>
                ) : (
                  visibleEmails.map((item) => {
                    const isSelected = (readingEmailId || selectedId) === item.id;
                    const isChecked = checkedIds.has(item.id);
                    const isStarred = starredIds.has(item.id);
                    const tier = PRIORITIES[item.priority] || PRIORITIES.P3;

                    return (
                      <div
                        key={item.id}
                        onClick={() => selectEmail(item)}
                        className={`group flex items-center h-10 sm:h-11 px-3 sm:px-4 border-b transition-all duration-150 cursor-pointer text-[13px] sm:text-[13.5px] select-none relative ${
                          isSelected && layoutMode === 'split'
                            ? dark ? 'bg-[#2E1A40] shadow-[inset_3.5px_0_0_0_#F59E0B]' : 'bg-[#FAF5FF] shadow-[inset_3.5px_0_0_0_#581C87] border-[#DDD6FE]'
                            : isChecked
                            ? dark ? 'bg-[#242B3D]' : 'bg-[#F5F3FF] border-[#DDD6FE]'
                            : item.unread
                            ? dark ? 'bg-[#181D29] hover:bg-[#202737]' : 'bg-[#FFFFFF] hover:bg-[#F3F7FC] hover:shadow-[0_2px_8px_rgba(88,28,135,0.05)] hover:z-10'
                            : dark ? 'bg-[#141822] hover:bg-[#1C2230]' : 'bg-[#FAFCFE] hover:bg-[#F3F7FC] hover:shadow-[0_2px_8px_rgba(88,28,135,0.05)] hover:z-10'
                        } ${dark ? 'border-[#22293A]' : 'border-[#EBF0F5]'}`}
                      >
                        {/* Checkbox column */}
                        <button
                          onClick={(e) => toggleCheckEmail(item.id, e)}
                          className="p-1 -ml-1 transition shrink-0 cursor-pointer hover:scale-110 active:scale-95 duration-150"
                          title="Select"
                        >
                          {isChecked ? (
                            <CheckSquare className="w-4 h-4 text-[#F59E0B] drop-shadow-[0_0_4px_rgba(245,158,11,0.35)]" />
                          ) : (
                            <Square className={`w-4 h-4 transition-colors ${dark ? 'text-[#64748B] hover:text-[#CBD5E1]' : 'text-[#94A3B8] hover:text-[#581C87]'}`} />
                          )}
                        </button>

                        {/* Star column */}
                        <button
                          onClick={(e) => toggleStarEmail(item.id, e)}
                          className="p-1 transition shrink-0 cursor-pointer hover:scale-125 active:scale-95 duration-150"
                          title={isStarred ? "Starred" : "Not starred"}
                        >
                          <Star className={`w-4 h-4 transition ${isStarred ? "fill-[#F59E0B] text-[#F59E0B] drop-shadow-[0_0_6px_rgba(245,158,11,0.55)]" : dark ? "text-[#64748B] hover:text-[#F59E0B]" : "text-[#CBD5E1] hover:text-[#F59E0B]"}`} />
                        </button>

                        {/* Priority indicator dot */}
                        <span
                          className="w-2 h-2 rounded-full shrink-0 ml-1 mr-3 shadow-xs group-hover:scale-125 transition-transform duration-150"
                          style={{ backgroundColor: tier.color }}
                          title={`${tier.id} · ${tier.name}`}
                        />

                        {/* Sender Column */}
                        <div
                          className={`${
                            layoutMode === 'split' ? 'w-28 sm:w-36' : 'w-36 sm:w-48 lg:w-56'
                          } shrink-0 truncate pr-2 sm:pr-3 transition-colors ${
                            item.unread
                              ? dark ? 'font-bold text-[#F8FAFC]' : 'font-bold text-[#1E1231]'
                              : dark ? 'font-normal text-[#CBD5E1]' : 'font-medium text-[#4D3A5B]'
                          }`}
                        >
                          {item.sender}
                        </div>

                        {/* Subject & Snippet Column */}
                        <div className="flex-1 min-w-0 flex items-center gap-1.5 truncate pr-3">
                          <span
                            className={`shrink-0 truncate max-w-[50%] transition-colors ${
                              item.unread
                                ? dark ? 'font-bold text-[#F8FAFC]' : 'font-bold text-[#1E1231]'
                                : dark ? 'font-normal text-[#CBD5E1]' : 'font-medium text-[#2E1840]'
                            }`}
                          >
                            {item.subject}
                          </span>
                          <span className={`shrink-0 ${dark ? 'text-[#64748B]' : 'text-[#CBD5E1]'}`}>—</span>
                          <span className={`truncate text-xs sm:text-[13px] ${
                            dark ? 'text-[#94A3B8]' : 'text-[#6B5E78]'
                          }`}>
                            {item.paragraphs?.[0] || item.snippet || ''}
                          </span>

                          {/* Inline Tag Chips: OTP, Attachment */}
                          {item.otp && (
                            <span className="ml-2 shrink-0 px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-[#FEF3C7] text-[#92400E] border border-[#FCD34D] shadow-xs">
                              OTP: {item.otp}
                            </span>
                          )}
                          {item.attachment && (
                            <Paperclip className={`w-3.5 h-3.5 shrink-0 ml-1 ${dark ? 'text-[#94A3B8]' : 'text-[#64748B]'}`} />
                          )}
                        </div>

                        {/* Timestamp & Hover Actions (Right Edge) */}
                        <div className="relative shrink-0 flex items-center justify-end w-24">
                          {/* Timestamp */}
                          <span
                            className={`text-xs tabular-nums text-right group-hover:hidden ${
                              item.unread
                                ? dark ? 'font-bold text-[#F8FAFC]' : 'font-bold text-[#1E1231]'
                                : dark ? 'text-[#94A3B8]' : 'text-[#716080]'
                            }`}
                          >
                            {item.time}
                          </span>

                          {/* Floating Hover Quick Actions */}
                          <div
                            onClick={(e) => e.stopPropagation()}
                            className={`hidden group-hover:flex items-center gap-1 ${
                              dark ? 'bg-[#202737] border border-[#2D3648]' : 'bg-white/95 backdrop-blur-xs border border-[#CBD5E1] shadow-sm'
                            } px-1.5 py-0.5 rounded-lg`}
                          >
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                triggerToast('Snoozed for 3 hours');
                              }}
                              title="Snooze"
                              className={`p-1 rounded-md transition cursor-pointer hover:scale-110 active:scale-95 ${
                                dark ? 'text-[#94A3B8] hover:text-[#F59E0B] hover:bg-[#2D3648]' : 'text-[#64748B] hover:text-[#581C87] hover:bg-[#581C87]/10'
                              }`}
                            >
                              <Clock className="w-3.5 h-3.5" />
                            </button>
                            <a
                              href={`https://mail.google.com/mail/u/0/#inbox/${item.thread_id || item.id}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              title="Open in Gmail"
                              className={`p-1 rounded-md transition cursor-pointer hover:scale-110 active:scale-95 ${
                                dark ? 'text-[#94A3B8] hover:text-[#F59E0B] hover:bg-[#2D3648]' : 'text-[#64748B] hover:text-[#581C87] hover:bg-[#581C87]/10'
                              }`}
                            >
                              <ExternalLink className="w-3.5 h-3.5" />
                            </a>
                          </div>
                        </div>
                      </div>
                    );
                  })
                )}

                {/* Bottom Pagination Button */}
                {hasNextPage && (
                  <div className="p-4 text-center">
                    <button
                      onClick={async () => {
                        try {
                          const count = await emailsHook.loadMore?.();
                          if (count > 0) {
                            triggerToast(`Loaded ${count} older emails`);
                          } else {
                            triggerToast('All available emails loaded');
                          }
                        } catch {
                          triggerToast('Failed to load more emails');
                        }
                      }}
                      disabled={emailsHook.isLoadingMore}
                      className={`inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-semibold transition cursor-pointer shadow-sm border ${
                        dark
                          ? 'bg-[#241232] text-[#F8FAFC] border-[#3B1E52] hover:bg-[#2E163F] hover:border-[#F59E0B]/40 disabled:opacity-50'
                          : 'bg-[#FFFFFF] text-[#1D0B2B] border-[#CBD5E1] hover:bg-[#F8FAFC] hover:border-[#7E22CE]/40 disabled:opacity-50'
                      }`}
                    >
                      {emailsHook.isLoadingMore ? (
                        <>
                          <RefreshCw className="w-3.5 h-3.5 animate-spin text-[#F59E0B]" />
                          <span>Loading more emails...</span>
                        </>
                      ) : (
                        <span>Load more emails</span>
                      )}
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* OPEN EMAIL READING CANVAS */}
            {(readingEmailId || layoutMode === 'split') && (
              <div
                className={`flex-1 flex flex-col overflow-y-auto ${
                  dark ? 'bg-[#140A1D]' : 'bg-[#FFFFFF]'
                }`}
              >
                {currentEmail ? (
                  <>
                    {/* Action Header Strip for Email */}
                    <div
                      className={`h-12 px-6 flex items-center justify-between border-b shrink-0 ${
                        dark ? 'bg-[#1A0C24]/80 border-[#2D153E]' : 'bg-[#F8FAFC] border-[#E2E8F0]'
                      }`}
                    >
                      {/* Left: Priority Badge Popover + View Toggle */}
                      <div className="flex items-center gap-3">
                        <div className="relative" onClick={(e) => e.stopPropagation()}>
                          <button
                            onClick={() => {
                              setPriorityMenuOpen((o) => !o);
                            }}
                            className={`inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold transition cursor-pointer border ${
                              dark
                                ? 'bg-[#281438] text-[#F8FAFC] border-[#3B1E52] hover:bg-[#341A49]'
                                : 'bg-[#FFFFFF] text-[#1D0B2B] border-[#CBD5E1] hover:bg-[#F1F5F9]'
                            }`}
                          >
                            <span
                              className="w-2 h-2 rounded-full shadow-sm"
                              style={{ backgroundColor: currentPriority?.color }}
                            />
                            <span>{currentPriority?.id} · {currentPriority?.name}</span>
                            <ChevronDown className="w-3 h-3 opacity-60" />
                          </button>

                          {priorityMenuOpen && (
                            <div
                              className={`absolute left-0 top-9 z-50 w-64 rounded-2xl p-3 shadow-xl border space-y-3 ${
                                dark
                                  ? 'bg-[#1E0F2B] border-[#361A4B] text-[#F8FAFC]'
                                  : 'bg-[#FFFFFF] border-[#E2E8F0] text-[#1D0B2B]'
                              }`}
                            >
                              <div className="text-xs space-y-1">
                                <p>Matched: <span className="text-[#F59E0B] font-medium">{currentEmail.matched}</span></p>
                                {currentEmail.note && <p className="text-[#94A3B8]">{currentEmail.note}</p>}
                              </div>
                              <div className="pt-2 border-t grid grid-cols-4 gap-1 border-[#361A4B] dark:border-[#361A4B]">
                                {Object.values(PRIORITIES).map((tier) => (
                                  <button
                                    key={tier.id}
                                    onClick={() => changePriority(currentEmail, tier.id)}
                                    className={`py-1.5 rounded-lg text-xs font-semibold flex items-center justify-center gap-1 transition ${
                                      currentEmail.priority === tier.id
                                        ? dark ? 'bg-[#341A49] text-white border border-[#7E22CE]/50' : 'bg-[#EDE9FE] text-[#2E103F] border border-[#7E22CE]/30'
                                        : dark ? 'hover:bg-[#281438] text-[#94A3B8]' : 'hover:bg-[#EDF2F7] text-[#64748B]'
                                    }`}
                                  >
                                    <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: tier.color }} />
                                    {tier.id}
                                  </button>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>

                        {/* Mode toggle (Rich HTML vs Text) */}
                        {rawHtml && (
                          <div className={`flex items-center p-0.5 rounded-lg border text-xs ${
                            dark ? 'border-[#361A4B] bg-[#180B23]' : 'border-[#E2E8F0] bg-[#F1F5F9]'
                          }`}>
                            <button
                              onClick={() => setViewMode('rich')}
                              className={`px-2.5 py-1 rounded-md font-semibold transition cursor-pointer ${
                                viewMode === 'rich'
                                  ? dark ? 'bg-[#2E163F] text-[#F8FAFC] shadow-sm' : 'bg-[#FFFFFF] text-[#1D0B2B] shadow-sm'
                                  : 'text-[#94A3B8]'
                              }`}
                            >
                              Rich HTML
                            </button>
                            <button
                              onClick={() => setViewMode('plain')}
                              className={`px-2.5 py-1 rounded-md font-semibold transition cursor-pointer ${
                                viewMode === 'plain'
                                  ? dark ? 'bg-[#2E163F] text-[#F8FAFC] shadow-sm' : 'bg-[#FFFFFF] text-[#1D0B2B] shadow-sm'
                                  : 'text-[#94A3B8]'
                              }`}
                            >
                              Text
                            </button>
                          </div>
                        )}
                      </div>

                      {/* Right: Actions (Done, Open in Gmail, Prev/Next) */}
                      <div className="flex items-center gap-2">
                        {currentEmail.id && (
                          <a
                            href={`https://mail.google.com/mail/u/0/#inbox/${currentEmail.thread_id || currentEmail.id}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition cursor-pointer ${
                              dark ? 'hover:bg-[#281438] text-[#CBD5E1] hover:text-[#F59E0B]' : 'hover:bg-[#EDF2F7] text-[#4D3A5B] hover:text-[#7E22CE]'
                            }`}
                            title="Open in Gmail"
                          >
                            <ExternalLink className="w-3.5 h-3.5" />
                            <span className="hidden sm:inline">Open in Gmail</span>
                          </a>
                        )}

                        {/* Navigation buttons for next/prev email */}
                        <div className="flex items-center gap-0.5 ml-2 pl-2 border-l border-[#361A4B] dark:border-[#361A4B]">
                          <button
                            disabled={!prevEmail}
                            onClick={() => selectEmail(prevEmail)}
                            className="p-1.5 rounded text-[#94A3B8] hover:text-white disabled:opacity-30"
                            title="Previous email"
                          >
                            <ChevronLeft className="w-4 h-4" />
                          </button>
                          <button
                            disabled={!nextEmail}
                            onClick={() => selectEmail(nextEmail)}
                            className="p-1.5 rounded text-[#94A3B8] hover:text-white disabled:opacity-30"
                            title="Next email"
                          >
                            <ChevronRight className="w-4 h-4" />
                          </button>
                        </div>
                      </div>
                    </div>

                    {/* Email Reader Canvas */}
                    <article className="px-6 sm:px-12 py-8 max-w-4xl w-full select-text">
                      <h1 className={`text-xl sm:text-2xl font-bold tracking-tight mb-6 ${dark ? 'text-[#F8FAFC]' : 'text-[#1D0B2B]'}`}>
                        {currentEmail.subject}
                      </h1>

                      {/* Sender row header */}
                      <div className={`flex items-start justify-between gap-4 mb-8 pb-6 border-b ${
                        dark ? 'border-[#2D153E]' : 'border-[#E2E8F0]'
                      }`}>
                        <div className="flex items-center gap-3.5 min-w-0">
                          <div
                            className={`w-10 h-10 rounded-full text-xs font-bold flex items-center justify-center shrink-0 ${
                              dark ? 'bg-[#281438] text-[#F8FAFC] ring-1 ring-[#3B1E52]' : 'bg-[#EDE9FE] text-[#3B0764] ring-1 ring-[#CBD5E1]'
                            }`}
                          >
                            {currentEmail.initials}
                          </div>
                          <div className="min-w-0 truncate">
                            <div className="flex items-baseline gap-2">
                              <span className={`text-sm font-semibold truncate ${dark ? 'text-[#F8FAFC]' : 'text-[#1D0B2B]'}`}>{currentEmail.sender}</span>
                              <span className="text-xs text-[#94A3B8] truncate">&lt;{currentEmail.email}&gt;</span>
                            </div>
                            <div className="text-xs text-[#94A3B8] mt-0.5">to: me</div>
                          </div>
                        </div>

                        <div className="flex flex-col items-end shrink-0">
                          <span className="text-xs text-[#94A3B8]">{currentEmail.fullDate}</span>
                          {loadingDetail && (
                            <span className="text-[11px] text-[#F59E0B] flex items-center gap-1 mt-1 font-semibold">
                              <RefreshCw className="w-3 h-3 animate-spin" />
                              Loading...
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Body Rendering */}
                      <div className="min-h-[220px]">
                        {loadingDetail && !rawHtml && !rawBody ? (
                          <div className="py-8 space-y-4 animate-pulse">
                            <div className={`h-4 rounded w-3/4 ${dark ? 'bg-[#281438]' : 'bg-[#EDF2F7]'}`} />
                            <div className={`h-4 rounded w-full ${dark ? 'bg-[#281438]' : 'bg-[#EDF2F7]'}`} />
                            <div className={`h-4 rounded w-5/6 ${dark ? 'bg-[#281438]' : 'bg-[#EDF2F7]'}`} />
                            <div className={`h-36 rounded w-full ${dark ? 'bg-[#241232]' : 'bg-[#F8FAFC]'}`} />
                          </div>
                        ) : viewMode === 'rich' && rawHtml ? (
                          <HtmlEmailViewer html={rawHtml} dark={dark} />
                        ) : (
                          <FormattedTextEmail
                            text={rawBody || currentEmail.paragraphs?.join('\n\n') || ''}
                            dark={dark}
                          />
                        )}
                      </div>

                      {/* Attachment Pills */}
                      {currentEmail.attachment && (
                        <div className={`mt-8 pt-6 border-t ${dark ? 'border-[#2D153E]' : 'border-[#E2E8F0]'}`}>
                          <button
                            onClick={() => triggerToast(`Downloaded ${currentEmail.attachment.name}`)}
                            className={`inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full text-xs font-semibold transition cursor-pointer border ${
                              dark ? 'bg-[#281438] text-[#F8FAFC] border-[#3B1E52] hover:bg-[#341A49]' : 'bg-[#FFFFFF] text-[#1D0B2B] border-[#CBD5E1] hover:bg-[#F1F5F9]'
                            }`}
                          >
                            <Paperclip className="w-3.5 h-3.5 text-[#F59E0B]" />
                            <span>{currentEmail.attachment.name}</span>
                            <span className="text-[#94A3B8]">· {currentEmail.attachment.size}</span>
                          </button>
                        </div>
                      )}
                    </article>
                  </>
                ) : (
                  <div className="flex-1 flex items-center justify-center text-[#94A3B8] text-sm">
                    No message selected
                  </div>
                )}
              </div>
            )}
          </div>
        </main>
      </div>

      {/* Floating Undo / Action Toast */}
      {toast && (
        <div
          className={`fixed bottom-6 left-1/2 -translate-x-1/2 px-4 py-2.5 rounded-xl shadow-2xl border text-xs font-medium flex items-center gap-3 z-50 ${
            dark
              ? 'bg-[#241232] border-[#3B1E52] text-[#F8FAFC]'
              : 'bg-[#1D0B2B] border-[#3B1254] text-[#F8FAFC]'
          }`}
        >
          <span>{toast.message}</span>
          {toast.undo && (
            <button
              onClick={() => {
                toast.undo();
                setToast(null);
              }}
              className="text-[#F59E0B] hover:underline font-semibold cursor-pointer"
            >
              Undo
            </button>
          )}
        </div>
      )}
    </div>
  );
}
