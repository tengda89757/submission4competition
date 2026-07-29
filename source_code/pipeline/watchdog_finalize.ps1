<#
  watchdog_finalize.ps1 — Wait for retrain_all.ps1 to finish, then auto-run
  finalize_all.ps1 (all levels end-to-end + scoring + submission packaging).
  Run detached; log: pipeline\logs\watchdog.log
#>
param([int]$PollSeconds = 300, [int]$MaxHours = 12)
$ErrorActionPreference = "Continue"
$AppDir = Split-Path $PSScriptRoot -Parent
$log = Join-Path $PSScriptRoot "logs\watchdog.log"
$retrainLog = Join-Path $PSScriptRoot "logs\retrain_all.log"
function Log($m) { Add-Content -Path $log -Value ("[{0}] {1}" -f (Get-Date -Format "MM-dd HH:mm:ss"), $m) }

Log "watchdog start (poll=${PollSeconds}s, max=${MaxHours}h)"
$deadline = (Get-Date).AddHours($MaxHours)
while ((Get-Date) -lt $deadline) {
    if (Select-String -Path $retrainLog -Pattern '=== retrain_all done ===' -Quiet -ErrorAction SilentlyContinue) {
        Log "retrain_all done detected -> launching finalize_all"
        & powershell.exe -ExecutionPolicy Bypass -NoProfile -File (Join-Path $PSScriptRoot "finalize_all.ps1") 2>&1 |
            Add-Content (Join-Path $PSScriptRoot "logs\finalize_console.log")
        Log "finalize_all exit=$LASTEXITCODE"
        exit 0
    }
    Start-Sleep -Seconds $PollSeconds
}
Log "watchdog TIMEOUT — retrain_all never finished"
exit 1
