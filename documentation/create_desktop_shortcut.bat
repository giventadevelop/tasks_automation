@echo off
REM Create Desktop shortcut for Daily Tasks Automation (no secrets).
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0create_desktop_shortcut.ps1" %*
if errorlevel 1 (
    echo [FAIL] Could not create shortcut.
    pause
    exit /b 1
)
pause
exit /b 0
