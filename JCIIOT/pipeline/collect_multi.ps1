<#
  collect_multi.ps1 — background-friendly wrapper for collect_demos_multi.py.
  Usage:
    powershell -ExecutionPolicy Bypass -File pipeline\collect_multi.ps1 -Level L3 -Object blue_tote_b01_near_left -NumRollouts 20
#>
param(
    [ValidateSet("L1","L2","L3","L4","L5")][string]$Level = "L1",
    [string]$Object = "",
    [int]$NumRollouts = 20,
    [double]$Dist = 0.0,
    [double]$ShiftX = 0.0,
    [double]$ShiftY = 0.0,
    [double]$ArrivalTol = 0.0,
    [string]$Log = ""
)
$ErrorActionPreference = "Continue"
$AppDir = Split-Path $PSScriptRoot -Parent
$VenvPy = Join-Path $AppDir ".venv\Scripts\python.exe"
Set-Location $AppDir
Remove-Item Env:\MUJOCO_GL -ErrorAction SilentlyContinue
$env:PYTHONIOENCODING = "utf-8"
if (-not $Log) { $Log = Join-Path $PSScriptRoot ("logs\collect_" + $Level.ToLower() + ".log") }

$a = @((Join-Path $PSScriptRoot "collect_demos_multi.py"), "--level", $Level, "--num-rollouts", $NumRollouts)
if ($Object) { $a += @("--object", $Object) }
if ($Dist -gt 0) { $a += @("--dist", $Dist) }
if ($ShiftX -ne 0) { $a += @("--shift-x", $ShiftX) }
if ($ShiftY -ne 0) { $a += @("--shift-y", $ShiftY) }
if ($ArrivalTol -gt 0) { $a += @("--arrival-tol", $ArrivalTol) }

Write-Host "collect_multi: level=$Level object=$Object rollouts=$NumRollouts -> $Log" -ForegroundColor Cyan
& $VenvPy @a 2>&1 | Out-File -Encoding utf8 $Log
Write-Host "Exit: $LASTEXITCODE"
Select-String -Path $Log -Pattern 'Attempts:|HDF5 saved' | ForEach-Object { $_.Line }
exit $LASTEXITCODE
