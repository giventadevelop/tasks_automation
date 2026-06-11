@echo off
setlocal
REM ============================================================
REM   One-time setup for YouTube_Transcribe.
REM   Creates ~/venvs/whisper inside WSL with faster-whisper installed.
REM   Safe to run multiple times — it's idempotent.
REM ============================================================
echo Ensuring WSL venv ~/venvs/whisper has faster-whisper...
wsl.exe -e bash -lc "set -e; \
  if [ ! -x ~/venvs/whisper/bin/python ]; then \
    echo '[setup] creating venv ~/venvs/whisper'; \
    python3 -m venv ~/venvs/whisper; \
  fi; \
  if ! ~/venvs/whisper/bin/python -c 'import faster_whisper' 2>/dev/null; then \
    echo '[setup] installing faster-whisper (this may take 1-2 min)'; \
    ~/venvs/whisper/bin/pip install -q faster-whisper; \
  fi; \
  if ! ~/venvs/whisper/bin/python -c 'import sumy, nltk' 2>/dev/null; then \
    echo '[setup] installing sumy + nltk (for 7-sentence auto-summary)'; \
    ~/venvs/whisper/bin/pip install -q sumy; \
    ~/venvs/whisper/bin/python -c 'import nltk; nltk.download(\"punkt_tab\", quiet=True); nltk.download(\"punkt\", quiet=True)'; \
  fi; \
  echo '[setup] faster-whisper OK:'; \
  ~/venvs/whisper/bin/python -c 'import faster_whisper, sys; print(\"  faster_whisper\", faster_whisper.__version__, \"on\", sys.version.split()[0])'; \
  if ! command -v ffmpeg >/dev/null; then \
    echo '[setup] WARNING: ffmpeg not found in WSL. Install with: sudo apt install -y ffmpeg'; \
  else \
    echo '[setup] ffmpeg: '$(ffmpeg -version 2>/dev/null | head -1); \
  fi; \
  if [ ! -x ~/.local/share/pipx/venvs/yt-dlp/bin/yt-dlp ]; then \
    echo '[setup] WARNING: yt-dlp not found at ~/.local/share/pipx/venvs/yt-dlp/'; \
    echo '[setup] install with: pipx install yt-dlp'; \
  else \
    echo '[setup] yt-dlp: '$(~/.local/share/pipx/venvs/yt-dlp/bin/yt-dlp --version); \
  fi"
set RC=%ERRORLEVEL%
if %RC% NEQ 0 (
  echo === Setup FAILED — exit code %RC%.
) else (
  echo === Setup OK.
)
endlocal
pause
exit /b %RC%
