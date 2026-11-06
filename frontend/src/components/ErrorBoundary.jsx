import React from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';

export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('[MailMind UI ErrorBoundary caught error]:', error, errorInfo);
  }

  handleReload = () => {
    try {
      // Clear transient active item pointer in case corrupted ID caused crash
      window.location.reload();
    } catch (_) {
      window.location.href = '/';
    }
  };

  handleResetState = () => {
    try {
      localStorage.removeItem('mailmind_preferred_view');
      window.location.href = '/';
    } catch (_) {
      window.location.reload();
    }
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen w-full flex items-center justify-center bg-zinc-950 text-zinc-100 p-6 select-none font-sans">
          <div className="max-w-md w-full bg-zinc-900 border border-zinc-800 rounded-2xl p-6 shadow-2xl text-center space-y-4">
            <div className="w-12 h-12 rounded-full bg-rose-500/10 border border-rose-500/20 text-rose-500 mx-auto flex items-center justify-center">
              <AlertCircle className="w-6 h-6" />
            </div>
            
            <div className="space-y-1">
              <h2 className="text-lg font-semibold text-white tracking-tight">Something went wrong</h2>
              <p className="text-xs text-zinc-400">
                MailMind encountered an unexpected display error. Your emails and account data remain safe.
              </p>
            </div>

            {this.state.error?.message && (
              <div className="p-2.5 rounded-lg bg-zinc-950/60 border border-zinc-800 text-[11px] font-mono text-zinc-400 truncate text-left">
                {this.state.error.message}
              </div>
            )}

            <div className="pt-2 flex flex-col sm:flex-row gap-2">
              <button
                onClick={this.handleReload}
                className="flex-1 flex items-center justify-center gap-2 py-2 px-4 rounded-xl text-xs font-medium bg-blue-600 hover:bg-blue-500 text-white transition cursor-pointer"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                Reload MailMind
              </button>
              <button
                onClick={this.handleResetState}
                className="py-2 px-3 rounded-xl text-xs font-medium bg-zinc-800 hover:bg-zinc-700 text-zinc-300 transition cursor-pointer"
              >
                Reset View
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
