#!/usr/bin/env python3
"""
MailMind Unified Development Runner (run_dev.py)
Starts FastAPI backend and Vite React frontend concurrently.
Supervises both processes and ensures clean startup and shutdown.
"""

import atexit
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser

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


def is_mailmind_backend(port: int = BACKEND_PORT) -> bool:
    """Verifies that the server on port is MailMind FastAPI backend and healthy."""
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/health",
            headers={"User-Agent": "MailMind-HealthCheck"}
        )
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            data = json.loads(resp.read().decode())
            return data.get("service") == "AI Email Priority Dashboard"
    except Exception:
        return False


def free_port(port: int) -> bool:
    """Terminates any conflicting process occupying the specified port on Windows."""
    if sys.platform != "win32":
        return False
    try:
        res = subprocess.run(f"netstat -ano | findstr :{port}", shell=True, capture_output=True, text=True)
        killed_any = False
        current_pid = os.getpid()
        for line in res.stdout.strip().splitlines():
            parts = line.strip().split()
            if len(parts) >= 5 and "LISTENING" in parts:
                local_addr = parts[1]
                if local_addr.endswith(f":{port}"):
                    pid = parts[-1]
                    if pid.isdigit() and int(pid) != current_pid and int(pid) != 0:
                        subprocess.run(["taskkill", "/pid", pid, "/f", "/t"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        killed_any = True
        if killed_any:
            time.sleep(0.5)
        return killed_any
    except Exception:
        return False


processes = []
_cleaned_up = False


def cleanup():
    global _cleaned_up
    if _cleaned_up:
        return
    _cleaned_up = True
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


atexit.register(cleanup)


def open_browser_when_ready(frontend_url: str, stop_event: threading.Event):
    """Waits for Vite dev server to respond and opens the browser."""
    waited = 0.0
    while waited < 20.0 and not stop_event.is_set():
        if is_port_open(FRONTEND_PORT):
            time.sleep(0.6)
            if not stop_event.is_set():
                print(f"\033[32m[browser]\033[0m Opening {frontend_url} in your default browser...")
                webbrowser.open(frontend_url)
            return
        time.sleep(0.3)
        waited += 0.3


def main():
    args = sys.argv[1:]
    no_browser = "--no-browser" in args or os.getenv("NO_BROWSER") == "1"
    frontend_only = "--frontend-only" in args
    backend_only = "--backend-only" in args
    no_reload = "--no-reload" in args
    reuse_backend = "--reuse-backend" in args

    print("\033[1m\033[34m====================================================\033[0m")
    print("\033[1m\033[36m    MailMind Full-Stack Development Workspace       \033[0m")
    print("\033[1m\033[34m====================================================\033[0m\n")

    stop_browser_event = threading.Event()
    backend_proc = None
    frontend_proc = None

    # 1. Start FastAPI backend (unless frontend-only)
    if not frontend_only:
        backend_already_running = False
        if reuse_backend and is_mailmind_backend(BACKEND_PORT):
            print(f"\033[32m[backend]\033[0m MailMind FastAPI server is already running on port {BACKEND_PORT}. Reusing active instance (--reuse-backend).")
            backend_already_running = True
        else:
            if is_port_open(BACKEND_PORT):
                print(f"\033[33m[backend]\033[0m Port {BACKEND_PORT} is in use. Resetting port for clean session...")
                free_port(BACKEND_PORT)

            print(f"\033[35m[backend]\033[0m Launching FastAPI (uvicorn) on http://127.0.0.1:{BACKEND_PORT}...")
            uvicorn_cmd = [sys.executable, "-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", str(BACKEND_PORT)]
            if not no_reload:
                uvicorn_cmd.append("--reload")

            backend_proc = subprocess.Popen(
                uvicorn_cmd,
                cwd=ROOT_DIR
            )
            processes.append(backend_proc)

        # Wait up to 15s for backend to become fully healthy before proceeding
        if not backend_already_running:
            print(f"\033[35m[backend]\033[0m Waiting for backend to initialize and warm up ML pipeline...")
            waited = 0.0
            ready = False
            while waited < 15.0:
                if is_mailmind_backend(BACKEND_PORT):
                    ready = True
                    break
                time.sleep(0.3)
                waited += 0.3

            if ready:
                print(f"\033[32m[backend]\033[0m FastAPI backend is healthy and ready to accept requests.")
            else:
                print(f"\033[31m[backend]\033[0m Warning: Backend startup took longer than 15s. Proceeding with frontend...")

    # 2. Start Vite frontend (unless backend-only)
    if not backend_only:
        # Free both 5173 and 5174 to avoid port drift
        for p in (FRONTEND_PORT, 5174):
            if is_port_open(p):
                print(f"\033[33m[frontend]\033[0m Port {p} is in use. Freeing port for MailMind...")
                free_port(p)

        print(f"\033[36m[frontend]\033[0m Launching Vite React frontend on http://localhost:{FRONTEND_PORT}...")
        npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
        frontend_proc = subprocess.Popen(
            [npm_cmd, "run", "dev"],
            cwd=FRONTEND_DIR,
            shell=(sys.platform == "win32")
        )
        processes.append(frontend_proc)

        if not no_browser:
            browser_thread = threading.Thread(
                target=open_browser_when_ready,
                args=(f"http://localhost:{FRONTEND_PORT}", stop_browser_event),
                daemon=True
            )
            browser_thread.start()

    # Wait and supervise running child processes
    try:
        if processes:
            while True:
                for proc in list(processes):
                    ret = proc.poll()
                    if ret is not None:
                        name = "FastAPI Backend" if proc == backend_proc else "Vite Frontend"
                        print(f"\n\033[31m[mailmind]\033[0m {name} terminated with code {ret}.")
                        return ret
                time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n\033[33m[mailmind]\033[0m Interrupted by user.")
    finally:
        stop_browser_event.set()
        cleanup()


if __name__ == "__main__":
    main()
