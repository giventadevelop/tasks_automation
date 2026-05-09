@echo off
REM ============================================================
REM  Single-command laundry order — pure browser-use CLI flow.
REM  Double-click this file.
REM ============================================================
cd /d "%~dp0"

call start_chrome_cdp.bat
if %ERRORLEVEL% NEQ 0 (
    echo Could not start Chrome CDP. Aborting.
    pause
    exit /b 1
)

echo.
echo Running laundry order flow via browser-use...
wsl.exe -e bash -lc "/mnt/c/E_Drive/project_workspace/tasks_automation/Laundry_TryCents/laundry_flow.sh"
set RC=%ERRORLEVEL%

echo.
if %RC% EQU 0 (
    echo === DONE — order flow finished successfully. ===
) else (
    echo === FAILED — exit code %RC%. Review the Chrome tab to see where it stopped. ===
)
pause
exit /b %RC%
