@echo off
setlocal EnableDelayedExpansion
call "%~dp0_env.bat"
REM Non-interactive scheduled runner (Task Scheduler / hourly retries until 11 PM).

set "LOG_DIR=%MODULE_ROOT%\logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd"') do set "LOG_DAY=%%I"
for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format HH"') do set "LOG_HOUR=%%I"
set "LOG_FILE=%LOG_DIR%\whatsapp_poll_%LOG_DAY%_%LOG_HOUR%.log"
set "LOG_DAILY=%LOG_DIR%\whatsapp_poll_%LOG_DAY%.log"

set "PY="
where py >nul 2>&1 && set "PY=py -3"
if not defined PY where python >nul 2>&1 && set "PY=python"
if not defined PY (
    echo [%date% %time%] FAIL: Python not found>>"%LOG_FILE%"
    exit /b 1
)

%PY% "%MODULE_ROOT%\log_rotate.py" >>"%LOG_FILE%" 2>&1

echo.>>"%LOG_FILE%"
echo ============================================================>>"%LOG_FILE%"
echo [%date% %time%] scheduled run started>>"%LOG_FILE%"

%PY% -u "%MODULE_ROOT%\schedule_gate.py" >>"%LOG_FILE%" 2>&1
set GATE_RC=!ERRORLEVEL!
echo [%date% %time%] schedule_gate exit=!GATE_RC!>>"%LOG_FILE%"
if !GATE_RC! GEQ 2 (
    echo [%date% %time%] schedule gate: skip>>"%LOG_FILE%"
    %PY% "%MODULE_ROOT%\generate_log_viewer.py" >nul 2>&1
    exit /b 0
)

echo [%date% %time%] schedule gate: proceed>>"%LOG_FILE%"
echo [%date% %time%] log file: %LOG_FILE%>>"%LOG_FILE%"

%PY% -u -c "import sys; sys.path.insert(0, r'%MODULE_ROOT%'); from run_status import mark_attempt; mark_attempt('poll')" >>"%LOG_FILE%" 2>&1

call "%~dp0start_edge_cdp.bat" >>"%LOG_FILE%" 2>&1
set EDGE_RC=!ERRORLEVEL!
echo [%date% %time%] start_edge_cdp exit=!EDGE_RC!>>"%LOG_FILE%"
if !EDGE_RC! NEQ 0 (
    echo [%date% %time%] FAIL: Edge CDP>>"%LOG_FILE%"
    %PY% -u "%MODULE_ROOT%\schedule_gate.py" --mark-failed "edge_cdp_failed">>"%LOG_FILE%" 2>&1
    %PY% "%MODULE_ROOT%\generate_log_viewer.py" >nul 2>&1
    exit /b 1
)

echo [%date% %time%] edge warmup 10s before poll script...>>"%LOG_FILE%"
REM ping delay survives Task Scheduler / redirected stdin; timeout often does not
ping -n 11 127.0.0.1 >nul

%PY% -u -c "import websocket" >nul 2>&1
if errorlevel 1 (
    echo [%date% %time%] installing requirements...>>"%LOG_FILE%"
    %PY% -m pip install -q -r "%MODULE_ROOT%\requirements.txt" >>"%LOG_FILE%" 2>&1
)

set "CONTACT=Volleyball Friday"
set "SEND=1"
set "POLL_TITLE="
set "SCHEDULED=1"
set "PYTHONIOENCODING=utf-8"
set "PYTHONUNBUFFERED=1"

echo [%date% %time%] launching whatsapp_poll.py contact=!CONTACT! send=1 scheduled=1>>"%LOG_FILE%"
%PY% -u "%MODULE_ROOT%\whatsapp_poll.py" >>"%LOG_FILE%" 2>&1
set RC=!ERRORLEVEL!
echo [%date% %time%] whatsapp_poll.py exit=!RC!>>"%LOG_FILE%"

if !RC! EQU 0 (
    %PY% -u "%MODULE_ROOT%\schedule_gate.py" --mark-success "poll_sent">>"%LOG_FILE%" 2>&1
    echo [%date% %time%] DONE exit=!RC! marked success>>"%LOG_FILE%"
) else (
    %PY% -u "%MODULE_ROOT%\schedule_gate.py" --mark-failed "exit_!RC!">>"%LOG_FILE%" 2>&1
    echo [%date% %time%] FAILED exit=!RC! marked failed — will retry next hour>>"%LOG_FILE%"
)

echo [%date% %time%] run complete exit=!RC!>>"%LOG_DAILY%"
%PY% "%MODULE_ROOT%\generate_log_viewer.py" >nul 2>&1
exit /b !RC!
