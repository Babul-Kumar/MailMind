import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import net from 'node:net';

const LOCAL_BACKEND = 'http://127.0.0.1:8000';
const CLOUD_BACKEND = 'https://mailmind-api-xzu8.onrender.com';

/**
 * Checks whether a local TCP host:port is accepting connections.
 */
function checkPortOpen(port = 8000, host = '127.0.0.1', timeoutMs = 250) {
  return new Promise((resolve) => {
    const socket = new net.Socket();
    socket.setTimeout(timeoutMs);
    socket.once('connect', () => {
      socket.destroy();
      resolve(true);
    });
    socket.once('timeout', () => {
      socket.destroy();
      resolve(false);
    });
    socket.once('error', () => {
      resolve(false);
    });
    socket.connect(port, host);
  });
}

export default defineConfig(async ({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const explicitTarget = env.VITE_BACKEND_TARGET || env.VITE_API_BASE_URL;

  // Initial check at server startup
  let isLocalRunning = await checkPortOpen(8000, '127.0.0.1', 300);
  let lastProbeTime = Date.now();

  async function refreshBackendStatus() {
    const now = Date.now();
    // Cache probe for 2 seconds to avoid socket overhead
    if (now - lastProbeTime > 2000) {
      lastProbeTime = now;
      isLocalRunning = await checkPortOpen(8000, '127.0.0.1', 200);
    }
    return isLocalRunning;
  }

  const resolveTarget = () => {
    if (explicitTarget && explicitTarget.trim()) {
      return explicitTarget.trim().replace(/\/+$/, '');
    }
    return isLocalRunning ? LOCAL_BACKEND : CLOUD_BACKEND;
  };

  const initialTarget = resolveTarget();
  console.log(`\x1b[36m[vite proxy]\x1b[0m API requests routed to: \x1b[32m${initialTarget}\x1b[0m${!explicitTarget && !isLocalRunning ? ' (auto-fallback: local backend offline)' : ''}`);

  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        '/api': {
          target: initialTarget,
          changeOrigin: true,
          secure: false,
          cookiePathRewrite: '/',
          router: () => {
            // Asynchronously probe local backend in background
            refreshBackendStatus().catch(() => {});
            return resolveTarget();
          },
          configure: (proxy) => {
            proxy.on('error', (err, req, res) => {
              // Immediately flag local as down if connection refused
              if (err.code === 'ECONNREFUSED') {
                isLocalRunning = false;
              }
              if (!res.headersSent) {
                res.writeHead(503, { 'Content-Type': 'application/json' });
                res.end(
                  JSON.stringify({
                    status: 'backend_offline',
                    message:
                      'Backend server is unreachable. Ensure the local backend is running on http://127.0.0.1:8000 or verify network connectivity.',
                    code: err.code || 'ECONNREFUSED',
                  })
                );
              }
            });

            proxy.on('proxyRes', (proxyRes) => {
              // Strip Secure flag on cookies when testing over local http://
              const setCookieHeaders = proxyRes.headers['set-cookie'];
              if (setCookieHeaders && Array.isArray(setCookieHeaders)) {
                proxyRes.headers['set-cookie'] = setCookieHeaders.map((c) =>
                  c.replace(/;\s*Secure/gi, '')
                );
              }
            });
          },
        },
      },
    },
    build: {
      outDir: 'dist',
      emptyOutDir: true,
    },
  };
});
