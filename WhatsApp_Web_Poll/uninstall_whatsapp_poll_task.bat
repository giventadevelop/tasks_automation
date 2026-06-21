@echo off
setlocal
set "TASK_NAME=WhatsApp Volleyball Poll (Thursday)"
schtasks /query /tn "%TASK_NAME%" >nul 2>&1
if not errorlevel 1 (
    schtasks /delete /tn "%TASK_NAME%" /f
    echo Removed: %TASK_NAME%
)
schtasks /query /tn "WhatsApp Volleyball Poll (Thursday logon)" >nul 2>&1
if not errorlevel 1 (
    schtasks /delete /tn "WhatsApp Volleyball Poll (Thursday logon)" /f
    echo Removed: WhatsApp Volleyball Poll (Thursday logon)
)
if not defined TASK_NAME_ONLY pause
