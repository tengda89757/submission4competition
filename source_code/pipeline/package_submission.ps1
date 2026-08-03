<#
  package_submission.ps1 — Bundle a level's trajectory + objective score + manifest
  into a ready-to-submit folder and .zip.

  The competition deliverable is the trajectory JSON (competition description ships
  trajectory_template.json); the organizer verifies it for the objective score and
  reviews the method for the subjective score. This packages everything consistently.

  Usage:
    powershell -ExecutionPolicy Bypass -File pipeline\package_submission.ps1 -Level L1
    powershell -ExecutionPolicy Bypass -File pipeline\package_submission.ps1 -Level L1 -Trajectory <path> -MethodSummary "SOP-MapGuard + retrained BC 3000ep"
#>
param(
    [ValidateSet("L1","L2","L3","L4","L5")][string]$Level = "L1",
    [string]$Trajectory = "",
    [string]$OutDir = "",
    [string]$MethodSummary = "",
    [string]$Team = ""
)

$ErrorActionPreference = "Continue"
$AppDir = Split-Path $PSScriptRoot -Parent
$VenvPy = Join-Path $AppDir ".venv\Scripts\python.exe"
$LevelIndex = @{ L1=0; L2=1; L3=2; L4=3; L5=4 }[$Level]
if (-not $OutDir) { $OutDir = Join-Path $PSScriptRoot "submissions" }

$cfg = Get-Content (Join-Path $AppDir "knowledge\task_config.json") -Raw | ConvertFrom-Json
$task = $cfg.tasks | Where-Object { $_.level -eq $Level }
$envName = $task.env_name
$recDir = Join-Path $AppDir "recordings\$envName"

# Pick trajectory: explicit > newest *_OK > newest any
if (-not $Trajectory) {
    $cand = Get-ChildItem $recDir -Filter "trajectory_*_OK.json" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime | Select-Object -Last 1
    if (-not $cand) { $cand = Get-ChildItem $recDir -Filter "trajectory_*.json" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime | Select-Object -Last 1 }
    if (-not $cand) { Write-Host "No trajectory found in $recDir. Run pipeline\run_level.ps1 -Level $Level first." -ForegroundColor Red; exit 1 }
    $Trajectory = $cand.FullName
}
if (-not (Test-Path $Trajectory)) { Write-Host "Trajectory not found: $Trajectory" -ForegroundColor Red; exit 1 }

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$stage = Join-Path $OutDir "${Level}_$ts"
New-Item -ItemType Directory -Force -Path $stage | Out-Null

# Score (best-effort; needs venv)
$scorePath = Join-Path $stage "score.json"
$scoreVal = "n/a"
if (Test-Path $VenvPy) {
    & $VenvPy (Join-Path $PSScriptRoot "score_trajectory.py") --trajectory $Trajectory --task-index $LevelIndex --out $scorePath | Out-Null
    if (Test-Path $scorePath) { try { $scoreVal = (Get-Content $scorePath -Raw | ConvertFrom-Json).score } catch {} }
} else {
    Write-Host "venv missing — packaging without a fresh score." -ForegroundColor Yellow
}

Copy-Item $Trajectory (Join-Path $stage "trajectory.json") -Force

$manifest = [ordered]@{
    competition       = "JCIIOT 2026 RunningRobot"
    level             = $Level
    env_name          = $envName
    task_index        = $LevelIndex
    max_score         = $task.max_score
    objective_score   = $scoreVal
    score_rule_version= "grasp_success_gate_l5_multi_v2"
    official_reference_commit = "129e94a9cff787031472045e19c24a4baeaefc48"
    method_summary    = $MethodSummary
    team              = $Team
    source_trajectory = $Trajectory
    packaged_at       = (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
    files             = @("trajectory.json", "score.json")
}
$manifest | ConvertTo-Json -Depth 6 | Out-File -Encoding utf8 (Join-Path $stage "submission_manifest.json")

$zip = Join-Path $OutDir "${Level}_$ts.zip"
if (Test-Path $zip) { Remove-Item $zip -Force }
Compress-Archive -Path (Join-Path $stage "*") -DestinationPath $zip -Force

Write-Host "`nSubmission staged: $stage" -ForegroundColor Green
Write-Host "Submission zip   : $zip   (objective score: $scoreVal / $($task.max_score))" -ForegroundColor Green
