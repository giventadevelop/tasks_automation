# Create Desktop shortcut to launch_daily_tasks_dashboard.bat (sets TASKS_AUTOMATION_ROOT).
param(
    [string]$ShortcutName = "Daily Tasks Automation",
    [string]$ShortcutPath = ""
)

$ErrorActionPreference = "Stop"
$DocDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $DocDir "..")).Path
$Launcher = Join-Path $DocDir "launch_daily_tasks_dashboard.bat"

if (-not (Test-Path $Launcher)) {
    Write-Error "Missing launcher: $Launcher"
}

if (-not $ShortcutPath) {
    $desktop = [Environment]::GetFolderPath("Desktop")
    $ShortcutPath = Join-Path $desktop "$ShortcutName.lnk"
}

$wsh = New-Object -ComObject WScript.Shell
$sc = $wsh.CreateShortcut($ShortcutPath)
$sc.TargetPath = $Launcher
$sc.WorkingDirectory = $DocDir
$sc.Description = "Daily Tasks Automation dashboard (repo root via TASKS_AUTOMATION_ROOT)"
$sc.Save()

Write-Host "[ok] Shortcut created:"
Write-Host "     $ShortcutPath"
Write-Host "     Target: $Launcher"
Write-Host "     TASKS_AUTOMATION_ROOT will be: $RepoRoot"
