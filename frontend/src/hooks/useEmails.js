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
  fetchAnalysisConfig,
  updateAnalysisConfig,
  fetchAnalysisSummary,
  startIncrementalAnalysis,
  fetchAnalysisStatus,
  fetchRecentEmails,
  fetchHistoryEmails,
  fetchAttentionActions,
  syncIncomingEmails,
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

  // Analysis Period & Incremental Processing State
  const [analysisPeriod, setAnalysisPeriod] = useState(() => {
    try {
      return localStorage.getItem('mailmind_analysis_period') || 'last_3_months';
    } catch {
      return 'last_3_months';
    }
  });
  const [customStartDate, setCustomStartDate] = useState(() => {
    try {
      return localStorage.getItem('mailmind_custom_start') || '';
    } catch {
      return '';
    }
  });
  const [customEndDate, setCustomEndDate] = useState(() => {
    try {
      return localStorage.getItem('mailmind_custom_end') || '';
    } catch {
      return '';
    }
  });
  const [analysisSummary, setAnalysisSummary] = useState(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const analysisPollTimerRef = useRef(null);

  // History Mailbox State
  const [historyEmails, setHistoryEmails] = useState([]);
  const [historyPagination, setHistoryPagination] = useState({
    page: 1,
    page_size: 50,
    total_items: 0,
    total_pages: 1,
    has_next: false,
    has_prev: false,
  });
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyFilter, setHistoryFilterState] = useState({
    startDate: '',
    endDate: '',
    query: '',
    analyzedOnly: false,
  });

  // Default to ALL for clear priority-based triage
  const [activeFilter, setActiveFilterState] = useState(() => {
    try {
      const stored = localStorage.getItem('mailmind_preferred_view');
      return stored && stored !== 'NEEDS_ATTENTION' ? stored : 'ALL';
    } catch {
      return 'ALL';
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
      localStorage.setItem('mailmind_preferred_view', newFilter);
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
  const loadData = useCallback(async (customPage, customPageSize, customQuery, customFilter, customAction, customPeriod, forceSync = false) => {
    if (!isAuthenticated) return;

    const reqId = ++activeRequestIdRef.current;

    const pageToUse = customPage !== undefined ? customPage : page;
    const sizeToUse = customPageSize !== undefined ? customPageSize : pageSize;
    const filterToUse = customFilter !== undefined ? customFilter : activeFilter;
    const actionToUse = customAction !== undefined ? customAction : actionFilter;
    const searchToUse = customQuery !== undefined ? customQuery : debouncedSearchQuery;
    const periodToUse = customPeriod !== undefined ? customPeriod : analysisPeriod;

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
        period: periodToUse,
        sync: forceSync || (pageToUse === 1 && !searchToUse.trim()),
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

  // Trigger Mailbox Analysis scoped to current period
  const triggerScan = useCallback(async ({ scope = 'mailbox', mode = 'incremental', forceRescan = false } = {}) => {
    if (!isAuthenticated) return;
    setIsLoading(true);
    setError(null);
    try {
      const res = await startIncrementalAnalysis({
        period: analysisPeriod,
        custom_start_date: customStartDate,
        custom_end_date: customEndDate,
        force_reanalysis: forceRescan,
      });
      if (res?.data) {
        setScanStatus({
          status: 'ANALYZING',
          period: analysisPeriod,
          total: res.data.total_eligible || 0,
          analyzed: res.data.already_analyzed || 0,
          cached: res.data.reused_from_cache || 0,
          progress_percent: res.data.progress_percentage || 0,
        });
      }
      setIsScanning(true);
    } catch (err) {
      console.error('Error initiating scan:', err);
      setError(err.message || 'Failed to start Gmail scan.');
    } finally {
      setIsLoading(false);
    }
  }, [isAuthenticated, analysisPeriod, customStartDate, customEndDate]);

  // Trigger Full Rescan
  const triggerRescan = useCallback(async ({ scope = 'mailbox' } = {}) => {
    if (!isAuthenticated) return;
    setIsLoading(true);
    setError(null);
    try {
      const res = await rescanMailbox({ scope, period: analysisPeriod });
      setScanStatus(res.scan_status);
      setIsScanning(true);
    } catch (err) {
      console.error('Error initiating rescan:', err);
      setError(err.message || 'Failed to start full rescan.');
    } finally {
      setIsLoading(false);
    }
  }, [isAuthenticated, analysisPeriod]);

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

  // Dedicated refresh triggering an immediate Gmail check for incoming emails
  const handleRefresh = useCallback((customPeriod) => {
    return loadData(1, undefined, undefined, undefined, undefined, customPeriod, true);
  }, [loadData]);

  // Background heartbeat: periodically check for new incoming emails every 45 seconds
  useEffect(() => {
    if (!isAuthenticated) return;

    const bgSyncTimer = setInterval(async () => {
      if (typeof document !== 'undefined' && document.visibilityState === 'hidden') {
        return;
      }
      if (isScanning || isLoading) {
        return;
      }

      try {
        const res = await syncIncomingEmails({ period: analysisPeriod });
        if (res && res.new_emails_count > 0) {
          console.log(`[MailMind] Automatically recognized ${res.new_emails_count} incoming email(s). Updating inbox.`);
          loadDataRef.current();
        }
      } catch (err) {
        // Non-intrusive background check
      }
    }, 45000);

    return () => clearInterval(bgSyncTimer);
  }, [isAuthenticated, isScanning, isLoading, analysisPeriod]);

  // Initial load once upon authentication: restores period config and loads scoped emails
  useEffect(() => {
    if (isAuthenticated) {
      if (!initialLoadedRef.current) {
        initialLoadedRef.current = true;
        fetchAnalysisConfig()
          .then((cfgRes) => {
            const serverPeriod = cfgRes?.data?.period || analysisPeriod || 'last_3_months';
            setAnalysisPeriod(serverPeriod);
            if (cfgRes?.data?.custom_start_date) setCustomStartDate(cfgRes.data.custom_start_date);
            if (cfgRes?.data?.custom_end_date) setCustomEndDate(cfgRes.data.custom_end_date);

            return loadDataRef.current(1, undefined, undefined, undefined, undefined, serverPeriod).then(() => {
              return checkScanStatus().then((status) => {
                if (!status || status.status === 'NOT_STARTED' || (status.status === 'COMPLETE' && status.total === 0)) {
                  startIncrementalAnalysis({ period: serverPeriod }).catch(() => {});
                }
              });
            });
          })
          .catch(() => {
            loadDataRef.current().then(() => {
              checkScanStatus();
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
  }, [isAuthenticated, checkScanStatus]);

  // Subsequent data fetch when query, page, or filters change
  useEffect(() => {
    if (isAuthenticated && initialLoadedRef.current) {
      loadDataRef.current();
    }
  }, [isAuthenticated, page, pageSize, activeFilter, actionFilter, debouncedSearchQuery, gmailQuery, analysisPeriod]);

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

  // Load analysis configuration and summary from backend
  const loadAnalysisConfigAndSummary = useCallback(async () => {
    if (!isAuthenticated) return;
    try {
      const [cfgRes, sumRes] = await Promise.all([
        fetchAnalysisConfig().catch(() => null),
        fetchAnalysisSummary().catch(() => null),
      ]);
      if (cfgRes?.data?.period) {
        setAnalysisPeriod(cfgRes.data.period);
        setCustomStartDate(cfgRes.data.custom_start_date || '');
        setCustomEndDate(cfgRes.data.custom_end_date || '');
      }
      if (sumRes?.data) {
        setAnalysisSummary(sumRes.data);
      }
    } catch (e) {
      console.warn('Failed to fetch analysis config/summary:', e);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    if (isAuthenticated) {
      loadAnalysisConfigAndSummary();
    }
  }, [isAuthenticated, loadAnalysisConfigAndSummary]);

  // Handle changing analysis period
  const changeAnalysisPeriod = useCallback(async (newPeriod, newCustomStart, newCustomEnd) => {
    if (!isAuthenticated) return;
    setAnalysisPeriod(newPeriod);
    if (newCustomStart !== undefined) setCustomStartDate(newCustomStart);
    if (newCustomEnd !== undefined) setCustomEndDate(newCustomEnd);
    try {
      localStorage.setItem('mailmind_analysis_period', newPeriod);
      if (newCustomStart) localStorage.setItem('mailmind_custom_start', newCustomStart);
      if (newCustomEnd) localStorage.setItem('mailmind_custom_end', newCustomEnd);
    } catch {}

    setIsAnalyzing(true);
    try {
      await updateAnalysisConfig({
        period: newPeriod,
        custom_start_date: newCustomStart,
        custom_end_date: newCustomEnd,
      });

      const startRes = await startIncrementalAnalysis({
        period: newPeriod,
        custom_start_date: newCustomStart,
        custom_end_date: newCustomEnd,
      });
      if (startRes?.data) {
        setScanStatus({
          status: 'ANALYZING',
          period: newPeriod,
          total: startRes.data.total_eligible || 0,
          analyzed: startRes.data.already_analyzed || 0,
          cached: startRes.data.reused_from_cache || 0,
          progress_percent: startRes.data.progress_percentage || 0,
        });
        setIsScanning(true);
      }

      if (analysisPollTimerRef.current) clearInterval(analysisPollTimerRef.current);
      analysisPollTimerRef.current = setInterval(async () => {
        try {
          const statusRes = await fetchAnalysisStatus();
          if (statusRes?.data) {
            setAnalysisSummary(statusRes.data);
            if (statusRes.data.status === 'completed' || statusRes.data.status === 'failed') {
              clearInterval(analysisPollTimerRef.current);
              analysisPollTimerRef.current = null;
              setIsAnalyzing(false);
              loadDataRef.current();
            }
          }
        } catch {
          clearInterval(analysisPollTimerRef.current);
          analysisPollTimerRef.current = null;
          setIsAnalyzing(false);
        }
      }, 1500);

      loadDataRef.current(1, pageSize, undefined, undefined, undefined, newPeriod, true);
    } catch (err) {
      console.error('Error changing analysis period:', err);
      setIsAnalyzing(false);
    }
  }, [isAuthenticated, pageSize]);

  // History Mailbox Loader
  const loadHistoryData = useCallback(async (customPage, customFilters) => {
    if (!isAuthenticated) return;
    const pToUse = customPage !== undefined ? customPage : historyPagination.page;
    const fToUse = customFilters !== undefined ? customFilters : historyFilter;
    setHistoryLoading(true);
    try {
      const res = await fetchHistoryEmails({
        page: pToUse,
        pageSize: 50,
        query: fToUse.query || '',
        startDate: fToUse.startDate || '',
        endDate: fToUse.endDate || '',
        analyzedOnly: Boolean(fToUse.analyzedOnly),
      });
      if (res?.data?.items) {
        setHistoryEmails(res.data.items);
        setHistoryPagination(res.data.pagination || {
          page: pToUse,
          page_size: 50,
          total_items: res.data.items.length,
          total_pages: 1,
          has_next: false,
          has_prev: false,
        });
      }
    } catch (err) {
      console.warn('Failed to load history emails:', err);
    } finally {
      setHistoryLoading(false);
    }
  }, [isAuthenticated, historyPagination.page, historyFilter]);

  const setHistoryFilter = useCallback((newFilter) => {
    setHistoryFilterState((prev) => ({ ...prev, ...newFilter }));
    loadHistoryData(1, { ...historyFilter, ...newFilter });
  }, [historyFilter, loadHistoryData]);

  useEffect(() => {
    if (isAuthenticated && activeFilter === 'HISTORY') {
      loadHistoryData(1);
    }
  }, [isAuthenticated, activeFilter, loadHistoryData]);

  const [isLoadingMore, setIsLoadingMore] = useState(false);

  const loadMore = useCallback(async () => {
    if (isLoading || isLoadingMore || !pagination?.has_next) return 0;
    setIsLoadingMore(true);
    try {
      const nextPage = (pagination?.page || page || 1) + 1;
      const priorityParam = activeFilter !== 'ALL' ? activeFilter : '';
      const actionParam = actionFilter === 'ACTION_REQUIRED' ? true : actionFilter === 'NO_ACTION' ? false : null;
      const queryParam = debouncedSearchQuery.trim() || gmailQuery;

      const data = await fetchEmails({
        page: nextPage,
        pageSize,
        priority: priorityParam,
        query: queryParam,
        actionRequired: actionParam,
        period: analysisPeriod,
        sync: false,
      });

      let addedCount = 0;
      if (data?.emails && data.emails.length > 0) {
        setEmails((prev) => {
          const existingIds = new Set(prev.map((e) => e.id || e.email_id || e.message_id));
          const newEmails = data.emails.filter((e) => !existingIds.has(e.id || e.email_id || e.message_id));
          addedCount = newEmails.length;
          return [...prev, ...newEmails];
        });
      }

      if (data?.pagination) {
        setPagination(data.pagination);
        setPage(data.pagination.page || nextPage);
      } else if (!data?.emails || data.emails.length === 0) {
        setPagination((prev) => ({ ...(prev || {}), has_next: false }));
      }

      return addedCount;
    } catch (err) {
      console.warn('Failed to load more emails:', err);
      throw err;
    } finally {
      setIsLoadingMore(false);
    }
  }, [isLoading, isLoadingMore, pagination, page, pageSize, activeFilter, actionFilter, debouncedSearchQuery, gmailQuery, analysisPeriod]);

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
    loadMore,
    isLoadingMore,
    isJustUpdated,
    isShowingCached,
    isOfflineMode,
    cachedTimestamp,
    loadingStep,
    error,
    gmailQuery,
    setGmailQuery,
    lastUpdated,
    refresh: handleRefresh,
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
    analysisPeriod,
    customStartDate,
    customEndDate,
    changeAnalysisPeriod,
    analysisSummary,
    isAnalyzing,
    historyEmails,
    historyPagination,
    historyLoading,
    historyFilter,
    setHistoryFilter,
    loadHistoryData,
  };
}
