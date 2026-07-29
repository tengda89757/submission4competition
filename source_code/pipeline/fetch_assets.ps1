<#
  fetch_assets.ps1 — Resolve Git-LFS assets that GitHub leaves as pointer stubs.

  Why: the official repo's Git-LFS API budget is exhausted, so `git clone` /
  `git lfs pull` / "Download ZIP" all leave *.pth, *.hdf5, *.zip as ~130-byte
  pointer files. The github.com/.../raw/... web endpoint still serves the real
  bytes. This script downloads them to the correct locations and verifies
  size + sha256 (a falsifiable integrity check).

  Usage (from anywhere):
    powershell -ExecutionPolicy Bypass -File pipeline\fetch_assets.ps1              # essential only (.pth + .hdf5)
    powershell -ExecutionPolicy Bypass -File pipeline\fetch_assets.ps1 -Only pth   # just one asset by id
    powershell -ExecutionPolicy Bypass -File pipeline\fetch_assets.ps1 -All        # + optional USD/mesh zips
    powershell -ExecutionPolicy Bypass -File pipeline\fetch_assets.ps1 -Force      # re-download even if valid
#>
param(
    [switch]$All,
    [switch]$Force,
    [string]$Only = "",
    [string]$RepoRoot = ""
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"   # HUGE speedup for Invoke-WebRequest large files

if (-not $RepoRoot) {
    # pipeline/ lives under JCIIOT2026-master/JCIIOT/pipeline → repo root is two levels up
    $RepoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
}
$manifestPath = Join-Path $PSScriptRoot "assets_manifest.json"
if (-not (Test-Path $manifestPath)) { throw "Manifest not found: $manifestPath" }
$assets = (Get-Content $manifestPath -Raw | ConvertFrom-Json).assets

function Test-Stub([string]$file, [long]$expected) {
    # A pointer stub is a tiny text file; treat < 4KB as a stub when the real file is large.
    if (-not (Test-Path $file)) { return $true }
    $len = (Get-Item $file).Length
    return ($len -ne $expected)
}

$results = @()
foreach ($a in $assets) {
    if ($Only -and $a.id -ne $Only) { continue }
    if (-not $All -and -not $a.essential -and -not $Only) { continue }

    $dest = Join-Path $RepoRoot $a.path
    $destDir = Split-Path $dest -Parent
    if (-not (Test-Path $destDir)) { New-Item -ItemType Directory -Force -Path $destDir | Out-Null }

    $expSize = 0
    if ($a.size) { $expSize = [long]$a.size }
    if ($expSize -gt 0) {
        $needs = $Force -or (Test-Stub $dest $expSize)
    } else {
        # unknown size: re-download only if missing or still a tiny pointer stub
        $needs = $Force -or (-not (Test-Path $dest)) -or ((Get-Item $dest).Length -lt 4096)
    }
    if (-not $needs) {
        Write-Host ("[skip] {0}  (already {1:N0} bytes)" -f $a.id, (Get-Item $dest).Length) -ForegroundColor DarkGray
        $results += [pscustomobject]@{ id = $a.id; status = "ok(existing)"; bytes = (Get-Item $dest).Length }
        continue
    }

    $part = "$dest.part"
    if (Test-Path $part) { Remove-Item $part -Force }
    Write-Host ("[get ] {0} -> {1}" -f $a.id, $a.path) -ForegroundColor Cyan
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    Invoke-WebRequest -Uri $a.url -OutFile $part -UseBasicParsing -MaximumRedirection 5 -TimeoutSec 1800
    $sw.Stop()

    $len = (Get-Item $part).Length
    if ($expSize -gt 0 -and $len -ne $expSize) {
        Remove-Item $part -Force
        $results += [pscustomobject]@{ id = $a.id; status = "FAIL(size $len != $($a.size))"; bytes = $len }
        Write-Host ("[FAIL] {0} size mismatch: got {1:N0}, want {2:N0}" -f $a.id, $len, $a.size) -ForegroundColor Red
        continue
    }
    if ($a.sha256) {
        $got = (Get-FileHash $part -Algorithm SHA256).Hash.ToLower()
        if ($got -ne $a.sha256.ToLower()) {
            Remove-Item $part -Force
            $results += [pscustomobject]@{ id = $a.id; status = "FAIL(sha256)"; bytes = $len }
            Write-Host ("[FAIL] {0} sha256 mismatch" -f $a.id) -ForegroundColor Red
            continue
        }
    }
    if (Test-Path $dest) { Remove-Item $dest -Force }
    Move-Item $part $dest -Force
    $mb = [math]::Round($len / 1MB, 1)
    $secs = [math]::Round($sw.Elapsed.TotalSeconds, 1)
    Write-Host ("[ ok ] {0}  {1} MB in {2}s (size+sha256 verified)" -f $a.id, $mb, $secs) -ForegroundColor Green
    $results += [pscustomobject]@{ id = $a.id; status = "downloaded+verified"; bytes = $len }
}

Write-Host "`n===== fetch_assets summary =====" -ForegroundColor Yellow
$results | Format-Table -AutoSize
$failed = @($results | Where-Object { $_.status -like "FAIL*" })
if ($failed.Count -gt 0) { exit 1 } else { exit 0 }
