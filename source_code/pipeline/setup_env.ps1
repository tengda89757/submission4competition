<#
  setup_env.ps1 — Reproducible Python environment for JCIIOT 2026 (Windows + NVIDIA GPU).

  Uses `uv` (already installed) to create an isolated Python 3.11 venv at
  JCIIOT/.venv, install a CUDA build of PyTorch, then the pinned app deps,
  then editable robosuite + robot-agent. robomimic is vendored (path-based).

  Exact resolved versions are frozen to pipeline/requirements.resolved.txt.

  Usage:
    powershell -ExecutionPolicy Bypass -File pipeline\setup_env.ps1
    powershell -ExecutionPolicy Bypass -File pipeline\setup_env.ps1 -TorchIndex cu128   # 50-series / Blackwell
    powershell -ExecutionPolicy Bypass -File pipeline\setup_env.ps1 -Cpu                 # CPU-only torch
#>
param(
    [string]$Python = "3.11",
    [string]$TorchIndex = "cu126",
    [switch]$Cpu,
    [switch]$SkipTorch
)

# NOTE: keep ErrorActionPreference = Continue. `uv` logs to stderr; with "Stop"
# a 2>&1 pipe turns that normal logging into a terminating error.
$ErrorActionPreference = "Continue"
$AppDir = Split-Path $PSScriptRoot -Parent          # JCIIOT
$VenvPy = Join-Path $AppDir ".venv\Scripts\python.exe"
$logDir = Join-Path $PSScriptRoot "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir "setup_env.log"
function Log($m) { $line = "[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $m; Write-Host $line; Add-Content -Path $log -Value $line }

function Invoke-Step([string]$desc, [string[]]$exe) {
    Log "RUN: $desc"
    $global:LASTEXITCODE = 0
    & $exe[0] $exe[1..($exe.Count-1)] 2>&1 | Tee-Object -FilePath $log -Append
    if ($LASTEXITCODE -ne 0) {
        Log "STEP FAILED (exit $LASTEXITCODE): $desc"
        exit $LASTEXITCODE
    }
}

Set-Location $AppDir
Log "AppDir = $AppDir"
Log ("uv version: " + (uv --version))

# 1. Standalone interpreter + venv
Invoke-Step "uv python install $Python" @("uv","python","install",$Python)
Invoke-Step "uv venv .venv" @("uv","venv",".venv","--python",$Python)

# 2. PyTorch (CUDA by default). torch==2.7.0 to match requirements.txt public version.
if (-not $SkipTorch) {
    $torchIdx = if ($Cpu) { "https://download.pytorch.org/whl/cpu" } else { "https://download.pytorch.org/whl/$TorchIndex" }
    Invoke-Step "install torch/vision/audio from $torchIdx" @(
        "uv","pip","install","--python",$VenvPy,
        "torch==2.7.0","torchvision==0.22.0","torchaudio==2.7.0","--index-url",$torchIdx)
}

# 3. Pinned application dependencies (mujoco, robosuite deps, streamlit, robomimic deps, ...)
Invoke-Step "install requirements.txt" @("uv","pip","install","--python",$VenvPy,"-r","requirements.txt")

# 4. Editable installs: robosuite (v1.5.2 fork) + robot-agent (src layout)
Invoke-Step "editable install robosuite" @("uv","pip","install","--python",$VenvPy,"--no-deps","-e","./robosuite")
Invoke-Step "editable install robot-agent" @("uv","pip","install","--python",$VenvPy,"--no-deps","-e",".")

# 5. Verify the toolchain imports and report CUDA status
Log "Verifying imports ..."
$verify = @'
import sys
print("python", sys.version.split()[0])
import numpy, scipy, mujoco
print("numpy", numpy.__version__, "| mujoco", mujoco.__version__)
import torch
print("torch", torch.__version__, "| cuda_available", torch.cuda.is_available(),
      "| cuda", torch.version.cuda, "| device", (torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu"))
import robomimic, streamlit
print("robomimic OK | streamlit", streamlit.__version__)
'@
$verify | & $VenvPy - 2>&1 | Tee-Object -FilePath $log -Append

# 6. Freeze resolved versions for reproducibility
Log "Freezing resolved versions -> pipeline/requirements.resolved.txt"
uv pip freeze --python $VenvPy 2>&1 | Out-File -Encoding utf8 (Join-Path $PSScriptRoot "requirements.resolved.txt")

Log "DONE. Venv python: $VenvPy"
