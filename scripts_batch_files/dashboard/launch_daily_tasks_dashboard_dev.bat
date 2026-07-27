@echo off
REM Dev launcher — always runs latest Python dashboard source (skips calendar_automate.exe).
REM Prefer Python 3.12: default `py -3` may be 3.14 and break some deps / PyInstaller workflows.
call "%~dp0_env.bat"

set "APP_PY=%TASKS_AUTOMATION_ROOT%\google_calendar_and_contacts_automate\google_calendar_and_contacts_automate.py"
if not exist "%APP_PY%" (
    echo [FAIL] Dashboard script not found:
    echo   %APP_PY%
    pause
    exit /b 1
)

cd /d "%TASKS_AUTOMATION_ROOT%\google_calendar_and_contacts_automate"

set "PY_CMD="
py -3.12 -c "import sys" >nul 2>&1 && set "PY_CMD=py -3.12"
if not defined PY_CMD py -3.11 -c "import sys" >nul 2>&1 && set "PY_CMD=py -3.11"
if not defined PY_CMD where py >nul 2>&1 && set "PY_CMD=py -3"
if not defined PY_CMD where python >nul 2>&1 && set "PY_CMD=python"

if not defined PY_CMD (
    echo [FAIL] Python 3 not found. Install Python or use launch_daily_tasks_dashboard.bat for the .exe.
    pause
    exit /b 1
)

echo [ok] Starting dashboard from source ^(%PY_CMD%^)
echo     TASKS_AUTOMATION_ROOT=%TASKS_AUTOMATION_ROOT%
start "" %PY_CMD% "%APP_PY%"
exit /b 0
