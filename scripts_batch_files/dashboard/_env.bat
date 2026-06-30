@echo off
if not defined TASKS_AUTOMATION_ROOT (
  for %%I in ("%~dp0..\..\") do set "TASKS_AUTOMATION_ROOT=%%~fI"
)
set "SCRIPTS_ROOT=%~dp0"
cd /d "%TASKS_AUTOMATION_ROOT%"
