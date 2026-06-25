# Install Windows Task Scheduler jobs for WhatsApp volleyball automation.
# Thursday poll: hourly 08:00-23:00 (retries until success or 11 PM)
# Friday turnout: 15:00 and 16:00 (3 PM + 4 PM retry)
param(
    [string]$PollTaskName = "WhatsApp Volleyball Poll (Thursday)",
    [string]$TurnoutTaskName = "WhatsApp Volleyball Turnout (Friday)"
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PollBat = Join-Path $ScriptDir "run_whatsapp_poll_scheduled.bat"
$TurnoutBat = Join-Path $ScriptDir "run_whatsapp_turnout_check_scheduled.bat"
$GatePy = Join-Path $ScriptDir "schedule_gate.py"

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
    # PowerShell ScheduledTask cmdlets lack StopExisting; patch via task XML.
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

# ---- Thursday poll (hourly 8 AM - 11 PM) ----
schtasks /delete /tn $PollTaskName /f 2>&1 | Out-Null
$pollCreate = cmd /c "schtasks /create /tn `"$PollTaskName`" /tr `"$PollBat`" /sc weekly /d THU /st 08:00 /ri 60 /du 15:00 /f" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Error "Thursday poll task failed: $pollCreate"
    exit 1
}
Write-Host "[ok] Thursday poll: weekly, 08:00 + hourly until 23:00 (retries if failed)"
Set-TaskSettings $PollTaskName | Out-Null
Set-TaskStopExistingPolicy $PollTaskName | Out-Null

# ---- Friday turnout (3 PM + 4 PM retry) ----
if (Test-Path $TurnoutBat) {
    $turnoutSlots = @(
        @{ Name = "${TurnoutTaskName} 3PM"; Time = "15:00" },
        @{ Name = "${TurnoutTaskName} 4PM"; Time = "16:00" }
    )
    foreach ($slot in $turnoutSlots) {
        try { schtasks /delete /tn $slot.Name /f 2>&1 | Out-Null } catch { }
        $turnoutCreate = cmd /c "schtasks /create /tn `"$($slot.Name)`" /tr `"$TurnoutBat`" /sc weekly /d FRI /st $($slot.Time) /f" 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[warn] $($slot.Name) failed: $turnoutCreate"
        } else {
            Write-Host "[ok] $($slot.Name): weekly Friday $($slot.Time)"
            Set-TaskSettings $slot.Name | Out-Null
        }
    }
} else {
    Write-Host "[warn] Missing $TurnoutBat — Friday turnout task not installed"
}

$pollInfo = Get-ScheduledTaskInfo -TaskName $PollTaskName
Write-Host ""
Write-Host "[ok] Installed tasks"
Write-Host "  Poll next run:    $($pollInfo.NextRunTime)"
try {
    $t3 = Get-ScheduledTaskInfo -TaskName "${TurnoutTaskName} 3PM"
    Write-Host "  Turnout 3PM next: $($t3.NextRunTime)"
    $t4 = Get-ScheduledTaskInfo -TaskName "${TurnoutTaskName} 4PM"
    Write-Host "  Turnout 4PM next: $($t4.NextRunTime)"
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
        & py -3 $GatePy 2>&1 | ForEach-Object { Write-Host $_ }
        if ($LASTEXITCODE -eq 0) { $runNow = $true }
    }
}
if ($runNow) {
    Write-Host ""
    Write-Host "[..] Today qualifies for poll — triggering now..."
    schtasks /run /tn $PollTaskName | Out-Null
}

exit 0
