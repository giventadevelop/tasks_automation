@echo off
REM Remove Daily Tasks Automation from Windows Startup.
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_startup_launch.ps1" -Remove
if errorlevel 1 (
    echo [FAIL] Could not remove startup shortcut.
    pause
    exit /b 1
)
pause
exit /b 0
