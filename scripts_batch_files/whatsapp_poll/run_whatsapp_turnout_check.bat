@echo off
setlocal EnableDelayedExpansion
call "%~dp0_env.bat"
REM Friday turnout (same as 3 PM scheduled job): weather + poll → go / weather-cancel / low-turnout.

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
    goto after_prompts
)

echo --- Friday turnout message (weather + poll → go / cancel) ---
echo.
set "CONTACT_INPUT="
set /p "CONTACT_INPUT=Contact / group name [Enter = Volleyball Friday]: "
if "%CONTACT_INPUT%"=="" (
    set "CONTACT=Volleyball Friday"
) else (
    set "CONTACT=%CONTACT_INPUT%"
)

set "SEND_INPUT="
set /p "SEND_INPUT=Press Enter to SEND the go/cancel message. Type CANCEL for dry-run: "
if /I "%SEND_INPUT%"=="CANCEL" (
    set "SEND="
) else (
    set "SEND=1"
)

:after_prompts
set "ACTION=check_turnout"
set "PYTHONIOENCODING=utf-8"
if not defined MIN_PLAYERS set "MIN_PLAYERS=6"

echo ============================================================
echo  Contact     = "%CONTACT%"
echo  Min Yes     = %MIN_PLAYERS%
if defined SEND ( echo  Mode        = REAL SEND ) else ( echo  Mode        = dry-run )
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
if errorlevel 1 %PY% -m pip install -q -r "%MODULE_ROOT%\requirements.txt"

%PY% "%MODULE_ROOT%\whatsapp_poll.py"
set RC=%ERRORLEVEL%
echo.
if %RC% EQU 0 ( echo === DONE. === ) else ( echo === FAILED exit %RC% === )
endlocal
pause
exit /b %RC%
