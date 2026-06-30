@echo off
if not defined TASKS_AUTOMATION_ROOT (
  for %%I in ("%~dp0..\..\") do set "TASKS_AUTOMATION_ROOT=%%~fI"
)
set "MODULE_ROOT=%TASKS_AUTOMATION_ROOT%\Laundry_TryCents"
set "SCRIPTS_ROOT=%~dp0"
cd /d "%MODULE_ROOT%"
