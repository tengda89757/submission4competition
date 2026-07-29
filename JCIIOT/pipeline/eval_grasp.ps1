<#
  eval_grasp.ps1 — Run the BC grasp policy in one FactorySorting scene (headless CLI
  equivalent of the dashboard's "Test Grasp" button).

  Reads per-level parameters (scene, object, grasp pose) from knowledge/task_config.json,
  so it always matches the baseline contract. Use it to sanity-check a checkpoint
  BEFORE running a full task or retraining.

  Usage:
    powershell -ExecutionPolicy Bypass -File pipeline\eval_grasp.ps1 -Level L1
    powershell -ExecutionPolicy Bypass -File pipeline\eval_grasp.ps1 -Level L3 -Device cuda -Renderer mjviewer
    powershell -ExecutionPolicy Bypass -File pipeline\eval_grasp.ps1 -Level L1 -Checkpoint robosuite\robosuite\model_epoch_500.pth
#>
param(
    [ValidateSet("L1","L2","L3","L4","L5")][string]$Level = "L1",
    [string]$Checkpoint = "",
    [string]$Device = "cpu",
    [string]$Renderer = "mjviewer",
    [int]$EvalSteps = 360,
    [string[]]$Extra = @()
)

$ErrorActionPreference = "Continue"
$AppDir = Split-Path $PSScriptRoot -Parent
$VenvPy = Join-Path $AppDir ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPy)) { Write-Host "venv missing — run pipeline\setup_env.ps1 first" -ForegroundColor Red; exit 1 }

# ── resolve per-level params from task_config.json ──
$cfg = Get-Content (Join-Path $AppDir "knowledge\task_config.json") -Raw | ConvertFrom-Json
$task = $cfg.tasks | Where-Object { $_.level -eq $Level }
if (-not $task) { Write-Host "Unknown level $Level" -ForegroundColor Red; exit 1 }
$envName = $task.env_name
$object  = $task.object
$source  = $task.source
$pose    = $cfg.grasp_poses.$source
$bx = $pose.pos[0]; $by = $pose.pos[1]; $yaw = $pose.yaw

# ── resolve checkpoint (prefer retrained 500, fall back to official 150) ──
if (-not $Checkpoint) {
    $c500 = Join-Path $AppDir "robosuite\robosuite\model_epoch_500.pth"
    $c150 = Join-Path $AppDir "robosuite\robosuite\model_epoch_150.pth"
    $Checkpoint = if (Test-Path $c500) { $c500 } else { $c150 }
}
if (-not (Test-Path $Checkpoint)) {
    Write-Host "Checkpoint not found: $Checkpoint`nRun pipeline\fetch_assets.ps1 -Only pth" -ForegroundColor Red; exit 1
}

$script = Join-Path $AppDir "robosuite\robosuite\environments\factory_sorting\load_factory_sorting_evalization.py"
$env:PYTHONPATH = @(
    (Join-Path $AppDir "src"), $AppDir,
    (Join-Path $AppDir "robomimic"), (Join-Path $AppDir "robosuite\robosuite")
) -join ";"
$env:PYTHONIOENCODING = "utf-8"

Write-Host "Level=$Level  scene=$envName  object=$object  pose=($bx,$by,$yaw)  ckpt=$(Split-Path $Checkpoint -Leaf)  device=$Device" -ForegroundColor Cyan

& $VenvPy $script `
    --checkpoint $Checkpoint `
    --factory-scene $envName `
    --object-name $object `
    --robot-base-pos $bx $by 0.0 `
    --robot-base-ori 0.0 0.0 $yaw `
    --renderer $Renderer `
    --device $Device `
    --eval-steps $EvalSteps `
    --debug-policy --debug-every 25 @Extra

exit $LASTEXITCODE
