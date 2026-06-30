# Install Windows Task Scheduler jobs for WhatsApp volleyball automation.
# Thursday poll: hourly 08:00-23:00 (retries until success or 11 PM)
# Friday turnout: every 20 min, 15:00-17:00 (3 PM - 5 PM)
param(
    [string]$PollTaskName = "WhatsApp Volleyball Poll (Thursday)",
    [string]$TurnoutTaskName = "WhatsApp Volleyball Turnout (Friday)"
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir "..\..")).Path
$ModuleRoot = Join-Path $RepoRoot "WhatsApp_Web_Poll"
$PollBat = Join-Path $ScriptDir "run_whatsapp_poll_scheduled.bat"
$TurnoutBat = Join-Path $ScriptDir "run_whatsapp_turnout_check_scheduled.bat"
$GatePy = Join-Path $ModuleRoot "schedule_gate.py"

function Set-TaskSettings($Name) {
    try {
        $settings = New-ScheduledTaskSettingsSet `
            -StartWhenAvailable `
            -AllowStartIfOnBatteries `
            -DontStopIfGoingOnBatteries `
            -MultipleInstances Queue `
            -ExecutionTimeLimit (New-TimeSpan -Minutes 45)
        Set-ScheduledTask -TaskName $Name -Settings $settings | Out-Null
        return $true
    } catch {
        Write-Host "[warn] Could not update settings for ${Name}: $_"
        return $false
    }
}

function Set-TaskStopExistingPolicy($Name) {
    $tmp = Join-Path $env:TEMP "tasks_automation_$([guid]::NewGuid().ToString('N')).xml"
    try {
        schtasks /query /tn $Name /xml | Out-File -FilePath $tmp -Encoding Unicode
        $raw = Get-Content $tmp -Raw -Encoding Unicode
        if ($raw -match '<MultipleInstancesPolicy>') {
            $raw = $raw -replace '<MultipleInstancesPolicy>[^<]+</MultipleInstancesPolicy>',
                '<MultipleInstancesPolicy>StopExisting</MultipleInstancesPolicy>'
        } else {
            $raw = $raw -replace '<Settings>',
                "<Settings>`r`n    <MultipleInstancesPolicy>StopExisting</MultipleInstancesPolicy>"
        }
        Set-Content -Path $tmp -Value $raw -Encoding Unicode
        schtasks /delete /tn $Name /f 2>&1 | Out-Null
        $create = schtasks /create /tn $Name /xml $tmp /f 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[warn] StopExisting XML patch failed for ${Name}: $create"
            return $false
        }
        Write-Host "[ok] ${Name}: MultipleInstancesPolicy=StopExisting (hourly retries replace stuck runs)"
        return $true
    } catch {
        Write-Host "[warn] StopExisting policy for ${Name}: $_"
        return $false
    } finally {
        Remove-Item $tmp -ErrorAction SilentlyContinue
    }
}

Write-Host "Installing for user: $env:USERNAME"
Write-Host "Script dir: $ScriptDir"
Write-Host "Module dir: $ModuleRoot"

schtasks /delete /tn $PollTaskName /f 2>&1 | Out-Null
$pollCreate = cmd /c "schtasks /create /tn `"$PollTaskName`" /tr `"$PollBat`" /sc weekly /d THU /st 08:00 /ri 60 /du 15:00 /f" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Error "Thursday poll task failed: $pollCreate"
    exit 1
}
Write-Host "[ok] Thursday poll: weekly, 08:00 + hourly until 23:00 (retries if failed)"
Set-TaskSettings $PollTaskName | Out-Null
Set-TaskStopExistingPolicy $PollTaskName | Out-Null

if (Test-Path $TurnoutBat) {
    foreach ($legacy in @(
        "${TurnoutTaskName} 3PM",
        "${TurnoutTaskName} 4PM",
        "${TurnoutTaskName} 5PM"
    )) {
        try { schtasks /delete /tn $legacy /f 2>&1 | Out-Null } catch { }
    }
    try { schtasks /delete /tn $TurnoutTaskName /f 2>&1 | Out-Null } catch { }

    $turnoutCreate = cmd /c "schtasks /create /tn `"$TurnoutTaskName`" /tr `"$TurnoutBat`" /sc weekly /d FRI /st 15:00 /ri 20 /du 02:00 /f" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[warn] Friday turnout task failed: $turnoutCreate"
    } else {
        Write-Host "[ok] $TurnoutTaskName`: weekly Friday 15:00 + every 20 min until 17:00"
        Set-TaskSettings $TurnoutTaskName | Out-Null
        Set-TaskStopExistingPolicy $TurnoutTaskName | Out-Null
    }
} else {
    Write-Host "[warn] Missing $TurnoutBat — Friday turnout task not installed"
}

$pollInfo = Get-ScheduledTaskInfo -TaskName $PollTaskName
Write-Host ""
Write-Host "[ok] Installed tasks"
Write-Host "  Poll next run:    $($pollInfo.NextRunTime)"
try {
    $tTurnout = Get-ScheduledTaskInfo -TaskName $TurnoutTaskName
    Write-Host "  Turnout next:     $($tTurnout.NextRunTime)"
} catch { }

Write-Host ""
Write-Host "Status files: $env:LOCALAPPDATA\tasks_automation\whatsapp_poll_status.json"
Write-Host "Logs viewer:  $(Join-Path $ScriptDir 'view_logs.bat')"
Write-Host "Test poll:    schtasks /run /tn `"$PollTaskName`""
Write-Host "Test turnout: schtasks /run /tn `"$TurnoutTaskName`""

$runNow = $false
if (Test-Path $GatePy) {
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        Push-Location $ModuleRoot
        try {
            & py -3 $GatePy 2>&1 | ForEach-Object { Write-Host $_ }
            if ($LASTEXITCODE -eq 0) { $runNow = $true }
        } finally {
            Pop-Location
        }
    }
}
if ($runNow) {
    Write-Host ""
    Write-Host "[..] Today qualifies for poll — triggering now..."
    schtasks /run /tn $PollTaskName | Out-Null
}

exit 0
