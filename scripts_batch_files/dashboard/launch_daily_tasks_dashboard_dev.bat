@echo off
REM Dev launcher — always runs latest Python dashboard source (skips calendar_automate.exe).
call "%~dp0_env.bat"

set "APP_PY=%TASKS_AUTOMATION_ROOT%\google_calendar_and_contacts_automate\google_calendar_and_contacts_automate.py"
if not exist "%APP_PY%" (
    echo [FAIL] Dashboard script not found:
    echo   %APP_PY%
    pause
    exit /b 1
)

where py >nul 2>&1 && (
    echo [ok] Starting dashboard from source ^(py -3^)
    echo     TASKS_AUTOMATION_ROOT=%TASKS_AUTOMATION_ROOT%
    start "" py -3 "%APP_PY%"
    exit /b 0
)
where python >nul 2>&1 && (
    echo [ok] Starting dashboard from source ^(python^)
    echo     TASKS_AUTOMATION_ROOT=%TASKS_AUTOMATION_ROOT%
    start "" python "%APP_PY%"
    exit /b 0
)

echo [FAIL] Python 3 not found. Install Python or use launch_daily_tasks_dashboard.bat for the .exe.
pause
exit /b 1
