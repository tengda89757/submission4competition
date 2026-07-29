<#
  train_full.ps1 — Full BC retrain on GPU (defaults per chat guidance: 3000 epochs).
  Logs to pipeline\logs\train_3000.log; installs result as model_epoch_500.pth.
  Usage: powershell -ExecutionPolicy Bypass -File pipeline\train_full.ps1 [-Epochs 3000] [-Dataset <hdf5>]
#>
param(
    [int]$Epochs = 3000,
    [int]$SaveEvery = 150,
    [string]$Dataset = "",
    [string]$Device = "cuda:0",
    [switch]$NoInstall
)
$ErrorActionPreference = "Continue"
$AppDir = Split-Path $PSScriptRoot -Parent
$VenvPy = Join-Path $AppDir ".venv\Scripts\python.exe"
if (-not $Dataset) { $Dataset = Join-Path $PSScriptRoot "collected\factory_sorting_l1_grasp.hdf5" }
$log = Join-Path $PSScriptRoot "logs\train_$Epochs.log"
New-Item -ItemType Directory -Force -Path (Join-Path $PSScriptRoot "logs") | Out-Null

Remove-Item Env:\MUJOCO_GL -ErrorAction SilentlyContinue
$env:PYTHONIOENCODING = "utf-8"
$env:HF_HUB_OFFLINE = "1"

$args2 = @((Join-Path $PSScriptRoot "train_bc.py"), "--dataset", $Dataset, "--epochs", $Epochs, "--save-every", $SaveEvery, "--device", $Device)
if ($NoInstall) { $args2 += "--no-install" }

Write-Host "Training: epochs=$Epochs dataset=$Dataset device=$Device -> $log" -ForegroundColor Cyan
& $VenvPy @args2 2>&1 | Out-File -Encoding utf8 $log
Write-Host "Exit: $LASTEXITCODE (log: $log)"
Get-Content $log -Tail 15
exit $LASTEXITCODE
