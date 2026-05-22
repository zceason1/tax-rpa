param(
    [string]$TaskName = "TaxRpaElevatedWorkflow",
    [string]$ProjectRoot = "",
    [string]$ConfigPath = "config\person_import.json",
    [string]$RunAsUser = "",
    [switch]$Submit,
    [switch]$Reset
)

$ErrorActionPreference = "Stop"

$defaultProjectRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ProjectRoot = $defaultProjectRoot
}

$ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path

$runner = Join-Path $ProjectRoot "scripts\run_elevated_workflow.ps1"
if (-not (Test-Path -LiteralPath $runner)) {
    throw "Runner script was not found: $runner"
}

$resolvedConfigPath = $ConfigPath
if (-not [System.IO.Path]::IsPathRooted($resolvedConfigPath)) {
    $resolvedConfigPath = Join-Path $ProjectRoot $resolvedConfigPath
}
if (-not (Test-Path -LiteralPath $resolvedConfigPath)) {
    throw "Workflow config was not found: $resolvedConfigPath"
}

if ([string]::IsNullOrWhiteSpace($RunAsUser)) {
    $RunAsUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
}

$runnerArgs = @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    "`"$runner`"",
    "-ProjectRoot",
    "`"$ProjectRoot`"",
    "-ConfigPath",
    "`"$resolvedConfigPath`""
)

if ($Submit) {
    $runnerArgs += "-Submit"
}

if ($Reset) {
    $runnerArgs += "-Reset"
}

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument ($runnerArgs -join " ") `
    -WorkingDirectory $ProjectRoot

$principal = New-ScheduledTaskPrincipal `
    -UserId $RunAsUser `
    -LogonType Interactive `
    -RunLevel Highest

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2)

$task = New-ScheduledTask `
    -Action $action `
    -Principal $principal `
    -Settings $settings `
    -Description "Run the tax RPA workflow with elevated privileges."

Register-ScheduledTask `
    -TaskName $TaskName `
    -InputObject $task `
    -Force | Out-Null

Write-Host "Registered scheduled task: $TaskName"
Write-Host "Run as user: $RunAsUser"
Write-Host "Action: powershell.exe $($runnerArgs -join ' ')"
