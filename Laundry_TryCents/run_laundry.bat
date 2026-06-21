@echo off
setlocal EnableDelayedExpansion
REM ============================================================
REM  Laundry TryCents order — CDP via Microsoft Edge (Windows-native).
REM  Double-click this file.
REM ============================================================
cd /d "%~dp0"

call "%~dp0start_edge_cdp.bat"
if errorlevel 1 (
    echo Could not start Edge CDP. Aborting.
    pause
    exit /b 1
)

set "PY="
where py >nul 2>&1 && set "PY=py -3"
if not defined PY where python >nul 2>&1 && set "PY=python"
if not defined PY (
    echo [FAIL] Python not found. Install Python 3 from https://python.org and retry.
    pause
    exit /b 1
)

%PY% -c "import websocket" >nul 2>&1
if errorlevel 1 (
    echo Installing websocket-client...
    %PY% -m pip install -q websocket-client
    if errorlevel 1 (
        echo [FAIL] Could not install websocket-client.
        pause
        exit /b 1
    )
)

echo.
echo Running laundry order flow via Edge CDP...
echo (Uses Edge + CDP directly — NOT browser-use / Selenium)
echo.
%PY% "%~dp0_cdp_driver.py"
set RC=%ERRORLEVEL%

echo.
if %RC% EQU 0 (
    echo === DONE — order flow finished. Review the Edge tab and click Submit. ===
) else (
    echo === FAILED — exit code %RC%. Review the Edge tab to see where it stopped. ===
)
pause
exit /b %RC%
