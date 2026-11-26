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
  Check,
  CheckSquare,
  Square,
  MinusSquare,
  RotateCcw,
  ArrowLeft,
  ArrowUp,
  ExternalLink,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Paperclip,
  Copy,
  LogOut,
  Columns,
  LayoutList,
  X,
  Mail,
  MailOpen,
  Trash2,
  Sparkles,
  Calendar,
  Keyboard,
  Filter
} from 'lucide-react';
import { useAuth } from './hooks/useAuth';
import { useEmails } from './hooks/useEmails';
import { AuthCallback } from './components/auth/AuthCallback';
import { ConnectAccountHero } from './components/auth/ConnectAccountHero';
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

function formatSenderTitle(senderDisplay, senderEmail) {
  if (!senderDisplay) return 'Unknown Sender';
  if (!senderDisplay.includes('@')) return senderDisplay;
  const email = senderEmail || senderDisplay;
  const [localPart = '', domainPart = ''] = email.split('@');
  const hostTokens = domainPart.split('.').filter(Boolean);
  const brandRaw = hostTokens.length >= 2 ? hostTokens[0] : hostTokens[0] || '';
  const genericSubs = new Set(['mail', 'email', 'mg', 'notify', 'noreply', 'no-reply', 'news', 'updates']);
  const primaryBrand = genericSubs.has(brandRaw.toLowerCase()) && hostTokens.length >= 3
    ? hostTokens[1]
    : brandRaw;
  const brand = primaryBrand
    ? primaryBrand.charAt(0).toUpperCase() + primaryBrand.slice(1)
    : '';
  const cleanLocal = localPart
    .replace(/^(no-?reply|noreply|donotreply|support|notifications?|updates?|alerts?|info)$/i, '')
    .replace(/[._-]+/g, ' ')
    .trim();
  if (brand && cleanLocal) {
    const capLocal = cleanLocal.replace(/\b\w/g, (c) => c.toUpperCase());
    return `${brand} · ${capLocal}`;
  }
  return brand || senderDisplay;
}

const AVATAR_TONES_LIGHT = [
  'bg-violet-100 text-violet-700 ring-violet-200/70',
  'bg-sky-100 text-sky-700 ring-sky-200/70',
  'bg-emerald-100 text-emerald-700 ring-emerald-200/70',
  'bg-amber-100 text-amber-800 ring-amber-200/70',
  'bg-indigo-100 text-indigo-700 ring-indigo-200/70',
  'bg-teal-100 text-teal-700 ring-teal-200/70',
];

const AVATAR_TONES_DARK = [
  'bg-violet-500/20 text-violet-300 ring-violet-500/30',
  'bg-sky-500/20 text-sky-300 ring-sky-500/30',
  'bg-emerald-500/20 text-emerald-300 ring-emerald-500/30',
  'bg-amber-500/20 text-amber-300 ring-amber-500/30',
  'bg-indigo-500/20 text-indigo-300 ring-indigo-500/30',
  'bg-teal-500/20 text-teal-300 ring-teal-500/30',
];

function getAvatarToneClass(seed, priority, dark) {
  if (priority === 'P1') {
    return dark
      ? 'bg-rose-500/20 text-rose-300 ring-rose-500/40'
      : 'bg-rose-100 text-rose-700 ring-rose-200';
  }
  let hash = 0;
  const s = String(seed || 'M');
  for (let i = 0; i < s.length; i++) {
    hash = (hash * 31 + s.charCodeAt(i)) | 0;
  }
  const idx = Math.abs(hash) % AVATAR_TONES_LIGHT.length;
  return dark ? AVATAR_TONES_DARK[idx] : AVATAR_TONES_LIGHT[idx];
}

function HighlightMatch({ text, query, dark }) {
  const str = String(text || '');
  const q = String(query || '').trim();
  if (!q) return str;
  const escaped = q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const parts = str.split(new RegExp(`(${escaped})`, 'gi'));
  return parts.map((part, idx) =>
    part.toLowerCase() === q.toLowerCase() ? (
      <mark
        key={idx}
        className={`rounded px-0.5 font-semibold ${
          dark ? 'bg-amber-500/25 text-[#FDE68A]' : 'bg-[#FDE68A]/70 text-[#78350F]'
        }`}
      >
        {part}
      </mark>
    ) : (
      part
    )
  );
}

// ============================================================================
// RICH GMAIL-STYLE EMAIL CONTENT RENDERERS
// ============================================================================

function HtmlEmailViewer({ html }) {
  const iframeRef = useRef(null);
  const [iframeHeight, setIframeHeight] = useState(420);
  const [iframeLoaded, setIframeLoaded] = useState(false);

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
          padding: 16px 18px;
          font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
          font-size: 14px;
          line-height: 1.65;
          color: #1E293B;
          background-color: transparent !important;
          word-break: break-word;
          overflow-wrap: break-word;
        }
        img {
          max-width: 100% !important;
          height: auto !important;
          border-radius: 6px;
        }
        table {
          max-width: 100% !important;
        }
        pre, code {
          font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
          font-size: 13px;
          background: #F1F5F9;
          padding: 2px 5px;
          border-radius: 4px;
        }
        pre {
          padding: 12px 14px;
          overflow-x: auto;
        }
        hr {
          border: none;
          border-top: 1px solid #E2E8F0;
          margin: 16px 0;
        }
        a {
          color: #6D28D9;
          text-decoration-thickness: 1px;
          text-underline-offset: 2px;
        }
        blockquote {
          border-left: 3px solid #CBD5E1;
          margin: 10px 0;
          padding-left: 12px;
          color: #475569;
        }
      </style>
    `;

    if (processed.includes('</head>')) {
      return processed.replace('</head>', `${resetStyles}</head>`);
    } else {
      return `${resetStyles}${processed}`;
    }
  }, [html]);

  useEffect(() => {
    const iframe = iframeRef.current;
    if (!iframe) return;
    setIframeLoaded(false);

    let observer = null;
    const measureHeight = () => {
      try {
        const doc = iframe.contentDocument || iframe.contentWindow?.document;
        if (doc && doc.body) {
          const bodyH = doc.body.scrollHeight;
          const docH = doc.documentElement.scrollHeight;
          const h = Math.max(bodyH, docH, 280);
          setIframeHeight(h + 24);
        }
      } catch {
        // Fallback for sandboxed context
      }
    };

    const handleLoad = () => {
      measureHeight();
      setIframeLoaded(true);
      try {
        const doc = iframe.contentDocument || iframe.contentWindow?.document;
        if (doc?.body && typeof ResizeObserver !== 'undefined') {
          observer = new ResizeObserver(measureHeight);
          observer.observe(doc.body);
        }
        doc?.querySelectorAll('img').forEach((img) => {
          img.addEventListener('load', measureHeight, { once: true });
        });
      } catch {
        // Ignore cross-origin restrictions if any
      }
    };

    iframe.addEventListener('load', handleLoad);
    const interval = setInterval(measureHeight, 450);
    const stopTimer = setTimeout(() => clearInterval(interval), 4000);
    const fadeFallback = setTimeout(() => setIframeLoaded(true), 220);

    return () => {
      iframe.removeEventListener('load', handleLoad);
      observer?.disconnect();
      clearInterval(interval);
      clearTimeout(stopTimer);
      clearTimeout(fadeFallback);
    };
  }, [cleanHtml]);

  return (
    <iframe
      ref={iframeRef}
      title="Email Content"
      srcDoc={cleanHtml}
      sandbox="allow-popups allow-popups-to-escape-sandbox allow-same-origin"
      className="iframe-smooth"
      style={{
        width: '100%',
        minHeight: '280px',
        height: `${iframeHeight}px`,
        opacity: iframeLoaded ? 1 : 0,
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
  const rawDisplay = cleanSenderName(item.sender);
  const senderEmail = (item.sender?.match(/<([^>]+)>/)?.[1]) || (item.sender?.includes('@') ? item.sender : '');
  const senderDisplay = formatSenderTitle(rawDisplay, senderEmail);
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
    unread: Boolean(item.is_unread || item.unread || (Array.isArray(item.labels) && item.labels.includes('UNREAD'))),
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
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [layoutMode, setLayoutMode] = useState(() => {
    try {
      const saved = localStorage.getItem('mailmind_layout_mode');
      if (saved === 'table' || saved === 'split') return saved;
    } catch {}
    return typeof window !== 'undefined' && window.innerWidth >= 1100 ? 'split' : 'table';
  }); // 'table' | 'split'
  const [view, setView] = useState('all'); // 'all' | 'attention' | 'recent'
  const [readingEmailId, setReadingEmailId] = useState(null); // when null: table view; when id: open email view
  const [selectedId, setSelectedId] = useState(null);
  const [priorityFilter, setPriorityFilter] = useState(null); // null | 'P1' | 'P2' | 'P3' | 'P4'
  const [windowId, setWindowId] = useState('last_3_months');
  const [search, setSearch] = useState('');
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  const [mobileReading, setMobileReading] = useState(false);
  const [aiSignalsExpanded, setAiSignalsExpanded] = useState(false);
  const [splitWidth, setSplitWidth] = useState(() => {
    try {
      const saved = Number(localStorage.getItem('mailmind_split_width'));
      if (saved >= 350 && saved <= 620) return saved;
    } catch {}
    return 430;
  });
  const [isResizing, setIsResizing] = useState(false);
  const [showScrollTop, setShowScrollTop] = useState(false);

  const listScrollRef = useRef(null);
  const readerScrollRef = useRef(null);
  const splitContainerRef = useRef(null);
  const searchInputRef = useRef(null);

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
      return stored ? new Set(JSON.parse(stored)) : new Set();
    } catch {
      return new Set();
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

  // Combine real backend emails
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
    return [];
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

  const [searchPopoverOpen, setSearchPopoverOpen] = useState(false);

  const closeAllMenus = () => {
    setPriorityMenuOpen(false);
    setWindowMenuOpen(false);
    setUserMenuOpen(false);
    setSelectMenuOpen(false);
    setSearchPopoverOpen(false);
    setShortcutsOpen(false);
  };

  const applyUnreadOnly = useCallback((nextVal) => {
    const resolved = typeof nextVal === 'function' ? nextVal(unreadOnly) : Boolean(nextVal);
    setUnreadOnly(resolved);
    emailsHook.setUnreadOnlyFilter?.(resolved);
  }, [unreadOnly, emailsHook.setUnreadOnlyFilter]);

  // Live full-mailbox breakdown counts from backend aggregate stats (with local unsaved override deltas)
  const { unreadCount, priorityCounts, recentCount } = useMemo(() => {
    const fallbackPriority = { P1: 0, P2: 0, P3: 0, P4: 0 };
    let fallbackUnread = 0;
    let fallbackRecent = 0;

    emails.forEach((em) => {
      if (em.unread && !statusMap[em.id]) fallbackUnread++;
      if (em.daysAgo <= 30) fallbackRecent++;
      if (fallbackPriority[em.priority] !== undefined) {
        fallbackPriority[em.priority]++;
      }
    });

    const serverCounts = emailsHook.stats?.counts;
    let resolvedPriority;
    if (serverCounts) {
      resolvedPriority = {
        P1: Number(serverCounts.P1 ?? 0),
        P2: Number(serverCounts.P2 ?? 0),
        P3: Number(serverCounts.P3 ?? 0),
        P4: Number(serverCounts.P4 ?? 0),
      };
      // Apply only local session overrides that have not yet re-aggregated on server
      Object.entries(overridesMap).forEach(([id, nextPriority]) => {
        const match = emails.find((m) => m.id === id);
        const serverOrig = match?.raw?.final_priority || match?.raw?.predicted_priority || match?.raw?.original_priority;
        if (serverOrig && nextPriority && serverOrig !== nextPriority) {
          if (resolvedPriority[serverOrig] !== undefined) {
            resolvedPriority[serverOrig] = Math.max(0, resolvedPriority[serverOrig] - 1);
          }
          if (resolvedPriority[nextPriority] !== undefined) {
            resolvedPriority[nextPriority] += 1;
          }
        }
      });
    } else {
      resolvedPriority = fallbackPriority;
    }

    if (
      view === 'all' &&
      priorityFilter &&
      !unreadOnly &&
      !search.trim() &&
      emailsHook.activeFilter === priorityFilter &&
      emailsHook.pagination?.total_emails !== undefined &&
      emailsHook.pagination?.total_emails !== null
    ) {
      resolvedPriority[priorityFilter] = Number(emailsHook.pagination.total_emails);
    }

    const resolvedUnread =
      unreadOnly &&
      view === 'all' &&
      !priorityFilter &&
      !search.trim() &&
      emailsHook.unreadOnlyFilter &&
      emailsHook.pagination?.total_emails !== undefined &&
      emailsHook.pagination?.total_emails !== null
        ? Number(emailsHook.pagination.total_emails)
        : (emailsHook.stats?.unread_count ?? fallbackUnread);

    const resolvedRecent =
      view === 'recent' &&
      !priorityFilter &&
      !unreadOnly &&
      !search.trim() &&
      emailsHook.activeFilter === 'RECENT' &&
      emailsHook.pagination?.total_emails !== undefined &&
      emailsHook.pagination?.total_emails !== null
        ? Number(emailsHook.pagination.total_emails)
        : (emailsHook.stats?.recent_count ?? fallbackRecent);

    return {
      unreadCount: Number(resolvedUnread) || 0,
      priorityCounts: resolvedPriority,
      recentCount: Number(resolvedRecent) || 0,
    };
  }, [
    emails,
    statusMap,
    overridesMap,
    emailsHook.stats,
    emailsHook.activeFilter,
    emailsHook.unreadOnlyFilter,
    emailsHook.pagination?.total_emails,
    view,
    priorityFilter,
    unreadOnly,
    search,
  ]);

  // Active Window Cutoff
  const cutoffDays = useMemo(() => {
    return WINDOWS.find((w) => w.id === windowId)?.days ?? 90;
  }, [windowId]);

  // Attention Counter (synced with backend active queue count)
  const attentionCount = useMemo(() => {
    if (
      view === 'attention' &&
      !priorityFilter &&
      !unreadOnly &&
      !search.trim() &&
      emailsHook.activeFilter === 'NEEDS_ATTENTION' &&
      emailsHook.pagination?.total_emails !== undefined &&
      emailsHook.pagination?.total_emails !== null
    ) {
      return Number(emailsHook.pagination.total_emails);
    }
    if (emailsHook.stats?.needs_attention_count !== undefined && emailsHook.stats.needs_attention_count !== null) {
      return Number(emailsHook.stats.needs_attention_count);
    }
    return emails.filter((e) => e.needsAttention && !statusMap[e.id]).length;
  }, [view, priorityFilter, unreadOnly, search, emailsHook.activeFilter, emailsHook.pagination?.total_emails, emailsHook.stats, emails, statusMap]);

  // Filtered List Items (Folder Filtering with Timeframe & Strict Time Sorting)
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
      } else if (view === 'recent' && emailsHook.activeFilter !== 'RECENT') {
        if (item.daysAgo > 30) return false;
      }

      if (priorityFilter) {
        if (!item.analyzed || item.priority !== priorityFilter) return false;
      }

      if (unreadOnly && !item.unread) {
        return false;
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
  }, [emails, view, statusMap, starredIds, priorityFilter, unreadOnly, search, windowId]);

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
    setAiSignalsExpanded(false);
    closeAllMenus();
  };

  // Keep reading pane at top and keyboard-selected row visible in list
  useEffect(() => {
    readerScrollRef.current?.scrollTo({ top: 0 });
    if (!currentEmail?.id || !listScrollRef.current) return;
    const rows = listScrollRef.current.querySelectorAll('[data-email-id]');
    for (const el of rows) {
      if (el.getAttribute('data-email-id') === String(currentEmail.id)) {
        el.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        break;
      }
    }
  }, [currentEmail?.id]);

  const setLayoutModeAndPersist = (nextMode) => {
    setLayoutMode(nextMode);
    if (nextMode === 'split') {
      setReadingEmailId(null);
      setMobileReading(false);
    }
    try {
      localStorage.setItem('mailmind_layout_mode', nextMode);
    } catch {}
  };

  const handlePageNav = (delta) => {
    emailsHook.setPage?.((p) => Math.max(1, p + delta));
    listScrollRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
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
    const targetId = item.raw?.email_id || item.raw?.id;
    advanceSelection(item.id);
    setStatusMap((map) => ({ ...map, [item.id]: { state: 'done' } }));
    closeAllMenus();

    if (targetId) {
      emailsHook.resolveEmail?.(targetId);
    }

    triggerToast('Marked done', () => {
      setStatusMap((map) => {
        const next = { ...map };
        if (prev) next[item.id] = prev;
        else delete next[item.id];
        return next;
      });
      if (targetId) {
        emailsHook.unresolveEmail?.(targetId);
      }
    });
  };

  const snoozeItem = (item, hours = 3, e = null) => {
    if (e) e.stopPropagation();
    if (!item) return;
    const prev = statusMap[item.id];
    const targetId = item.raw?.email_id || item.raw?.id;
    const untilIso = new Date(Date.now() + hours * 3600 * 1000).toISOString();
    advanceSelection(item.id);
    setStatusMap((map) => ({ ...map, [item.id]: { state: 'snoozed', until: untilIso } }));
    closeAllMenus();

    if (targetId) {
      emailsHook.snoozeEmail?.(targetId, untilIso, item.thread_id || null, 'Snoozed from MailMind inbox');
    }

    triggerToast(`Snoozed for ${hours} hours`, () => {
      setStatusMap((map) => {
        const next = { ...map };
        if (prev) next[item.id] = prev;
        else delete next[item.id];
        return next;
      });
      if (targetId) {
        emailsHook.unsnoozeEmail?.(targetId);
      }
    });
  };

  const restoreItem = (item, e = null) => {
    if (e) e.stopPropagation();
    if (!item) return;
    const prevState = statusMap[item.id]?.state;
    const targetId = item.raw?.email_id || item.raw?.id;
    setStatusMap((map) => {
      const next = { ...map };
      delete next[item.id];
      return next;
    });
    if (targetId) {
      if (prevState === 'snoozed' || item.raw?.is_snoozed) {
        emailsHook.unsnoozeEmail?.(targetId);
      } else {
        emailsHook.unresolveEmail?.(targetId);
      }
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

  // Keyboard navigation (Escape, /, Cmd/Ctrl+K, j/k, ArrowDown/Up, e, s, ?, Enter)
  useEffect(() => {
    const onKeyDown = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        closeAllMenus();
        searchInputRef.current?.focus();
        searchInputRef.current?.select?.();
        return;
      }

      if (e.key === 'Escape') {
        const anyMenuOpen =
          priorityMenuOpen ||
          windowMenuOpen ||
          userMenuOpen ||
          selectMenuOpen ||
          searchPopoverOpen ||
          shortcutsOpen ||
          mobileNavOpen;
        setPriorityMenuOpen(false);
        setWindowMenuOpen(false);
        setUserMenuOpen(false);
        setSelectMenuOpen(false);
        setSearchPopoverOpen(false);
        setShortcutsOpen(false);
        setMobileNavOpen(false);
        if (!anyMenuOpen && (readingEmailId || mobileReading)) {
          setReadingEmailId(null);
          setMobileReading(false);
        }
        return;
      }

      if (!auth.isAuthenticated || e.metaKey || e.ctrlKey || e.altKey) return;
      const tag = e.target?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || e.target?.isContentEditable) {
        return;
      }

      if (e.key === '/') {
        e.preventDefault();
        closeAllMenus();
        searchInputRef.current?.focus();
      } else if (e.key === '?') {
        e.preventDefault();
        setShortcutsOpen((o) => !o);
      } else if (e.key === 'j' || e.key === 'ArrowDown') {
        if (nextEmail) {
          e.preventDefault();
          setSelectedId(nextEmail.id);
          if (readingEmailId) setReadingEmailId(nextEmail.id);
        }
      } else if (e.key === 'k' || e.key === 'ArrowUp') {
        if (prevEmail) {
          e.preventDefault();
          setSelectedId(prevEmail.id);
          if (readingEmailId) setReadingEmailId(prevEmail.id);
        }
      } else if (e.key === 'e' && currentEmail) {
        e.preventDefault();
        if (statusMap[currentEmail.id]?.state === 'done') {
          restoreItem(currentEmail);
        } else {
          markDone(currentEmail);
        }
      } else if (e.key === 'h' && currentEmail) {
        e.preventDefault();
        snoozeItem(currentEmail, 3);
      } else if (e.key === 's' && currentEmail) {
        e.preventDefault();
        toggleStarEmail(currentEmail.id);
      } else if (e.key === 'Enter' && !readingEmailId && layoutMode === 'table' && currentEmail) {
        // Only trigger Enter if focus is not already inside an interactive button/link
        if (tag !== 'BUTTON' && tag !== 'A' && !e.target?.getAttribute('role')) {
          e.preventDefault();
          selectEmail(currentEmail);
        }
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [
    auth.isAuthenticated,
    priorityMenuOpen,
    windowMenuOpen,
    userMenuOpen,
    selectMenuOpen,
    searchPopoverOpen,
    shortcutsOpen,
    mobileNavOpen,
    readingEmailId,
    mobileReading,
    layoutMode,
    currentEmail,
    nextEmail,
    prevEmail,
    statusMap,
  ]);

  // Render OAuth callback
  if (currentPath === '/auth/callback') {
    return (
      <AuthCallback
        exchangeHandoff={auth.exchangeHandoff}
        onSuccess={() => {
          window.history.replaceState({}, document.title, '/');
          setCurrentPath('/');
          if (!auth.isAuthenticated) {
            auth.refreshStatus?.();
          }
        }}
        onCancel={() => {
          window.history.replaceState({}, document.title, '/');
          setCurrentPath('/');
        }}
      />
    );
  }

  // Render Login Page when unauthenticated
  if (!auth.isAuthenticated) {
    if (auth.isLoading) {
      return (
        <div className={`min-h-screen flex items-center justify-center ${dark ? 'bg-[#0F1219] text-white' : 'bg-[#F8FAFC] text-slate-800'}`}>
          <div className="flex flex-col items-center gap-3">
            <RefreshCw className="w-6 h-6 animate-spin text-[#7E22CE]" />
            <span className="text-xs font-semibold tracking-wide text-slate-400">Verifying session...</span>
          </div>
        </div>
      );
    }
    return (
      <ConnectAccountHero
        onLogin={auth.login}
        onDevLogin={auth.devLogin}
        isLoading={auth.isLoading}
        error={auth.error}
      />
    );
  }

  // Calculate authoritative full-mailbox & view pagination counts
  const isUnfilteredInbox = view === 'all' && !priorityFilter && !unreadOnly && !search.trim();
  const inboxTotalCount =
    emailsHook.stats?.total_analyzed ??
    (isUnfilteredInbox ? emailsHook.pagination?.total_emails : null) ??
    emails.length;
  const expectedServerFilter =
    priorityFilter ||
    (view === 'attention' ? 'NEEDS_ATTENTION' : view === 'recent' ? 'RECENT' : 'ALL');
  const isServerSynced =
    emailsHook.activeFilter === expectedServerFilter &&
    Boolean(unreadOnly) === Boolean(emailsHook.unreadOnlyFilter);
  const isCustomFiltered = Boolean(search.trim()) || !isServerSynced;
  const currentViewTotal = isCustomFiltered
    ? visibleEmails.length
    : (emailsHook.pagination?.total_emails ?? visibleEmails.length);

  const currentPage = emailsHook.pagination?.page || 1;
  const pageSize = emailsHook.pagination?.page_size || 50;
  const startNum = visibleEmails.length === 0 ? 0 : ((currentPage - 1) * pageSize) + 1;
  const endNum = visibleEmails.length === 0 ? 0 : Math.min(startNum + visibleEmails.length - 1, currentViewTotal);
  const hasNextPage = !isCustomFiltered ? Boolean(emailsHook.pagination?.has_next) : false;

  const activeWindowLabel = WINDOWS.find((w) => w.id === windowId)?.label || 'Last 3 months';
  const currentPriority = currentEmail ? (PRIORITIES[currentEmail.priority] || PRIORITIES.P3) : null;
  const currentTriage = currentEmail ? statusMap[currentEmail.id] : null;

  const userName = auth.user?.name || auth.user?.email?.split('@')[0] || 'User';
  const userInitials = auth.user?.name ? getSenderInitials(auth.user.name) : 'BK';

  const handleNavSelect = (navId) => {
    setView(navId);
    setReadingEmailId(null);
    setMobileReading(false);
    setMobileNavOpen(false);
    setPriorityFilter(null);
    applyUnreadOnly(false);
    if (navId === 'attention') {
      emailsHook.setActiveFilter?.('NEEDS_ATTENTION');
    } else if (navId === 'recent') {
      emailsHook.setActiveFilter?.('RECENT');
    } else {
      emailsHook.setActiveFilter?.('ALL');
    }
    listScrollRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const renderSidebarBody = (expanded, isDrawer = false) => (
    <>
      <div className="space-y-3 px-3">
        {isDrawer && (
          <div className={`flex items-center justify-between pb-2 mb-1 border-b ${dark ? 'border-[#252D3C]' : 'border-[#E2E8F0]'}`}>
            <div className="flex items-center gap-2.5">
              <BrandMark />
              <span className={`font-bold tracking-tight text-base ${dark ? 'text-[#F8FAFC]' : 'text-[#2E084D]'}`}>
                MailMind<span className="text-[#F59E0B] ml-0.5">•</span>
              </span>
            </div>
            <button
              type="button"
              onClick={() => setMobileNavOpen(false)}
              aria-label="Close navigation menu"
              className={`p-1.5 rounded-lg transition ${dark ? 'text-[#94A3B8] hover:text-white hover:bg-[#202737]' : 'text-[#64748B] hover:bg-[#EDF2F7]'}`}
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Primary Views */}
        <nav className="space-y-1" aria-label="Mailbox folders">
          {[
            { id: 'all', label: 'Inbox', icon: Inbox, count: inboxTotalCount },
            { id: 'attention', label: 'Needs Attention', icon: AlertCircle, count: attentionCount },
            { id: 'recent', label: 'Recent Mail', icon: Clock, count: recentCount }
          ].map((nav) => {
            const active = view === nav.id && !priorityFilter;
            const IconComponent = nav.icon;
            return (
              <button
                key={nav.id}
                type="button"
                onClick={() => handleNavSelect(nav.id)}
                className={`w-full flex items-center justify-between py-2.5 rounded-xl text-[13.5px] transition-all duration-150 cursor-pointer ${
                  expanded ? 'pl-3.5 pr-3' : 'px-2 justify-center'
                } ${
                  active
                    ? dark
                      ? 'bg-[#2E1A40] text-[#F8FAFC] font-semibold border-l-4 border-[#F59E0B] shadow-sm'
                      : 'bg-white text-[#3B0764] font-bold shadow-sm border border-[#E2E8F0] ring-1 ring-[#581C87]/10'
                    : dark
                    ? 'text-[#CBD5E1] hover:text-white hover:bg-[#202737]'
                    : 'text-[#524365] hover:text-[#2E084D] hover:bg-white/80 hover:shadow-sm'
                }`}
                title={nav.label}
              >
                  <div className="relative flex items-center gap-3 min-w-0">
                    {active && !dark && (
                      <span className="w-1.5 h-4 rounded-full bg-gradient-to-b from-[#F59E0B] to-[#D97706] shadow-[0_0_8px_rgba(245,158,11,0.5)] shrink-0" />
                    )}
                    <IconComponent
                      className={`w-4 h-4 shrink-0 transition-colors ${
                        active
                          ? dark ? 'text-[#F59E0B]' : 'text-[#581C87]'
                          : dark ? 'text-[#94A3B8]' : 'text-[#716080]'
                      }`}
                    />
                    {!expanded && nav.id === 'attention' && nav.count > 0 && (
                      <span className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-[#F59E0B] ring-2 ring-[#F5F8FC] dark:ring-[#141822]" />
                    )}
                    {expanded && <span className="truncate">{nav.label}</span>}
                  </div>

                {expanded && nav.count !== null && nav.count !== undefined && (
                  <span
                    className={`text-[11px] tabular-nums font-bold px-2 py-0.5 rounded-full transition-colors ${
                      active
                        ? dark
                          ? 'bg-[#F59E0B] text-[#1E082B] shadow-sm'
                          : 'bg-[#F59E0B]/20 text-[#B45309] border border-[#F59E0B]/35'
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
        <div className={`pt-3 border-t ${dark ? 'border-[#252D3C]' : 'border-[#E2E8F0]'}`}>
          {expanded && (
            <div className="px-3 pb-1.5 text-[11px] font-semibold text-[#94A3B8] uppercase tracking-wider">
              Priority
            </div>
          )}
          <div className={expanded ? 'space-y-0.5' : 'space-y-1.5 flex flex-col items-center'}>
            {Object.values(PRIORITIES).map((tier) => {
              const active = priorityFilter === tier.id;
              const tierCount = priorityCounts[tier.id] ?? 0;
              return (
                <button
                  key={tier.id}
                  type="button"
                  title={`${tier.name} (${tierCount.toLocaleString()})`}
                  onClick={() => {
                    const nextPriority = priorityFilter === tier.id ? null : tier.id;
                    setView('all');
                    setPriorityFilter(nextPriority);
                    setReadingEmailId(null);
                    setMobileReading(false);
                    setMobileNavOpen(false);
                    emailsHook.setActiveFilter?.(nextPriority || 'ALL');
                    listScrollRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
                  }}
                  className={`${
                    expanded
                      ? 'w-full flex items-center justify-between px-3 py-2 rounded-xl text-[13px]'
                      : 'w-9 h-9 flex items-center justify-center rounded-xl'
                  } transition-all duration-150 cursor-pointer ${
                    active
                      ? dark
                        ? 'bg-[#2E1A40] text-[#F8FAFC] font-semibold ring-1 ring-[#F59E0B]/40'
                        : 'bg-white text-[#3B0764] font-semibold shadow-sm border border-[#E2E8F0]'
                      : dark
                      ? 'text-[#CBD5E1] hover:text-white hover:bg-[#202737]'
                      : 'text-[#524365] hover:text-[#2E084D] hover:bg-white/80'
                  }`}
                >
                  <span className="flex items-center gap-2.5">
                    <span
                      className={`w-2.5 h-2.5 rounded-full shrink-0 shadow-sm ${
                        active ? 'ring-2 ring-offset-1 ring-[#F59E0B]/50' : ''
                      }`}
                      style={{ backgroundColor: tier.color }}
                    />
                    {expanded && <span>{tier.name}</span>}
                  </span>
                  {expanded && (
                    active ? (
                      <span className="text-[11px] text-[#F59E0B] hover:text-[#D97706] font-bold">Clear</span>
                    ) : (
                      <span
                        className={`text-[11px] tabular-nums font-semibold px-1.5 py-0.5 rounded-md ${
                          dark ? 'text-[#94A3B8] bg-[#202737]' : 'text-[#64748B] bg-[#EEF2F7]'
                        }`}
                      >
                        {tierCount.toLocaleString()}
                      </span>
                    )
                  )}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Footer of Sidebar: Live Background Scan Progress + Timeframe Selector */}
      {expanded && (
        <div className={`px-3 pt-3 space-y-2.5 border-t ${dark ? 'border-[#252D3C]' : 'border-[#E2E8F0]'}`}>
          {emailsHook.isScanning && emailsHook.scanStatus && (
            <div
              className={`rounded-xl p-2.5 border text-[11px] animate-fade-in ${
                dark
                  ? 'bg-[#181D29] border-[#2D3648] text-[#CBD5E1]'
                  : 'bg-white/90 border-[#E2E8F0] text-[#4D3A5B] shadow-sm'
              }`}
            >
              <div className="flex items-center justify-between gap-2 mb-1.5">
                <span className="flex items-center gap-1.5 font-semibold truncate">
                  <RefreshCw className="w-3 h-3 animate-spin text-[#F59E0B] shrink-0" />
                  <span className="truncate">Indexing mailbox</span>
                </span>
                <span className="tabular-nums font-bold text-[#F59E0B] shrink-0">
                  {Math.round(emailsHook.scanStatus.progress_percent || 0)}%
                </span>
              </div>
              <div className={`w-full h-1.5 rounded-full overflow-hidden ${dark ? 'bg-[#10141D]' : 'bg-[#EEF2F7]'}`}>
                <div
                  className="h-full rounded-full bg-gradient-to-r from-[#581C87] to-[#F59E0B] transition-all duration-300"
                  style={{ width: `${Math.min(100, Math.max(6, Math.round(emailsHook.scanStatus.progress_percent || 0)))}%` }}
                />
              </div>
              {emailsHook.scanStatus.total > 0 && (
                <div className="mt-1 text-[10px] text-[#94A3B8] tabular-nums">
                  {(emailsHook.scanStatus.analyzed || 0).toLocaleString()} of {emailsHook.scanStatus.total.toLocaleString()} emails
                </div>
              )}
            </div>
          )}
          <div className="relative" onClick={(e) => e.stopPropagation()}>
            <button
              type="button"
              onClick={() => {
                setWindowMenuOpen((o) => !o);
                setUserMenuOpen(false);
              }}
              className={`w-full flex items-center justify-between px-3 py-2.5 rounded-xl text-xs transition-all cursor-pointer border ${
                dark
                  ? 'text-[#CBD5E1] hover:text-white hover:bg-[#202737] border-[#2D3648]'
                  : 'bg-white/80 hover:bg-white text-[#4D3A5B] hover:text-[#2E084D] hover:border-[#94A3B8] border-[#CBD5E1] shadow-sm hover:shadow-sm'
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
                className={`absolute bottom-12 left-0 w-48 rounded-2xl p-1.5 shadow-xl border z-50 animate-slide-down ${
                  dark
                    ? 'bg-[#181D29] border-[#2D3648] text-[#F8FAFC]'
                    : 'bg-white/95 backdrop-blur-md border-[#CBD5E1] shadow-xl text-[#1E1231]'
                }`}
              >
                {WINDOWS.map((w) => (
                  <button
                    key={w.id}
                    type="button"
                    onClick={() => {
                      selectWindow(w.id);
                      if (isDrawer) setMobileNavOpen(false);
                    }}
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
    </>
  );

  return (
    <div
      ref={rootRef}
      onClick={closeAllMenus}
      className={`h-[100dvh] w-full overflow-hidden flex flex-col relative select-none transition-colors duration-200 safe-top-pad safe-bottom-pad ${
        dark ? 'bg-[#10141D] text-[#F8FAFC]' : 'bg-[#EEF2F7] text-[#1E1231]'
      }`}
    >
      {/* Sleek 2.5px Top Sync Progress Line */}
      <div className="fixed top-0 left-0 right-0 h-[2.5px] z-50 pointer-events-none overflow-hidden">
        <div
          className={`h-full bg-gradient-to-r from-[#581C87] via-[#F59E0B] to-[#CBD5E1] transition-all duration-500 ease-out ${
            syncing ? 'w-full opacity-100' : 'w-0 opacity-0'
          }`}
        />
      </div>

      {/* ==================================================================== */}
      {/* TOP BAR: RESPONSIVE HEADER WITH SEARCH, LOGO, CONTROLS, USER AVATAR  */}
      {/* ==================================================================== */}
      <header
        className={`relative z-40 h-14 sm:h-16 px-3 sm:px-6 flex items-center justify-between gap-2 border-b shrink-0 backdrop-blur-md transition-colors duration-200 ${
          dark
            ? 'bg-[#181D29]/95 border-[#2D3648] text-[#F8FAFC]'
            : 'bg-[#F5F8FC]/95 border-[#CBD5E1] text-[#1E1231] shadow-[0_1px_3px_rgba(88,28,135,0.03)]'
        }`}
      >
        {/* Left: Hamburger + Logo */}
        <div className="flex items-center gap-2 sm:gap-3 w-auto md:w-56 shrink-0">
          <button
            type="button"
            onClick={() => {
              if (typeof window !== 'undefined' && window.innerWidth < 768) {
                setMobileNavOpen((o) => !o);
              } else {
                setSidebarOpen((o) => !o);
              }
            }}
            aria-label="Toggle navigation menu"
            className={`p-2 rounded-full transition cursor-pointer hover:scale-105 active:scale-95 ${
              dark
                ? 'text-[#CBD5E1] hover:text-white hover:bg-[#202737]'
                : 'text-[#4D3A5B] hover:text-[#581C87] hover:bg-white hover:shadow-sm'
            }`}
            title="Main menu"
          >
            <Menu className="w-5 h-5" />
          </button>

          <div
            onClick={() => {
              setReadingEmailId(null);
              setMobileReading(false);
              setView('all');
              setPriorityFilter(null);
              applyUnreadOnly(false);
              emailsHook.setActiveFilter?.('ALL');
            }}
            className="flex items-center gap-2 font-semibold text-lg tracking-tight cursor-pointer"
          >
            <BrandMark />
            <span className={`hidden sm:inline font-bold tracking-tight text-lg ${dark ? 'text-[#F8FAFC]' : 'text-[#2E084D]'}`}>
              MailMind<span className="text-[#F59E0B] ml-0.5">•</span>
            </span>
          </div>
        </div>

        {/* Center: Expansive Rounded Pill Search Bar */}
        <div className="flex-1 max-w-2xl px-1 sm:px-6 relative" onClick={(e) => e.stopPropagation()}>
          <div
            className={`flex items-center h-10 sm:h-11 px-3 sm:px-4 rounded-full transition-all border ${
              dark
                ? 'bg-[#141822] border-[#2D3648] focus-within:bg-[#181D29] focus-within:border-[#F59E0B] focus-within:ring-2 focus-within:ring-[#F59E0B]/25 focus-within:shadow-md'
                : 'bg-white border-[#CBD5E1] hover:border-[#94A3B8] focus-within:bg-white focus-within:border-[#581C87] focus-within:ring-2 focus-within:ring-[#581C87]/15 focus-within:shadow-[0_2px_12px_rgba(88,28,135,0.08)]'
            }`}
          >
            <Search className={`w-4 h-4 shrink-0 mr-2 sm:mr-3 ${dark ? 'text-[#94A3B8]' : 'text-[#581C87]'}`} />
            <input
              ref={searchInputRef}
              type="text"
              aria-label="Search in emails"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                emailsHook.setSearchQuery?.(e.target.value);
              }}
              placeholder="Search emails, senders, topics..."
              className={`w-full bg-transparent text-[13.5px] focus:outline-none ${
                dark
                  ? 'text-[#F8FAFC] placeholder-[#94A3B8]'
                  : 'text-[#1E1231] placeholder-[#786B84]'
              }`}
            />

            <div className="flex items-center gap-1 shrink-0 ml-1">
              {!search && (
                <kbd
                  className={`hidden sm:inline-flex kbd-pill border mr-0.5 ${
                    dark
                      ? 'bg-[#202737] border-[#2D3648] text-[#94A3B8]'
                      : 'bg-[#F8FAFC] border-[#E2E8F0] text-[#64748B]'
                  }`}
                  title="Press / or Ctrl+K to search"
                >
                  /
                </kbd>
              )}

              {search && (
                <>
                  {emailsHook.isRefreshing && (
                    <RefreshCw className="w-3.5 h-3.5 animate-spin text-[#F59E0B] mr-0.5 shrink-0" />
                  )}
                  <button
                    type="button"
                    aria-label="Clear search"
                    onClick={() => {
                      setSearch('');
                      emailsHook.setSearchQuery?.('');
                      searchInputRef.current?.focus();
                    }}
                    className={`p-1 rounded-full transition cursor-pointer ${
                      dark
                        ? 'text-[#94A3B8] hover:text-white hover:bg-[#202737]'
                        : 'text-[#786B84] hover:text-[#1E1231] hover:bg-[#F1F5F9]'
                    }`}
                  >
                    <X className="w-4 h-4" />
                  </button>
                </>
              )}

              <button
                type="button"
                aria-label="Quick filters"
                onClick={() => {
                  setSearchPopoverOpen((o) => !o);
                  setShortcutsOpen(false);
                }}
                title="Quick triage filters"
                className={`relative p-1.5 rounded-full transition cursor-pointer ${
                  searchPopoverOpen
                    ? dark
                      ? 'bg-[#202737] text-[#F59E0B]'
                      : 'bg-[#FAF5FF] text-[#581C87]'
                    : dark
                    ? 'text-[#94A3B8] hover:text-white hover:bg-[#202737]'
                    : 'text-[#786B84] hover:text-[#1E1231] hover:bg-[#F1F5F9]'
                }`}
              >
                <SlidersHorizontal className="w-4 h-4" />
                {(priorityFilter || unreadOnly || view !== 'all') && (
                  <span className="absolute top-1 right-1 w-1.5 h-1.5 rounded-full bg-[#F59E0B]" />
                )}
              </button>
            </div>
          </div>

          {searchPopoverOpen && (
            <div
              className={`absolute left-1 sm:left-6 right-1 sm:right-6 top-12 rounded-2xl p-3.5 shadow-xl border z-50 animate-slide-down ${
                dark ? 'bg-[#181D29] border-[#2D3648] text-[#F8FAFC]' : 'bg-white border-[#CBD5E1] text-[#1E1231]'
              }`}
            >
              <div className="flex items-center justify-between mb-2.5">
                <span className="text-[11px] font-semibold uppercase tracking-wider text-[#94A3B8]">
                  Quick Filters
                </span>
                {(priorityFilter || unreadOnly || view !== 'all' || search) && (
                  <button
                    type="button"
                    onClick={() => {
                      setPriorityFilter(null);
                      applyUnreadOnly(false);
                      setView('all');
                      setSearch('');
                      emailsHook.setSearchQuery?.('');
                      emailsHook.setActiveFilter?.('ALL');
                      setSearchPopoverOpen(false);
                    }}
                    className="text-[11px] font-semibold text-[#F59E0B] hover:underline cursor-pointer"
                  >
                    Reset all
                  </button>
                )}
              </div>
              <div className="flex flex-wrap gap-1.5">
                {Object.values(PRIORITIES).map((tier) => (
                  <button
                    key={tier.id}
                    type="button"
                    onClick={() => {
                      const nextP = priorityFilter === tier.id ? null : tier.id;
                      setView('all');
                      setPriorityFilter(nextP);
                      emailsHook.setActiveFilter?.(nextP || 'ALL');
                      setSearchPopoverOpen(false);
                    }}
                    className={`inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition cursor-pointer border ${
                      priorityFilter === tier.id
                        ? dark ? 'bg-[#2E1A40] border-[#F59E0B] text-white' : 'bg-[#FAF5FF] border-[#581C87] text-[#3B0764]'
                        : dark ? 'bg-[#141822] border-[#252D3C] hover:bg-[#202737]' : 'bg-[#F8FAFC] border-[#E2E8F0] hover:bg-[#EEF2F7]'
                    }`}
                  >
                    <span className="w-2 h-2 rounded-full" style={{ backgroundColor: tier.color }} />
                    <span>{tier.name}</span>
                  </button>
                ))}
                <button
                  type="button"
                  onClick={() => {
                    applyUnreadOnly((u) => !u);
                    setSearchPopoverOpen(false);
                  }}
                  className={`inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition cursor-pointer border ${
                    unreadOnly
                      ? dark ? 'bg-[#2E1A40] border-[#F59E0B] text-white' : 'bg-[#FAF5FF] border-[#581C87] text-[#3B0764]'
                      : dark ? 'bg-[#141822] border-[#252D3C] hover:bg-[#202737]' : 'bg-[#F8FAFC] border-[#E2E8F0] hover:bg-[#EEF2F7]'
                  }`}
                >
                  <Mail className="w-3.5 h-3.5 text-[#F59E0B]" />
                  <span>Unread only ({unreadCount.toLocaleString()})</span>
                </button>
                <button
                  type="button"
                  onClick={() => {
                    handleNavSelect('attention');
                    setSearchPopoverOpen(false);
                  }}
                  className={`inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition cursor-pointer border ${
                    view === 'attention'
                      ? dark ? 'bg-[#2E1A40] border-[#F59E0B] text-white' : 'bg-[#FAF5FF] border-[#581C87] text-[#3B0764]'
                      : dark ? 'bg-[#141822] border-[#252D3C] hover:bg-[#202737]' : 'bg-[#F8FAFC] border-[#E2E8F0] hover:bg-[#EEF2F7]'
                  }`}
                >
                  <AlertCircle className="w-3.5 h-3.5 text-[#F59E0B]" />
                  <span>Needs Attention</span>
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Right: Quick Controls + Keyboard Help + User Profile */}
        <div className="flex items-center gap-1 sm:gap-1.5 shrink-0">
          <button
            type="button"
            aria-label="Sync mailbox"
            onClick={() => emailsHook.refresh?.(windowId)}
            className={`p-2 rounded-full transition cursor-pointer hover:scale-105 active:scale-95 ${
              dark
                ? 'text-[#CBD5E1] hover:text-white hover:bg-[#202737]'
                : 'text-[#4D3A5B] hover:text-[#581C87] hover:bg-white hover:shadow-sm'
            }`}
            title="Sync mailbox"
          >
            <RefreshCw className={`w-4 h-4 ${syncing ? 'animate-spin text-[#F59E0B]' : ''}`} />
          </button>

          <div className="relative hidden md:block" onClick={(e) => e.stopPropagation()}>
            <button
              type="button"
              aria-label="Keyboard shortcuts"
              onClick={() => {
                setShortcutsOpen((o) => !o);
                setUserMenuOpen(false);
                setSearchPopoverOpen(false);
              }}
              className={`p-2 rounded-full transition cursor-pointer hover:scale-105 active:scale-95 ${
                shortcutsOpen
                  ? dark
                    ? 'bg-[#202737] text-[#F59E0B]'
                    : 'bg-white text-[#581C87] shadow-sm'
                  : dark
                  ? 'text-[#CBD5E1] hover:text-white hover:bg-[#202737]'
                  : 'text-[#4D3A5B] hover:text-[#581C87] hover:bg-white hover:shadow-sm'
              }`}
              title="Keyboard shortcuts (?)"
            >
              <Keyboard className="w-4 h-4" />
            </button>

            {shortcutsOpen && (
              <div
                className={`absolute right-0 top-12 w-72 rounded-2xl p-4 shadow-2xl border z-50 animate-slide-down ${
                  dark ? 'bg-[#181D29] border-[#2D3648] text-[#F8FAFC]' : 'bg-white border-[#CBD5E1] text-[#1E1231]'
                }`}
              >
                <div className="text-[11px] font-semibold uppercase tracking-wider text-[#94A3B8] mb-3">
                  Keyboard Shortcuts
                </div>
                <div className="space-y-2.5 text-xs">
                  {[
                    { key: 'j / k', label: 'Next / Previous email' },
                    { key: '/ or ⌘K', label: 'Search emails' },
                    { key: 'e', label: 'Mark done / Restore' },
                    { key: 'h', label: 'Snooze 3 hours' },
                    { key: 's', label: 'Toggle star' },
                    { key: 'Esc', label: 'Back / Close menu' },
                  ].map((item) => (
                    <div key={item.key} className="flex items-center justify-between gap-3">
                      <span className={dark ? 'text-[#CBD5E1]' : 'text-[#4D3A5B]'}>{item.label}</span>
                      <kbd
                        className={`kbd-pill border ${
                          dark
                            ? 'bg-[#121620] border-[#2D3648] text-[#FBBF24]'
                            : 'bg-[#F8FAFC] border-[#CBD5E1] text-[#581C87]'
                        }`}
                      >
                        {item.key}
                      </kbd>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          <button
            type="button"
            aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'}
            onClick={() => setDark((d) => !d)}
            className={`p-2 rounded-full transition cursor-pointer hover:scale-105 active:scale-95 ${
              dark
                ? 'text-[#CBD5E1] hover:text-[#F59E0B] hover:bg-[#202737]'
                : 'text-[#4D3A5B] hover:text-[#581C87] hover:bg-white hover:shadow-sm'
            }`}
            title={dark ? 'Switch to light mode' : 'Switch to dark mode'}
          >
            {dark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4 text-[#581C87]" />}
          </button>

          {/* User Profile Avatar Dropdown */}
          <div className="relative ml-2" onClick={(e) => e.stopPropagation()}>
            {auth.isAuthenticated ? (
              <button
                type="button"
                aria-label="Account menu"
                onClick={() => {
                  setUserMenuOpen((o) => !o);
                  setWindowMenuOpen(false);
                  setShortcutsOpen(false);
                }}
                className={`w-8 h-8 rounded-full text-xs font-bold flex items-center justify-center shrink-0 ring-2 cursor-pointer transition hover:scale-105 active:scale-95 ${
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
                type="button"
                onClick={() => auth.devLogin ? auth.devLogin() : auth.login()}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold bg-gradient-to-r from-[#2E084D] to-[#581C87] hover:from-[#3B0A63] hover:to-[#6B21A8] text-white shadow-sm border border-[#7E22CE]/40 transition cursor-pointer"
                title="Connect your Gmail account"
              >
                <span>Connect Gmail</span>
              </button>
            )}

            {userMenuOpen && auth.isAuthenticated && (
              <div
                className={`absolute right-0 top-12 w-72 rounded-2xl p-3 shadow-2xl border z-50 animate-slide-down ${
                  dark
                    ? 'bg-[#181D29] border-[#2D3648] text-[#F8FAFC]'
                    : 'bg-[#FFFFFF] border-[#CBD5E1] text-[#1D0B2B]'
                }`}
              >
                <div className={`px-2 py-2 pb-3 border-b mb-2 ${dark ? 'border-[#252D3C]' : 'border-[#E2E8F0]'}`}>
                  <div className="flex items-center gap-3">
                    <div
                      className={`w-9 h-9 rounded-full text-xs font-bold flex items-center justify-center shrink-0 ring-1 ${
                        dark
                          ? 'bg-[#2E1A40] text-[#F8FAFC] ring-[#F59E0B]/50'
                          : 'bg-[#2E084D] text-white ring-[#F59E0B]/60'
                      }`}
                    >
                      {userInitials}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-semibold truncate">{userName}</p>
                      <p className="text-xs text-[#94A3B8] truncate">{auth.user?.email || 'Connected'}</p>
                    </div>
                  </div>
                  <div
                    className={`mt-3 inline-flex items-center gap-2 px-2.5 py-1 rounded-lg text-[11px] font-medium ${
                      dark
                        ? 'bg-emerald-500/10 text-emerald-300 border border-emerald-500/20'
                        : 'bg-emerald-50 text-emerald-700 border border-emerald-200/80'
                    }`}
                  >
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0" />
                    <span>Gmail synced · {inboxTotalCount.toLocaleString()} indexed</span>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setUserMenuOpen(false);
                    auth.logout();
                  }}
                  className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-xs font-semibold transition cursor-pointer ${
                    dark
                      ? 'hover:bg-[#202737] text-rose-400'
                      : 'hover:bg-rose-50 text-rose-600'
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

      {/* Mobile Slide-Over Navigation Drawer */}
      {mobileNavOpen && (
        <div className="md:hidden fixed inset-0 z-50 flex">
          <div
            onClick={() => setMobileNavOpen(false)}
            className="fixed inset-0 bg-black/50 backdrop-blur-[2px] animate-backdrop-in"
          />
          <aside
            onClick={(e) => e.stopPropagation()}
            className={`relative z-10 w-72 max-w-[85vw] h-full flex flex-col justify-between py-4 shadow-2xl border-r animate-slide-in-left safe-bottom-pad ${
              dark ? 'bg-[#141822] border-[#252D3C]' : 'bg-[#F5F8FC] border-[#CBD5E1]'
            }`}
          >
            {renderSidebarBody(true, true)}
          </aside>
        </div>
      )}

      {/* ==================================================================== */}
      {/* MAIN CONTAINER: SIDEBAR + CONTENT AREA                                */}
      {/* ==================================================================== */}
      <div className="flex-1 flex overflow-hidden">
        {/* ================================================================== */}
        {/* LEFT SIDEBAR (DESKTOP COLLAPSIBLE RAIL)                            */}
        {/* ================================================================== */}
        <aside
          className={`${
            sidebarOpen ? 'w-60' : 'w-16'
          } relative z-30 hidden md:flex flex-col justify-between shrink-0 border-r py-3 transition-[width] duration-300 ease-[cubic-bezier(0.16,1,0.3,1)] ${
            dark
              ? 'bg-[#141822] border-[#252D3C]'
              : 'bg-[#F5F8FC]/80 backdrop-blur-md border-[#CBD5E1]'
          }`}
        >
          {renderSidebarBody(sidebarOpen, false)}
        </aside>

        {/* ================================================================== */}
        {/* MAIN MAILBOX WORKSPACE: TOOLBAR + TABLE ROWS OR READING PANE       */}
        {/* ================================================================== */}
        <main
          className={`relative z-10 flex-1 flex flex-col overflow-hidden m-2 sm:m-3 rounded-2xl border shadow-sm transition-colors ${
            dark ? 'bg-[#181D29] border-[#2C3547]' : 'bg-[#FFFFFF] border-[#CBD5E1]/90 shadow-[0_2px_14px_rgba(88,28,135,0.04),0_1px_3px_rgba(0,0,0,0.03)]'
          }`}
        >
          {/* 1. ACTION TOOLBAR */}
          <div
            className={`relative z-10 min-h-[48px] px-3 sm:px-4 py-1.5 flex items-center justify-between gap-2 border-b shrink-0 text-xs ${
              dark ? 'bg-[#161B26] border-[#252D3C]' : 'bg-[#FFFFFF] border-[#E2E8F0]'
            }`}
          >
            {/* Left Controls: Back / Select All, Refresh, Batch Actions */}
            <div className="flex items-center gap-1.5 sm:gap-2 min-w-0">
              {(readingEmailId || (mobileReading && layoutMode === 'split')) && (
                <button
                  type="button"
                  onClick={() => {
                    setReadingEmailId(null);
                    setMobileReading(false);
                  }}
                  className={`${
                    readingEmailId ? 'flex' : 'flex lg:hidden'
                  } items-center gap-1.5 px-2.5 py-1.5 rounded-lg font-semibold transition cursor-pointer ${
                    dark
                      ? 'text-[#CBD5E1] hover:text-white hover:bg-[#202737]'
                      : 'text-[#4D3A5B] hover:text-[#581C87] hover:bg-[#F1F5F9]'
                  }`}
                >
                  <ArrowLeft className="w-4 h-4 text-[#F59E0B]" />
                  <span>Back to {view === 'attention' ? 'attention queue' : 'inbox'}</span>
                </button>
              )}

              {!readingEmailId && (
                <div className={`${mobileReading && layoutMode === 'split' ? 'hidden lg:flex' : 'flex'} items-center gap-1.5 sm:gap-2 min-w-0`}>
                  {/* Select All Checkbox */}
                  <button
                    type="button"
                    aria-label="Select all visible emails"
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
                    type="button"
                    aria-label="Refresh list"
                    onClick={() => emailsHook.refresh?.(windowId)}
                    className={`p-1.5 rounded-md transition cursor-pointer hover:scale-105 active:scale-95 ${
                      dark ? 'text-[#94A3B8] hover:text-white hover:bg-[#202737]' : 'text-[#64748B] hover:text-[#581C87] hover:bg-[#F1F5F9]'
                    }`}
                    title="Refresh"
                  >
                    <RefreshCw className={`w-4 h-4 ${syncing ? 'animate-spin text-[#F59E0B]' : ''}`} />
                  </button>

                  {/* Unread Only Quick Toggle */}
                  <button
                    type="button"
                    aria-pressed={unreadOnly}
                    onClick={() => applyUnreadOnly((u) => !u)}
                    className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11.5px] font-semibold transition cursor-pointer border ${
                      unreadOnly
                        ? dark
                          ? 'bg-[#2E1A40] text-[#FBBF24] border-[#F59E0B]/50 shadow-sm'
                          : 'bg-[#581C87] text-white border-[#581C87] shadow-sm'
                        : dark
                        ? 'bg-[#141822] text-[#94A3B8] border-[#252D3C] hover:text-white hover:border-[#334155]'
                        : 'bg-[#F8FAFC] text-[#4D3A5B] border-[#E2E8F0] hover:border-[#CBD5E1] hover:bg-white'
                    }`}
                    title="Filter unread messages"
                  >
                    <Filter className="w-3 h-3" />
                    <span>Unread</span>
                    <span
                      className={`tabular-nums px-1.5 py-0 rounded-full text-[10px] font-bold ${
                        unreadOnly
                          ? 'bg-white/20 text-white'
                          : dark
                          ? 'bg-[#202737] text-[#FBBF24]'
                          : 'bg-[#E2E8F0] text-[#3B0764]'
                      }`}
                    >
                      {unreadCount.toLocaleString()}
                    </span>
                  </button>

                  {/* Batch actions when checkboxes selected */}
                  {checkedIds.size > 0 && (
                    <div className={`flex items-center gap-1.5 ml-1 pl-2.5 border-l animate-fade-in ${dark ? 'border-[#2D3648]' : 'border-[#CBD5E1]'}`}>
                      <span className="font-semibold text-xs text-[#F59E0B] tabular-nums">
                        {checkedIds.size} selected
                      </span>
                      <button
                        type="button"
                        onClick={handleBatchDone}
                        className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold transition cursor-pointer ${
                          dark
                            ? 'bg-emerald-500/15 text-emerald-300 hover:bg-emerald-500/25 border border-emerald-500/30'
                            : 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border border-emerald-200'
                        }`}
                      >
                        <Check className="w-3.5 h-3.5" />
                        <span>Mark Done</span>
                      </button>
                      <button
                        type="button"
                        onClick={() => setCheckedIds(new Set())}
                        className={`px-2 py-1 rounded-md text-xs font-medium transition cursor-pointer ${
                          dark ? 'text-[#94A3B8] hover:text-white hover:bg-[#202737]' : 'text-[#64748B] hover:text-[#3B0764] hover:bg-[#F1F5F9]'
                        }`}
                      >
                        Clear
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Right Controls: Pagination + Clear Segmented Layout Toggle */}
            <div className="flex items-center gap-2 sm:gap-3 shrink-0">
              <span className={`tabular-nums text-[11.5px] sm:text-xs font-medium ${dark ? 'text-[#94A3B8]' : 'text-[#64748B]'}`}>
                {startNum}–{endNum} of {currentViewTotal.toLocaleString()}
              </span>

              <div className="flex items-center gap-0.5">
                <button
                  type="button"
                  aria-label="Previous page"
                  disabled={currentPage <= 1 || !!readingEmailId}
                  onClick={() => handlePageNav(-1)}
                  className={`p-1.5 rounded-lg transition cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed hover:scale-105 active:scale-95 ${
                    dark ? 'hover:bg-[#202737] text-[#CBD5E1]' : 'hover:bg-[#F1F5F9] text-[#4D3A5B]'
                  }`}
                  title="Newer"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <button
                  type="button"
                  aria-label="Next page"
                  disabled={!hasNextPage || !!readingEmailId}
                  onClick={() => handlePageNav(1)}
                  className={`p-1.5 rounded-lg transition cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed hover:scale-105 active:scale-95 ${
                    dark ? 'hover:bg-[#202737] text-[#CBD5E1]' : 'hover:bg-[#F1F5F9] text-[#4D3A5B]'
                  }`}
                  title="Older"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>

              {/* Desktop Segmented Layout Toggle (List vs Split View) */}
              <div
                className={`hidden lg:inline-flex items-center p-0.5 rounded-lg border ${
                  dark ? 'bg-[#121620] border-[#252D3C]' : 'bg-[#F1F5F9] border-[#CBD5E1]/70'
                }`}
                role="group"
                aria-label="Reading layout"
              >
                <button
                  type="button"
                  onClick={() => setLayoutModeAndPersist('table')}
                  className={`inline-flex items-center gap-1 px-2 py-1 rounded-md text-[11px] font-semibold transition cursor-pointer ${
                    layoutMode === 'table'
                      ? dark ? 'bg-[#283144] text-white shadow-sm' : 'bg-white text-[#3B0764] shadow-sm'
                      : dark ? 'text-[#94A3B8] hover:text-white' : 'text-[#64748B] hover:text-[#1E1231]'
                  }`}
                  title="Full width list"
                >
                  <LayoutList className="w-3.5 h-3.5" />
                  <span>List</span>
                </button>
                <button
                  type="button"
                  onClick={() => setLayoutModeAndPersist('split')}
                  className={`inline-flex items-center gap-1 px-2 py-1 rounded-md text-[11px] font-semibold transition cursor-pointer ${
                    layoutMode === 'split'
                      ? dark ? 'bg-[#283144] text-[#FBBF24] shadow-sm' : 'bg-white text-[#3B0764] shadow-sm'
                      : dark ? 'text-[#94A3B8] hover:text-white' : 'text-[#64748B] hover:text-[#1E1231]'
                  }`}
                  title="Side-by-side split reading pane"
                >
                  <Columns className="w-3.5 h-3.5" />
                  <span>Split</span>
                </button>
              </div>
            </div>
          </div>

          {/* NEEDS ATTENTION QUEUE HEADER BANNER */}
          {!readingEmailId && view === 'attention' && (
            <div
              className={`${mobileReading && layoutMode === 'split' ? 'hidden lg:flex' : 'flex'} items-center justify-between border-b shrink-0 px-4 py-2.5 ${
                dark ? 'bg-[#1C1327] border-[#2D1B3E]' : 'bg-[#FAF5FF] border-[#E9D5FF]'
              }`}
            >
              <div className="flex items-center gap-2.5 min-w-0">
                <AlertCircle className="w-4 h-4 text-[#F59E0B] shrink-0" />
                <span className={`text-xs font-bold shrink-0 ${dark ? 'text-[#F8FAFC]' : 'text-[#581C87]'}`}>
                  Needs Attention Queue
                </span>
                <span className="hidden sm:inline text-[11px] text-[#94A3B8] truncate">
                  · Operational alerts, tasks requiring action, and upcoming deadlines
                </span>
              </div>
              <span className={`text-xs font-bold px-2.5 py-0.5 rounded-full shrink-0 ${dark ? 'bg-[#F59E0B]/20 text-[#FBBF24]' : 'bg-[#581C87]/10 text-[#581C87]'}`}>
                {currentViewTotal.toLocaleString()} items
              </span>
            </div>
          )}

          {/* RECENT MAIL HEADER BANNER */}
          {!readingEmailId && view === 'recent' && (
            <div
              className={`${mobileReading && layoutMode === 'split' ? 'hidden lg:flex' : 'flex'} items-center justify-between border-b shrink-0 px-4 py-2.5 ${
                dark ? 'bg-[#181D29] border-[#252D3C]' : 'bg-[#F1F5F9] border-[#CBD5E1]'
              }`}
            >
              <div className="flex items-center gap-2.5">
                <Clock className="w-4 h-4 text-[#F59E0B]" />
                <span className={`text-xs font-bold ${dark ? 'text-[#F8FAFC]' : 'text-[#3B0764]'}`}>
                  Recent Mail
                </span>
                <span className="hidden sm:inline text-[11px] text-[#94A3B8]">
                  · Synced messages from the last 30 days
                </span>
              </div>
            </div>
          )}

          {/* Active Filter Chips Strip */}
          {(priorityFilter || unreadOnly || search.trim()) && !readingEmailId && (
            <div className={`${mobileReading && layoutMode === 'split' ? 'hidden lg:flex' : 'flex'} px-3 sm:px-4 py-2 border-b items-center flex-wrap gap-1.5 text-xs ${
              dark ? 'bg-[#141822]/80 border-[#252D3C]' : 'bg-[#F8FAFC] border-[#E2E8F0]'
            }`}>
              <span className="text-[11px] font-semibold uppercase tracking-wider text-[#94A3B8] mr-1">Active:</span>
              {priorityFilter && (
                <button
                  type="button"
                  onClick={() => {
                    setPriorityFilter(null);
                    emailsHook.setActiveFilter?.('ALL');
                  }}
                  className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full font-medium border cursor-pointer transition ${
                    dark ? 'bg-[#2E1A40] border-[#7E22CE]/50 text-[#F8FAFC] hover:bg-[#3B2152]' : 'bg-white border-[#CBD5E1] text-[#3B0764] hover:bg-[#F1F5F9]'
                  }`}
                >
                  <span className="w-2 h-2 rounded-full" style={{ backgroundColor: PRIORITIES[priorityFilter]?.color }} />
                  <span>Priority: {PRIORITIES[priorityFilter]?.name}</span>
                  <X className="w-3 h-3 opacity-70" />
                </button>
              )}
              {unreadOnly && (
                <button
                  type="button"
                  onClick={() => applyUnreadOnly(false)}
                  className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full font-medium border cursor-pointer transition ${
                    dark ? 'bg-[#202737] border-[#2D3648] text-[#FBBF24]' : 'bg-white border-[#CBD5E1] text-[#581C87]'
                  }`}
                >
                  <span>Unread only</span>
                  <X className="w-3 h-3 opacity-70" />
                </button>
              )}
              {search.trim() && (
                <button
                  type="button"
                  onClick={() => {
                    setSearch('');
                    emailsHook.setSearchQuery?.('');
                  }}
                  className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full font-medium border cursor-pointer transition ${
                    dark ? 'bg-[#202737] border-[#2D3648] text-[#CBD5E1]' : 'bg-white border-[#CBD5E1] text-[#4D3A5B]'
                  }`}
                >
                  <span>Search: &ldquo;{search.trim()}&rdquo;</span>
                  <X className="w-3 h-3 opacity-70" />
                </button>
              )}
              <button
                type="button"
                onClick={() => {
                  setPriorityFilter(null);
                  applyUnreadOnly(false);
                  setSearch('');
                  emailsHook.setSearchQuery?.('');
                  emailsHook.setActiveFilter?.('ALL');
                }}
                className="ml-auto text-[11px] font-semibold text-[#F59E0B] hover:underline cursor-pointer"
              >
                Reset all
              </button>
            </div>
          )}

          {/* Offline / Backend Unreachable Banner */}
          {emailsHook.isOfflineMode && (
            <div className={`mx-4 mt-2 mb-1 px-4 py-2.5 rounded-xl text-xs flex items-center justify-between border ${
              dark ? 'bg-amber-500/10 border-amber-500/20 text-amber-400' : 'bg-amber-50 border-amber-200 text-amber-800'
            }`}>
              <div className="flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0 text-amber-500" />
                <span>Backend server unreachable. Displaying cached local emails.</span>
              </div>
              <button
                type="button"
                onClick={() => emailsHook.refresh?.()}
                className="underline hover:opacity-80 font-medium cursor-pointer"
              >
                Retry Connection
              </button>
            </div>
          )}

          {/* 3. MAIL CONTENT: LIST VIEW vs SPLIT VIEW vs FULL READER */}
          <div ref={splitContainerRef} className="relative flex-1 flex overflow-hidden">
            {isResizing && <div className="fixed inset-0 z-50 cursor-col-resize select-none" />}

            {/* EMAIL LIST COLUMN */}
            <div
              ref={listScrollRef}
              onScroll={(e) => {
                const isFar = e.currentTarget.scrollTop > 320;
                if (isFar !== showScrollTop) setShowScrollTop(isFar);
              }}
              style={{ '--split-list-width': `${splitWidth}px` }}
              role="listbox"
              aria-label="Email list"
              className={`${
                readingEmailId && layoutMode !== 'split'
                  ? 'hidden'
                  : (mobileReading || readingEmailId) && layoutMode === 'split'
                  ? 'hidden lg:flex'
                  : 'flex'
              } relative flex-col overflow-y-auto smooth-scroll transition-opacity duration-200 ${
                emailsHook.isRefreshing ? 'opacity-80' : 'opacity-100'
              } ${
                layoutMode === 'split'
                  ? 'w-full lg:w-[var(--split-list-width)] shrink-0 lg:border-r'
                  : 'w-full'
              } ${dark ? 'border-[#252D3C]' : 'border-[#E2E8F0]'}`}
            >
              {emailsHook.isLoading && visibleEmails.length === 0 ? (
                <div className={`divide-y ${dark ? 'divide-[#22293A]' : 'divide-[#EBF0F5]'}`}>
                  {Array.from({ length: 8 }).map((_, skIdx) => (
                    <div key={skIdx} className="px-4 py-3.5 flex items-start gap-3">
                      <div className="w-8 h-8 rounded-full animate-shimmer shrink-0 mt-0.5" />
                      <div className="flex-1 space-y-2">
                        <div className="flex items-center justify-between gap-4">
                          <div className="h-3.5 w-36 rounded-md animate-shimmer" />
                          <div className="h-3 w-12 rounded-md animate-shimmer" />
                        </div>
                        <div className="h-3.5 w-3/4 rounded-md animate-shimmer" />
                      </div>
                    </div>
                  ))}
                </div>
              ) : visibleEmails.length === 0 ? (
                <div className="flex-1 flex flex-col items-center justify-center p-12 text-center text-[#94A3B8] animate-fade-in">
                  <div className={`w-14 h-14 rounded-2xl flex items-center justify-center mb-4 ${
                    dark ? 'bg-[#202737] text-[#F59E0B]' : 'bg-[#FAF5FF] text-[#7E22CE]'
                  }`}>
                    <Inbox className="w-7 h-7 stroke-[1.5]" />
                  </div>
                  <p className={`text-sm font-semibold ${dark ? 'text-[#F8FAFC]' : 'text-[#1E1231]'}`}>All caught up</p>
                  <p className="text-xs text-[#94A3B8] mt-1 max-w-xs">
                    No messages match your active filters or date range.
                  </p>
                  {(priorityFilter || unreadOnly || search.trim()) && (
                    <button
                      type="button"
                      onClick={() => {
                        setPriorityFilter(null);
                        applyUnreadOnly(false);
                        setSearch('');
                        emailsHook.setSearchQuery?.('');
                        emailsHook.setActiveFilter?.('ALL');
                      }}
                      className="mt-4 px-4 py-1.5 rounded-xl text-xs font-semibold bg-[#581C87] text-white hover:bg-[#6B21A8] transition cursor-pointer"
                    >
                      Clear active filters
                    </button>
                  )}
                </div>
              ) : (
                visibleEmails.map((item) => {
                  const isSelected = (readingEmailId || selectedId) === item.id;
                  const isChecked = checkedIds.has(item.id);
                  const isStarred = starredIds.has(item.id);
                  const isDone = statusMap[item.id]?.state === 'done';
                  const isSnoozed = statusMap[item.id]?.state === 'snoozed' || Boolean(item.raw?.is_snoozed);
                  const tier = PRIORITIES[item.priority] || PRIORITIES.P3;
                  const avatarTone = getAvatarToneClass(item.email || item.sender, item.priority, dark);
                  const isCompactSplit = layoutMode === 'split';

                  return (
                    <div
                      key={item.id}
                      data-email-id={item.id}
                      role="option"
                      aria-selected={isSelected}
                      tabIndex={0}
                      onClick={() => selectEmail(item)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault();
                          selectEmail(item);
                        }
                      }}
                      className={`group flex items-start gap-2.5 sm:gap-3 px-3 sm:px-4 py-2.5 sm:py-3 border-b transition-[background-color,box-shadow,opacity,transform] duration-150 ease-out active:scale-[0.998] cursor-pointer select-none relative focus:outline-none focus-visible:ring-2 focus-visible:ring-[#7E22CE] ${
                        isDone || isSnoozed ? 'opacity-60' : ''
                      } ${
                        isSelected && isCompactSplit
                          ? dark
                            ? 'bg-[#2E1A40]/90 shadow-[inset_3.5px_0_0_0_#F59E0B]'
                            : 'bg-[#FAF5FF] shadow-[inset_3.5px_0_0_0_#581C87] border-[#DDD6FE]'
                          : isChecked
                          ? dark ? 'bg-[#242B3D]' : 'bg-[#F5F3FF] border-[#DDD6FE]'
                          : item.priority === 'P1' && item.unread
                          ? dark
                            ? 'bg-rose-500/[0.04] hover:bg-[#202737] shadow-[inset_2.5px_0_0_0_#E11D48]'
                            : 'bg-rose-50/40 hover:bg-[#F3F7FC] shadow-[inset_2.5px_0_0_0_#E11D48]'
                          : item.unread
                          ? dark ? 'bg-[#181D29] hover:bg-[#202737]' : 'bg-[#FFFFFF] hover:bg-[#F3F7FC]'
                          : dark ? 'bg-[#141822]/90 hover:bg-[#1C2230]' : 'bg-[#FAFCFE] hover:bg-[#F3F7FC]'
                      } ${dark ? 'border-[#22293A]' : 'border-[#EBF0F5]'}`}
                    >
                      {/* Left Controls: Checkbox + Star + Circular Avatar */}
                      <div className="flex items-center gap-1 pt-0.5 shrink-0">
                        <button
                          type="button"
                          aria-label={isChecked ? `Deselect ${item.subject}` : `Select ${item.subject}`}
                          onClick={(e) => toggleCheckEmail(item.id, e)}
                          className="p-1 -ml-1 transition shrink-0 cursor-pointer hover:scale-110 active:scale-95"
                          title="Select"
                        >
                          {isChecked ? (
                            <CheckSquare className="w-4 h-4 text-[#F59E0B]" />
                          ) : (
                            <Square className={`w-4 h-4 transition-colors ${dark ? 'text-[#64748B] hover:text-[#CBD5E1]' : 'text-[#94A3B8] hover:text-[#581C87]'}`} />
                          )}
                        </button>

                        <button
                          type="button"
                          aria-label={isStarred ? `Remove star from ${item.subject}` : `Star ${item.subject}`}
                          onClick={(e) => toggleStarEmail(item.id, e)}
                          className="p-1 transition shrink-0 cursor-pointer hover:scale-110 active:scale-95"
                          title={isStarred ? "Starred" : "Not starred"}
                        >
                          <Star className={`w-4 h-4 transition ${isStarred ? "fill-[#F59E0B] text-[#F59E0B]" : dark ? "text-[#64748B] hover:text-[#F59E0B]" : "text-[#CBD5E1] hover:text-[#F59E0B]"}`} />
                        </button>

                        <div
                          className={`hidden sm:flex w-8 h-8 rounded-full text-[11px] font-bold items-center justify-center shrink-0 ring-1 ml-0.5 ${avatarTone}`}
                          aria-hidden="true"
                        >
                          {item.initials}
                        </div>
                      </div>

                      {/* Main 2-Line Adaptive Card Content */}
                      <div className="flex-1 min-w-0">
                        {/* Row 1: Sender + Priority/Deadline Chips + Timestamp/Hover Actions */}
                        <div className="flex items-center justify-between gap-2 mb-0.5">
                          <div className="flex items-center gap-1.5 min-w-0">
                            {item.unread && (
                              <span
                                className="w-2 h-2 rounded-full shrink-0"
                                style={{ backgroundColor: tier.color }}
                                title={`${tier.id} · ${tier.name}`}
                              />
                            )}
                            <span
                              className={`truncate text-[13.5px] ${
                                item.unread
                                  ? dark ? 'font-bold text-[#F8FAFC]' : 'font-bold text-[#1E1231]'
                                  : dark ? 'font-medium text-[#CBD5E1]' : 'font-semibold text-[#334155]'
                              }`}
                              title={item.email}
                            >
                              <HighlightMatch text={item.sender} query={search} dark={dark} />
                            </span>

                            {(item.priority === 'P1' || item.priority === 'P2') && (
                              <span
                                className={`shrink-0 px-1.5 py-0.5 rounded-md text-[10px] font-bold tracking-tight ${
                                  item.priority === 'P1'
                                    ? dark ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30' : 'bg-rose-50 text-rose-700 border border-rose-200'
                                    : dark ? 'bg-amber-500/15 text-amber-300 border border-amber-500/30' : 'bg-amber-50 text-amber-800 border border-amber-200'
                                }`}
                              >
                                {tier.name}
                              </span>
                            )}

                            {item.raw?.deadline_display && (
                              <span className={`hidden sm:inline-flex items-center gap-1 shrink-0 px-1.5 py-0.5 rounded-md text-[10px] font-semibold ${
                                dark ? 'bg-[#281438] text-[#FBBF24] border border-[#3B1E52]' : 'bg-[#FAF5FF] text-[#6B21A8] border border-[#E9D5FF]'
                              }`}>
                                <Calendar className="w-2.5 h-2.5" />
                                <span className="truncate max-w-[100px]">{item.raw.deadline_display}</span>
                              </span>
                            )}

                            {isDone && (
                              <span className={`shrink-0 px-1.5 py-0.5 rounded-md text-[10px] font-semibold ${
                                dark ? 'bg-emerald-500/15 text-emerald-300' : 'bg-emerald-50 text-emerald-700'
                              }`}>
                                Done
                              </span>
                            )}

                            {isSnoozed && !isDone && (
                              <span className={`shrink-0 px-1.5 py-0.5 rounded-md text-[10px] font-semibold ${
                                dark ? 'bg-amber-500/15 text-amber-300' : 'bg-amber-50 text-amber-800'
                              }`}>
                                Snoozed
                              </span>
                            )}
                          </div>

                          {/* Timestamp & Smooth Zero-Jitter Quick Actions */}
                          <div className="relative h-6 min-w-[78px] shrink-0 flex items-center justify-end">
                            <span
                              className={`text-[11.5px] tabular-nums text-right transition-opacity duration-150 group-hover:opacity-0 group-focus-within:opacity-0 ${
                                item.unread
                                  ? dark ? 'font-bold text-[#F8FAFC]' : 'font-bold text-[#1E1231]'
                                  : dark ? 'text-[#94A3B8]' : 'text-[#64748B]'
                              }`}
                            >
                              {item.time}
                            </span>

                            <div
                              onClick={(e) => e.stopPropagation()}
                              className={`opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 pointer-events-none group-hover:pointer-events-auto group-focus-within:pointer-events-auto scale-95 group-hover:scale-100 transition-all duration-150 absolute right-0 flex items-center gap-0.5 ${
                                dark ? 'bg-[#202737] border border-[#2D3648]' : 'bg-white border border-[#CBD5E1] shadow-sm'
                              } px-1 py-0.5 rounded-lg`}
                            >
                              <button
                                type="button"
                                onClick={(e) => isDone ? restoreItem(item, e) : markDone(item, e)}
                                title={isDone ? 'Restore' : 'Mark done'}
                                className={`p-1 rounded-md transition cursor-pointer hover:scale-110 active:scale-95 ${
                                  dark ? 'text-[#94A3B8] hover:text-emerald-400 hover:bg-[#2D3648]' : 'text-[#64748B] hover:text-emerald-600 hover:bg-emerald-50'
                                }`}
                              >
                                {isDone ? <RotateCcw className="w-3.5 h-3.5" /> : <Check className="w-3.5 h-3.5" />}
                              </button>
                              <button
                                type="button"
                                onClick={(e) => snoozeItem(item, 3, e)}
                                title="Snooze 3 hours"
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
                                onClick={(e) => e.stopPropagation()}
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

                        {/* Row 2: Subject + Snippet + OTP Copy Chip + Attachment */}
                        <div className="flex items-center gap-1.5 min-w-0">
                          <span
                            className={`truncate text-[13px] ${
                              isCompactSplit ? 'max-w-[58%]' : 'max-w-[46%]'
                            } shrink-0 ${
                              item.unread
                                ? dark ? 'font-semibold text-[#F8FAFC]' : 'font-semibold text-[#1E1231]'
                                : dark ? 'font-normal text-[#CBD5E1]' : 'font-medium text-[#334155]'
                            }`}
                          >
                            <HighlightMatch text={item.subject} query={search} dark={dark} />
                          </span>
                          <span className={`shrink-0 text-xs ${dark ? 'text-[#475569]' : 'text-[#CBD5E1]'}`}>—</span>
                          <span className={`truncate text-xs flex-1 min-w-0 ${
                            dark ? 'text-[#94A3B8]' : 'text-[#64748B]'
                          }`}>
                            {item.paragraphs?.[0] || item.snippet || ''}
                          </span>

                          {item.otp && (
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleCopyOtp(item.otp, item.id);
                              }}
                              title="Click to copy verification code"
                              className="ml-1 shrink-0 inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10.5px] font-mono font-bold bg-[#FEF3C7] text-[#92400E] border border-[#FCD34D] hover:bg-[#FDE68A] transition cursor-pointer shadow-sm"
                            >
                              <span>{copiedId === item.id ? 'Copied ✓' : `OTP: ${item.otp}`}</span>
                            </button>
                          )}
                          {item.attachment && (
                            <Paperclip className={`w-3.5 h-3.5 shrink-0 ml-1 ${dark ? 'text-[#94A3B8]' : 'text-[#64748B]'}`} />
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })
              )}

              {/* Clean Footer Pagination Load More Card */}
              {hasNextPage && (
                <div className={`p-4 text-center border-t ${dark ? 'border-[#22293A]' : 'border-[#EBF0F5]'}`}>
                  <button
                    type="button"
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
                        ? 'bg-[#202737] text-[#F8FAFC] border-[#2D3648] hover:bg-[#283144] hover:border-[#F59E0B]/40 disabled:opacity-50'
                        : 'bg-[#F8FAFC] text-[#1D0B2B] border-[#CBD5E1] hover:bg-white hover:border-[#581C87]/40 disabled:opacity-50'
                    }`}
                  >
                    {emailsHook.isLoadingMore ? (
                      <>
                        <RefreshCw className="w-3.5 h-3.5 animate-spin text-[#F59E0B]" />
                        <span>Loading older emails...</span>
                      </>
                    ) : (
                      <span>Load more emails ({endNum} of {currentViewTotal.toLocaleString()} shown)</span>
                    )}
                  </button>
                </div>
              )}

              {/* Floating Scroll-to-Top Pill */}
              {showScrollTop && (
                <button
                  type="button"
                  aria-label="Scroll list to top"
                  onClick={() => listScrollRef.current?.scrollTo({ top: 0, behavior: 'smooth' })}
                  className={`sticky bottom-4 self-end mr-4 z-10 p-2.5 rounded-full shadow-lg border transition-transform hover:scale-105 active:scale-95 animate-fade-up cursor-pointer ${
                    dark
                      ? 'bg-[#202737]/95 border-[#334155] text-[#FBBF24] hover:bg-[#283144]'
                      : 'bg-white/95 border-[#CBD5E1] text-[#581C87] hover:bg-[#FAF5FF]'
                  } backdrop-blur-md`}
                  title="Back to top"
                >
                  <ArrowUp className="w-4 h-4" />
                </button>
              )}
            </div>

            {/* Draggable Desktop Split-Pane Resizer Handle */}
            {layoutMode === 'split' && (
              <div
                role="separator"
                aria-orientation="vertical"
                aria-label="Resize reading pane"
                title="Drag to resize · Double-click to reset"
                onDoubleClick={() => {
                  setSplitWidth(430);
                  try {
                    localStorage.setItem('mailmind_split_width', '430');
                  } catch {}
                }}
                onPointerDown={(e) => {
                  e.preventDefault();
                  const container = splitContainerRef.current;
                  if (!container) return;
                  setIsResizing(true);
                  const startX = e.clientX;
                  const startW = splitWidth;
                  const onMove = (ev) => {
                    const maxW = Math.min(620, Math.floor(container.clientWidth * 0.56));
                    const nextW = Math.max(350, Math.min(maxW, startW + (ev.clientX - startX)));
                    setSplitWidth(nextW);
                  };
                  const onUp = () => {
                    setIsResizing(false);
                    window.removeEventListener('pointermove', onMove);
                    window.removeEventListener('pointerup', onUp);
                    setSplitWidth((latest) => {
                      try {
                        localStorage.setItem('mailmind_split_width', String(latest));
                      } catch {}
                      return latest;
                    });
                  };
                  window.addEventListener('pointermove', onMove);
                  window.addEventListener('pointerup', onUp);
                }}
                className={`hidden lg:flex w-1.5 shrink-0 cursor-col-resize items-center justify-center group transition-colors ${
                  isResizing
                    ? dark ? 'bg-[#F59E0B]/35' : 'bg-[#7E22CE]/25'
                    : dark ? 'bg-transparent hover:bg-[#F59E0B]/25' : 'bg-transparent hover:bg-[#7E22CE]/15'
                }`}
              >
                <span
                  className={`w-0.5 h-10 rounded-full transition-all ${
                    isResizing
                      ? 'bg-[#F59E0B] scale-y-125'
                      : dark ? 'bg-[#2D3648] group-hover:bg-[#F59E0B]' : 'bg-[#CBD5E1] group-hover:bg-[#7E22CE]'
                  }`}
                />
              </div>
            )}

            {/* OPEN EMAIL READING CANVAS */}
            {(readingEmailId || layoutMode === 'split') && (
              <div
                ref={readerScrollRef}
                className={`${
                  readingEmailId || mobileReading ? 'flex' : 'hidden lg:flex'
                } flex-1 flex-col overflow-y-auto smooth-scroll transition-colors ${
                  dark ? 'bg-[#131722]' : 'bg-[#FFFFFF]'
                }`}
              >
                {currentEmail ? (
                  <>
                    {/* Sticky Action Header Strip for Email */}
                    <div
                      className={`sticky top-0 z-10 min-h-[48px] px-4 sm:px-8 py-2.5 flex flex-wrap items-center justify-between gap-2 border-b shrink-0 backdrop-blur-md ${
                        dark ? 'bg-[#131722]/95 border-[#252D3C]' : 'bg-[#FFFFFF]/95 border-[#E2E8F0]'
                      }`}
                    >
                      {/* Left: Priority Badge Popover + View Toggle */}
                      <div className="flex items-center gap-2 sm:gap-3">
                        <div className="relative" onClick={(e) => e.stopPropagation()}>
                          <button
                            type="button"
                            onClick={() => {
                              setPriorityMenuOpen((o) => !o);
                            }}
                            className={`inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold transition cursor-pointer border ${
                              dark
                                ? 'bg-[#202737] text-[#F8FAFC] border-[#2D3648] hover:bg-[#283144]'
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
                              className={`absolute left-0 top-9 z-50 w-72 rounded-2xl p-3.5 shadow-xl border space-y-3 animate-scale-in ${
                                dark
                                  ? 'bg-[#1E2534] border-[#2E384B] text-[#F8FAFC]'
                                  : 'bg-[#FFFFFF] border-[#E2E8F0] text-[#1D0B2B]'
                              }`}
                            >
                              <div className="text-xs space-y-1.5">
                                <p>
                                  Matched:{' '}
                                  <span className="text-[#F59E0B] font-semibold">
                                    {currentEmail.matched}
                                  </span>
                                </p>
                                {currentEmail.raw?.top_signals?.length > 0 && (
                                  <div className="flex flex-wrap gap-1 pt-0.5">
                                    {currentEmail.raw.top_signals.slice(0, 4).map((sig, sIdx) => (
                                      <span
                                        key={sIdx}
                                        className={`px-1.5 py-0.5 rounded text-[10px] font-medium border ${
                                          dark
                                            ? 'bg-[#252D3F] border-[#334155] text-[#CBD5E1]'
                                            : 'bg-[#F8FAFC] border-[#E2E8F0] text-[#475569]'
                                        }`}
                                        title={`Weight: +${sig.weight}`}
                                      >
                                        +{sig.term}
                                        {sig.contribution_pct != null ? ` (${sig.contribution_pct}%)` : ''}
                                      </span>
                                    ))}
                                  </div>
                                )}
                                {currentEmail.note && (
                                  <p className="text-[#94A3B8] leading-relaxed">{currentEmail.note}</p>
                                )}
                              </div>
                              <div
                                className={`pt-2 border-t grid grid-cols-4 gap-1 ${
                                  dark ? 'border-[#2E384B]' : 'border-[#E2E8F0]'
                                }`}
                              >
                                {Object.values(PRIORITIES).map((tier) => (
                                  <button
                                    key={tier.id}
                                    type="button"
                                    onClick={() => changePriority(currentEmail, tier.id)}
                                    className={`py-1.5 rounded-lg text-xs font-semibold flex items-center justify-center gap-1 transition cursor-pointer ${
                                      currentEmail.priority === tier.id
                                        ? dark
                                          ? 'bg-[#2E1A40] text-white border border-[#7E22CE]/60'
                                          : 'bg-[#EDE9FE] text-[#2E103F] border border-[#7E22CE]/30'
                                        : dark
                                        ? 'hover:bg-[#252D3F] text-[#94A3B8]'
                                        : 'hover:bg-[#EDF2F7] text-[#64748B]'
                                    }`}
                                  >
                                    <span
                                      className="w-1.5 h-1.5 rounded-full"
                                      style={{ backgroundColor: tier.color }}
                                    />
                                    {tier.id}
                                  </button>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>

                        {/* Mode toggle (Rich HTML vs Text) */}
                        {rawHtml && (
                          <div
                            className={`flex items-center p-0.5 rounded-lg border text-xs ${
                              dark ? 'border-[#252D3C] bg-[#121620]' : 'border-[#E2E8F0] bg-[#F1F5F9]'
                            }`}
                          >
                            <button
                              type="button"
                              onClick={() => setViewMode('rich')}
                              className={`px-2.5 py-1 rounded-md font-semibold transition cursor-pointer ${
                                viewMode === 'rich'
                                  ? dark
                                    ? 'bg-[#283144] text-[#F8FAFC] shadow-sm'
                                    : 'bg-[#FFFFFF] text-[#1D0B2B] shadow-sm'
                                  : 'text-[#94A3B8]'
                              }`}
                            >
                              Rich HTML
                            </button>
                            <button
                              type="button"
                              onClick={() => setViewMode('plain')}
                              className={`px-2.5 py-1 rounded-md font-semibold transition cursor-pointer ${
                                viewMode === 'plain'
                                  ? dark
                                    ? 'bg-[#283144] text-[#F8FAFC] shadow-sm'
                                    : 'bg-[#FFFFFF] text-[#1D0B2B] shadow-sm'
                                  : 'text-[#94A3B8]'
                              }`}
                            >
                              Text
                            </button>
                          </div>
                        )}
                      </div>

                      {/* Right: Triage Actions (Done/Restore, Snooze, Open in Gmail, Prev/Next) */}
                      <div className="flex items-center gap-1 sm:gap-1.5">
                        {currentTriage?.state === 'done' || currentTriage?.state === 'snoozed' ? (
                          <button
                            type="button"
                            onClick={() => restoreItem(currentEmail)}
                            className={`inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-semibold transition cursor-pointer ${
                              dark
                                ? 'bg-amber-500/15 text-amber-300 hover:bg-amber-500/25'
                                : 'bg-amber-50 text-amber-800 hover:bg-amber-100'
                            }`}
                            title="Restore to inbox"
                          >
                            <RotateCcw className="w-3.5 h-3.5" />
                            <span className="hidden sm:inline">Restore</span>
                          </button>
                        ) : (
                          <>
                            <button
                              type="button"
                              onClick={() => markDone(currentEmail)}
                              className={`inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-semibold transition cursor-pointer ${
                                dark
                                  ? 'bg-emerald-500/15 text-emerald-300 hover:bg-emerald-500/25 border border-emerald-500/25'
                                  : 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border border-emerald-200'
                              }`}
                              title="Mark as done (e)"
                            >
                              <Check className="w-3.5 h-3.5" />
                              <span className="hidden sm:inline">Done</span>
                            </button>

                            <button
                              type="button"
                              onClick={() => snoozeItem(currentEmail, 3)}
                              className={`inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-semibold transition cursor-pointer ${
                                dark
                                  ? 'hover:bg-[#202737] text-[#CBD5E1] hover:text-[#F59E0B]'
                                  : 'hover:bg-[#EDF2F7] text-[#4D3A5B] hover:text-[#7E22CE]'
                              }`}
                              title="Snooze 3 hours (h)"
                            >
                              <Clock className="w-3.5 h-3.5" />
                              <span className="hidden md:inline">Snooze</span>
                            </button>
                          </>
                        )}

                        {currentEmail.id && (
                          <a
                            href={`https://mail.google.com/mail/u/0/#inbox/${currentEmail.thread_id || currentEmail.id}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className={`inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-semibold transition cursor-pointer ${
                              dark
                                ? 'hover:bg-[#202737] text-[#CBD5E1] hover:text-[#F59E0B]'
                                : 'hover:bg-[#EDF2F7] text-[#4D3A5B] hover:text-[#7E22CE]'
                            }`}
                            title="Open in Gmail"
                          >
                            <ExternalLink className="w-3.5 h-3.5" />
                            <span className="hidden sm:inline">Open in Gmail</span>
                          </a>
                        )}

                        {/* Navigation buttons for next/prev email */}
                        <div
                          className={`flex items-center gap-0.5 ml-1 pl-2 border-l ${
                            dark ? 'border-[#252D3C]' : 'border-[#E2E8F0]'
                          }`}
                        >
                          <button
                            type="button"
                            disabled={!prevEmail}
                            onClick={() => selectEmail(prevEmail)}
                            className={`p-1.5 rounded-lg transition cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed ${
                              dark
                                ? 'text-[#94A3B8] hover:text-white hover:bg-[#202737]'
                                : 'text-[#64748B] hover:text-[#1D0B2B] hover:bg-[#EDF2F7]'
                            }`}
                            title="Previous email (k)"
                          >
                            <ChevronLeft className="w-4 h-4" />
                          </button>
                          {visibleEmails.length > 0 && currentIdx >= 0 && (
                            <span className="hidden xl:inline-block px-1.5 text-[11px] font-medium tabular-nums text-[#94A3B8]">
                              {currentIdx + 1} / {visibleEmails.length}
                            </span>
                          )}
                          <button
                            type="button"
                            disabled={!nextEmail}
                            onClick={() => selectEmail(nextEmail)}
                            className={`p-1.5 rounded-lg transition cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed ${
                              dark
                                ? 'text-[#94A3B8] hover:text-white hover:bg-[#202737]'
                                : 'text-[#64748B] hover:text-[#1D0B2B] hover:bg-[#EDF2F7]'
                            }`}
                            title="Next email (j)"
                          >
                            <ChevronRight className="w-4 h-4" />
                          </button>
                        </div>
                      </div>
                    </div>

                    {/* Email Reader Canvas */}
                    <article
                      key={currentEmail.id}
                      className="px-4 sm:px-8 lg:px-10 py-6 sm:py-8 max-w-4xl w-full select-text animate-fade-in"
                    >
                      <h1
                        className={`text-lg sm:text-2xl font-bold tracking-tight leading-snug mb-5 ${
                          dark ? 'text-[#F8FAFC]' : 'text-[#1D0B2B]'
                        }`}
                      >
                        {currentEmail.subject}
                      </h1>

                      {/* Sender row header */}
                      <div
                        className={`flex items-start justify-between gap-4 mb-5 pb-5 border-b ${
                          dark ? 'border-[#252D3C]' : 'border-[#E2E8F0]'
                        }`}
                      >
                        <div className="flex items-center gap-3.5 min-w-0">
                          <div
                            className={`w-10 h-10 rounded-full text-xs font-bold flex items-center justify-center shrink-0 ring-1 ${getAvatarToneClass(
                              currentEmail.email || currentEmail.sender,
                              currentEmail.priority,
                              dark
                            )}`}
                          >
                            {currentEmail.initials}
                          </div>
                          <div className="min-w-0">
                            <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                              <span
                                className={`text-sm font-semibold truncate ${
                                  dark ? 'text-[#F8FAFC]' : 'text-[#1D0B2B]'
                                }`}
                              >
                                {currentEmail.sender}
                              </span>
                              <span className="text-xs text-[#94A3B8] truncate">
                                &lt;{currentEmail.email}&gt;
                              </span>
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

                      {/* Quick Action Callout: OTP Verification Code */}
                      {currentEmail.otp && (
                        <div
                          className={`mb-5 px-4 py-3 rounded-xl border flex flex-wrap items-center justify-between gap-3 ${
                            dark
                              ? 'bg-amber-500/10 border-amber-500/30 text-amber-200'
                              : 'bg-[#FFFBEB] border-[#FCD34D] text-[#78350F]'
                          }`}
                        >
                          <div className="flex items-center gap-2.5">
                            <span className="text-xs font-semibold uppercase tracking-wider opacity-80">
                              Verification Code
                            </span>
                            <code
                              className={`px-2.5 py-1 rounded-lg text-sm font-mono font-bold tracking-widest ${
                                dark ? 'bg-[#131722] text-[#FBBF24]' : 'bg-white text-[#92400E] shadow-sm'
                              }`}
                            >
                              {currentEmail.otp}
                            </code>
                          </div>
                          <button
                            type="button"
                            onClick={() => handleCopyOtp(currentEmail.otp, currentEmail.id)}
                            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition cursor-pointer ${
                              copiedId === currentEmail.id
                                ? 'bg-emerald-600 text-white'
                                : 'bg-[#F59E0B] text-white hover:bg-[#D97706]'
                            }`}
                          >
                            {copiedId === currentEmail.id ? (
                              <>
                                <Check className="w-3.5 h-3.5" />
                                <span>Copied</span>
                              </>
                            ) : (
                              <span>Copy Code</span>
                            )}
                          </button>
                        </div>
                      )}

                      {/* Deadline Alert Strip */}
                      {currentEmail.raw?.deadline_display && (
                        <div
                          className={`mb-5 px-3.5 py-2.5 rounded-xl border flex items-center gap-2.5 text-xs font-medium ${
                            dark
                              ? 'bg-rose-500/10 border-rose-500/25 text-rose-300'
                              : 'bg-rose-50 border-rose-200 text-rose-700'
                          }`}
                        >
                          <Calendar className="w-4 h-4 shrink-0" />
                          <span>
                            Detected deadline: <strong>{currentEmail.raw.deadline_display}</strong>
                          </span>
                        </div>
                      )}

                      {/* Collapsible AI Priority Attribution Strip */}
                      {(currentEmail.matched || currentEmail.raw?.top_signals?.length > 0) && (
                        <div
                          className={`mb-6 rounded-xl border overflow-hidden transition-colors ${
                            dark
                              ? 'bg-[#181D29] border-[#252D3C]'
                              : 'bg-[#F8FAFC] border-[#E2E8F0]'
                          }`}
                        >
                          <button
                            type="button"
                            onClick={() => setAiSignalsExpanded((v) => !v)}
                            className="w-full px-3.5 py-2.5 flex items-center justify-between gap-2 text-xs cursor-pointer"
                          >
                            <div className="flex items-center gap-2 min-w-0">
                              <Sparkles className="w-3.5 h-3.5 text-[#F59E0B] shrink-0" />
                              <span
                                className={`font-semibold ${
                                  dark ? 'text-[#E2E8F0]' : 'text-[#334155]'
                                }`}
                              >
                                AI Triage Insight
                              </span>
                              <span className="text-[#94A3B8] truncate">
                                · {currentEmail.matched}
                              </span>
                            </div>
                            <ChevronDown
                              className={`w-3.5 h-3.5 text-[#94A3B8] shrink-0 transition-transform duration-200 ${
                                aiSignalsExpanded ? 'rotate-180' : ''
                              }`}
                            />
                          </button>
                          {aiSignalsExpanded && (
                            <div
                              className={`px-3.5 pb-3 pt-1 border-t space-y-2 text-xs animate-fade-in ${
                                dark ? 'border-[#252D3C]' : 'border-[#E2E8F0]'
                              }`}
                            >
                              {currentEmail.note && (
                                <p className="text-[#94A3B8] leading-relaxed">{currentEmail.note}</p>
                              )}
                              {currentEmail.raw?.top_signals?.length > 0 && (
                                <div className="flex flex-wrap gap-1.5">
                                  {currentEmail.raw.top_signals.slice(0, 6).map((sig, sIdx) => (
                                    <span
                                      key={sIdx}
                                      className={`px-2 py-0.5 rounded-md text-[11px] font-medium border ${
                                        dark
                                          ? 'bg-[#202737] border-[#2D3648] text-[#CBD5E1]'
                                          : 'bg-white border-[#CBD5E1] text-[#334155]'
                                      }`}
                                      title={`Weight: +${sig.weight}`}
                                    >
                                      +{sig.term}
                                      {sig.contribution_pct != null ? ` (${sig.contribution_pct}%)` : ''}
                                    </span>
                                  ))}
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      )}

                      {/* Body Rendering */}
                      <div className="min-h-[220px]">
                        {loadingDetail && !rawHtml && !rawBody ? (
                          <div className="py-6 space-y-3.5">
                            <div className="h-4 rounded-md w-3/4 animate-shimmer" />
                            <div className="h-4 rounded-md w-full animate-shimmer" />
                            <div className="h-4 rounded-md w-5/6 animate-shimmer" />
                            <div className="h-36 rounded-xl w-full animate-shimmer mt-2" />
                          </div>
                        ) : viewMode === 'rich' && rawHtml ? (
                          <div
                            className={
                              dark
                                ? 'rounded-2xl bg-[#FFFFFF] text-[#1E293B] border border-[#2D3648] shadow-sm p-2 sm:p-4 overflow-hidden'
                                : ''
                            }
                          >
                            <HtmlEmailViewer html={rawHtml} />
                          </div>
                        ) : (
                          <FormattedTextEmail
                            text={rawBody || currentEmail.paragraphs?.join('\n\n') || ''}
                            dark={dark}
                          />
                        )}
                      </div>

                      {/* Attachment Pills */}
                      {currentEmail.attachment && (
                        <div className={`mt-8 pt-6 border-t ${dark ? 'border-[#252D3C]' : 'border-[#E2E8F0]'}`}>
                          <button
                            type="button"
                            onClick={() => triggerToast(`Downloaded ${currentEmail.attachment.name}`)}
                            className={`inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full text-xs font-semibold transition cursor-pointer border ${
                              dark
                                ? 'bg-[#202737] text-[#F8FAFC] border-[#2D3648] hover:bg-[#283144]'
                                : 'bg-[#FFFFFF] text-[#1D0B2B] border-[#CBD5E1] hover:bg-[#F1F5F9]'
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
                  <div className="flex-1 flex flex-col items-center justify-center p-10 text-center text-[#94A3B8]">
                    <div
                      className={`w-14 h-14 rounded-2xl flex items-center justify-center mb-4 ${
                        dark ? 'bg-[#202737] text-[#F59E0B]' : 'bg-[#FAF5FF] text-[#7E22CE]'
                      }`}
                    >
                      <Mail className="w-7 h-7 stroke-[1.5]" />
                    </div>
                    <p className={`text-sm font-semibold ${dark ? 'text-[#F8FAFC]' : 'text-[#1D0B2B]'}`}>
                      Select an email to read
                    </p>
                    <p className="text-xs text-[#94A3B8] mt-1 max-w-xs">
                      Choose any message on the left or press <kbd className="px-1.5 py-0.5 rounded bg-black/10 dark:bg-white/10 font-mono">j</kbd> / <kbd className="px-1.5 py-0.5 rounded bg-black/10 dark:bg-white/10 font-mono">k</kbd> to step through your inbox.
                    </p>
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
          className={`fixed bottom-6 left-1/2 -translate-x-1/2 px-4 py-2.5 rounded-xl shadow-2xl border text-xs font-medium flex items-center gap-3 z-50 safe-bottom-pad animate-fade-up ${
            dark
              ? 'bg-[#202737] border-[#2D3648] text-[#F8FAFC]'
              : 'bg-[#1D0B2B] border-[#3B1254] text-[#F8FAFC]'
          }`}
        >
          <span>{toast.message}</span>
          {toast.undo && (
            <button
              type="button"
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
