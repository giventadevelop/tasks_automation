@echo off
REM Starts Chrome with CDP on port 9222 IF it isn't already running.
REM Uses your cloned profile at C:\chrome-cdp so you stay logged in to TryCents.

REM curl ships with Windows 10/11. -f makes it return non-zero on HTTP errors,
REM -s silent, --max-time 2 caps the check at 2 seconds.
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

REM wait up to 15s for CDP to come up
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
echo        If Chrome opened but CDP isn't listening, fully quit Chrome
echo        ^(Task Manager -^> end all chrome.exe^) and re-run.
exit /b 1
