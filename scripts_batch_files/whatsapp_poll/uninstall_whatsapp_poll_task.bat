@echo off
setlocal
set "TASK_POLL=WhatsApp Volleyball Poll (Thursday)"
set "TASK_TURNOUT_3=WhatsApp Volleyball Turnout (Friday) 3PM"
set "TASK_TURNOUT_4=WhatsApp Volleyball Turnout (Friday) 4PM"
set "TASK_TURNOUT_5=WhatsApp Volleyball Turnout (Friday) 5PM"
for %%T in ("%TASK_POLL%" "%TASK_TURNOUT_3%" "%TASK_TURNOUT_4%" "%TASK_TURNOUT_5%" "WhatsApp Volleyball Poll (Thursday logon)" "WhatsApp Volleyball Turnout (Friday)") do (
    schtasks /query /tn %%~T >nul 2>&1
    if not errorlevel 1 (
        schtasks /delete /tn %%~T /f
        echo Removed: %%~T
    )
)
if not defined TASK_NAME_ONLY pause
