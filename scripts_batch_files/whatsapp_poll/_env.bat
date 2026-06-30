@echo off
REM WhatsApp module paths — call from any bat in this folder (do not call standalone).
if not defined TASKS_AUTOMATION_ROOT (
  for %%I in ("%~dp0..\..\") do set "TASKS_AUTOMATION_ROOT=%%~fI"
)
set "MODULE_ROOT=%TASKS_AUTOMATION_ROOT%\WhatsApp_Web_Poll"
set "SCRIPTS_ROOT=%~dp0"
cd /d "%MODULE_ROOT%"
