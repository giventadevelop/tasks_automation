@echo off
setlocal EnableDelayedExpansion
REM ============================================================
REM   YouTube Transcribe — interactive launcher.
REM   Prompts for a URL, runs yt-dlp + faster-whisper in WSL.
REM ============================================================
cd /d "%~dp0"

REM Clear inherited values so an old env can't poison this run
set "URL="
set "WHISPER_MODEL="
set "TRANSLATE="

echo.
echo --- YouTube Transcribe ---
echo.
set "URL_INPUT="
set /p "URL_INPUT=YouTube URL: "
if "%URL_INPUT%"=="" (
    echo No URL given. Aborting.
    pause
    exit /b 1
)
set "URL=%URL_INPUT%"

set "MODEL_INPUT="
set /p "MODEL_INPUT=Whisper model [tiny/base/small/medium/large-v3] (Enter = small): "
if "%MODEL_INPUT%"=="" (
    set "WHISPER_MODEL=small"
) else (
    set "WHISPER_MODEL=%MODEL_INPUT%"
)

set "TRANS_INPUT="
set /p "TRANS_INPUT=Force English translation? Enter=auto (only if non-English), N=skip: "
if /I "%TRANS_INPUT%"=="N" (
    set "TR_FLAG=--no-translate"
) else (
    set "TR_FLAG="
)

echo.
echo ============================================================
echo  URL    = %URL%
echo  Model  = %WHISPER_MODEL%
echo  Trans. = %TR_FLAG% (blank = auto)
echo ============================================================
echo.

REM Build bash command. Single-quote the URL so it survives spaces/&.
set "BASH_CMD=cd '/mnt/c/E_Drive/project_workspace/tasks_automation/YouTube_Transcribe'"
set "BASH_CMD=%BASH_CMD% && WHISPER_MODEL='%WHISPER_MODEL%' ~/venvs/whisper/bin/python transcribe_youtube.py '%URL%' %TR_FLAG%"

echo Launching script...
echo.
wsl.exe -e bash -lc "%BASH_CMD%"
set RC=%ERRORLEVEL%

echo.
if %RC% EQU 0 (
    echo === DONE. Outputs are in: transcripts\
) else (
    echo === FAILED — exit code %RC%. See output above.
    echo If this is the first run, try: setup.bat
)
endlocal
pause
exit /b %RC%
