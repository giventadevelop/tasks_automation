# Install Windows Task Scheduler job for Thursday WhatsApp volleyball poll.
# Uses schtasks (weekly) + StartWhenAvailable (catches wake at 10-11 AM if 8 AM missed).
param(
    [string]$TaskName = "WhatsApp Volleyball Poll (Thursday)"
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RunBat = Join-Path $ScriptDir "run_whatsapp_poll_scheduled.bat"
$GatePy = Join-Path $ScriptDir "schedule_gate.py"

if (-not (Test-Path $RunBat)) {
    Write-Error "Missing $RunBat"
    exit 1
}

$userId = $env:USERNAME
Write-Host "Installing for user: $userId"
Write-Host "Script: $RunBat"

schtasks /delete /tn $TaskName /f 2>$null | Out-Null

$create = schtasks /create /tn $TaskName /tr $RunBat /sc weekly /d THU /st 08:00 /f 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Error "schtasks failed: $create"
    exit 1
}
Write-Host "[ok] Weekly trigger: Thursday 08:00"

try {
    $settings = New-ScheduledTaskSettingsSet `
        -StartWhenAvailable `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -MultipleInstances IgnoreNew `
        -ExecutionTimeLimit (New-TimeSpan -Minutes 30)
    Set-ScheduledTask -TaskName $TaskName -Settings $settings | Out-Null
    Write-Host "[ok] StartWhenAvailable=ON - if PC wakes at 10-11 AM on Thursday (missed 8 AM), Task Scheduler should run automatically."
    Write-Host "     (You must be logged in; unlock Windows after sleep.)"
} catch {
    Write-Host "[warn] Could not update task settings: $_"
}

try {
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
    $unlockClass = Get-CimClass -Namespace Root/Microsoft/Windows/TaskScheduler -ClassName MSFT_TaskSessionStateChangeTrigger
    $unlock = New-CimInstance -CimClass $unlockClass -ClientOnly -Property @{
        Enabled     = $true
        StateChange = 8
    }
    $newTriggers = @($task.Triggers) + @($unlock)
    Set-ScheduledTask -TaskName $TaskName -Trigger $newTriggers | Out-Null
    Write-Host "[ok] Added session-unlock trigger."
} catch {
    Write-Host "[warn] Unlock trigger not added (StartWhenAvailable still covers most wake-ups)."
}

$info = Get-ScheduledTaskInfo -TaskName $TaskName
Write-Host ""
Write-Host "[ok] Task installed: $TaskName"
Write-Host "  Next scheduled: $($info.NextRunTime)"
Write-Host ('  Test: schtasks /run /tn "' + $TaskName + '"')
Write-Host "  Logs: $(Join-Path $ScriptDir 'logs')"

$runNow = $false
if (Test-Path $GatePy) {
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        & py -3 $GatePy 2>&1 | ForEach-Object { Write-Host $_ }
        if ($LASTEXITCODE -eq 0) { $runNow = $true }
    }
}
if ($runNow) {
    Write-Host ""
    Write-Host "[..] Today qualifies - starting poll now (not waiting for next week)..."
    schtasks /run /tn $TaskName | Out-Null
    Start-Sleep -Seconds 2
    Write-Host "[ok] Triggered. Check Edge and: $(Join-Path $ScriptDir 'logs')"
} else {
    Write-Host ""
    Write-Host "No immediate run (wrong day/time/season or already sent today)."
}

Write-Host ""
Write-Host ('Install via: powershell -NoProfile -ExecutionPolicy Bypass -File "' + $PSCommandPath + '"')
exit 0
