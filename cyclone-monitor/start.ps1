# start.ps1
# User request: launch the local cyclone dashboard from this project.
param([int]$Port = 8765, [int]$Interval = 300)
$ErrorActionPreference = 'Stop'
$monitorPython = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $monitorPython)) {
    throw 'Create the virtual environment and install the package as described in README.md.'
}
& $monitorPython -m cyclone_monitor --data-dir (Join-Path $PSScriptRoot 'data') --port $Port --interval $Interval
if ($LASTEXITCODE -ne 0) { throw "Cyclone Monitor exited with code $LASTEXITCODE" }
# Purpose: visible Windows launch. Upstream: installed cyclone_monitor package implements the dashboard.
# Environment: PowerShell, project .venv. Generated: 2026-09-28 America/New_York.
# Change record: new implementation, lines 1-12; finalized 2026-09-29 America/New_York.
