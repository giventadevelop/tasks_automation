@echo off
setlocal EnableDelayedExpansion
REM One-shot: install deps, build calendar_automate.exe, optional desktop shortcut.
call "%~dp0_env.bat"
set "REPO=%TASKS_AUTOMATION_ROOT%"
set "APP_DIR=%REPO%\google_calendar_and_contacts_automate"
set "EXE=%APP_DIR%\dist\calendar_automate.exe"

echo ============================================================
echo  Daily Tasks Automation — build
echo  Repo: %REPO%
echo ============================================================
echo.

set "PY="
REM Prefer 3.12 for PyInstaller stability (3.14 can show "Failed to load module…")
py -3.12 -c "import sys" >nul 2>&1 && set "PY=py -3.12"
if not defined PY py -3.11 -c "import sys" >nul 2>&1 && set "PY=py -3.11"
if not defined PY where py >nul 2>&1 && set "PY=py -3"
if not defined PY where python >nul 2>&1 && set "PY=python"
if not defined PY (
    echo [FAIL] Python 3 not found.
    pause
    exit /b 1
)
echo [ok] Build Python: %PY%

echo [1/3] Installing build dependencies...
%PY% -m pip install -q google-api-python-client google-auth-httplib2 google-auth-oauthlib anthropic tenacity httpx jproperties pyinstaller websocket-client
if errorlevel 1 (
    echo [FAIL] pip install failed.
    pause
    exit /b 1
)

echo [2/3] Building calendar_automate.exe (PyInstaller onefile)...
echo       Close any running calendar_automate.exe if rebuild fails with "Access is denied".
cd /d "%APP_DIR%"
%PY% -m PyInstaller --noconfirm --clean google_calendar_and_contacts_automate.spec
if errorlevel 1 (
    echo [FAIL] PyInstaller build failed.
    pause
    exit /b 1
)

if not exist "%EXE%" (
    echo [FAIL] Expected output not found: %EXE%
    pause
    exit /b 1
)

echo [ok] Built: %EXE%
echo.

if /I "%~1"=="--shortcut" (
    echo [3/3] Creating desktop shortcut...
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0create_desktop_shortcut.ps1"
) else (
    echo [3/3] Skipping shortcut ^(pass --shortcut to create desktop icon^)
    echo       Or run: scripts_batch_files\dashboard\create_desktop_shortcut.bat
)

echo.
echo ============================================================
echo  DONE
echo  Launch dashboard (packaged .exe):
echo    scripts_batch_files\dashboard\launch_daily_tasks_dashboard.bat
echo  Launch dashboard (latest Python source / dev):
echo    scripts_batch_files\dashboard\launch_daily_tasks_dashboard_dev.bat
echo  Or double-click desktop shortcut if created.
echo.
echo  WhatsApp / Laundry / YouTube run from scripts_batch_files\
echo  TASKS_AUTOMATION_ROOT=%REPO%
echo ============================================================
pause
exit /b 0
