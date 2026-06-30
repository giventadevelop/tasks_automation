@echo off
REM Launcher for Daily Tasks dashboard — sets TASKS_AUTOMATION_ROOT to repo root.
REM Prefers calendar_automate.exe if built. For latest Python source use launch_daily_tasks_dashboard_dev.bat
call "%~dp0_env.bat"

set "EXE=%TASKS_AUTOMATION_ROOT%\google_calendar_and_contacts_automate\dist\calendar_automate.exe"
if exist "%EXE%" (
    start "" "%EXE%"
    exit /b 0
)

where py >nul 2>&1 && (
    start "" py -3 "%TASKS_AUTOMATION_ROOT%\google_calendar_and_contacts_automate\google_calendar_and_contacts_automate.py"
    exit /b 0
)
where python >nul 2>&1 && (
    start "" python "%TASKS_AUTOMATION_ROOT%\google_calendar_and_contacts_automate\google_calendar_and_contacts_automate.py"
    exit /b 0
)

echo [FAIL] No calendar_automate.exe or Python found.
pause
exit /b 1
