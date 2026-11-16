@echo off
setlocal EnableDelayedExpansion

REM ==============================================================================
REM MailMind - Complete Full-Stack Application Launcher
REM Starts FastAPI Backend (Port 8000) and Vite React Frontend (Port 5173)
REM ==============================================================================

title MailMind - AI Email Priority Platform

REM 1. Force execution context to the project root directory
cd /d "%~dp0"

echo ====================================================================
echo   MailMind : AI Email Priority Intelligence and Action Platform
echo   CSE472 - Automated Email Triage Full-Stack Environment
echo ====================================================================
echo.

REM 2. Display Help if requested
if "%~1"=="--help" goto :show_help
if "%~1"=="-h" goto :show_help
if "%~1"=="/?" goto :show_help
goto :check_env

:show_help
echo Usage: run.bat [options]
echo.
echo Options:
echo   (no args)       Starts both FastAPI backend and Vite frontend (recommended)
echo   --no-browser    Starts full stack without opening the browser automatically
echo   --split         Starts backend and frontend in two separate command windows
echo   --backend-only  Starts only the FastAPI REST backend server (port 8000)
echo   --frontend-only Starts only the Vite React frontend server (port 5173)
echo   --no-reload     Disables auto-reload in FastAPI backend
echo   --help, -h, /?  Displays this help message
echo.
exit /b 0

:check_env
REM 3. Check for .env file; initialize from .env.example if missing
if exist ".env" goto :check_python
if not exist ".env.example" goto :no_env_example
echo [INFO] .env not found. Initializing default configuration from .env.example...
copy ".env.example" ".env" >nul
echo [OK] Default .env created. Configure Google OAuth credentials in .env if needed.
echo.
goto :check_python

:no_env_example
echo [WARN] Neither .env nor .env.example found. Proceeding with application defaults.
echo.

:check_python
REM 4. Detect Python environment (prioritizing local .venv)
set "PYTHON_EXE="

if exist "%~dp0.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
    echo [OK] Python virtual environment detected: .venv
    if exist "%~dp0.venv\Scripts\activate.bat" (
        call "%~dp0.venv\Scripts\activate.bat"
    )
    goto :python_found
)

where python >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON_EXE=python"
    echo [INFO] Local .venv not found. Using system Python.
    goto :python_found
)

where py >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON_EXE=py -3"
    echo [INFO] Using Windows Python Launcher: py -3
    goto :python_found
)

echo.
echo [ERROR] Python is not installed or not found on PATH.
echo Please install Python 3.10+ from https://www.python.org/
echo Ensure "Add python.exe to PATH" is checked during installation.
echo.
pause
exit /b 1

:python_found
for /f "tokens=*" %%v in ('"!PYTHON_EXE!" --version 2^>^&1') do (
    echo [OK] %%v
)

REM 5. Detect Node.js and npm
where npm >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Node.js / npm is not installed or not found on PATH.
    echo Please install Node.js 18+ from https://nodejs.org/
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%v in ('node -v 2^>nul') do set "NODE_VER=%%v"
for /f "tokens=*" %%v in ('npm -v 2^>nul') do set "NPM_VER=%%v"
echo [OK] Node.js: !NODE_VER! ^| npm: !NPM_VER!
echo.

REM 6. Verify backend dependencies
echo [INFO] Verifying backend dependencies (FastAPI, Uvicorn, Scikit-Learn)...
"!PYTHON_EXE!" -c "import fastapi, uvicorn, sklearn" >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Backend dependencies verified.
    goto :check_frontend_deps
)

echo [INFO] Missing backend dependencies. Installing from requirements.txt...
"!PYTHON_EXE!" -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Failed to install backend Python dependencies.
    pause
    exit /b 1
)
echo [OK] Backend dependencies installed successfully.

:check_frontend_deps
REM 7. Verify frontend dependencies
if exist "frontend\node_modules\" (
    echo [OK] Frontend dependencies verified.
    goto :deps_ready
)

echo [INFO] Frontend dependencies not found. Running npm install in frontend...
pushd frontend
call npm install
set "NPM_INSTALL_ERR=%errorlevel%"
popd
if %NPM_INSTALL_ERR% neq 0 (
    echo.
    echo [ERROR] Failed to install frontend npm packages.
    pause
    exit /b 1
)
echo [OK] Frontend dependencies installed successfully.

:deps_ready
echo.

REM 8. Support --split mode
if "%~1"=="--split" goto :run_split
if "%~1"=="-split" goto :run_split
goto :run_unified

:run_split
echo ====================================================================
echo   Launching MailMind in Separate Windows (--split mode)
echo     - Backend:  http://127.0.0.1:8000
echo     - Frontend: http://localhost:5173
echo ====================================================================
echo.
start "MailMind Backend (FastAPI)" cmd /k "cd /d "%~dp0" && "!PYTHON_EXE!" -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload"
timeout /t 2 /nobreak >nul
start "MailMind Frontend (Vite)" cmd /k "cd /d "%~dp0frontend" && npm run dev"
timeout /t 2 /nobreak >nul
start http://localhost:5173
echo [OK] MailMind services launched in separate windows.
exit /b 0

:run_unified
REM 9. Launch Unified Application Runner (run_dev.py)
echo ====================================================================
echo   Starting MailMind Full-Stack Platform:
echo     - Backend REST API:  http://127.0.0.1:8000
echo     - Swagger API Docs:  http://127.0.0.1:8000/docs
echo     - Frontend React UI: http://localhost:5173
echo.
echo   Press Ctrl+C to gracefully stop all services.
echo ====================================================================
echo.

"!PYTHON_EXE!" run_dev.py %*

set "EXIT_CODE=%errorlevel%"
if %EXIT_CODE% neq 0 (
    echo.
    echo [INFO] MailMind terminated with exit code %EXIT_CODE%.
    pause
)

exit /b %EXIT_CODE%
