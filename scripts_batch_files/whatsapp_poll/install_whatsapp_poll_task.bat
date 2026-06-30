@echo off
setlocal
call "%~dp0_env.bat"

echo Installing WhatsApp Thursday scheduled task for current user...
echo (No Administrator required for normal user-level tasks.)
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_whatsapp_poll_task.ps1"
if %ERRORLEVEL% EQU 0 goto success

echo.
echo [warn] PowerShell install failed — trying simple schtasks fallback (weekly 08:00 only)...
echo.

set "TASK_NAME=WhatsApp Volleyball Poll (Thursday)"
set "RUN_BAT=%~dp0run_whatsapp_poll_scheduled.bat"

schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1
schtasks /create /tn "%TASK_NAME%" /tr "%RUN_BAT%" /sc weekly /d THU /st 08:00 /f
if errorlevel 1 (
    echo.
    echo [FAIL] Could not create scheduled task.
    echo.
    echo Try:
    echo   1. Run this .bat from your normal account ^(not blocked by policy^)
    echo   2. Or run PowerShell as:
    echo        powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_whatsapp_poll_task.ps1"
    echo   3. If still "Access is denied", ask IT — Group Policy may block Task Scheduler.
    pause
    exit /b 1
)

echo.
echo [ok] Simple weekly task installed ^(Thursday 08:00 only^).
echo      For unlock-after-sleep, re-run after fixing PowerShell install.
goto success

:success
echo.
echo Guards in run_whatsapp_poll_scheduled.bat:
echo   - Thursdays only, May 12 - Oct 30
echo   - Hourly 08:00-23:00 (retries if failed until 11 PM)
echo   - Friday turnout: 15:00-17:00 every 20 min (weather + go / cancel messages)
echo.
echo Test poll:    schtasks /run /tn "WhatsApp Volleyball Poll (Thursday)"
echo Test turnout: schtasks /run /tn "WhatsApp Volleyball Turnout (Friday)"
echo View logs:    %~dp0view_logs.bat
echo Remove: %~dp0uninstall_whatsapp_poll_task.bat
pause
exit /b 0
