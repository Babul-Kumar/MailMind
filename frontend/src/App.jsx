import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import {
  Menu,
  Search,
  SlidersHorizontal,
  Sun,
  Moon,
  RefreshCw,
  PenLine,
  Inbox,
  AlertCircle,
  Star,
  Clock,
  Send,
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
  Maximize2,
  Minimize2,
  X,
  Mail,
  MailOpen,
  Trash2
} from 'lucide-react';
import { useAuth } from './hooks/useAuth';
import { useEmails } from './hooks/useEmails';
import { AuthCallback } from './components/auth/AuthCallback';
import { cleanSenderName, formatEmailDate } from './utils/formatting';
import { submitFeedback, fetchEmailDetail } from './services/api';

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
  { id: 'last_1_year', label: 'Last 1 year', days: 365 },
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
    avatarBg: 'bg-stone-200/80 text-stone-700',
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
    sender: 'ByteByteGo',
    email: 'bytebytego@substack.com',
    initials: 'BB',
    avatarBg: 'bg-indigo-100/70 text-indigo-900',
    subject: 'The Hidden Work Behind Every Database Request',
    time: 'Nov 3',
    fullDate: 'Nov 3, 2:10 PM',
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
  }
];

// ============================================================================
// BRAND LOGO ICON
// ============================================================================

function BrandMark() {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="none"
      className="w-5 h-5 shrink-0"
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

    // Convert links so they always open safely in an external new tab
    let processed = html.replace(/<a\s+(?:[^>]*?\s+)?href="([^"]*)"/gi, (match, url) => {
      return `<a href="${url}" target="_blank" rel="noopener noreferrer"`;
    });

    const resetStyles = `
      <style>
        html, body {
          margin: 0;
          padding: 16px 20px;
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
          font-size: 14px;
          line-height: 1.6;
          color: ${dark ? '#EDEDED' : '#1F2937'};
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
          color: #2563EB;
        }
        blockquote {
          border-left: 2px solid ${dark ? '#3F3F46' : '#E5E7EB'};
          margin: 8px 0;
          padding-left: 12px;
          color: ${dark ? '#A1A1AA' : '#6B7280'};
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
            className="text-blue-500 hover:underline break-all"
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
      dark ? 'text-[#E4E4E7]' : 'text-[#27272A]'
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
    thread_id: item.thread_id || item.threadId || item.id,
    sender: senderDisplay,
    email: senderEmail || 'user@example.com',
    recipients: item.recipients || 'me',
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

  // Compose Dialog State
  const [composeOpen, setComposeOpen] = useState(false);
  const [composeMinimized, setComposeMinimized] = useState(false);
  const [composeData, setComposeData] = useState({ to: '', subject: '', body: '' });

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

  // Attention Counter
  const attentionCount = useMemo(() => {
    return emails.filter((e) => e.needsAttention && !statusMap[e.id]).length;
  }, [emails, statusMap]);

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

  // Filtered List Items (Meticulous Gmail Tab & Folder Filtering)
  const visibleEmails = useMemo(() => {
    return emails.filter((item) => {
      const st = statusMap[item.id]?.state;
      const isStarred = starredIds.has(item.id);

      // View filtering
      if (view === 'attention') {
        if (!item.needsAttention) return false;
      } else if (view === 'recent') {
        if (item.daysAgo > cutoffDays) return false;
      }
      // 'all' shows all emails

      // Category Tab Filtering
      if (categoryTab !== 'all') {
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
  }, [emails, view, categoryTab, statusMap, starredIds, priorityFilter, search]);

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

    if (nextId === 'all_time') {
      setView('all');
      setCategoryTab('all');
    }

    if (emailsHook.changeAnalysisPeriod) {
      emailsHook.changeAnalysisPeriod(nextId);
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

  // Calculate Gmail pagination numbers
  const totalEmails = emailsHook.pagination?.total_emails || emails.length;
  const currentPage = emailsHook.pagination?.page || 1;
  const pageSize = emailsHook.pagination?.page_size || 50;
  const startNum = visibleEmails.length === 0 ? 0 : 1;
  const endNum = Math.min(visibleEmails.length, totalEmails);

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
      {/* TOP BAR: GMAIL HEADER WITH EXPANSIVE PILL SEARCH, LOGO, USER AVATAR  */}
      {/* ==================================================================== */}
      <header
        className={`h-16 px-4 sm:px-6 flex items-center justify-between border-b shrink-0 z-20 ${
          dark
            ? 'bg-[#121214] border-[#27272A]'
            : 'bg-[#F5F5F4] border-[#E4E4E7]'
        }`}
      >
        {/* Left: Hamburger + Logo */}
        <div className="flex items-center gap-3 w-56 shrink-0">
          <button
            onClick={() => setSidebarOpen((o) => !o)}
            className={`p-2 rounded-full transition cursor-pointer ${
              dark
                ? 'text-[#A1A1AA] hover:text-white hover:bg-zinc-800'
                : 'text-[#71717A] hover:text-black hover:bg-zinc-200'
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
            }}
            className="flex items-center gap-2.5 font-semibold text-lg tracking-tight cursor-pointer"
          >
            <BrandMark />
            <span className="font-medium tracking-tight">MailMind</span>
          </div>
        </div>

        {/* Center: Expansive Rounded Pill Search Bar (Exactly like Gmail) */}
        <div className="flex-1 max-w-2xl px-2 sm:px-6">
          <div
            className={`flex items-center h-11 px-4 rounded-full transition-all border ${
              dark
                ? 'bg-zinc-800/80 border-transparent focus-within:bg-[#18181B] focus-within:border-zinc-700 focus-within:shadow-md'
                : 'bg-zinc-200/60 border-transparent focus-within:bg-white focus-within:border-zinc-300 focus-within:shadow-md'
            }`}
          >
            <Search className="w-4 h-4 text-zinc-400 shrink-0 mr-3" />
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
                  ? 'text-white placeholder-zinc-400'
                  : 'text-zinc-900 placeholder-zinc-500'
              }`}
            />
            {search ? (
              <button
                onClick={() => setSearch('')}
                className="p-1 text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200"
              >
                <X className="w-4 h-4" />
              </button>
            ) : (
              <button
                title="Search options"
                className="p-1 text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200"
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
            className={`p-2 rounded-full transition cursor-pointer ${
              dark
                ? 'text-[#A1A1AA] hover:text-white hover:bg-zinc-800'
                : 'text-[#71717A] hover:text-black hover:bg-zinc-200'
            }`}
            title="Sync mailbox"
          >
            <RefreshCw className={`w-4 h-4 ${syncing ? 'animate-spin' : ''}`} />
          </button>

          <button
            onClick={() => setDark((d) => !d)}
            className={`p-2 rounded-full transition cursor-pointer ${
              dark
                ? 'text-[#A1A1AA] hover:text-white hover:bg-zinc-800'
                : 'text-[#71717A] hover:text-black hover:bg-zinc-200'
            }`}
            title={dark ? 'Switch to light mode' : 'Switch to dark mode'}
          >
            {dark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
          </button>

          {/* User Profile Avatar Dropdown */}
          <div className="relative ml-2" onClick={(e) => e.stopPropagation()}>
            <button
              onClick={() => {
                setUserMenuOpen((o) => !o);
                setWindowMenuOpen(false);
              }}
              className={`w-8 h-8 rounded-full text-xs font-semibold flex items-center justify-center shrink-0 ring-2 cursor-pointer transition ${
                dark
                  ? 'bg-zinc-800 text-white ring-zinc-700 hover:ring-zinc-500'
                  : 'bg-zinc-200 text-zinc-900 ring-zinc-300 hover:ring-zinc-400'
              }`}
            >
              {userInitials}
            </button>

            {userMenuOpen && (
              <div
                className={`absolute right-0 top-11 w-56 rounded-2xl p-2 shadow-xl border z-50 ${
                  dark
                    ? 'bg-[#1F1F23] border-[#27272A] text-[#F4F4F5]'
                    : 'bg-[#FFFFFF] border-[#E4E4E7] text-[#18181B]'
                }`}
              >
                <div className="px-3 py-2 border-b border-zinc-200/40 dark:border-zinc-800/60 mb-1">
                  <p className="text-xs font-semibold truncate">{userName}</p>
                  <p className="text-[11px] text-[#71717A] truncate">{auth.user?.email || 'Connected'}</p>
                </div>
                <button
                  onClick={() => {
                    setUserMenuOpen(false);
                    auth.logout();
                  }}
                  className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-xs transition cursor-pointer ${
                    dark
                      ? 'hover:bg-zinc-800 text-rose-400'
                      : 'hover:bg-zinc-100 text-rose-600'
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
              ? 'bg-[#121214] border-[#27272A]'
              : 'bg-[#F5F5F4] border-[#E4E4E7]'
          }`}
        >
          <div className="space-y-3 px-3">
            {/* Gmail-style Compose Button */}
            <div className="pt-0.5">
              <button
                onClick={() => {
                  setComposeOpen(true);
                  setComposeMinimized(false);
                }}
                className={`flex items-center gap-3.5 py-3 rounded-2xl font-medium text-sm transition-all shadow-sm cursor-pointer border ${
                  sidebarOpen ? 'px-5 w-full justify-start' : 'w-10 h-10 justify-center px-0 mx-auto'
                } ${
                  dark
                    ? 'bg-[#2B3945] hover:bg-[#344453] text-[#C2E7FF] border-blue-900/40'
                    : 'bg-[#C2E7FF] hover:bg-[#B3DCF5] text-[#001D35] border-blue-200/60'
                }`}
                title="Compose"
              >
                <PenLine className="w-4 h-4 shrink-0 text-blue-500 dark:text-blue-400" />
                {sidebarOpen && <span className="font-semibold tracking-wide">Compose</span>}
              </button>
            </div>

            {/* Primary Views (Gmail Style + AI Email Triage) */}
            <nav className="space-y-1">
              {[
                { id: 'all', label: 'Inbox', icon: Inbox, count: totalEmails },
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
                        emailsHook.setActiveFilter?.('NEEDS_ATTENTION');
                      } else if (nav.id === 'recent') {
                        emailsHook.setActiveFilter?.('ALL');
                      }
                    }}
                    className={`w-full flex items-center justify-between py-2 rounded-r-full text-[13.5px] transition cursor-pointer ${
                      sidebarOpen ? 'pl-4 pr-3' : 'px-2 justify-center rounded-xl'
                    } ${
                      active
                        ? dark
                          ? 'bg-zinc-800/90 text-white font-semibold'
                          : 'bg-zinc-200 text-zinc-900 font-semibold'
                        : dark
                        ? 'text-[#A1A1AA] hover:text-white hover:bg-zinc-800/40'
                        : 'text-[#71717A] hover:text-zinc-900 hover:bg-zinc-200/50'
                    }`}
                    title={nav.label}
                  >
                    <div className="flex items-center gap-3.5 min-w-0">
                      <IconComponent
                        className={`w-4 h-4 shrink-0 ${
                          active
                            ? 'text-blue-500'
                            : 'text-zinc-500'
                        }`}
                      />
                      {sidebarOpen && <span className="truncate">{nav.label}</span>}
                    </div>

                    {sidebarOpen && nav.count > 0 && (
                      <span
                        className={`text-xs tabular-nums font-medium ${
                          active
                            ? dark ? 'text-white' : 'text-zinc-900'
                            : 'text-[#71717A]'
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
              <div className="pt-3 border-t border-zinc-200/40 dark:border-zinc-800/60">
                <div className="px-4 pb-1.5 text-[11px] font-semibold text-zinc-400 uppercase tracking-wider">
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
                      className={`w-full flex items-center justify-between px-4 py-1.5 rounded-r-full text-[13px] transition cursor-pointer ${
                        active
                          ? dark
                            ? 'bg-zinc-800/90 text-white font-medium'
                            : 'bg-zinc-200 text-zinc-900 font-medium'
                          : dark
                          ? 'text-[#A1A1AA] hover:text-white hover:bg-zinc-800/40'
                          : 'text-[#71717A] hover:text-zinc-900 hover:bg-zinc-200/50'
                      }`}
                    >
                      <span className="flex items-center gap-3">
                        <span
                          className="w-2 h-2 rounded-full shrink-0"
                          style={{ backgroundColor: tier.color }}
                        />
                        <span>{tier.name}</span>
                      </span>
                      {active && (
                        <span className="text-[11px] text-zinc-400">Clear</span>
                      )}
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* Footer of Sidebar: Timeframe Selector */}
          {sidebarOpen && (
            <div className="px-3 pt-3 border-t border-zinc-200/40 dark:border-zinc-800/60">
              <div className="relative" onClick={(e) => e.stopPropagation()}>
                <button
                  onClick={() => {
                    setWindowMenuOpen((o) => !o);
                    setUserMenuOpen(false);
                  }}
                  className={`w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs transition cursor-pointer ${
                    dark
                      ? 'text-[#A1A1AA] hover:text-white hover:bg-zinc-800/50'
                      : 'text-[#71717A] hover:text-zinc-900 hover:bg-zinc-200/50'
                  }`}
                >
                  <span className="flex items-center gap-2">
                    <RefreshCw className={`w-3.5 h-3.5 ${syncing ? 'animate-spin' : ''}`} />
                    <span>{activeWindowLabel}</span>
                  </span>
                  <ChevronDown className="w-3.5 h-3.5 opacity-60" />
                </button>

                {windowMenuOpen && (
                  <div
                    className={`absolute bottom-11 left-0 w-48 rounded-2xl p-1.5 shadow-xl border z-50 ${
                      dark
                        ? 'bg-[#1F1F23] border-[#27272A] text-[#F4F4F5]'
                        : 'bg-[#FFFFFF] border-[#E4E4E7] text-[#18181B]'
                    }`}
                  >
                    {WINDOWS.map((w) => (
                      <button
                        key={w.id}
                        onClick={() => selectWindow(w.id)}
                        className={`w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs transition cursor-pointer ${
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
                        {windowId === w.id && <Check className="w-3 h-3 text-blue-500" />}
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
          className={`flex-1 flex flex-col overflow-hidden ${
            dark ? 'bg-[#18181B]' : 'bg-[#FFFFFF]'
          }`}
        >
          {/* 1. GMAIL ACTION TOOLBAR */}
          <div
            className={`h-12 px-4 flex items-center justify-between border-b shrink-0 text-xs ${
              dark ? 'border-[#27272A]' : 'border-[#E4E4E7]'
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
                      ? 'text-zinc-300 hover:text-white hover:bg-zinc-800'
                      : 'text-zinc-700 hover:text-black hover:bg-zinc-100'
                  }`}
                >
                  <ArrowLeft className="w-4 h-4" />
                  <span>Back to all mail</span>
                </button>
              ) : (
                <>
                  {/* Select All Checkbox */}
                  <button
                    onClick={toggleSelectAll}
                    className={`p-1.5 rounded-md transition cursor-pointer ${
                      dark ? 'text-zinc-400 hover:text-white hover:bg-zinc-800' : 'text-zinc-600 hover:text-black hover:bg-zinc-100'
                    }`}
                    title="Select all"
                  >
                    {checkedIds.size === visibleEmails.length && visibleEmails.length > 0 ? (
                      <CheckSquare className="w-4 h-4 text-blue-500" />
                    ) : checkedIds.size > 0 ? (
                      <MinusSquare className="w-4 h-4 text-blue-500" />
                    ) : (
                      <Square className="w-4 h-4" />
                    )}
                  </button>

                  <button
                    onClick={() => emailsHook.refresh?.(windowId)}
                    className={`p-1.5 rounded-md transition cursor-pointer ${
                      dark ? 'text-zinc-400 hover:text-white hover:bg-zinc-800' : 'text-zinc-600 hover:text-black hover:bg-zinc-100'
                    }`}
                    title="Refresh"
                  >
                    <RefreshCw className={`w-4 h-4 ${syncing ? 'animate-spin' : ''}`} />
                  </button>

                  {/* Batch actions when checkboxes selected */}
                  {checkedIds.size > 0 && (
                    <div className="flex items-center gap-2 ml-2 pl-3 border-l border-zinc-300 dark:border-zinc-700">
                      <span className="font-medium text-xs">
                        {checkedIds.size} selected
                      </span>

                      <button
                        onClick={() => setCheckedIds(new Set())}
                        className="px-2 py-1 rounded-md text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200"
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
              <span className={`tabular-nums ${dark ? 'text-zinc-400' : 'text-zinc-500'}`}>
                {startNum}–{endNum} of {totalEmails.toLocaleString()}
              </span>

              <div className="flex items-center gap-1">
                <button
                  disabled={currentPage <= 1 || !!readingEmailId}
                  onClick={() => emailsHook.setPage?.((p) => Math.max(1, p - 1))}
                  className={`p-1.5 rounded-md transition cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed ${
                    dark ? 'hover:bg-zinc-800 text-zinc-300' : 'hover:bg-zinc-100 text-zinc-700'
                  }`}
                  title="Newer"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <button
                  disabled={!emailsHook.pagination?.has_next || !!readingEmailId}
                  onClick={() => emailsHook.loadMore?.()}
                  className={`p-1.5 rounded-md transition cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed ${
                    dark ? 'hover:bg-zinc-800 text-zinc-300' : 'hover:bg-zinc-100 text-zinc-700'
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
                className={`p-1.5 rounded-md transition cursor-pointer ${
                  layoutMode === 'split'
                    ? 'bg-blue-500/10 text-blue-500'
                    : dark
                    ? 'text-zinc-400 hover:bg-zinc-800'
                    : 'text-zinc-600 hover:bg-zinc-100'
                }`}
                title={layoutMode === 'split' ? 'Switch to Full Table View' : 'Switch to Split Reading View'}
              >
                <Columns className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* 2. GMAIL CATEGORY TABS (Primary, Updates, Promotions, Social, All) */}
          {!readingEmailId && (
            <div
              className={`flex items-center border-b shrink-0 px-2 sm:px-4 ${
                dark ? 'border-[#27272A]' : 'border-[#E4E4E7]'
              }`}
            >
              {[
                { id: 'primary', label: 'Primary', icon: Inbox, count: categoryCounts.primary, badgeColor: 'bg-blue-500' },
                { id: 'promotions', label: 'Promotions', icon: Tag, count: categoryCounts.promotions, badgeColor: 'bg-emerald-600' },
                { id: 'social', label: 'Social', icon: Users, count: categoryCounts.social, badgeColor: 'bg-blue-600' },
                { id: 'updates', label: 'Updates', icon: Info, count: categoryCounts.updates, badgeColor: 'bg-amber-600' },
                { id: 'all', label: 'All', icon: Archive, count: emails.length, badgeColor: 'bg-zinc-500' }
              ].map((tab) => {
                const active = categoryTab === tab.id;
                const IconComponent = tab.icon;
                return (
                  <button
                    key={tab.id}
                    onClick={() => setCategoryTab(tab.id)}
                    className={`flex items-center gap-3 px-4 sm:px-6 py-3 text-[13.5px] font-medium transition cursor-pointer border-b-2 -mb-[2px] ${
                      active
                        ? dark
                          ? 'border-blue-500 text-blue-400'
                          : 'border-blue-600 text-blue-600'
                        : 'border-transparent text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-200 hover:bg-zinc-100/50 dark:hover:bg-zinc-800/30'
                    }`}
                  >
                    <IconComponent className="w-4 h-4 shrink-0" />
                    <span>{tab.label}</span>
                    {tab.count > 0 && (
                      <span
                        className={`text-[10px] font-semibold text-white px-1.5 py-0.2 rounded-full ${tab.badgeColor}`}
                      >
                        {tab.count}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          )}

          {/* 3. MAIL CONTENT: TABLE VIEW vs FULL THREAD VIEW vs SPLIT VIEW */}
          <div className="flex-1 flex overflow-hidden">
            {/* EMAIL LIST TABLE (Shown when not reading in table mode, or in split mode) */}
            {(!readingEmailId || layoutMode === 'split') && (
              <div
                className={`flex-1 flex flex-col overflow-y-auto ${
                  layoutMode === 'split' ? 'w-full md:w-[420px] lg:w-[480px] shrink-0 border-r' : 'w-full'
                } ${dark ? 'border-[#27272A]' : 'border-[#E4E4E7]'}`}
              >
                {visibleEmails.length === 0 ? (
                  <div className="flex-1 flex flex-col items-center justify-center p-12 text-center text-zinc-400">
                    <Inbox className="w-12 h-12 stroke-[1.2] mb-3 opacity-40" />
                    <p className="text-sm font-medium">All caught up</p>
                    <p className="text-xs text-zinc-500 mt-1">No messages match the active view or filter</p>
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
                        className={`group flex items-center h-10 sm:h-11 px-3 sm:px-4 border-b transition-colors cursor-pointer text-[13px] sm:text-[13.5px] select-none ${
                          isSelected && layoutMode === 'split'
                            ? dark ? 'bg-[#1E293B]' : 'bg-[#E0E7FF]/70'
                            : isChecked
                            ? dark ? 'bg-zinc-800/80' : 'bg-blue-50/60'
                            : item.unread
                            ? dark ? 'bg-zinc-900/60 hover:bg-zinc-800/50' : 'bg-white hover:bg-zinc-100/90'
                            : dark ? 'bg-[#18181B] hover:bg-zinc-800/40 opacity-85' : 'bg-zinc-50/50 hover:bg-zinc-100'
                        } ${dark ? 'border-[#27272A]' : 'border-[#E4E4E7]'}`}
                      >
                        {/* Checkbox column */}
                        <button
                          onClick={(e) => toggleCheckEmail(item.id, e)}
                          className="p-1 -ml-1 text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200 transition shrink-0"
                          title="Select"
                        >
                          {isChecked ? (
                            <CheckSquare className="w-4 h-4 text-blue-500" />
                          ) : (
                            <Square className="w-4 h-4" />
                          )}
                        </button>



                        {/* Priority indicator dot */}
                        <span
                          className="w-2 h-2 rounded-full shrink-0 ml-1 mr-3"
                          style={{ backgroundColor: tier.color }}
                          title={`${tier.id} · ${tier.name}`}
                        />

                        {/* Sender Column: fixed width, strictly aligned down the screen! */}
                        <div
                          className={`w-36 sm:w-48 lg:w-56 shrink-0 truncate pr-3 ${
                            item.unread
                              ? dark ? 'font-semibold text-white' : 'font-semibold text-zinc-950'
                              : dark ? 'font-normal text-zinc-300' : 'font-normal text-zinc-700'
                          }`}
                        >
                          {item.sender}
                        </div>

                        {/* Subject & Snippet Column: flexible width with clean ellipsis */}
                        <div className="flex-1 min-w-0 flex items-center gap-1.5 truncate pr-3">
                          <span
                            className={`shrink-0 truncate max-w-[50%] ${
                              item.unread
                                ? dark ? 'font-semibold text-white' : 'font-semibold text-zinc-900'
                                : dark ? 'font-normal text-zinc-200' : 'font-normal text-zinc-800'
                            }`}
                          >
                            {item.subject}
                          </span>
                          <span className="text-zinc-400 shrink-0">—</span>
                          <span className={`truncate text-xs sm:text-[13px] ${
                            dark ? 'text-zinc-400' : 'text-zinc-500'
                          }`}>
                            {item.paragraphs?.[0] || item.snippet || ''}
                          </span>

                          {/* Inline Tag Chips: OTP, Attachment */}
                          {item.otp && (
                            <span className="ml-2 shrink-0 px-1.5 py-0.5 rounded text-[10px] font-mono font-medium bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-500/20">
                              OTP: {item.otp}
                            </span>
                          )}
                          {item.attachment && (
                            <Paperclip className="w-3.5 h-3.5 text-zinc-400 shrink-0 ml-1" />
                          )}
                        </div>

                        {/* Timestamp & Hover Actions (Right Edge) */}
                        <div className="relative shrink-0 flex items-center justify-end w-24">
                          {/* Timestamp */}
                          <span
                            className={`text-xs tabular-nums text-right group-hover:hidden ${
                              item.unread
                                ? dark ? 'font-semibold text-white' : 'font-semibold text-zinc-900'
                                : dark ? 'text-zinc-400' : 'text-zinc-500'
                            }`}
                          >
                            {item.time}
                          </span>

                          {/* Floating Hover Quick Actions */}
                          <div
                            onClick={(e) => e.stopPropagation()}
                            className={`hidden group-hover:flex items-center gap-1 ${
                              dark ? 'bg-zinc-800' : 'bg-zinc-100'
                            } px-1.5 py-0.5 rounded-md`}
                          >

                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                triggerToast('Snoozed for 3 hours');
                              }}
                              title="Snooze"
                              className="p-1 rounded text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-100 hover:bg-zinc-200 dark:hover:bg-zinc-700 transition"
                            >
                              <Clock className="w-3.5 h-3.5" />
                            </button>
                            <a
                              href={`https://mail.google.com/mail/u/0/#inbox/${item.thread_id || item.id}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              title="Open in Gmail"
                              className="p-1 rounded text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-100 hover:bg-zinc-200 dark:hover:bg-zinc-700 transition"
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
                {emailsHook.pagination?.has_next && (
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
                      className={`inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-medium transition cursor-pointer shadow-sm ${
                        dark
                          ? 'bg-zinc-800 text-white hover:bg-zinc-700 disabled:opacity-50'
                          : 'bg-zinc-100 text-zinc-900 hover:bg-zinc-200 disabled:opacity-50'
                      }`}
                    >
                      {emailsHook.isLoadingMore ? (
                        <>
                          <RefreshCw className="w-3.5 h-3.5 animate-spin" />
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
                  dark ? 'bg-[#18181B]' : 'bg-[#FFFFFF]'
                }`}
              >
                {currentEmail ? (
                  <>
                    {/* Action Header Strip for Email */}
                    <div
                      className={`h-12 px-6 flex items-center justify-between border-b shrink-0 ${
                        dark ? 'border-[#27272A]' : 'border-[#E4E4E7]'
                      }`}
                    >
                      {/* Left: Priority Badge Popover + View Toggle */}
                      <div className="flex items-center gap-3">
                        <div className="relative" onClick={(e) => e.stopPropagation()}>
                          <button
                            onClick={() => {
                              setPriorityMenuOpen((o) => !o);
                            }}
                            className={`inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium transition cursor-pointer ${
                              dark
                                ? 'bg-zinc-800 text-white hover:bg-zinc-700'
                                : 'bg-zinc-100 text-zinc-900 hover:bg-zinc-200'
                            }`}
                          >
                            <span
                              className="w-2 h-2 rounded-full"
                              style={{ backgroundColor: currentPriority?.color }}
                            />
                            <span>{currentPriority?.id} · {currentPriority?.name}</span>
                            <ChevronDown className="w-3 h-3 opacity-60" />
                          </button>

                          {priorityMenuOpen && (
                            <div
                              className={`absolute left-0 top-9 z-50 w-64 rounded-2xl p-3 shadow-xl border space-y-3 ${
                                dark
                                  ? 'bg-[#1F1F23] border-[#27272A] text-white'
                                  : 'bg-[#FFFFFF] border-[#E4E4E7] text-zinc-900'
                              }`}
                            >
                              <div className="text-xs space-y-1">
                                <p>Matched: <span className="text-zinc-400">{currentEmail.matched}</span></p>
                                {currentEmail.note && <p className="text-zinc-400">{currentEmail.note}</p>}
                              </div>
                              <div className="pt-2 border-t grid grid-cols-4 gap-1 border-zinc-200 dark:border-zinc-800">
                                {Object.values(PRIORITIES).map((tier) => (
                                  <button
                                    key={tier.id}
                                    onClick={() => changePriority(currentEmail, tier.id)}
                                    className={`py-1.5 rounded-lg text-xs font-medium flex items-center justify-center gap-1 transition ${
                                      currentEmail.priority === tier.id
                                        ? dark ? 'bg-zinc-700 text-white' : 'bg-zinc-200 text-zinc-900'
                                        : 'hover:bg-zinc-100 dark:hover:bg-zinc-800 text-zinc-400'
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
                            dark ? 'border-[#27272A] bg-zinc-900/60' : 'border-[#E4E4E7] bg-zinc-100/70'
                          }`}>
                            <button
                              onClick={() => setViewMode('rich')}
                              className={`px-2.5 py-1 rounded-md font-medium transition cursor-pointer ${
                                viewMode === 'rich'
                                  ? dark ? 'bg-zinc-800 text-white shadow-sm' : 'bg-white text-zinc-900 shadow-sm'
                                  : 'text-zinc-500'
                              }`}
                            >
                              Rich HTML
                            </button>
                            <button
                              onClick={() => setViewMode('plain')}
                              className={`px-2.5 py-1 rounded-md font-medium transition cursor-pointer ${
                                viewMode === 'plain'
                                  ? dark ? 'bg-zinc-800 text-white shadow-sm' : 'bg-white text-zinc-900 shadow-sm'
                                  : 'text-zinc-500'
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
                            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition cursor-pointer ${
                              dark ? 'hover:bg-zinc-800 text-zinc-300' : 'hover:bg-zinc-100 text-zinc-700'
                            }`}
                            title="Open in Gmail"
                          >
                            <ExternalLink className="w-3.5 h-3.5" />
                            <span className="hidden sm:inline">Open in Gmail</span>
                          </a>
                        )}



                        {/* Navigation buttons for next/prev email */}
                        <div className="flex items-center gap-0.5 ml-2 pl-2 border-l border-zinc-200 dark:border-zinc-800">
                          <button
                            disabled={!prevEmail}
                            onClick={() => selectEmail(prevEmail)}
                            className="p-1.5 rounded text-zinc-400 hover:text-zinc-800 dark:hover:text-zinc-100 disabled:opacity-30"
                            title="Previous email"
                          >
                            <ChevronLeft className="w-4 h-4" />
                          </button>
                          <button
                            disabled={!nextEmail}
                            onClick={() => selectEmail(nextEmail)}
                            className="p-1.5 rounded text-zinc-400 hover:text-zinc-800 dark:hover:text-zinc-100 disabled:opacity-30"
                            title="Next email"
                          >
                            <ChevronRight className="w-4 h-4" />
                          </button>
                        </div>
                      </div>
                    </div>

                    {/* Email Reader Canvas */}
                    <article className="px-6 sm:px-12 py-8 max-w-4xl w-full select-text">
                      <h1 className="text-xl sm:text-2xl font-bold tracking-tight mb-6">
                        {currentEmail.subject}
                      </h1>

                      {/* Sender row header */}
                      <div className="flex items-start justify-between gap-4 mb-8 pb-6 border-b border-zinc-200/60 dark:border-zinc-800/60">
                        <div className="flex items-center gap-3.5 min-w-0">
                          <div
                            className={`w-10 h-10 rounded-full text-xs font-bold flex items-center justify-center shrink-0 ${
                              dark ? 'bg-zinc-800 text-white' : currentEmail.avatarBg
                            }`}
                          >
                            {currentEmail.initials}
                          </div>
                          <div className="min-w-0 truncate">
                            <div className="flex items-baseline gap-2">
                              <span className="text-sm font-semibold truncate">{currentEmail.sender}</span>
                              <span className="text-xs text-zinc-500 truncate">&lt;{currentEmail.email}&gt;</span>
                            </div>
                            <div className="text-xs text-zinc-400 mt-0.5">to: me</div>
                          </div>
                        </div>

                        <div className="flex flex-col items-end shrink-0">
                          <span className="text-xs text-zinc-500">{currentEmail.fullDate}</span>
                          {loadingDetail && (
                            <span className="text-[11px] text-blue-500 flex items-center gap-1 mt-1">
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
                            <div className={`h-4 rounded w-3/4 ${dark ? 'bg-zinc-800' : 'bg-zinc-200'}`} />
                            <div className={`h-4 rounded w-full ${dark ? 'bg-zinc-800' : 'bg-zinc-200'}`} />
                            <div className={`h-4 rounded w-5/6 ${dark ? 'bg-zinc-800' : 'bg-zinc-200'}`} />
                            <div className={`h-36 rounded w-full ${dark ? 'bg-zinc-800/50' : 'bg-zinc-100'}`} />
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
                        <div className="mt-8 pt-6 border-t border-zinc-200/60 dark:border-zinc-800/60">
                          <button
                            onClick={() => triggerToast(`Downloaded ${currentEmail.attachment.name}`)}
                            className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs transition cursor-pointer ${
                              dark ? 'bg-zinc-800 text-white hover:bg-zinc-700' : 'bg-zinc-100 text-zinc-800 hover:bg-zinc-200'
                            }`}
                          >
                            <Paperclip className="w-3.5 h-3.5 text-zinc-400" />
                            <span className="font-medium">{currentEmail.attachment.name}</span>
                            <span className="text-zinc-500">· {currentEmail.attachment.size}</span>
                          </button>
                        </div>
                      )}
                    </article>
                  </>
                ) : (
                  <div className="flex-1 flex items-center justify-center text-zinc-400 text-sm">
                    No message selected
                  </div>
                )}
              </div>
            )}
          </div>
        </main>
      </div>



      {/* Floating Compose Dialog (Gmail style) */}
      {composeOpen && (
        <div
          className={`fixed bottom-0 right-4 sm:right-12 z-50 rounded-t-2xl shadow-2xl border transition-all duration-200 overflow-hidden flex flex-col ${
            composeMinimized ? 'w-72 h-11' : 'w-[95vw] sm:w-[540px] h-[480px]'
          } ${
            dark ? 'bg-[#1E1E22] border-zinc-700 text-zinc-100' : 'bg-white border-zinc-300 text-zinc-900'
          }`}
        >
          {/* Compose Header */}
          <div
            className={`px-4 py-2.5 flex items-center justify-between border-b cursor-pointer select-none ${
              dark ? 'bg-[#26262B] border-zinc-700/80' : 'bg-zinc-100 border-zinc-200'
            }`}
            onClick={() => setComposeMinimized((m) => !m)}
          >
            <span className="text-xs font-semibold">New Message</span>
            <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
              <button
                onClick={() => setComposeMinimized((m) => !m)}
                className="p-1 rounded hover:bg-zinc-200 dark:hover:bg-zinc-700 text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200"
                title={composeMinimized ? 'Expand' : 'Minimize'}
              >
                {composeMinimized ? <Maximize2 className="w-3.5 h-3.5" /> : <Minimize2 className="w-3.5 h-3.5" />}
              </button>
              <button
                onClick={() => setComposeOpen(false)}
                className="p-1 rounded hover:bg-zinc-200 dark:hover:bg-zinc-700 text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200"
                title="Close"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          {!composeMinimized && (
            <>
              {/* Recipients Input */}
              <div className="flex items-center px-4 py-2 border-b border-zinc-200 dark:border-zinc-800 text-xs">
                <span className="text-zinc-400 w-12 shrink-0">To:</span>
                <input
                  type="email"
                  value={composeData.to}
                  onChange={(e) => setComposeData((prev) => ({ ...prev, to: e.target.value }))}
                  placeholder="recipient@example.com"
                  className="w-full bg-transparent outline-none text-xs"
                />
              </div>

              {/* Subject Input */}
              <div className="flex items-center px-4 py-2 border-b border-zinc-200 dark:border-zinc-800 text-xs">
                <span className="text-zinc-400 w-12 shrink-0">Subject:</span>
                <input
                  type="text"
                  value={composeData.subject}
                  onChange={(e) => setComposeData((prev) => ({ ...prev, subject: e.target.value }))}
                  placeholder="Subject"
                  className="w-full bg-transparent outline-none text-xs font-medium"
                />
              </div>

              {/* Message Body */}
              <div className="flex-1 p-4 overflow-y-auto">
                <textarea
                  value={composeData.body}
                  onChange={(e) => setComposeData((prev) => ({ ...prev, body: e.target.value }))}
                  placeholder="Write your email here..."
                  className="w-full h-full bg-transparent outline-none text-xs leading-relaxed resize-none"
                />
              </div>

              {/* Compose Action Footer */}
              <div className={`px-4 py-3 border-t flex items-center justify-between ${
                dark ? 'border-zinc-800 bg-[#1A1A1D]' : 'border-zinc-200 bg-zinc-50'
              }`}>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => {
                      triggerToast('Message sent successfully');
                      setComposeData({ to: '', subject: '', body: '' });
                      setComposeOpen(false);
                    }}
                    className="inline-flex items-center gap-1.5 px-5 py-2 rounded-xl text-xs font-semibold bg-blue-600 hover:bg-blue-500 text-white transition shadow-sm cursor-pointer"
                  >
                    <span>Send</span>
                    <Send className="w-3.5 h-3.5" />
                  </button>
                  <a
                    href={`https://mail.google.com/mail/u/0/?view=cm&fs=1&to=${encodeURIComponent(composeData.to)}&su=${encodeURIComponent(composeData.subject)}&body=${encodeURIComponent(composeData.body)}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-[11px] text-zinc-400 hover:text-zinc-200 px-2 py-1 rounded"
                    title="Open draft directly in Gmail"
                  >
                    <ExternalLink className="w-3 h-3" />
                    <span>In Gmail</span>
                  </a>
                </div>

                <div className="flex items-center gap-1 text-zinc-400">
                  <button
                    onClick={() => {
                      setComposeData({ to: '', subject: '', body: '' });
                      setComposeOpen(false);
                      triggerToast('Draft discarded');
                    }}
                    className="p-1.5 rounded hover:bg-zinc-200 dark:hover:bg-zinc-800 hover:text-rose-500 transition cursor-pointer"
                    title="Discard draft"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {/* Floating Undo / Action Toast */}
      {toast && (
        <div
          className={`fixed bottom-6 left-1/2 -translate-x-1/2 px-4 py-2.5 rounded-xl shadow-lg border text-xs font-medium flex items-center gap-3 z-50 ${
            dark
              ? 'bg-[#1F1F23] border-[#27272A] text-white'
              : 'bg-zinc-900 border-zinc-800 text-white'
          }`}
        >
          <span>{toast.message}</span>
          {toast.undo && (
            <button
              onClick={() => {
                toast.undo();
                setToast(null);
              }}
              className="text-amber-400 hover:underline font-semibold"
            >
              Undo
            </button>
          )}
        </div>
      )}
    </div>
  );
}
