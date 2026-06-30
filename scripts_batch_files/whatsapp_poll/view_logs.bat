@echo off
setlocal
call "%~dp0_env.bat"

set "PY="
where py >nul 2>&1 && set "PY=py -3"
if not defined PY where python >nul 2>&1 && set "PY=python"
if not defined PY (
    echo Python not found.
    pause
    exit /b 1
)

%PY% "%MODULE_ROOT%\log_rotate.py"
%PY% "%MODULE_ROOT%\generate_log_viewer.py"
if errorlevel 1 (
    echo Failed to build log viewer.
    pause
    exit /b 1
)

set "INDEX=%MODULE_ROOT%\logs\index.html"
if exist "%INDEX%" (
    start "" "%INDEX%"
    echo Opened %INDEX%
) else (
    echo No index.html generated.
)
exit /b 0
