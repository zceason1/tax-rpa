param(
    [string]$TaskName = "TaxRpaElevatedWorkflow"
)

$ErrorActionPreference = "Stop"

Start-ScheduledTask -TaskName $TaskName
Write-Host "Started scheduled task: $TaskName"
