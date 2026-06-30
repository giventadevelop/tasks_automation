@echo off
setlocal EnableDelayedExpansion
call "%~dp0_env.bat"
REM Manual cleanup: delete transcripts older than N days (default 20).

for /f "delims=" %%W in ('wsl wslpath -a "%MODULE_ROOT%"') do set "WSL_MODULE=%%W"
if not defined WSL_MODULE (
    echo [FAIL] Could not resolve WSL path for %MODULE_ROOT%
    pause
    exit /b 1
)

set "DAYS_INPUT="
set /p "DAYS_INPUT=Delete files older than how many days? [Enter = 20]: "
if "%DAYS_INPUT%"=="" set "DAYS_INPUT=20"

echo.
echo Pruning transcripts/ older than %DAYS_INPUT% days...
echo.
wsl.exe -e bash -lc "cd '!WSL_MODULE!' && ~/venvs/whisper/bin/python transcribe_youtube.py --prune-days %DAYS_INPUT%"
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
