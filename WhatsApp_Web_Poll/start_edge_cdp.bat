@echo off
setlocal EnableDelayedExpansion
REM Starts Microsoft Edge with CDP on port 9222 IF it isn't already running.
REM Uses C:\edge-cdp as the dedicated profile (sign in to WhatsApp Web once there).
REM Works from any project folder — no hardcoded paths.

set "CDP_PORT=9222"
set "CDP_URL=http://localhost:%CDP_PORT%/json/version"

curl.exe -fs --max-time 2 "%CDP_URL%" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    for /f "delims=" %%B in ('curl.exe -fs --max-time 2 "%CDP_URL%" 2^>nul') do set "CDP_JSON=%%B"
    echo [ok] Browser CDP already running on port %CDP_PORT%.
    echo !CDP_JSON! | findstr /i "Edg" >nul && (
        echo       ^(Microsoft Edge^)
    ) || (
        echo !CDP_JSON! | findstr /i "Chrome" >nul && (
            echo [warn] Port %CDP_PORT% is used by Chrome, not Edge.
            echo       Close Chrome completely, then run this script again.
        ) || (
            echo       ^(browser type unknown — check Task Manager^)
        )
    )
    exit /b 0
)

set "EDGE_EXE="
if exist "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" (
    set "EDGE_EXE=%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"
) else if exist "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" (
    set "EDGE_EXE=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"
)

if not defined EDGE_EXE (
    echo [FAIL] Microsoft Edge not found in Program Files.
    echo        Install Edge or use start_chrome_cdp.bat instead.
    exit /b 1
)

echo [..] Starting Edge with CDP on port %CDP_PORT%...
echo       Profile: C:\edge-cdp  ^(one-time WhatsApp Web login there^)
start "" "%EDGE_EXE%" ^
    --remote-debugging-port=%CDP_PORT% ^
    --remote-allow-origins=* ^
    --user-data-dir=C:\edge-cdp ^
    --no-first-run ^
    --no-default-browser-check ^
    "https://web.whatsapp.com/"

set /a tries=0
:waitloop
timeout /t 1 /nobreak >nul
curl.exe -fs --max-time 2 "%CDP_URL%" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [ok] Edge CDP is up.
    REM Brief warmup so web.whatsapp.com can start loading before automation attaches.
    timeout /t 5 /nobreak >nul
    exit /b 0
)
set /a tries+=1
if %tries% LSS 20 goto waitloop

echo [FAIL] Edge did not expose CDP on port %CDP_PORT% within 20s.
echo.
echo Common fixes:
echo   1. Close ALL Edge windows ^(Task Manager -^> end every msedge.exe^).
echo   2. Re-run this script — Edge must start WITH --remote-debugging-port.
echo   3. If Chrome is using port 9222, quit Chrome or change CDP_PORT in both scripts.
exit /b 1
