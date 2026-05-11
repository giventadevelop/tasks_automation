@echo off
REM Starts Chrome on Windows with CDP on port 9222 IF it isn't already running.
REM Uses C:\chrome-cdp as the dedicated profile (must be already signed-in to WhatsApp Web).

curl.exe -fs --max-time 2 http://localhost:9222/json/version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [ok] Chrome CDP already running on port 9222.
    exit /b 0
)

echo [..] Starting Chrome with CDP on port 9222...
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" ^
    --remote-debugging-port=9222 ^
    --remote-allow-origins=* ^
    --user-data-dir=C:\chrome-cdp ^
    --no-first-run ^
    --no-default-browser-check

set /a tries=0
:waitloop
timeout /t 1 /nobreak >nul
curl.exe -fs --max-time 1 http://localhost:9222/json/version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [ok] Chrome CDP is up.
    exit /b 0
)
set /a tries+=1
if %tries% LSS 15 goto waitloop

echo [FAIL] Chrome did not expose CDP on port 9222 within 15s.
echo        Fully quit Chrome ^(Task Manager -^> end all chrome.exe^) and re-run.
exit /b 1
