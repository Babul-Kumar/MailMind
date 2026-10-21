import React, { useState, useEffect, useRef } from 'react';
import { MailMindLogo } from '../brand/MailMindLogo';
import { AlertCircle, RefreshCw, ArrowLeft, ShieldCheck } from 'lucide-react';
import { fetchAuthExchange, fetchAuthStatus } from '../../services/api';

let _currentExchangePromise = null;
let _currentHandoffCode = null;

/**
 * Dedicated /auth/callback Route Component
 * Handles the secure one-time OAuth handoff exchange between Vercel and Render.
 * 
 * Invariants:
 * 1. Handoff code is single-use and short-lived.
 * 2. Handoff code is NEVER treated as a bearer token or stored in localStorage/sessionStorage.
 * 3. Handoff code is stripped from the URL immediately upon consumption.
 * 4. Google OAuth tokens remain strictly backend-only.
 */
export function AuthCallback({ onSuccess, onCancel, onAuthenticationComplete, exchangeHandoff }) {
  const [status, setStatus] = useState('exchanging'); // 'exchanging' | 'success' | 'error'
  const [errorMessage, setErrorMessage] = useState(null);

  useEffect(() => {
    let isMounted = true;
    const urlParams = new URLSearchParams(window.location.search);
    const handoffFromUrl = urlParams.get('handoff');
    const authError = urlParams.get('auth_error') || urlParams.get('error');

    // Handle OAuth error parameter from Google/Backend
    if (authError) {
      window.history.replaceState({}, document.title, '/');
      setStatus('error');
      setErrorMessage(
        authError === 'access_denied'
          ? 'Google sign-in was canceled or access was denied. Please try again.'
          : 'Authentication was interrupted. Please try again.'
      );
      return;
    }

    const handoffCode = handoffFromUrl || _currentHandoffCode;

    if (!handoffCode) {
      // If no handoff code in query or cache, check if we already have an active valid session
      fetchAuthStatus().then((authStatus) => {
        if (!isMounted) return;
        if (authStatus && authStatus.authenticated && authStatus.user) {
          setStatus('success');
          window.history.replaceState({}, document.title, '/');
          if (onAuthenticationComplete) onAuthenticationComplete(authStatus.user);
          setTimeout(() => {
            if (onSuccess) onSuccess(authStatus.user);
          }, 350);
        } else {
          setStatus('error');
          setErrorMessage('Missing authentication handoff code. Please sign in again.');
        }
      }).catch(() => {
        if (!isMounted) return;
        setStatus('error');
        setErrorMessage('Missing authentication handoff code. Please sign in again.');
      });
      return;
    }

    // Clean URL query parameter so token is not exposed in address bar
    if (handoffFromUrl) {
      _currentHandoffCode = handoffFromUrl;
      window.history.replaceState({}, document.title, window.location.pathname);
    }

    // Reuse or create in-flight exchange promise across React 18 StrictMode mounts
    if (!_currentExchangePromise) {
      const doExchange = exchangeHandoff || fetchAuthExchange;
      _currentExchangePromise = doExchange(handoffCode);
    }

    _currentExchangePromise
      .then((data) => {
        if (!isMounted) return;
        if (data && (data.authenticated || data.user)) {
          setStatus('success');
          window.history.replaceState({}, document.title, '/');
          const user = data.user || data;
          if (onAuthenticationComplete) {
            onAuthenticationComplete(user);
          }
          setTimeout(() => {
            if (onSuccess) {
              onSuccess(user);
            }
          }, 350);
        } else {
          throw new Error('Authentication exchange returned unauthenticated status.');
        }
      })
      .catch(async (err) => {
        if (!isMounted) return;
        // Fallback: If code was already consumed or already processed, check if session is active
        try {
          const authStatus = await fetchAuthStatus();
          if (authStatus && authStatus.authenticated && authStatus.user) {
            setStatus('success');
            window.history.replaceState({}, document.title, '/');
            if (onAuthenticationComplete) {
              onAuthenticationComplete(authStatus.user);
            }
            setTimeout(() => {
              if (onSuccess) {
                onSuccess(authStatus.user);
              }
            }, 350);
            return;
          }
        } catch (_) {}

        console.error('Handoff exchange failed:', err);
        setStatus('error');
        window.history.replaceState({}, document.title, '/');
        const isExpiredOrUsed =
          err.message?.includes('expired') ||
          err.message?.includes('consumed') ||
          err.message?.includes('Invalid') ||
          err.message?.includes('400');
        setErrorMessage(
          isExpiredOrUsed
            ? 'Your sign-in link expired or has already been used. Please try signing in again.'
            : 'Unable to establish a secure session. Please check your connection and try again.'
        );
      })
      .finally(() => {
        setTimeout(() => {
          _currentExchangePromise = null;
          _currentHandoffCode = null;
        }, 5000);
      });

    return () => {
      isMounted = false;
    };
  }, [onSuccess, onAuthenticationComplete, exchangeHandoff]);

  const handleReturnToLogin = () => {
    window.history.replaceState({}, document.title, '/');
    if (onCancel) {
      onCancel();
    } else {
      window.location.href = '/';
    }
  };

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '70vh',
        padding: '2rem 1rem',
        textAlign: 'center',
      }}
    >
      <div
        style={{
          maxWidth: '460px',
          width: '100%',
          backgroundColor: 'var(--bg-surface)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-lg)',
          padding: '2.5rem 2rem',
          boxShadow: 'var(--shadow-md)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: '1.5rem',
        }}
      >
        {/* Brand Logo */}
        <div
          style={{
            width: '64px',
            height: '64px',
            borderRadius: 'var(--radius-lg)',
            backgroundColor: 'var(--bg-card)',
            border: '1px solid var(--border-subtle)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 4px 14px rgba(99, 102, 241, 0.2)',
          }}
        >
          <MailMindLogo size={38} isScanning={status === 'exchanging'} />
        </div>

        {/* State: Exchanging (Loading) */}
        {status === 'exchanging' && (
          <>
            <div>
              <h2
                style={{
                  fontSize: '1.35rem',
                  fontWeight: 700,
                  color: 'var(--text-main)',
                  letterSpacing: '-0.02em',
                  margin: '0 0 0.5rem 0',
                }}
              >
                Completing Secure Sign-In...
              </h2>
              <p
                style={{
                  fontSize: '0.88rem',
                  color: 'var(--text-secondary)',
                  lineHeight: 1.5,
                  margin: 0,
                }}
              >
                Establishing your authenticated session with MailMind. This only takes a moment.
              </p>
            </div>

            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.6rem',
                color: 'var(--accent)',
                fontSize: '0.85rem',
                fontWeight: 500,
                padding: '0.5rem 1rem',
                backgroundColor: 'rgba(99, 102, 241, 0.08)',
                borderRadius: 'var(--radius-full)',
              }}
            >
              <RefreshCw size={15} className="spin-animation" style={{ animation: 'spin 1.5s linear infinite' }} />
              <span>Verifying one-time security credential...</span>
            </div>
          </>
        )}

        {/* State: Success */}
        {status === 'success' && (
          <>
            <div>
              <h2
                style={{
                  fontSize: '1.35rem',
                  fontWeight: 700,
                  color: 'var(--text-main)',
                  letterSpacing: '-0.02em',
                  margin: '0 0 0.5rem 0',
                }}
              >
                Sign-In Successful!
              </h2>
              <p
                style={{
                  fontSize: '0.88rem',
                  color: 'var(--text-secondary)',
                  lineHeight: 1.5,
                  margin: 0,
                }}
              >
                Redirecting to your prioritized inbox...
              </p>
            </div>

            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                color: '#22c55e',
                fontSize: '0.85rem',
                fontWeight: 600,
              }}
            >
              <ShieldCheck size={18} />
              <span>Session Authenticated</span>
            </div>
          </>
        )}

        {/* State: Error */}
        {status === 'error' && (
          <>
            <div>
              <h2
                style={{
                  fontSize: '1.35rem',
                  fontWeight: 700,
                  color: 'var(--p1-color, #ef4444)',
                  letterSpacing: '-0.02em',
                  margin: '0 0 0.5rem 0',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '0.5rem',
                }}
              >
                <AlertCircle size={22} />
                <span>Authentication Failed</span>
              </h2>
              <p
                style={{
                  fontSize: '0.88rem',
                  color: 'var(--text-secondary)',
                  lineHeight: 1.5,
                  margin: '0.5rem 0 0 0',
                }}
              >
                {errorMessage}
              </p>
            </div>

            <button
              onClick={handleReturnToLogin}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '0.5rem',
                width: '100%',
                padding: '0.75rem 1.25rem',
                backgroundColor: 'var(--accent, #6366f1)',
                color: '#ffffff',
                border: 'none',
                borderRadius: 'var(--radius-md)',
                fontSize: '0.9rem',
                fontWeight: 600,
                cursor: 'pointer',
                boxShadow: 'var(--shadow-sm)',
                transition: 'background var(--transition-fast)',
              }}
            >
              <ArrowLeft size={16} />
              <span>Return to Sign In</span>
            </button>
          </>
        )}
      </div>
    </div>
  );
}

export default AuthCallback;
