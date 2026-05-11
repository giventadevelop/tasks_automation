@echo off
setlocal
REM ============================================================
REM   WhatsApp Web Poll prototype — interactive launcher.
REM   Clears inherited env vars so you can't accidentally re-use a stale value.
REM ============================================================
cd /d "%~dp0"

REM Force-clear any inherited values
set "CONTACT="
set "SEND="
set "POLL_TITLE="

call start_chrome_cdp.bat
if %ERRORLEVEL% NEQ 0 (
    echo Could not ensure Chrome+CDP. Aborting.
    pause
    exit /b 1
)

echo.
echo --- WhatsApp Poll prototype ---
echo.
set "CONTACT_INPUT="
set /p "CONTACT_INPUT=Contact name to search [Enter = Gain Joseph]: "
if "%CONTACT_INPUT%"=="" (
    set "CONTACT=Gain Joseph"
) else (
    set "CONTACT=%CONTACT_INPUT%"
)

set "SEND_INPUT="
set /p "SEND_INPUT=Type YES to actually send, anything else = dry-run [Enter = dry-run]: "
if /I "%SEND_INPUT%"=="YES" (
    set "SEND=1"
) else (
    set "SEND="
)

echo.
echo ============================================================
echo  Contact = "%CONTACT%"
if defined SEND ( echo  Mode    = REAL SEND ) else ( echo  Mode    = dry-run )
echo ============================================================
echo.

REM Build a single bash command. We pass CONTACT via the bash inline-export
REM syntax (VAR=value cmd) so bash handles the quoting, not env(1).
REM Note: %CONTACT% may contain spaces, so we wrap it in single quotes inside
REM the bash -lc string.
set "BASH_CMD=cd '/mnt/c/E_Drive/project_workspace/tasks_automation/WhatsApp_Web_Poll' && CONTACT='%CONTACT%'"
if defined SEND set "BASH_CMD=%BASH_CMD% SEND=1"
set "BASH_CMD=%BASH_CMD% ~/.local/share/pipx/venvs/browser-use/bin/python whatsapp_poll.py"

echo Launching script...
wsl.exe -e bash -lc "%BASH_CMD%"
set RC=%ERRORLEVEL%

echo.
if %RC% EQU 0 (
    echo === DONE. ===
) else (
    echo === FAILED — exit code %RC%. See output above. ===
)
endlocal
pause
exit /b %RC%
