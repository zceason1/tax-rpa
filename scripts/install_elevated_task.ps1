param(
    [string]$TaskName = "TaxRpaElevatedWorkflow",
    [string]$ConfigPath = "config\person_import.json",
    [string]$RunAsUser = "",
    [string]$GrantRunToUser = "",
    [switch]$Submit,
    [switch]$Reset
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$artifacts = Join-Path $projectRoot "artifacts"
New-Item -ItemType Directory -Force -Path $artifacts | Out-Null

$logPath = Join-Path $artifacts "elevated-task-register.log"
$bootstrapPath = Join-Path $artifacts "elevated-task-register-bootstrap.ps1"
$registerScript = Join-Path $PSScriptRoot "register_elevated_task.ps1"
if (-not (Test-Path -LiteralPath $registerScript)) {
    throw "Register script was not found: $registerScript"
}

$bootstrap = @'
param(
    [string]$RegisterScript,
    [string]$TaskName,
    [string]$ProjectRoot,
    [string]$ConfigPath,
    [string]$RunAsUser,
    [string]$GrantRunToUser,
    [string]$LogPath,
    [switch]$Submit,
    [switch]$Reset
)

$ErrorActionPreference = "Stop"

$registerArgs = @{
    TaskName = $TaskName
    ProjectRoot = $ProjectRoot
    ConfigPath = $ConfigPath
}

if (-not [string]::IsNullOrWhiteSpace($RunAsUser)) {
    $registerArgs.RunAsUser = $RunAsUser
}

if (-not [string]::IsNullOrWhiteSpace($GrantRunToUser)) {
    $registerArgs.GrantRunToUser = $GrantRunToUser
}

if ($Submit) {
    $registerArgs.Submit = $true
}

if ($Reset) {
    $registerArgs.Reset = $true
}

& $RegisterScript @registerArgs *> $LogPath
"--- query ---" >> $LogPath
schtasks.exe /Query /TN $TaskName /FO LIST /V >> $LogPath 2>&1
'@

Set-Content -LiteralPath $bootstrapPath -Value $bootstrap -Encoding UTF8

$bootstrapArgs = @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    $bootstrapPath,
    "-RegisterScript",
    $registerScript,
    "-TaskName",
    $TaskName,
    "-ProjectRoot",
    $projectRoot,
    "-ConfigPath",
    $ConfigPath,
    "-LogPath",
    $logPath
)

if (-not [string]::IsNullOrWhiteSpace($RunAsUser)) {
    $bootstrapArgs += @("-RunAsUser", $RunAsUser)
}

if (-not [string]::IsNullOrWhiteSpace($GrantRunToUser)) {
    $bootstrapArgs += @("-GrantRunToUser", $GrantRunToUser)
}

if ($Submit) {
    $bootstrapArgs += "-Submit"
}

if ($Reset) {
    $bootstrapArgs += "-Reset"
}

$process = Start-Process `
    -FilePath "powershell.exe" `
    -Verb RunAs `
    -Wait `
    -PassThru `
    -ArgumentList $bootstrapArgs

if ($process.ExitCode -ne 0) {
    throw "Elevated task registration failed with exit code $($process.ExitCode). See log: $logPath"
}

Write-Host "Registered elevated task: $TaskName"
Write-Host "Log: $logPath"
