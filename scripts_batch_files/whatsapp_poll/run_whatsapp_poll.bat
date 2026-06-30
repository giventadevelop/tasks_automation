@echo off
setlocal EnableDelayedExpansion
call "%~dp0_env.bat"
REM WhatsApp Web Poll — interactive launcher (Windows-native).

if not "%SKIP_PROMPTS%"=="1" (
    set "CONTACT="
    set "SEND="
    set "POLL_TITLE="
)

call "%~dp0start_edge_cdp.bat"
if errorlevel 1 (
    echo Could not ensure Edge+CDP. Aborting.
    pause
    exit /b 1
)

if "%SKIP_PROMPTS%"=="1" (
    if not defined CONTACT set "CONTACT=Volleyball Friday"
    goto after_prompts
)

echo --- WhatsApp Poll prototype ---
echo (Uses Edge + CDP directly — NOT browser-use / Playwright / Selenium)
echo.
set "CONTACT_INPUT="
set /p "CONTACT_INPUT=Contact name to search [Enter = Volleyball Friday]: "
if "%CONTACT_INPUT%"=="" (
    set "CONTACT=Volleyball Friday"
) else (
    set "CONTACT=%CONTACT_INPUT%"
)

set "SEND_INPUT="
set /p "SEND_INPUT=Press Enter to SEND for real. Type CANCEL for dry-run: "
if /I "%SEND_INPUT%"=="CANCEL" (
    set "SEND="
) else (
    set "SEND=1"
)

:after_prompts
if "%SKIP_PROMPTS%"=="1" (
    echo --- WhatsApp Poll ^(dashboard launch^) ---
) else (
    echo.
)
echo ============================================================
echo  Contact = "%CONTACT%"
if defined SEND ( echo  Mode    = REAL SEND ) else ( echo  Mode    = dry-run )
echo  Folder  = %MODULE_ROOT%
echo ============================================================
echo.

set "PY="
where py >nul 2>&1 && set "PY=py -3"
if not defined PY where python >nul 2>&1 && set "PY=python"
if not defined PY (
    echo [FAIL] Python not found. Install Python 3 from https://python.org and retry.
    pause
    exit /b 1
)

echo Using: %PY%
%PY% -c "import websocket" >nul 2>&1
if errorlevel 1 (
    echo Installing websocket-client...
    %PY% -m pip install -q -r "%MODULE_ROOT%\requirements.txt"
    if errorlevel 1 (
        echo [FAIL] Could not install websocket-client. Run: %PY% -m pip install websocket-client
        pause
        exit /b 1
    )
)

echo Launching script...
%PY% "%MODULE_ROOT%\whatsapp_poll.py"
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
