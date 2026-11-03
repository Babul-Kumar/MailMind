#!/usr/bin/env python3
"""
MailMind Unified Development Runner (run_dev.py)
Starts FastAPI backend and Vite React frontend concurrently.
Reuses existing backend if already active on port 8000.
Handles clean shutdown on SIGINT / Ctrl+C.
"""

import os
import signal
import socket
import subprocess
import sys
import time

BACKEND_PORT = 8000
FRONTEND_PORT = 5173
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(ROOT_DIR, "frontend")


def is_port_open(port: int, host: str = "127.0.0.1", timeout: float = 0.3) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, ConnectionRefusedError):
        return False


processes = []


def cleanup():
    print("\n\033[33m[mailmind]\033[0m Shutting down development services...")
    for proc in processes:
        if proc.poll() is None:
            try:
                if sys.platform == "win32":
                    subprocess.run(["taskkill", "/pid", str(proc.pid), "/f", "/t"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    proc.terminate()
            except Exception:
                pass


def main():
    print("\033[1m\033[34m====================================================\033[0m")
    print("\033[1m\033[36m    MailMind Full-Stack Development Workspace       \033[0m")
    print("\033[1m\033[34m====================================================\033[0m\n")

    # 1. Check or start FastAPI backend
    backend_running = is_port_open(BACKEND_PORT)
    if backend_running:
        print(f"\033[32m[backend]\033[0m FastAPI server is already running on port {BACKEND_PORT}. Reusing active instance.")
    else:
        print(f"\033[35m[backend]\033[0m Launching FastAPI (uvicorn) on http://127.0.0.1:{BACKEND_PORT}...")
        backend_proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", str(BACKEND_PORT), "--reload"],
            cwd=ROOT_DIR
        )
        processes.append(backend_proc)

        # Wait up to 5s for backend port to bind
        waited = 0.0
        while waited < 5.0:
            if is_port_open(BACKEND_PORT):
                break
            time.sleep(0.25)
            waited += 0.25

    # 2. Start Vite frontend
    print(f"\033[36m[frontend]\033[0m Launching Vite React frontend on http://localhost:{FRONTEND_PORT}...")
    npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
    frontend_proc = subprocess.Popen(
        [npm_cmd, "run", "dev"],
        cwd=FRONTEND_DIR
    )
    processes.append(frontend_proc)

    try:
        frontend_proc.wait()
    except KeyboardInterrupt:
        pass
    finally:
        cleanup()


if __name__ == "__main__":
    main()
