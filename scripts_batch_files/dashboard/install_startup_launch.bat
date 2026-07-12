@echo off
REM Install Daily Tasks Automation to Windows Startup (current user).
REM Creates a shortcut in the Startup folder pointing at the dashboard launcher.
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_startup_launch.ps1" %*
if errorlevel 1 (
    echo [FAIL] Could not install startup shortcut.
    pause
    exit /b 1
)
pause
exit /b 0
