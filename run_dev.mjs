#!/usr/bin/env node
/**
 * MailMind Unified Development Runner (run_dev.mjs)
 * Starts the FastAPI backend and Vite React frontend concurrently.
 * Reuses existing backend if already running on port 8000.
 * Handles graceful shutdown on SIGINT / SIGTERM / Ctrl+C.
 */

import { spawn } from 'node:child_process';
import net from 'node:net';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const BACKEND_PORT = 8000;
const FRONTEND_PORT = 5173;

/**
 * Checks whether a local TCP port is currently open.
 */
function isPortOpen(port, host = '127.0.0.1', timeoutMs = 300) {
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

const childProcesses = [];

function cleanupAndExit(code = 0) {
  console.log('\n\x1b[33m[mailmind]\x1b[0m Shutting down development services...');
  for (const child of childProcesses) {
    if (child && !child.killed) {
      try {
        if (process.platform === 'win32') {
          spawn('taskkill', ['/pid', child.pid, '/f', '/t'], { stdio: 'ignore' });
        } else {
          child.kill('SIGTERM');
        }
      } catch {
        // Process might already be stopped
      }
    }
  }
  process.exit(code);
}

process.on('SIGINT', () => cleanupAndExit(0));
process.on('SIGTERM', () => cleanupAndExit(0));

async function main() {
  console.log('\x1b[1m\x1b[34m====================================================\x1b[0m');
  console.log('\x1b[1m\x1b[36m    MailMind Full-Stack Development Workspace       \x1b[0m');
  console.log('\x1b[1m\x1b[34m====================================================\x1b[0m\n');

  const backendRunning = await isPortOpen(BACKEND_PORT);
  if (backendRunning) {
    console.log(`\x1b[32m[backend]\x1b[0m FastAPI server is already running on port ${BACKEND_PORT}. Reusing active instance.`);
  } else {
    console.log(`\x1b[35m[backend]\x1b[0m Launching FastAPI (uvicorn) on http://127.0.0.1:${BACKEND_PORT}...`);
    const pythonCmd = process.platform === 'win32' ? 'python' : 'python3';
    const backendProcess = spawn(
      pythonCmd,
      ['-m', 'uvicorn', 'backend.app.main:app', '--host', '127.0.0.1', '--port', String(BACKEND_PORT), '--reload'],
      {
        cwd: __dirname,
        stdio: 'inherit',
        shell: true,
      }
    );
    childProcesses.push(backendProcess);

    backendProcess.on('exit', (code) => {
      if (code !== null && code !== 0) {
        console.error(`\x1b[31m[backend]\x1b[0m Uvicorn exited with code ${code}`);
      }
    });
  }

  // Wait 500ms for backend port to bind if freshly started
  if (!backendRunning) {
    let waited = 0;
    while (waited < 5000) {
      if (await isPortOpen(BACKEND_PORT)) break;
      await new Promise((r) => setTimeout(r, 250));
      waited += 250;
    }
  }

  console.log(`\x1b[36m[frontend]\x1b[0m Launching Vite React frontend on http://localhost:${FRONTEND_PORT}...`);
  const npmCmd = process.platform === 'win32' ? 'npm.cmd' : 'npm';
  const frontendProcess = spawn(
    npmCmd,
    ['run', 'dev'],
    {
      cwd: path.join(__dirname, 'frontend'),
      stdio: 'inherit',
      shell: true,
    }
  );
  childProcesses.push(frontendProcess);

  frontendProcess.on('exit', (code) => {
    if (code !== null && code !== 0) {
      console.error(`\x1b[31m[frontend]\x1b[0m Vite exited with code ${code}`);
    }
    cleanupAndExit(code || 0);
  });
}

main().catch((err) => {
  console.error('\x1b[31m[mailmind error]\x1b[0m Failed to launch development workspace:', err);
  cleanupAndExit(1);
});
