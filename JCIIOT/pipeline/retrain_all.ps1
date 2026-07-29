<#
  retrain_all.ps1 — One-shot: re-collect (markers hidden) → merge → retrain 3000 → matrix eval.
  Designed to run detached (Start-Process) so terminal recycling can't kill it.
  Log: pipeline\logs\retrain_all.log
#>
param([int]$Epochs = 3000, [switch]$SkipCollect)
$ErrorActionPreference = "Continue"
$AppDir = Split-Path $PSScriptRoot -Parent
$VenvPy = Join-Path $AppDir ".venv\Scripts\python.exe"
Set-Location $AppDir
Remove-Item Env:\MUJOCO_GL -ErrorAction SilentlyContinue
$env:PYTHONIOENCODING = "utf-8"
$env:HF_HUB_OFFLINE = "1"
$log = Join-Path $PSScriptRoot "logs\retrain_all.log"
function Log($m) { $line = "[{0}] {1}" -f (Get-Date -Format "MM-dd HH:mm:ss"), $m; Add-Content -Path $log -Value $line }

Log "=== retrain_all start (markers hidden) ==="

# 1) re-collect demos with markers HIDDEN
if (-not $SkipCollect) {
& $VenvPy pipeline\collect_demos_multi.py --level L1 --num-rollouts 50 2>&1 | Out-File -Encoding utf8 pipeline\logs\recollect_l1.log
Log "L1 collect exit=$LASTEXITCODE"
& $VenvPy pipeline\collect_demos_multi.py --level L3 --object blue_tote_b01_near_left --num-rollouts 20 2>&1 | Out-File -Encoding utf8 pipeline\logs\recollect_l3.log
Log "L3 collect exit=$LASTEXITCODE"
& $VenvPy pipeline\collect_demos_multi.py --level L4 --num-rollouts 20 2>&1 | Out-File -Encoding utf8 pipeline\logs\recollect_l4.log
Log "L4 collect exit=$LASTEXITCODE"
}

# 2) merge newest per-level files (incl. white-tote side-table demos for L5 transfer)
# NOTE: today's L1 recollect is named l1_line_5_container_h01_near_*.hdf5 (new tag scheme);
# match l1_* so the marker-free set wins over yesterday's l1_grasp_* files.
$l1 = Get-ChildItem pipeline\collected\raw -Recurse -Filter "l1_*.hdf5"         | Sort-Object LastWriteTime | Select-Object -Last 1
$l3 = Get-ChildItem pipeline\collected\raw -Recurse -Filter "l3_*.hdf5"         | Sort-Object LastWriteTime | Select-Object -Last 1
$l4 = Get-ChildItem pipeline\collected\raw -Recurse -Filter "l4_*.hdf5"         | Sort-Object LastWriteTime | Select-Object -Last 1
$l5a = Get-ChildItem pipeline\collected\raw -Recurse -Filter "l5_white_tote_b01_right_left_*.hdf5"  | Sort-Object LastWriteTime | Select-Object -Last 1
$l5b = Get-ChildItem pipeline\collected\raw -Recurse -Filter "l5_white_tote_b01_right_right_*.hdf5" | Sort-Object LastWriteTime | Select-Object -Last 1
Log ("merge inputs: " + $l1.Name + " " + $l3.Name + " " + $l4.Name + " " + $l5a.Name + " " + $l5b.Name)
& $VenvPy pipeline\merge_datasets.py --out pipeline\collected\merged_grasp_v2.hdf5 $l1.FullName $l3.FullName $l4.FullName $l5a.FullName $l5b.FullName 2>&1 | Add-Content $log

# 3) retrain
& $VenvPy pipeline\train_bc.py --dataset pipeline\collected\merged_grasp_v2.hdf5 --epochs $Epochs --save-every 250 --device cuda:0 --no-install 2>&1 | Out-File -Encoding utf8 pipeline\logs\train_v2.log
Log "train exit=$LASTEXITCODE"

# 4) matrix eval: newest run's 3000 ckpt on L1/L3/L4 (isolated grasp)
$run = Get-ChildItem pipeline\train_output -Directory | Sort-Object Name | Select-Object -Last 1
$ck  = Get-ChildItem $run.FullName -Recurse -Filter "model_epoch_$Epochs.pth" | Select-Object -First 1
if (-not $ck) { $ck = Get-ChildItem $run.FullName -Recurse -Filter "model_epoch_*.pth" | Sort-Object LastWriteTime | Select-Object -Last 1 }
Log ("eval ckpt: " + $ck.FullName)
# recalibrate grasp poses for each level before its eval (config keys are shared)
& $VenvPy pipeline\patch_grasp_pose.py --level L1 2>&1 | Out-Null
& $VenvPy pipeline\patch_grasp_pose.py --level L3 --object blue_tote_b01_near_left 2>&1 | Out-Null
& $VenvPy pipeline\patch_grasp_pose.py --level L4 2>&1 | Out-Null
foreach ($lvl in @("L1","L3","L4")) {
    $r = powershell -ExecutionPolicy Bypass -NoProfile -File pipeline\eval_grasp.ps1 -Level $lvl -Checkpoint $ck.FullName 2>&1 |
         Where-Object { $_ -match 'Final grasp' }
    Log ("eval " + $lvl + ": " + ($r -join " "))
}

# 5) install only if L1 grasp succeeded
$l1ok = Select-String -Path $log -Pattern 'eval L1: .*True' -Quiet
if ($l1ok) {
    Copy-Item $ck.FullName (Join-Path $AppDir "robosuite\robosuite\model_epoch_500.pth") -Force
    Log "INSTALLED as model_epoch_500.pth"
} else {
    Remove-Item (Join-Path $AppDir "robosuite\robosuite\model_epoch_500.pth") -ErrorAction SilentlyContinue
    Log "L1 eval failed -> model_epoch_500.pth removed (fallback to official 150)"
}
Log "=== retrain_all done ==="
