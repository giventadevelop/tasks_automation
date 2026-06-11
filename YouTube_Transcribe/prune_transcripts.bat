@echo off
setlocal
REM ============================================================
REM   Manual cleanup: delete transcripts older than 20 days.
REM   Same script the Hermes weekly cron uses, just runnable on demand.
REM ============================================================
cd /d "%~dp0"

set "DAYS_INPUT="
set /p "DAYS_INPUT=Delete files older than how many days? [Enter = 20]: "
if "%DAYS_INPUT%"=="" set "DAYS_INPUT=20"

echo.
echo Pruning transcripts/ older than %DAYS_INPUT% days...
echo.
wsl.exe -e bash -lc "cd '/mnt/c/E_Drive/project_workspace/tasks_automation/YouTube_Transcribe' && ~/venvs/whisper/bin/python transcribe_youtube.py --prune-days %DAYS_INPUT%"
set RC=%ERRORLEVEL%

echo.
if %RC% EQU 0 (
    echo === DONE.
) else (
    echo === FAILED — exit code %RC%.
)
endlocal
pause
exit /b %RC%
