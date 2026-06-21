@echo off
REM Launcher for Daily Tasks dashboard — sets TASKS_AUTOMATION_ROOT to repo root (no secrets).
setlocal
cd /d "%~dp0\.."
set "TASKS_AUTOMATION_ROOT=%CD%"

set "EXE=%CD%\google_calendar_and_contacts_automate\dist\calendar_automate.exe"
if exist "%EXE%" (
    start "" "%EXE%"
    exit /b 0
)

where py >nul 2>&1 && (
    start "" py -3 "%CD%\google_calendar_and_contacts_automate\google_calendar_and_contacts_automate.py"
    exit /b 0
)
where python >nul 2>&1 && (
    start "" python "%CD%\google_calendar_and_contacts_automate\google_calendar_and_contacts_automate.py"
    exit /b 0
)

echo [FAIL] No calendar_automate.exe or Python found.
pause
exit /b 1
