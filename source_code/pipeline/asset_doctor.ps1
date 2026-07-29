<#
  asset_doctor.ps1 — Falsifiable environment/asset consistency check.

  Scans every Git-LFS-tracked file (*.pth, *.hdf5, *.zip) and reports whether it
  is REAL content or an unresolved ~130-byte LFS POINTER STUB. Also cross-checks
  the essential files against the manifest's expected size + sha256.

  This directly answers the recurring chat question: "give me the exact contract
  between the official checkpoint and the eval environment" — run this and you
  get a green/red table.

  Usage:  powershell -ExecutionPolicy Bypass -File pipeline\asset_doctor.ps1
#>
param([string]$RepoRoot = "")

$ErrorActionPreference = "Stop"
if (-not $RepoRoot) { $RepoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent }

$manifestPath = Join-Path $PSScriptRoot "assets_manifest.json"
$manifest = if (Test-Path $manifestPath) { (Get-Content $manifestPath -Raw | ConvertFrom-Json).assets } else { @() }
$byPath = @{}
foreach ($m in $manifest) { $byPath[(Join-Path $RepoRoot $m.path)] = $m }

function Is-LfsPointer([string]$file) {
    if ((Get-Item $file).Length -gt 4096) { return $false }
    try {
        $first = Get-Content $file -TotalCount 1 -ErrorAction Stop
        return ($first -like "version https://git-lfs.github.com/spec/v1*")
    } catch { return $false }
}

Write-Host "Repo root: $RepoRoot`n" -ForegroundColor Yellow
$patterns = @("*.pth", "*.hdf5", "*.zip")
$rows = @()
foreach ($pat in $patterns) {
    Get-ChildItem -Path $RepoRoot -Recurse -Filter $pat -File -ErrorAction SilentlyContinue | ForEach-Object {
        $f = $_.FullName
        if ($f -match '\\pipeline\\|\\\.venv\\') { return }   # skip pipeline artifacts & venv
        $stub = Is-LfsPointer $f
        $state = if ($stub) { "STUB (LFS pointer)" } else { "real" }
        $verified = ""
        if ($byPath.ContainsKey($f)) {
            $exp = $byPath[$f]
            if (-not $stub -and $_.Length -eq [long]$exp.size) {
                if ($exp.sha256) {
                    $got = (Get-FileHash $f -Algorithm SHA256).Hash.ToLower()
                    $verified = if ($got -eq $exp.sha256.ToLower()) { "sha256 OK" } else { "sha256 MISMATCH" }
                } else { $verified = "size OK" }
            } elseif (-not $stub) { $verified = "size mismatch ($($_.Length) != $($exp.size))" }
        }
        $rows += [pscustomobject]@{
            State    = $state
            Verified = $verified
            SizeKB   = [math]::Round($_.Length / 1KB, 1)
            Path     = $f.Substring($RepoRoot.Length).TrimStart('\')
        }
    }
}

$stubs = @($rows | Where-Object { $_.State -like "STUB*" })
$rows | Sort-Object State, Path | Format-Table -AutoSize -Wrap

Write-Host ("`nTotals: {0} tracked file(s); {1} STUB(s) still unresolved." -f $rows.Count, $stubs.Count) -ForegroundColor Yellow
if ($stubs.Count -gt 0) {
    Write-Host "Run:  powershell -ExecutionPolicy Bypass -File pipeline\fetch_assets.ps1 -All" -ForegroundColor Cyan
    exit 1
}
Write-Host "All LFS assets resolved." -ForegroundColor Green
exit 0
