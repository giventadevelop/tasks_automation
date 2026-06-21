@echo off
setlocal EnableDelayedExpansion
REM Scheduled Friday turnout check (no prompts). Reads poll; cancels if Yes < MIN_PLAYERS.
cd /d "%~dp0"

set "LOG_DIR=%~dp0logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd"') do set "LOG_DAY=%%I"
set "LOG_FILE=%LOG_DIR%\whatsapp_turnout_%LOG_DAY%.log"

echo.>>"%LOG_FILE%"
echo ============================================================>>"%LOG_FILE%"
echo [%date% %time%] turnout check started>>"%LOG_FILE%"

set "PY="
where py >nul 2>&1 && set "PY=py -3"
if not defined PY where python >nul 2>&1 && set "PY=python"
if not defined PY (
    echo [%date% %time%] FAIL: Python not found>>"%LOG_FILE%"
    exit /b 1
)

%PY% "%~dp0schedule_gate_turnout.py" >>"%LOG_FILE%" 2>&1
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
set "ACTION=check_turnout"
set "MIN_PLAYERS=6"
set "PYTHONIOENCODING=utf-8"
set "SCHEDULED=1"

echo [%date% %time%] launching turnout check contact=%CONTACT% min_yes=%MIN_PLAYERS%>>"%LOG_FILE%"
%PY% "%~dp0whatsapp_poll.py" >>"%LOG_FILE%" 2>&1
set RC=%ERRORLEVEL%

if %RC% EQU 0 (
    %PY% "%~dp0schedule_gate_turnout.py" --mark >>"%LOG_FILE%" 2>&1
    echo [%date% %time%] DONE exit=%RC%>>"%LOG_FILE%"
) else (
    echo [%date% %time%] FAILED exit=%RC% — not marking as ran>>"%LOG_FILE%"
)

exit /b %RC%
