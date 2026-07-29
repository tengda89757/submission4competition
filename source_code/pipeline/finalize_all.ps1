<#
  finalize_all.ps1 — Post-training finisher: pick the best checkpoint, run every
  level end-to-end (canonical prompts), score, and package submissions.

  Designed to run detached after retrain_all.ps1 completes. For each level:
    1. recalibrate the grasp pose for that scene/object (patch_grasp_pose.py)
    2. run_level -Canonical -Score with the chosen checkpoint
    3. package_submission.ps1 into pipeline\submissions

  Checkpoint policy (falsifiable, per-level):
    - If pipeline\logs\retrain_all.log shows the v2 ckpt PASSED a level's isolated
      grasp eval, use v2 for that level; otherwise fall back to the official 150.
    - You can force one with -Checkpoint.

  Usage:
    powershell -ExecutionPolicy Bypass -File pipeline\finalize_all.ps1
    powershell -ExecutionPolicy Bypass -File pipeline\finalize_all.ps1 -Levels L1,L3,L4
    powershell -ExecutionPolicy Bypass -File pipeline\finalize_all.ps1 -Checkpoint <path>
#>
param(
    [string[]]$Levels = @("L1","L2","L3","L4","L5"),
    [string]$Checkpoint = "",
    [string]$Team = "BIPT-EDU"
)
$ErrorActionPreference = "Continue"
$AppDir = Split-Path $PSScriptRoot -Parent
$VenvPy = Join-Path $AppDir ".venv\Scripts\python.exe"
Set-Location $AppDir
Remove-Item Env:\MUJOCO_GL -ErrorAction SilentlyContinue
$env:PYTHONIOENCODING = "utf-8"
$log = Join-Path $PSScriptRoot "logs\finalize_all.log"
New-Item -ItemType Directory -Force -Path (Join-Path $PSScriptRoot "logs") | Out-Null
function Log($m) { $line = "[{0}] {1}" -f (Get-Date -Format "MM-dd HH:mm:ss"), $m; Add-Content -Path $log -Value $line; Write-Host $line }

Log "=== finalize_all start (levels: $($Levels -join ',')) ==="

# resolve the newest v2 checkpoint (model_epoch_3000.pth from the latest train run)
$v2 = Get-ChildItem (Join-Path $PSScriptRoot "train_output") -Recurse -Filter "model_epoch_3000.pth" -ErrorAction SilentlyContinue |
      Sort-Object LastWriteTime | Select-Object -Last 1
$official = Join-Path $AppDir "robosuite\robosuite\model_epoch_150.pth"
Log ("v2 ckpt: " + $(if ($v2) { $v2.FullName } else { "NOT FOUND" }))

# per-level object overrides (erratum-synced)
$objOverride = @{ L3 = "blue_tote_b01_near_left" }

# parse eval results from retrain_all.log: lines like "eval L3: ... Final grasp status: True"
$evalPass = @{}
if (Test-Path (Join-Path $PSScriptRoot "logs\retrain_all.log")) {
    foreach ($lvl in @("L1","L3","L4")) {
        if (Select-String -Path (Join-Path $PSScriptRoot "logs\retrain_all.log") -Pattern ("eval " + $lvl + ": .*True") -Quiet) { $evalPass[$lvl] = $true }
    }
}
Log ("eval passes from retrain log: " + ($evalPass.Keys -join ',' ))

$summary = @()
foreach ($lvl in $Levels) {
    Log "----- $lvl -----"
    # choose checkpoint
    $ck = $Checkpoint
    if (-not $ck) {
        if ($v2 -and $evalPass.ContainsKey($lvl)) { $ck = $v2.FullName }
        elseif ($v2 -and ($lvl -in @("L2","L5"))) { $ck = $v2.FullName }   # only hope for transfer levels
        else { $ck = "" }                                                  # official 150 fallback
    }
    Log ("checkpoint: " + $(if ($ck) { $ck } else { "official 150 (fallback)" }))

    $rlArgs = @("-ExecutionPolicy","Bypass","-NoProfile","-File",(Join-Path $PSScriptRoot "run_level.ps1"),
                "-Level",$lvl,"-Canonical","-Score")
    if ($objOverride.ContainsKey($lvl)) { $rlArgs += @("-ObjectName",$objOverride[$lvl]) }
    if ($ck) { $rlArgs += @("-Checkpoint",$ck) }
    & powershell.exe @rlArgs 2>&1 | Out-File -Encoding utf8 (Join-Path $PSScriptRoot "logs\finalize_$lvl.log")
    Log ("$lvl run exit=$LASTEXITCODE")

    # package newest OK trajectory (package_submission picks it up automatically)
    & powershell.exe -ExecutionPolicy Bypass -NoProfile -File (Join-Path $PSScriptRoot "package_submission.ps1") `
        -Level $lvl -Team $Team `
        -MethodSummary "Erratum-synced task_config; site-geometry grasp-pose calibration; multi-scene BC retrain (105 demos, markers hidden, 3000 ep) with official-150 fallback; canonical prompts; headless pipeline" `
        2>&1 | Add-Content (Join-Path $PSScriptRoot "logs\finalize_$lvl.log")
    Log ("$lvl package exit=$LASTEXITCODE")

    # extract score for the summary
    $rec = Get-ChildItem (Join-Path $AppDir "recordings") -Recurse -Filter "score_*.json" -ErrorAction SilentlyContinue |
           Sort-Object LastWriteTime | Select-Object -Last 1
    $total = "?"
    if ($rec) {
        try { $total = (Get-Content $rec.FullName -Raw | ConvertFrom-Json).total } catch {}
    }
    $summary += ("{0}: ckpt={1} score={2}" -f $lvl, $(if ($ck) { Split-Path $ck -Leaf } else { "150" }), $total)
    Log ("$lvl score=$total")
}

Log "=== SUMMARY ==="
$summary | ForEach-Object { Log $_ }
Log "=== finalize_all done ==="
