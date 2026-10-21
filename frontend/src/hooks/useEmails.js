import { useState, useEffect, useCallback, useRef } from 'react';
import {
  fetchEmails,
  fetchScanStatus,
  startScan,
  cancelScan,
  rescanMailbox,
  resolveAction,
  unresolveAction,
  snoozeAction,
  unsnoozeAction,
  fetchActionQueue,
} from '../services/api';

export function useEmails(isAuthenticated = false, user = null) {
  const [emails, setEmails] = useState([]);
  const [stats, setStats] = useState(null);
  const [profile, setProfile] = useState(null);
  const [pagination, setPagination] = useState({
    page: 1,
    page_size: 50,
    total_emails: 0,
    total_pages: 1,
    has_next: false,
    has_prev: false,
  });
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [isLoading, setIsLoading] = useState(false);
  const [loadingStep, setLoadingStep] = useState('');
  const [error, setError] = useState(null);
  const [gmailQuery, setGmailQuery] = useState('');
  const [lastUpdated, setLastUpdated] = useState(null);
  const [isJustUpdated, setIsJustUpdated] = useState(false);

  // Cached and Offline resilience state
  const [isShowingCached, setIsShowingCached] = useState(false);
  const [isOfflineMode, setIsOfflineMode] = useState(false);
  const [cachedTimestamp, setCachedTimestamp] = useState(null);

  // Default to Needs Attention for productivity, with preference fallback
  const [activeFilter, setActiveFilterState] = useState(() => {
    try {
      return localStorage.getItem('mailmind_preferred_view') || 'NEEDS_ATTENTION';
    } catch {
      return 'NEEDS_ATTENTION';
    }
  });
  const [actionFilter, setActionFilterState] = useState('ALL');
  const [searchQuery, setSearchQueryState] = useState('');
  const [debouncedSearchQuery, setDebouncedSearchQuery] = useState('');

  // Cache key scoped to the authenticated account
  const getCacheKey = useCallback((u) => {
    const uid = u?.user_id || u?.id || u?.email || 'default';
    return `mailmind_cache_${uid}`;
  }, []);

  // Debounce search input to avoid hitting backend on every keystroke
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearchQuery(searchQuery);
    }, 280);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  const setActiveFilter = useCallback((newFilter) => {
    setActiveFilterState(newFilter);
    setActionFilterState('ALL');
    setPage(1);
    try {
      if (newFilter === 'NEEDS_ATTENTION' || newFilter === 'ALL') {
        localStorage.setItem('mailmind_preferred_view', newFilter);
      }
    } catch {
      // Ignore localStorage write errors in private mode
    }
  }, []);

  const setActionFilter = useCallback((newAction) => {
    setActionFilterState(newAction);
    setPage(1);
  }, []);

  const setSearchQuery = useCallback((newQuery) => {
    setSearchQueryState(newQuery);
    setPage(1);
  }, []);

  // Scan state from background scan engine
  const [scanStatus, setScanStatus] = useState(null);
  const [isScanning, setIsScanning] = useState(false);
  const pollTimerRef = useRef(null);
  const retryTimerRef = useRef(null);
  const consecutiveErrorsRef = useRef(0);
  const activeRequestIdRef = useRef(0);
  const [initialFetchComplete, setInitialFetchComplete] = useState(false);

  // Stable references for state during async cache saves
  const emailsRef = useRef(emails);
  const statsRef = useRef(stats);
  const profileRef = useRef(profile);
  const paginationRef = useRef(pagination);
  useEffect(() => {
    emailsRef.current = emails;
    statsRef.current = stats;
    profileRef.current = profile;
    paginationRef.current = pagination;
  }, [emails, stats, profile, pagination]);

  // Helper to persist bounded account-scoped cache
  const saveAccountCache = useCallback((u, patch = {}) => {
    const uid = u?.user_id || u?.id || u?.email;
    if (!uid) return;
    try {
      const key = `mailmind_cache_${uid}`;
      const toStore = {
        emails: (patch.emails !== undefined ? patch.emails : emailsRef.current || []).slice(0, 100),
        stats: patch.stats !== undefined ? patch.stats : statsRef.current,
        profile: patch.profile !== undefined ? patch.profile : profileRef.current,
        pagination: patch.pagination !== undefined ? patch.pagination : paginationRef.current,
        actionQueue: patch.actionQueue !== undefined ? patch.actionQueue : undefined,
        lastUpdated: new Date().toISOString(),
      };
      localStorage.setItem(key, JSON.stringify(toStore));
    } catch (e) {
      console.warn('Failed to save account cache:', e);
    }
  }, []);

  // Immediate cached restoration as soon as user or session is available
  useEffect(() => {
    if (!isAuthenticated) {
      setIsShowingCached(false);
      setIsOfflineMode(false);
      setCachedTimestamp(null);
      return;
    }

    const cacheKey = getCacheKey(user);
    try {
      const cachedRaw = localStorage.getItem(cacheKey);
      if (cachedRaw) {
        const cached = JSON.parse(cachedRaw);
        if (cached && typeof cached === 'object') {
          if (Array.isArray(cached.emails) && cached.emails.length > 0) {
            setEmails(cached.emails);
          }
          if (cached.stats) setStats(cached.stats);
          if (cached.profile) setProfile(cached.profile);
          if (cached.pagination) setPagination(cached.pagination);
          if (cached.lastUpdated) {
            setLastUpdated(new Date(cached.lastUpdated));
            setCachedTimestamp(cached.lastUpdated);
          }
          setIsShowingCached(true);
        }
      }
    } catch (e) {
      console.warn('Could not restore account cache:', e);
    }
  }, [isAuthenticated, user, getCacheKey]);

  // Load emails and stats from backend
  const loadData = useCallback(async (customPage, customPageSize, customQuery, customFilter, customAction) => {
    if (!isAuthenticated) return;

    const reqId = ++activeRequestIdRef.current;

    const pageToUse = customPage !== undefined ? customPage : page;
    const sizeToUse = customPageSize !== undefined ? customPageSize : pageSize;
    const filterToUse = customFilter !== undefined ? customFilter : activeFilter;
    const actionToUse = customAction !== undefined ? customAction : actionFilter;
    const searchToUse = customQuery !== undefined ? customQuery : debouncedSearchQuery;

    const priorityParam = filterToUse !== 'ALL' ? filterToUse : '';
    const actionParam = actionToUse === 'ACTION_REQUIRED' ? true : actionToUse === 'NO_ACTION' ? false : null;
    const queryParam = searchToUse.trim() || gmailQuery;

    setIsLoading(true);
    setError(null);
    setLoadingStep('Accessing mailbox cache...');

    try {
      const data = await fetchEmails({
        page: pageToUse,
        pageSize: sizeToUse,
        priority: priorityParam,
        query: queryParam,
        actionRequired: actionParam,
      });

      if (activeRequestIdRef.current !== reqId) {
        // A newer request has already been issued, discard stale response
        return;
      }

      consecutiveErrorsRef.current = 0;
      setEmails(data.emails || []);
      setStats(data.stats || null);
      setProfile(data.profile || null);
      const newPag = data.pagination || {
        page: pageToUse,
        page_size: sizeToUse,
        total_emails: data.emails?.length || 0,
        total_pages: 1,
        has_next: false,
        has_prev: false,
      };
      setPagination(newPag);

      if (data.scan_status) {
        setScanStatus(data.scan_status);
        const active = ['QUEUED', 'SCANNING', 'ANALYZING', 'FINALIZING'].includes(data.scan_status.status);
        setIsScanning(active);
      }

      setLastUpdated(new Date());
      setIsShowingCached(false);
      setIsOfflineMode(false);
      setLoadingStep('Mailbox synchronized');

      // Save bounded cache
      saveAccountCache(user, {
        emails: data.emails || [],
        stats: data.stats || null,
        profile: data.profile || null,
        pagination: newPag,
      });

      setIsJustUpdated(true);
      setTimeout(() => {
        setIsJustUpdated(false);
      }, 1500);
    } catch (err) {
      if (activeRequestIdRef.current !== reqId) {
        return;
      }
      consecutiveErrorsRef.current += 1;
      if (err.status === 401) {
        setEmails([]);
        setStats(null);
        setProfile(null);
        setIsShowingCached(false);
        setIsOfflineMode(false);
        setError('Your session has expired. Sign in again to continue.');
      } else {
        console.warn('Network or backend sync issue, checking cached state:', err);
        setIsOfflineMode(true);
        // If we have cached emails or data, keep displaying saved emails without a destructive error
        if (emailsRef.current && emailsRef.current.length > 0) {
          setIsShowingCached(true);
          setError(null);
        } else {
          setError(err.message || 'Network unavailable. Showing saved emails.');
        }

        // Bounded retry with exponential backoff (max 3 automated retries, then waits for user)
        if (consecutiveErrorsRef.current <= 3 && err.status !== 401) {
          const delay = Math.pow(2, consecutiveErrorsRef.current - 1) * 1000 + Math.random() * 500;
          if (retryTimerRef.current) clearTimeout(retryTimerRef.current);
          retryTimerRef.current = setTimeout(() => {
            loadDataRef.current();
          }, delay);
        }
      }
    } finally {
      if (activeRequestIdRef.current === reqId) {
        setIsLoading(false);
        setInitialFetchComplete(true);
      }
    }
  }, [isAuthenticated, user, page, pageSize, activeFilter, actionFilter, debouncedSearchQuery, gmailQuery, saveAccountCache]);

  // Check and update scan status
  const checkScanStatus = useCallback(async () => {
    if (!isAuthenticated) return null;
    try {
      const statusData = await fetchScanStatus();
      setScanStatus(statusData);
      const active = ['QUEUED', 'SCANNING', 'ANALYZING', 'FINALIZING'].includes(statusData.status);
      setIsScanning(active);
      return statusData;
    } catch (err) {
      console.warn('Failed to poll scan status:', err);
      return null;
    }
  }, [isAuthenticated]);

  // Polling loop for active background scans
  const lastRefreshedCount = useRef(0);
  const loadDataRef = useRef(loadData);
  useEffect(() => {
    loadDataRef.current = loadData;
  });

  const initialLoadedRef = useRef(false);

  useEffect(() => {
    if (!isAuthenticated) {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
      if (retryTimerRef.current) clearTimeout(retryTimerRef.current);
      return;
    }

    // Initial check
    checkScanStatus();

    const startPolling = () => {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
      pollTimerRef.current = setInterval(async () => {
        // Slow down polling when document is not visible
        if (typeof document !== 'undefined' && document.visibilityState === 'hidden') {
          return;
        }

        const latest = await checkScanStatus();
        if (latest) {
          const isActive = ['QUEUED', 'SCANNING', 'ANALYZING', 'FINALIZING'].includes(latest.status);
          if (!isActive) {
            // Scan finished or stopped — refresh email view and stop polling
            clearInterval(pollTimerRef.current);
            pollTimerRef.current = null;
            loadDataRef.current();
          } else if (latest.status === 'ANALYZING' && latest.analyzed) {
            // As batches complete and are committed to cache, refresh list periodically if not loading and error-free
            if (latest.analyzed - lastRefreshedCount.current >= 50 && !isLoading && consecutiveErrorsRef.current < 3) {
              lastRefreshedCount.current = latest.analyzed;
              loadDataRef.current();
            }
          }
        }
      }, 2500);
    };

    if (isScanning) {
      startPolling();
    }

    return () => {
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
    };
  }, [isAuthenticated, isScanning, checkScanStatus, isLoading]);

  // Trigger Complete Scan (Incremental by default, or full discovery)
  const triggerScan = useCallback(async ({ scope = 'mailbox', mode = 'incremental', forceRescan = false } = {}) => {
    if (!isAuthenticated) return;
    setIsLoading(true);
    setError(null);
    try {
      const res = await startScan({
        scope,
        mode,
        query: gmailQuery,
        forceRescan,
      });
      setScanStatus(res.scan_status);
      setIsScanning(true);
    } catch (err) {
      console.error('Error initiating scan:', err);
      setError(err.message || 'Failed to start Gmail scan.');
    } finally {
      setIsLoading(false);
    }
  }, [isAuthenticated, gmailQuery]);

  // Trigger Full Rescan
  const triggerRescan = useCallback(async ({ scope = 'mailbox' } = {}) => {
    if (!isAuthenticated) return;
    setIsLoading(true);
    setError(null);
    try {
      const res = await rescanMailbox({ scope });
      setScanStatus(res.scan_status);
      setIsScanning(true);
    } catch (err) {
      console.error('Error initiating rescan:', err);
      setError(err.message || 'Failed to start full rescan.');
    } finally {
      setIsLoading(false);
    }
  }, [isAuthenticated]);

  // Cancel running scan
  const triggerCancelScan = useCallback(async () => {
    try {
      const res = await cancelScan();
      setScanStatus(res.scan_status);
      setIsScanning(false);
    } catch (err) {
      console.error('Error cancelling scan:', err);
    }
  }, []);

  // Initial load once upon authentication
  useEffect(() => {
    if (isAuthenticated) {
      if (!initialLoadedRef.current) {
        initialLoadedRef.current = true;
        loadDataRef.current().then(() => {
          checkScanStatus().then((status) => {
            if (!status || status.status === 'NOT_STARTED' || (status.status === 'COMPLETE' && status.total === 0)) {
              triggerScan({ scope: 'mailbox', mode: 'incremental' });
            }
          });
        });
      }
    } else {
      initialLoadedRef.current = false;
      setEmails([]);
      setStats(null);
      setProfile(null);
      setError(null);
      setIsLoading(false);
      setScanStatus(null);
      setIsScanning(false);
    }
  }, [isAuthenticated, checkScanStatus, triggerScan]);

  // Subsequent data fetch when query, page, or filters change
  useEffect(() => {
    if (isAuthenticated && initialLoadedRef.current) {
      loadDataRef.current();
    }
  }, [isAuthenticated, page, pageSize, activeFilter, actionFilter, debouncedSearchQuery, gmailQuery]);

  // Smart Action Queue State
  const [actionQueue, setActionQueue] = useState({
    active_queue: [],
    older_actions: [],
    snoozed_items: [],
    resolved_items: [],
    counts: {
      urgent: 0,
      due_soon: 0,
      other_active: 0,
      total_active: 0,
      older: 0,
      snoozed: 0,
      resolved: 0,
    },
  });
  const [actionQueueLoading, setActionQueueLoading] = useState(false);
  const [actionSortBy, setActionSortBy] = useState('urgent');
  const [olderSortBy, setOlderSortBy] = useState('oldest');
  const [recentlyResolved, setRecentlyResolved] = useState(null);

  // Load Action Queue from backend
  const loadActionQueue = useCallback(async (customSort, customOlderSort) => {
    if (!isAuthenticated) return;
    const sToUse = customSort || actionSortBy;
    const osToUse = customOlderSort || olderSortBy;
    setActionQueueLoading(true);
    try {
      const res = await fetchActionQueue({ sortBy: sToUse, olderSortBy: osToUse });
      if (res.data) {
        setActionQueue(res.data);
        saveAccountCache(user, { actionQueue: res.data });
      }
    } catch (err) {
      console.warn('Could not load action queue:', err);
    } finally {
      setActionQueueLoading(false);
    }
  }, [isAuthenticated, user, actionSortBy, olderSortBy, saveAccountCache]);

  // Refresh action queue whenever activeFilter becomes 'NEEDS_ATTENTION'
  useEffect(() => {
    if (isAuthenticated && activeFilter === 'NEEDS_ATTENTION') {
      loadActionQueue();
    }
  }, [isAuthenticated, activeFilter, loadActionQueue]);

  // Mark Resolved with Optimistic Update and Undo
  const handleResolve = useCallback(async (messageId, threadId = null, note = null) => {
    if (!messageId) return;

    // Optimistic UI update
    setActionQueue((prev) => {
      const itemToResolve = prev.active_queue.find((e) => (e.email_id || e.id || e.message_id) === messageId)
        || prev.older_actions.find((e) => (e.email_id || e.id || e.message_id) === messageId);

      const newActive = prev.active_queue.filter((e) => (e.email_id || e.id || e.message_id) !== messageId);
      const newOlder = prev.older_actions.filter((e) => (e.email_id || e.id || e.message_id) !== messageId);
      const resolvedList = itemToResolve
        ? [{ ...itemToResolve, is_resolved: true, queue_placement: 'RESOLVED' }, ...prev.resolved_items]
        : prev.resolved_items;

      return {
        ...prev,
        active_queue: newActive,
        older_actions: newOlder,
        resolved_items: resolvedList,
        counts: {
          ...prev.counts,
          total_active: Math.max(0, newActive.length),
          older: Math.max(0, newOlder.length),
          resolved: (prev.counts.resolved || 0) + 1,
        },
      };
    });

    setEmails((prev) =>
      prev.map((e) => ((e.email_id || e.id || e.message_id) === messageId ? { ...e, is_resolved: true } : e))
    );

    // Provide undo toast
    setRecentlyResolved({ messageId, timestamp: Date.now() });

    try {
      await resolveAction(messageId, threadId, note);
    } catch (err) {
      console.error('Failed to resolve action:', err);
      setError('Could not save resolution on server. Please try again.');
      // Revert optimistic update
      loadActionQueue();
    }
  }, [loadActionQueue]);

  // Undo / Unresolve
  const handleUnresolve = useCallback(async (messageId) => {
    if (!messageId) return;
    setRecentlyResolved(null);
    try {
      await unresolveAction(messageId);
      await loadActionQueue();
      loadDataRef.current();
    } catch (err) {
      console.error('Failed to undo resolution:', err);
      setError('Failed to undo resolution.');
    }
  }, [loadActionQueue]);

  // Snooze Action
  const handleSnooze = useCallback(async (messageId, snoozeUntil, threadId = null, reason = null) => {
    if (!messageId || !snoozeUntil) return;

    // Optimistic UI update
    setActionQueue((prev) => {
      const itemToSnooze = prev.active_queue.find((e) => (e.email_id || e.id || e.message_id) === messageId)
        || prev.older_actions.find((e) => (e.email_id || e.id || e.message_id) === messageId);

      const newActive = prev.active_queue.filter((e) => (e.email_id || e.id || e.message_id) !== messageId);
      const newOlder = prev.older_actions.filter((e) => (e.email_id || e.id || e.message_id) !== messageId);
      const snoozedList = itemToSnooze
        ? [{ ...itemToSnooze, is_snoozed: true, snoozed_until: snoozeUntil, queue_placement: 'SNOOZED' }, ...prev.snoozed_items]
        : prev.snoozed_items;

      return {
        ...prev,
        active_queue: newActive,
        older_actions: newOlder,
        snoozed_items: snoozedList,
        counts: {
          ...prev.counts,
          total_active: Math.max(0, newActive.length),
          older: Math.max(0, newOlder.length),
          snoozed: (prev.counts.snoozed || 0) + 1,
        },
      };
    });

    try {
      await snoozeAction(messageId, snoozeUntil, threadId, reason);
    } catch (err) {
      console.error('Failed to snooze action:', err);
      setError('Could not snooze item on server.');
      loadActionQueue();
    }
  }, [loadActionQueue]);

  // Unsnooze Action
  const handleUnsnooze = useCallback(async (messageId) => {
    if (!messageId) return;
    try {
      await unsnoozeAction(messageId);
      await loadActionQueue();
      loadDataRef.current();
    } catch (err) {
      console.error('Failed to unsnooze:', err);
      setError('Failed to unsnooze item.');
    }
  }, [loadActionQueue]);

  const isInitialLoading = isLoading && emails.length === 0;
  const isRefreshing = isLoading && emails.length > 0;


  return {
    emails,
    stats,
    profile,
    pagination,
    page,
    setPage,
    pageSize,
    setPageSize,
    isLoading,
    isInitialLoading,
    initialFetchComplete,
    isRefreshing,
    isJustUpdated,
    isShowingCached,
    isOfflineMode,
    cachedTimestamp,
    loadingStep,
    error,
    gmailQuery,
    setGmailQuery,
    lastUpdated,
    refresh: loadData,
    activeFilter,
    setActiveFilter,
    actionFilter,
    setActionFilter,
    searchQuery,
    setSearchQuery,
    scanStatus,
    isScanning,
    startScan: triggerScan,
    rescan: triggerRescan,
    cancelScan: triggerCancelScan,
    actionQueue,
    actionQueueLoading,
    actionSortBy,
    setActionSortBy,
    olderSortBy,
    setOlderSortBy,
    loadActionQueue,
    resolveEmail: handleResolve,
    unresolveEmail: handleUnresolve,
    snoozeEmail: handleSnooze,
    unsnoozeEmail: handleUnsnooze,
    recentlyResolved,
    clearRecentlyResolved: () => setRecentlyResolved(null),
  };
}
