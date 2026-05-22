param(
    [string]$ProjectRoot = "",
    [string]$ConfigPath = "config\person_import.json",
    [switch]$Submit,
    [switch]$Reset
)

$ErrorActionPreference = "Stop"

$defaultProjectRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ProjectRoot = $defaultProjectRoot
}

Set-Location -LiteralPath $ProjectRoot

$python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "Python venv was not found: $python. Copy the prepared .venv with this project, or create it before running the elevated workflow."
}

$resolvedConfigPath = $ConfigPath
if (-not [System.IO.Path]::IsPathRooted($resolvedConfigPath)) {
    $resolvedConfigPath = Join-Path $ProjectRoot $resolvedConfigPath
}
if (-not (Test-Path -LiteralPath $resolvedConfigPath)) {
    throw "Workflow config was not found: $resolvedConfigPath"
}

$arguments = @(
    "-m",
    "tax_rpa.cli.run_tax_workflow",
    "--config",
    $resolvedConfigPath,
    "--no-self-elevate"
)

if ($Submit) {
    $arguments += "--submit"
}

if ($Reset) {
    $arguments += "--reset"
}

& $python @arguments
exit $LASTEXITCODE
