[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$latexDir = Join-Path $PSScriptRoot 'latex'
$buildDir = Join-Path $latexDir 'build'
$generator = Join-Path $PSScriptRoot 'build_technical_report_latex.py'
$sourcePdf = Join-Path $buildDir 'technical_report.pdf'
$outputDir = Join-Path $repoRoot 'output\pdf'
$outputPdf = Join-Path $outputDir 'TECHNICAL_REPORT.pdf'

foreach ($command in @('xelatex', 'biber')) {
    if (-not (Get-Command $command -ErrorAction SilentlyContinue)) {
        throw "Required command is unavailable: $command"
    }
}

$pythonExe = $env:JCIIOT_REPORT_PYTHON
if (-not $pythonExe) {
    foreach ($candidate in @('python3', 'python')) {
        $resolved = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($resolved -and $resolved.Source -notmatch 'WindowsApps') {
            $pythonExe = $resolved.Source
            break
        }
    }
}
if (-not $pythonExe -or -not (Test-Path -LiteralPath $pythonExe)) {
    throw 'A Python 3 interpreter is required. Set JCIIOT_REPORT_PYTHON to its full path.'
}

New-Item -ItemType Directory -Force -Path $buildDir | Out-Null
New-Item -ItemType Directory -Force -Path $outputDir | Out-Null

& $pythonExe $generator
if ($LASTEXITCODE -ne 0) {
    throw 'Markdown-to-LaTeX generation failed.'
}

Push-Location $latexDir
try {
    $xelatexArgs = @(
        '-interaction=nonstopmode',
        '-halt-on-error',
        '-file-line-error',
        '-synctex=0',
        '-output-directory=build',
        'technical_report.tex'
    )

    & xelatex @xelatexArgs
    if ($LASTEXITCODE -ne 0) {
        throw 'Initial XeLaTeX pass failed. See report/latex/build/technical_report.log.'
    }

    & biber --input-directory build --output-directory build technical_report
    if ($LASTEXITCODE -ne 0) {
        throw 'Biber pass failed. See report/latex/build/technical_report.blg.'
    }

    foreach ($pass in 2..3) {
        & xelatex @xelatexArgs
        if ($LASTEXITCODE -ne 0) {
            throw "XeLaTeX pass $pass failed. See report/latex/build/technical_report.log."
        }
    }
}
finally {
    Pop-Location
}

if (-not (Test-Path -LiteralPath $sourcePdf)) {
    throw "Expected PDF was not created: $sourcePdf"
}

$logPath = Join-Path $buildDir 'technical_report.log'
$log = Get-Content -Raw -LiteralPath $logPath
$fatalPatterns = @(
    'LaTeX Warning: There were undefined references',
    'LaTeX Warning: Citation .* undefined',
    'Package biblatex Warning: Please \(re\)run Biber',
    'Overfull \\[hv]box',
    'Missing character:'
)
$problems = foreach ($pattern in $fatalPatterns) {
    if ($log -match $pattern) {
        $pattern
    }
}
if ($problems) {
    throw "LaTeX quality checks failed: $($problems -join ', ')"
}

Copy-Item -LiteralPath $sourcePdf -Destination $outputPdf -Force

$pdfInfo = Get-Command pdfinfo -ErrorAction SilentlyContinue
if ($pdfInfo) {
    & $pdfInfo.Source $outputPdf
    if ($LASTEXITCODE -ne 0) {
        throw 'pdfinfo could not reopen the final PDF.'
    }
}

$hash = Get-FileHash -Algorithm SHA256 -LiteralPath $outputPdf
Write-Host "Built: $outputPdf"
Write-Host "SHA256: $($hash.Hash.ToLowerInvariant())"
