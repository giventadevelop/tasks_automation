@echo off
setlocal EnableDelayedExpansion
REM Non-interactive scheduled runner (Task Scheduler / wake / unlock).
REM No prompts: CONTACT=Volleyball Friday, SEND=1 always.
cd /d "%~dp0"

set "LOG_DIR=%~dp0logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd"') do set "LOG_DAY=%%I"
set "LOG_FILE=%LOG_DIR%\whatsapp_poll_%LOG_DAY%.log"

echo.>>"%LOG_FILE%"
echo ============================================================>>"%LOG_FILE%"
echo [%date% %time%] scheduled run started>>"%LOG_FILE%"

set "PY="
where py >nul 2>&1 && set "PY=py -3"
if not defined PY where python >nul 2>&1 && set "PY=python"
if not defined PY (
    echo [%date% %time%] FAIL: Python not found>>"%LOG_FILE%"
    exit /b 1
)

%PY% "%~dp0schedule_gate.py" >>"%LOG_FILE%" 2>&1
if errorlevel 1 (
    echo [%date% %time%] schedule gate: skip>>"%LOG_FILE%"
    exit /b 0
)

echo [%date% %time%] schedule gate: proceed>>"%LOG_FILE%"

call "%~dp0start_edge_cdp.bat" >>"%LOG_FILE%" 2>&1
if errorlevel 1 (
    echo [%date% %time%] FAIL: Edge CDP>>"%LOG_FILE%"
    exit /b 1
)

%PY% -c "import websocket" >nul 2>&1
if errorlevel 1 (
    %PY% -m pip install -q -r "%~dp0requirements.txt" >>"%LOG_FILE%" 2>&1
)

set "CONTACT=Volleyball Friday"
set "SEND=1"
set "POLL_TITLE="
set "SCHEDULED=1"
set "PYTHONIOENCODING=utf-8"

echo [%date% %time%] launching whatsapp_poll.py (scheduled, no prompts) contact=%CONTACT% send=1>>"%LOG_FILE%"
%PY% "%~dp0whatsapp_poll.py" >>"%LOG_FILE%" 2>&1
set RC=%ERRORLEVEL%

if %RC% EQU 0 (
    %PY% "%~dp0schedule_gate.py" --mark >>"%LOG_FILE%" 2>&1
    echo [%date% %time%] DONE exit=%RC%>>"%LOG_FILE%"
) else (
    echo [%date% %time%] FAILED exit=%RC% — not marking as ran>>"%LOG_FILE%"
)

exit /b %RC%
