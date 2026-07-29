<#
  collect_demos.ps1 — Collect scripted expert grasp demonstrations for the BC policy.

  IMPORTANT: the bundled robosuite/dataset/table_setup_from_dishwasher_sample.hdf5 is
  only a robomimic FORMAT SAMPLE from an unrelated iGibson task — it is NOT training
  data. To retrain the grasp policy you must first collect real FactorySorting demos.
  This wraps load_factory_sorting_1_3fo3erfhisem_collect.py, which scripts a two-arm
  side grasp and saves only SUCCESSFUL episodes as a robomimic HDF5 with exactly the
  obs keys the policy expects (Tiago EEF/gripper + robot0_robotview images).

  The L1 grasp policy is shared across all levels (single model_epoch_*.pth), so
  L1 demos are what you retrain on.

  Usage:
    powershell -ExecutionPolicy Bypass -File pipeline\collect_demos.ps1 -NumRollouts 50
    powershell -ExecutionPolicy Bypass -File pipeline\collect_demos.ps1 -NumRollouts 2 -Render   # visual debug
#>
param(
    [int]$NumRollouts = 50,
    [string]$Output = "",
    [switch]$Render,
    [int]$Seed = 0
)

$ErrorActionPreference = "Continue"
$AppDir = Split-Path $PSScriptRoot -Parent
$VenvPy = Join-Path $AppDir ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPy)) { Write-Host "venv missing — run pipeline\setup_env.ps1 first" -ForegroundColor Red; exit 1 }

$collectDir = Join-Path $PSScriptRoot "collected"
$rawDir = Join-Path $collectDir "raw"
New-Item -ItemType Directory -Force -Path $rawDir | Out-Null
if (-not $Output) { $Output = Join-Path $collectDir "factory_sorting_l1_grasp.hdf5" }

$script = Join-Path $AppDir "robosuite\robosuite\environments\factory_sorting\load_factory_sorting_1_3fo3erfhisem_collect.py"
Remove-Item Env:\MUJOCO_GL -ErrorAction SilentlyContinue      # Windows default (wgl); egl is Linux-only
$env:PYTHONPATH = @((Join-Path $AppDir "src"), $AppDir, (Join-Path $AppDir "robomimic"), (Join-Path $AppDir "robosuite\robosuite")) -join ";"
$env:PYTHONIOENCODING = "utf-8"

$collectArgs = @("--num-rollouts", $NumRollouts, "--directory", $rawDir, "--output-name", "l1_grasp")
if ($Seed) { $collectArgs += @("--seed", $Seed) }
if (-not $Render) { $collectArgs += "--no-render" }

Write-Host "Collecting $NumRollouts scripted L1 grasp rollouts (render=$($Render.IsPresent)) ..." -ForegroundColor Cyan
& $VenvPy $script @collectArgs
$code = $LASTEXITCODE

$newest = Get-ChildItem $rawDir -Recurse -Filter "l1_grasp_*.hdf5" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime | Select-Object -Last 1
if ($newest) {
    Copy-Item $newest.FullName $Output -Force
    Write-Host "`nCollected dataset: $($newest.FullName)" -ForegroundColor Green
    Write-Host "Installed as     : $Output" -ForegroundColor Green
    Write-Host "Next: .venv\Scripts\python pipeline\train_bc.py --dataset `"$Output`" --epochs 3000" -ForegroundColor Cyan
} else {
    Write-Host "No HDF5 produced. Check output above (grasp may have failed for all rollouts)." -ForegroundColor Yellow
}
exit $code
