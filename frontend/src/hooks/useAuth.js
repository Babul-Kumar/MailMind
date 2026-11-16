import { useState, useEffect, useCallback, useRef } from 'react';
import { fetchAuthStatus, fetchAuthLogin, fetchAuthExchange, fetchAuthDevLogin, logout as apiLogout } from '../services/api';

const AUTH_BROADCAST_CHANNEL = 'mailmind_auth_sync';

export function useAuth() {
  const [user, setUser] = useState(() => {
    if (typeof window !== 'undefined') {
      try {
        const raw = localStorage.getItem('mailmind_last_user');
        return raw ? JSON.parse(raw) : null;
      } catch (_) {
        return null;
      }
    }
    return null;
  });

  const [isAuthenticated, setIsAuthenticated] = useState(() => {
    if (typeof window !== 'undefined') {
      return Boolean(localStorage.getItem('mailmind_last_user'));
    }
    return false;
  });

  const [isLoading, setIsLoading] = useState(true);
  const [isOffline, setIsOffline] = useState(false);
  const [error, setError] = useState(null);

  // Broadcast channel for multi-tab synchronization
  const channelRef = useRef(null);

  useEffect(() => {
    if (typeof window !== 'undefined' && 'BroadcastChannel' in window) {
      try {
        channelRef.current = new BroadcastChannel(AUTH_BROADCAST_CHANNEL);
        channelRef.current.onmessage = (event) => {
          if (event.data?.type === 'LOGOUT') {
            setUser(null);
            setIsAuthenticated(false);
            try {
              localStorage.removeItem('mailmind_last_user');
            } catch (_) {}
          } else if (event.data?.type === 'LOGIN' && event.data?.user) {
            setUser(event.data.user);
            setIsAuthenticated(true);
          }
        };
      } catch (_) {}
    }

    return () => {
      if (channelRef.current) {
        channelRef.current.close();
      }
    };
  }, []);

  const clearClientCaches = useCallback(() => {
    if (typeof window === 'undefined') return;
    try {
      localStorage.removeItem('mailmind_last_user');
      // Purge all account-scoped caches
      const keysToRemove = [];
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (key && key.startsWith('mailmind_cache_')) {
          keysToRemove.push(key);
        }
      }
      keysToRemove.forEach((k) => localStorage.removeItem(k));
    } catch (_) {}
  }, []);

  const checkStatus = useCallback(async (initialError = null) => {
    setIsLoading(true);
    if (!initialError) {
      setError(null);
    }
    try {
      const data = await fetchAuthStatus();
      if (data.authenticated && data.user) {
        setUser(data.user);
        setIsAuthenticated(true);
        setIsOffline(false);
        setError(null);
        try {
          localStorage.setItem('mailmind_last_user', JSON.stringify(data.user));
        } catch (_) {}
      } else {
        // In local development, automatically connect to the local active developer mailbox if available
        const isLocal = typeof window !== 'undefined' && (
          window.location.hostname === 'localhost' ||
          window.location.hostname === '127.0.0.1' ||
          window.location.port === '5173' ||
          window.location.port === '5174'
        );
        if (isLocal) {
          try {
            const devData = await fetchAuthDevLogin();
            if (devData && devData.authenticated && devData.user) {
              setUser(devData.user);
              setIsAuthenticated(true);
              setIsOffline(false);
              setError(null);
              try {
                localStorage.setItem('mailmind_last_user', JSON.stringify(devData.user));
              } catch (_) {}
              return;
            }
          } catch (_) {}
        }

        setUser(null);
        setIsAuthenticated(false);
        setIsOffline(false);
        clearClientCaches();
        if (initialError) {
          setError(initialError);
        }
      }
    } catch (err) {
      console.warn('Backend session check error (offline or cold start):', err);
      // Check if we have a cached user from earlier session
      let cachedUser = null;
      try {
        const raw = localStorage.getItem('mailmind_last_user');
        cachedUser = raw ? JSON.parse(raw) : null;
      } catch (_) {}

      if (cachedUser) {
        // Backend temporarily unavailable / cold start -> preserve session in offline mode
        setUser(cachedUser);
        setIsAuthenticated(true);
        setIsOffline(true);
        setError('Backend is connecting. Showing saved emails.');
      } else {
        setError(initialError || err.message || 'Authentication check failed');
        setUser(null);
        setIsAuthenticated(false);
        setIsOffline(true);
      }
    } finally {
      setIsLoading(false);
    }
  }, [clearClientCaches]);

  const exchangeHandoff = useCallback(async (handoffCode) => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await fetchAuthExchange(handoffCode);
      if (data && data.authenticated && data.user) {
        setUser(data.user);
        setIsAuthenticated(true);
        setIsOffline(false);
        setError(null);
        try {
          localStorage.setItem('mailmind_last_user', JSON.stringify(data.user));
          if (channelRef.current) {
            channelRef.current.postMessage({ type: 'LOGIN', user: data.user });
          }
        } catch (_) {}
        return data;
      } else {
        throw new Error('Authentication response unauthenticated.');
      }
    } catch (err) {
      // Check if session is already active (e.g. handoff was already consumed by first concurrent request or page reload)
      try {
        const status = await fetchAuthStatus();
        if (status && status.authenticated && status.user) {
          setUser(status.user);
          setIsAuthenticated(true);
          setIsOffline(false);
          setError(null);
          return status;
        }
      } catch (_) {}

      console.error('Failed to exchange handoff code:', err);
      setUser(null);
      setIsAuthenticated(false);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    // If on callback route or handoff query exists, let AuthCallback component handle exchange
    if (typeof window !== 'undefined') {
      const pathname = window.location.pathname;
      const search = window.location.search;
      if (pathname.includes('/auth/callback') || search.includes('handoff=') || search.includes('auth_error=')) {
        return;
      }
    }

    // Normal mount check
    checkStatus();
  }, [checkStatus]);

  // Active auto-reconnect polling when backend is offline or cold starting
  useEffect(() => {
    if (!isOffline) return;
    let isCancelled = false;

    const intervalId = setInterval(async () => {
      try {
        const data = await fetchAuthStatus();
        if (!isCancelled && data) {
          setIsOffline(false);
          checkStatus();
        }
      } catch (_) {
        // Backend still starting up; continue polling quietly
      }
    }, 2000);

    return () => {
      isCancelled = true;
      clearInterval(intervalId);
    };
  }, [isOffline, checkStatus]);

  const login = useCallback(async () => {
    setError(null);
    try {
      const data = await fetchAuthLogin();
      if (data.auth_url) {
        window.location.href = data.auth_url;
      } else {
        throw new Error('No authorization URL returned by server.');
      }
    } catch (err) {
      console.error('OAuth login initiation failed:', err);
      const errMsg = err?.message || '';
      if (errMsg.includes('503')) {
        setIsOffline(true);
        setError('Backend server is connecting... Retrying automatically.');
      } else {
        setError(errMsg || 'Failed to start Google sign-in.');
      }
    }
  }, []);

  const switchAccount = useCallback(async () => {
    try {
      await apiLogout();
    } catch (_) {}
    clearClientCaches();
    setUser(null);
    setIsAuthenticated(false);
    if (channelRef.current) {
      try {
        channelRef.current.postMessage({ type: 'LOGOUT' });
      } catch (_) {}
    }
    // Google OAuth with prompt=select_account forces account selection screen
    try {
      const data = await fetchAuthLogin('select_account');
      if (data.auth_url) {
        window.location.href = data.auth_url;
      }
    } catch (err) {
      console.error('Account switch initiation failed:', err);
      const errMsg = err?.message || '';
      if (errMsg.includes('503')) {
        setIsOffline(true);
        setError('Backend server is connecting... Retrying automatically.');
      } else {
        setError(errMsg || 'Failed to initiate account switch.');
      }
    }
  }, [clearClientCaches]);

  const logout = useCallback(async () => {
    try {
      await apiLogout();
    } catch (e) {
      console.warn('Logout request warning:', e);
    }
    clearClientCaches();
    setUser(null);
    setIsAuthenticated(false);
    if (channelRef.current) {
      try {
        channelRef.current.postMessage({ type: 'LOGOUT' });
      } catch (_) {}
    }
  }, [clearClientCaches]);

  const devLogin = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await fetchAuthDevLogin();
      if (data && data.authenticated && data.user) {
        setUser(data.user);
        setIsAuthenticated(true);
        setIsOffline(false);
        try {
          localStorage.setItem('mailmind_last_user', JSON.stringify(data.user));
          if (channelRef.current) {
            channelRef.current.postMessage({ type: 'LOGIN', user: data.user });
          }
        } catch (_) {}
        return data;
      }
    } catch (err) {
      console.warn('Dev login failed:', err);
      const errMsg = err?.message || '';
      const isServerOffline = errMsg.includes('503') || errMsg.includes('Failed to fetch') || errMsg.includes('Network');
      if (isServerOffline) {
        setIsOffline(true);
        setError('Backend server is connecting... Retrying automatically.');
        return;
      }
      return login();
    } finally {
      setIsLoading(false);
    }
  }, [login]);

  return {
    user,
    isAuthenticated,
    isLoading,
    isOffline,
    error,
    login,
    devLogin,
    switchAccount,
    logout,
    refreshStatus: checkStatus,
    exchangeHandoff,
  };
}

