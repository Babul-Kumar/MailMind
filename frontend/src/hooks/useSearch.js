import { useState, useEffect, useMemo } from 'react';
import { PRIORITY_CONFIG, isNeedsAttention } from '../utils/priority';

export function useSearch(emails) {
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedSearchQuery, setDebouncedSearchQuery] = useState('');
  const [activeFilter, setActiveFilter] = useState('ALL'); // 'ALL', 'NEEDS_ATTENTION', 'IMPORTANT', 'P1', 'P2', 'P3', 'P4'
  const [focusMode, setFocusMode] = useState(false);
  const [sortBy, setSortBy] = useState('date_desc');

  // Debounce search query changes by 200ms to keep filtering snappy
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearchQuery(searchQuery);
    }, 200);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  const filteredEmails = useMemo(() => {
    if (!emails) return [];
    let list = [...emails];

    // 1. Focus Mode: Reuses the unified Needs Attention criteria
    if (focusMode) {
      list = list.filter(isNeedsAttention);
    } else if (activeFilter === 'NEEDS_ATTENTION') {
      // 2. Needs Attention View: P1 Critical OR (P2 + meaningful action) OR (action + genuine deadline)
      list = list.filter(isNeedsAttention);
    } else if (activeFilter === 'IMPORTANT') {
      // 3. Important View: Strictly P2 Priority (no overlap bugs)
      list = list.filter((e) => (e.final_priority || e.predicted_priority) === 'P2');
    } else if (activeFilter !== 'ALL') {
      // 4. Specific Priority Tab (P1, P2, P3, P4)
      list = list.filter((e) => (e.final_priority || e.predicted_priority) === activeFilter);
    }

    // 5. Keyword Search (uses debounced query)
    if (debouncedSearchQuery.trim()) {
      const q = debouncedSearchQuery.toLowerCase().trim();
      list = list.filter((e) => {
        const subj = (e.subject || '').toLowerCase();
        const sndr = (e.sender || '').toLowerCase();
        const body = (e.body || '').toLowerCase();
        return subj.includes(q) || sndr.includes(q) || body.includes(q);
      });
    }

    // 6. Sorting
    list.sort((a, b) => {
      if (sortBy === 'priority_desc') {
        const rankA = PRIORITY_CONFIG[a.predicted_priority]?.rank || 0;
        const rankB = PRIORITY_CONFIG[b.predicted_priority]?.rank || 0;
        return rankB - rankA;
      }
      if (sortBy === 'deadline_asc') {
        const hasA = a.deadline_detected ? 1 : 0;
        const hasB = b.deadline_detected ? 1 : 0;
        if (hasA !== hasB) return hasB - hasA; // Deadlines first
        if (a.deadline_datetime && b.deadline_datetime) {
          return new Date(a.deadline_datetime).getTime() - new Date(b.deadline_datetime).getTime();
        }
        return new Date(b.date || 0).getTime() - new Date(a.date || 0).getTime();
      }
      if (sortBy === 'sender_asc') {
        return (a.sender || '').localeCompare(b.sender || '');
      }
      if (sortBy === 'confidence_desc') {
        return (b.confidence || 0) - (a.confidence || 0);
      }
      if (sortBy === 'date_asc') {
        return new Date(a.date || 0).getTime() - new Date(b.date || 0).getTime();
      }
      return new Date(b.date || 0).getTime() - new Date(a.date || 0).getTime();
    });

    return list;
  }, [emails, debouncedSearchQuery, activeFilter, focusMode, sortBy]);

  const attentionCount = useMemo(() => {
    if (!emails) return 0;
    return emails.filter(isNeedsAttention).length;
  }, [emails]);

  return {
    searchQuery,
    setSearchQuery,
    activeFilter,
    setActiveFilter,
    focusMode,
    setFocusMode,
    sortBy,
    setSortBy,
    filteredEmails,
    attentionCount,
  };
}
