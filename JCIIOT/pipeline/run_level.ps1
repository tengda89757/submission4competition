<#
  run_level.ps1 — Run a full L1..L5 task end-to-end (headless CLI equivalent of the
  dashboard's "Execute" button). Launches robot_agent.task_subprocess_runner in an
  isolated process (so a MuJoCo/native crash never takes down the caller), which
  plans with the configured LLM, drives navigation + BC grasp + place, and writes a
  trajectory JSON. Optionally scores it.

  The per-level task prompt is the SAME text the Streamlit dashboard sends (copied
  from app.py TASKS), so the LLM planner sees an identical instruction. Note L3's
  prompt says "blue material transfer bin" — matching the official docx ruling
  (task_config.json's "orange" is baseline-only and NOT the graded target).

  Usage:
    powershell -ExecutionPolicy Bypass -File pipeline\run_level.ps1 -Level L1 -Score
    powershell -ExecutionPolicy Bypass -File pipeline\run_level.ps1 -Level L1 -Backend ollama -OllamaModel qwen2.5:7b
#>
param(
    [ValidateSet("L1","L2","L3","L4","L5")][string]$Level = "L1",
    [string]$Task = "",
    [ValidateSet("ollama","openai","local")][string]$Backend = "ollama",
    [string]$OllamaModel = "qwen2.5:7b",
    [string]$OllamaUrl = "http://localhost:11434",
    [switch]$Canonical,
    [string]$ObjectName = "",
    [string]$Checkpoint = "",
    [switch]$ScriptedOnly,
    [switch]$Score,
    [switch]$KnowledgeDisabled
)

$ErrorActionPreference = "Continue"
$AppDir = Split-Path $PSScriptRoot -Parent
$VenvPy = Join-Path $AppDir ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPy)) { Write-Host "venv missing — run pipeline\setup_env.ps1 first" -ForegroundColor Red; exit 1 }

# scripted-grasp mode for the child process (skills/scripted_grasp.py):
#   -ScriptedOnly → skip the BC policy (approach from reset pose — matches demo collection)
#   default       → BC first, scripted expert fallback on BC failure
if ($ScriptedOnly) { $env:ROBOT_AGENT_SCRIPTED_GRASP = "only" } else { $env:ROBOT_AGENT_SCRIPTED_GRASP = "fallback" }

$LevelIndex = @{ L1=0; L2=1; L3=2; L4=3; L5=4 }[$Level]
# Canonical task prompts (verbatim from app.py TASKS).
$DESC = @{
 L1 = 'For this task, you need to transport a blue, hollow plastic box. Please move it from the starting point Pick Station 2 to the destination Place Station 3. Please follow the Standard Operating Procedure (SOP).'
 L2 = 'Current Task Material Information. Material Name: Green-rimmed storage bin. Starting Location: Pick Station 1. Target Location: Place Station 3. Quantity to Transport: 1.'
 L3 = 'Please follow the SOP. The object is a blue material transfer bin. The Pick Station is Pick Station 1, and the Place Station is Place Station 2.'
 L4 = 'Please strictly adhere to the Standard Operating Procedure (SOP) for this task. The object to be handled is a blue, hollow plastic box. The Pick Station is designated as Pick Station 5, and the Place Station is designated as Place Station 2.'
 L5 = 'Move the three white-rimmed storage bins from Pick Station 6 to Place Station 1.'
}
if (-not $Task) { $Task = $DESC[$Level] }

$cfg = Get-Content (Join-Path $AppDir "knowledge\task_config.json") -Raw | ConvertFrom-Json
$taskCfg = $cfg.tasks | Where-Object { $_.level -eq $Level }
$envName = $taskCfg.env_name

# -Canonical: build an explicit task with exact port/object names (validated 10/10 on L1;
# removes the LLM's SOP-station-name mapping fragility). -ObjectName overrides the baseline
# object (e.g. L3 erratum: pick from Placement Point 1 = side table blue tote).
if ($Canonical) {
    $src = $taskCfg.source; $tgt = $taskCfg.target
    $obj = if ($ObjectName) { $ObjectName } else { $taskCfg.object }
    # grasp_poses is keyed by source port and shared across scenes — recalibrate it
    # for THIS scene/object right before running (pipeline/patch_grasp_pose.py).
    & $VenvPy (Join-Path $PSScriptRoot "patch_grasp_pose.py") --level $Level --object $obj 2>&1 |
        Where-Object { $_ -match 'computed|patched|Error' } | ForEach-Object { Write-Host $_ -ForegroundColor DarkCyan }
    if ($Level -eq "L5") {
        $objs = @("white_tote_b01_left_center","white_tote_b01_left_front","white_tote_b01_left_back")
        $steps = ($objs | ForEach-Object { "move to $src, pick up $_ at $src, move to $tgt, place down at $tgt" }) -join "; then "
        $Task = "Transport three objects from $src to $tgt one at a time, strictly in this order: $steps."
    } else {
        $Task = "Transport the object from $src to $tgt. First move to $src, then pick up $obj at $src, then move to $tgt, then place down at $tgt."
    }
}
$recDir = Join-Path $AppDir "recordings\$envName"
New-Item -ItemType Directory -Force -Path $recDir | Out-Null
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$resultJson = Join-Path $recDir "result_$ts.json"

# child env (mirrors app.py _run_task_in_mujoco_process)
Remove-Item Env:\MUJOCO_GL -ErrorAction SilentlyContinue      # Windows default (wgl); egl is Linux-only
$env:PYTHONPATH = @((Join-Path $AppDir "src"), $AppDir, (Join-Path $AppDir "robomimic"), (Join-Path $AppDir "robosuite\robosuite")) -join ";"
$env:PYTHONIOENCODING = "utf-8"
$env:GATE_OLLAMA = "true"
$env:GATE_STEP_TIMEOUT = "false"
if ($Backend -eq "ollama") { $env:OLLAMA_BASE_URL = $OllamaUrl; $env:OLLAMA_MODEL = $OllamaModel; $env:OPENAI_API_KEY = ""; $env:LOCAL_LLM_MODEL = "" }

$runner = Join-Path $AppDir "src\robot_agent\task_subprocess_runner.py"
$kb = if ($KnowledgeDisabled) { "false" } else { "true" }

# -Checkpoint: per-level model selection. The backend loads model_epoch_500.pth
# first — temporarily occupy that slot with the chosen model, restore afterwards.
$slot = Join-Path $AppDir "robosuite\robosuite\model_epoch_500.pth"
$slotBackup = ""
if ($Checkpoint) {
    if (-not (Test-Path $Checkpoint)) { Write-Host "checkpoint not found: $Checkpoint" -ForegroundColor Red; exit 1 }
    if (Test-Path $slot) {
        $slotBackup = "$slot.bak_runlevel"
        Move-Item $slot $slotBackup -Force
    }
    Copy-Item $Checkpoint $slot -Force
    Write-Host "using checkpoint: $Checkpoint (slotted as model_epoch_500.pth)" -ForegroundColor DarkCyan
}

Write-Host "Level=$Level idx=$LevelIndex scene=$envName backend=$Backend model=$OllamaModel" -ForegroundColor Cyan
Write-Host "Task: $Task" -ForegroundColor DarkGray

& $VenvPy $runner --task $Task --task-index $LevelIndex --timestamp $ts --result-json $resultJson --app-dir $AppDir --knowledge-enabled $kb
$code = $LASTEXITCODE

if ($Checkpoint) {
    Remove-Item $slot -ErrorAction SilentlyContinue
    if ($slotBackup -and (Test-Path $slotBackup)) { Move-Item $slotBackup $slot -Force }
}

$traj = Get-ChildItem $recDir -Filter "trajectory_${ts}_*.json" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime | Select-Object -Last 1
if ($traj) { Write-Host "Trajectory: $($traj.FullName)" -ForegroundColor Green } else { Write-Host "No trajectory produced (see $resultJson and subprocess log)." -ForegroundColor Yellow }

if ($Score -and $traj) {
    $scoreOut = Join-Path $recDir "score_${ts}.json"
    $scoreArgs = @("--trajectory", $traj.FullName, "--task-index", $LevelIndex, "--out", $scoreOut)
    if ($ObjectName) { $scoreArgs += @("--object", $ObjectName) }
    & $VenvPy (Join-Path $PSScriptRoot "score_trajectory.py") @scoreArgs
}
exit $code
