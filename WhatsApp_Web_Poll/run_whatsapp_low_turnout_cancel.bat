@echo off
setlocal EnableDelayedExpansion
REM Send the low-turnout cancellation message (no poll read). Dashboard / manual use.
cd /d "%~dp0"

if not "%SKIP_PROMPTS%"=="1" (
    set "CONTACT="
    set "SEND="
)

call "%~dp0start_edge_cdp.bat"
if errorlevel 1 (
    echo Could not ensure Edge+CDP. Aborting.
    pause
    exit /b 1
)

if "%SKIP_PROMPTS%"=="1" (
    if not defined CONTACT set "CONTACT=Volleyball Friday"
    set "SEND=1"
    goto after_prompts
)

echo --- Send volleyball low-turnout cancellation message ---
echo.
set "CONTACT_INPUT="
set /p "CONTACT_INPUT=Contact / group name [Enter = Volleyball Friday]: "
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
set "ACTION=send_low_turnout_cancel"
set "PYTHONIOENCODING=utf-8"

echo ============================================================
echo  Contact = "%CONTACT%"
if defined SEND ( echo  Mode    = REAL SEND ) else ( echo  Mode    = dry-run )
echo ============================================================
echo.

set "PY="
where py >nul 2>&1 && set "PY=py -3"
if not defined PY where python >nul 2>&1 && set "PY=python"
if not defined PY (
    echo [FAIL] Python not found.
    pause
    exit /b 1
)

%PY% -c "import websocket" >nul 2>&1
if errorlevel 1 %PY% -m pip install -q -r "%~dp0requirements.txt"

%PY% "%~dp0whatsapp_poll.py"
set RC=%ERRORLEVEL%
echo.
if %RC% EQU 0 ( echo === DONE. === ) else ( echo === FAILED exit %RC% === )
endlocal
pause
exit /b %RC%
