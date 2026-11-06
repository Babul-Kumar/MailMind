import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import http from 'node:http';
import https from 'node:https';

const httpAgent = new http.Agent({
  keepAlive: false,
  timeout: 30000,
});

const httpsAgent = new https.Agent({
  keepAlive: false,
  timeout: 30000,
});

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  // Default strictly to local backend for local development
  const target = (env.VITE_BACKEND_TARGET || env.VITE_API_BASE_URL || 'http://127.0.0.1:8000')
    .trim()
    .replace(/\/+$/, '');

  const agent = target.startsWith('https') ? httpsAgent : httpAgent;

  console.log(`\x1b[36m[vite proxy]\x1b[0m API requests -> \x1b[32m${target}\x1b[0m`);

  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        '/api': {
          target,
          changeOrigin: true,
          secure: false,
          agent,
          cookiePathRewrite: '/',
          configure: (proxy) => {
            proxy.on('error', (err, req, res) => {
              if (!res.headersSent) {
                res.writeHead(503, { 'Content-Type': 'application/json' });
                res.end(
                  JSON.stringify({
                    status: 'backend_offline',
                    message:
                      `Backend server is unreachable at ${target}. Ensure FastAPI is running on http://127.0.0.1:8000.`,
                    code: err.code || 'ECONNREFUSED',
                  })
                );
              }
            });

            proxy.on('proxyRes', (proxyRes) => {
              // Strip Secure flag on cookies so local HTTP can set cookies cleanly
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
