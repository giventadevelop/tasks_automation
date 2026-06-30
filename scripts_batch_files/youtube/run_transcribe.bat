@echo off
setlocal EnableDelayedExpansion
call "%~dp0_env.bat"
REM YouTube Transcribe — interactive launcher (yt-dlp + faster-whisper in WSL).

set "URL="
set "WHISPER_MODEL="
set "TRANSLATE="

for /f "delims=" %%W in ('wsl wslpath -a "%MODULE_ROOT%"') do set "WSL_MODULE=%%W"
if not defined WSL_MODULE (
    echo [FAIL] Could not resolve WSL path for %MODULE_ROOT%
    pause
    exit /b 1
)

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

set "BASH_CMD=cd '!WSL_MODULE!'"
set "BASH_CMD=!BASH_CMD! && WHISPER_MODEL='!WHISPER_MODEL!' ~/venvs/whisper/bin/python transcribe_youtube.py '!URL!' !TR_FLAG!"

echo Launching script...
echo.
wsl.exe -e bash -lc "!BASH_CMD!"
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
