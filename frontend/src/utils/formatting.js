export function formatEmailDate(dateStr) {
  if (!dateStr) return '';
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr.slice(0, 16);
    
    const now = new Date();
    const isToday = d.toDateString() === now.toDateString();
    
    if (isToday) {
      return d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
    }
    
    const isThisYear = d.getFullYear() === now.getFullYear();
    if (isThisYear) {
      return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
    }
    
    return d.toLocaleDateString([], { month: 'numeric', day: 'numeric', year: '2-digit' });
  } catch {
    return dateStr.slice(0, 16);
  }
}

export function cleanSenderName(senderStr) {
  if (!senderStr) return 'Unknown Sender';
  // Extracts display name if formatted as "First Last <email@domain.com>"
  const match = senderStr.match(/^"?([^"<]+)"?\s*<.*>$/);
  if (match && match[1].trim()) {
    return match[1].trim();
  }
  // Otherwise return username or address
  return senderStr.replace(/<.*>/, '').trim() || senderStr;
}

export function extractSnippet(body, subject, maxChars = 110) {
  const text = (body || subject || '').replace(/\s+/g, ' ').trim();
  if (text.length <= maxChars) return text;
  return text.slice(0, maxChars) + '...';
}

const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

function formatTimeDeterministic(d) {
  let h = d.getHours();
  const m = d.getMinutes();
  const ampm = h >= 12 ? 'PM' : 'AM';
  h = h % 12;
  if (h === 0) h = 12;
  const mStr = m < 10 ? `0${m}` : `${m}`;
  return `${h}:${mStr} ${ampm}`;
}

/**
 * Derives deadline presentation state from existing deadline_datetime.
 * Does NOT infer new deadlines or modify deadline_detected.
 *
 * States:
 * - UPCOMING: ⏰ Oct 5 · 5 days
 * - TODAY:    ⏰ Today · 11:59 PM (or ⏰ Today)
 * - OVERDUE:  ⚠ Overdue · Sep 30 · 11:59 PM (or ⚠ Overdue · Sep 30)
 *
 * @param {Object} email - Email object
 * @param {Date} [now=new Date()] - Reference date for comparison
 * @returns {Object|null} Presentation state
 */
export function getDeadlineState(email, now = new Date()) {
  if (!email || !email.deadline_detected) return null;

  const raw = email.deadline_datetime || email.deadline_display;
  if (!raw || typeof raw !== 'string') return null;

  const trimmed = raw.trim();
  const isDateOnly = email.deadline_precision === 'DATE' || /^\d{4}-\d{2}-\d{2}$/.test(trimmed);

  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 0, 0, 0, 0);
  const todayEnd = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 23, 59, 59, 999);

  if (isDateOnly) {
    const dateMatch = trimmed.match(/^(\d{4})-(\d{2})-(\d{2})/);
    let y, m, d;
    if (dateMatch) {
      y = parseInt(dateMatch[1], 10);
      m = parseInt(dateMatch[2], 10);
      d = parseInt(dateMatch[3], 10);
    } else {
      const parsed = new Date(trimmed);
      if (isNaN(parsed.getTime())) return null;
      y = parsed.getFullYear();
      m = parsed.getMonth() + 1;
      d = parsed.getDate();
    }

    const deadlineStart = new Date(y, m - 1, d, 0, 0, 0, 0);
    const deadlineEnd = new Date(y, m - 1, d, 23, 59, 59, 999);
    const dateStr = `${MONTH_NAMES[m - 1]} ${d}`;
    const fullDateStr = `${MONTH_NAMES[m - 1]} ${d}, ${y}`;

    if (deadlineEnd < todayStart) {
      if (email.deadline_status === 'HISTORICAL') {
        return {
          state: 'historical',
          icon: '📅',
          label: `Past · ${dateStr}`,
          longLabel: fullDateStr,
          dateStr,
          fullDateStr,
          timeStr: null,
          isDateOnly: true,
          daysUntil: Math.floor((deadlineStart.getTime() - todayStart.getTime()) / (1000 * 60 * 60 * 24)),
        };
      }

      // Past — Overdue
      return {
        state: 'overdue',
        icon: '⚠',
        label: `Overdue · ${dateStr}`,
        longLabel: fullDateStr,
        dateStr,
        fullDateStr,
        timeStr: null,
        isDateOnly: true,
        daysUntil: Math.floor((deadlineStart.getTime() - todayStart.getTime()) / (1000 * 60 * 60 * 24)),
      };
    }

    if (deadlineStart.getTime() === todayStart.getTime()) {
      // Due today
      return {
        state: 'today',
        icon: '⏰',
        label: 'Today',
        longLabel: 'today',
        dateStr,
        fullDateStr,
        timeStr: null,
        isDateOnly: true,
        daysUntil: 0,
      };
    }

    // Future — Upcoming
    const daysUntil = Math.ceil((deadlineStart.getTime() - todayStart.getTime()) / (1000 * 60 * 60 * 24));
    const daysLabel = daysUntil === 1 ? '1 day' : `${daysUntil} days`;
    return {
      state: 'upcoming',
      icon: '⏰',
      label: `${dateStr} · ${daysLabel}`,
      longLabel: fullDateStr,
      dateStr,
      fullDateStr,
      timeStr: null,
      isDateOnly: true,
      daysUntil,
    };
  }

  // DATETIME parsing
  let deadline;
  const isoMatch = trimmed.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{1,2}):(\d{2})(?::(\d{2}))?/);
  if (isoMatch) {
    const y = parseInt(isoMatch[1], 10);
    const m = parseInt(isoMatch[2], 10);
    const d = parseInt(isoMatch[3], 10);
    const hh = parseInt(isoMatch[4], 10);
    const mm = parseInt(isoMatch[5], 10);
    const ss = isoMatch[6] ? parseInt(isoMatch[6], 10) : 0;
    deadline = new Date(y, m - 1, d, hh, mm, ss);
  } else {
    deadline = new Date(trimmed);
  }

  if (isNaN(deadline.getTime())) return null;

  const y = deadline.getFullYear();
  const m = deadline.getMonth() + 1;
  const d = deadline.getDate();
  const dateStr = `${MONTH_NAMES[m - 1]} ${d}`;
  const fullDateStr = `${MONTH_NAMES[m - 1]} ${d}, ${y}`;
  const timeStr = formatTimeDeterministic(deadline);

  if (deadline < now) {
    if (email.deadline_status === 'HISTORICAL') {
      return {
        state: 'historical',
        icon: '📅',
        label: `Past · ${dateStr} · ${timeStr}`,
        longLabel: `${fullDateStr} at ${timeStr}`,
        dateStr,
        fullDateStr,
        timeStr,
        isDateOnly: false,
        daysUntil: Math.floor((deadline.getTime() - now.getTime()) / (1000 * 60 * 60 * 24)),
      };
    }

    // Past — Overdue
    return {
      state: 'overdue',
      icon: '⚠',
      label: `Overdue · ${dateStr} · ${timeStr}`,
      longLabel: `${fullDateStr} at ${timeStr}`,
      dateStr,
      fullDateStr,
      timeStr,
      isDateOnly: false,
      daysUntil: Math.floor((deadline.getTime() - now.getTime()) / (1000 * 60 * 60 * 24)),
    };
  }

  if (deadline >= todayStart && deadline <= todayEnd) {
    // Deadline is today
    return {
      state: 'today',
      icon: '⏰',
      label: `Today · ${timeStr}`,
      longLabel: `today at ${timeStr}`,
      dateStr,
      fullDateStr,
      timeStr,
      isDateOnly: false,
      daysUntil: 0,
    };
  }

  // Future — Upcoming
  const deadlineCalendarDate = new Date(y, m - 1, d, 0, 0, 0, 0);
  const daysUntil = Math.max(1, Math.round((deadlineCalendarDate.getTime() - todayStart.getTime()) / (1000 * 60 * 60 * 24)));
  const daysLabel = daysUntil === 1 ? '1 day' : `${daysUntil} days`;
  return {
    state: 'upcoming',
    icon: '⏰',
    label: `${dateStr} · ${daysLabel}`,
    longLabel: `${fullDateStr} at ${timeStr}`,
    dateStr,
    fullDateStr,
    timeStr,
    isDateOnly: false,
    daysUntil,
  };
}
