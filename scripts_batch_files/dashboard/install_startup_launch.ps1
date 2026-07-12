# Install or remove a Startup-folder shortcut for Daily Tasks Automation.
param(
    [switch]$Remove,
    [string]$ShortcutName = "Daily Tasks Automation"
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir "..\..")).Path
# Prefer production launcher (exe when built); falls back to Python inside that bat.
$Launcher = Join-Path $ScriptDir "launch_daily_tasks_dashboard.bat"

if (-not (Test-Path $Launcher)) {
    Write-Error "Missing launcher: $Launcher"
}

$startup = [Environment]::GetFolderPath("Startup")
$ShortcutPath = Join-Path $startup "$ShortcutName.lnk"

if ($Remove) {
    if (Test-Path $ShortcutPath) {
        Remove-Item -LiteralPath $ShortcutPath -Force
        Write-Host "[ok] Removed startup shortcut:"
        Write-Host "     $ShortcutPath"
    } else {
        Write-Host "[ok] No startup shortcut found at:"
        Write-Host "     $ShortcutPath"
    }
    exit 0
}

if (-not (Test-Path $Launcher)) {
    Write-Error "Missing launcher: $Launcher"
}

$wsh = New-Object -ComObject WScript.Shell
$sc = $wsh.CreateShortcut($ShortcutPath)
$sc.TargetPath = $Launcher
$sc.WorkingDirectory = $ScriptDir
$sc.Description = "Launch Daily Tasks Automation on Windows logon (TASKS_AUTOMATION_ROOT via launcher)"
$sc.Save()

Write-Host "[ok] Startup shortcut created:"
Write-Host "     $ShortcutPath"
Write-Host "     Target: $Launcher"
Write-Host "     Repo:   $RepoRoot"
Write-Host ""
Write-Host "The dashboard will open when you sign in to Windows."
Write-Host "To remove later, run: uninstall_startup_launch.bat"
