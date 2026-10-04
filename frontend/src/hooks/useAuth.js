import { useState, useEffect, useCallback } from 'react';
import { fetchAuthStatus, fetchAuthLogin, fetchAuthExchange, logout as apiLogout } from '../services/api';

export function useAuth() {
  const [user, setUser] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

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
        setError(null);
      } else {
        setUser(null);
        setIsAuthenticated(false);
        if (initialError) {
          setError(initialError);
        }
      }
    } catch (err) {
      console.error('Failed to check auth status:', err);
      setError(initialError || err.message || 'Authentication check failed');
      setUser(null);
      setIsAuthenticated(false);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    // Check URL parameters for OAuth errors or one-time handoff codes
    const urlParams = new URLSearchParams(window.location.search);
    const authError = urlParams.get('auth_error');
    const handoffCode = urlParams.get('handoff');

    if (authError) {
      window.history.replaceState({}, document.title, '/');
      checkStatus(`OAuth authentication error: ${authError}`);
      return;
    }

    if (handoffCode) {
      // Immediately sanitize URL to prevent handoff token leakage in history or bookmarks
      window.history.replaceState({}, document.title, '/');
      setIsLoading(true);
      setError(null);
      fetchAuthExchange(handoffCode)
        .then((data) => {
          if (data && data.authenticated && data.user) {
            setUser(data.user);
            setIsAuthenticated(true);
            setError(null);
          } else {
            setUser(null);
            setIsAuthenticated(false);
            setError('OAuth handoff failed: Invalid session.');
          }
        })
        .catch((err) => {
          console.error('Failed to exchange handoff code:', err);
          setError(err.message || 'OAuth handoff exchange failed.');
          setUser(null);
          setIsAuthenticated(false);
        })
        .finally(() => {
          setIsLoading(false);
        });
      return;
    }

    checkStatus();
  }, [checkStatus]);

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
      setError(err.message || 'Failed to start Google sign-in.');
    }
  }, []);

  const switchAccount = useCallback(async () => {
    try {
      await apiLogout();
    } catch (e) {
      // Continue even if logout failed
    }
    setUser(null);
    setIsAuthenticated(false);
    // Google OAuth with prompt=select_account forces account selection screen
    try {
      const data = await fetchAuthLogin('select_account');
      if (data.auth_url) {
        window.location.href = data.auth_url;
      }
    } catch (err) {
      console.error('Account switch initiation failed:', err);
      setError(err.message || 'Failed to initiate account switch.');
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await apiLogout();
    } catch (e) {
      console.warn('Logout request error:', e);
    }
    setUser(null);
    setIsAuthenticated(false);
  }, []);

  return {
    user,
    isAuthenticated,
    isLoading,
    error,
    login,
    switchAccount,
    logout,
    refreshStatus: checkStatus,
  };
}
