param(
    [string]$TaskName = "TaxRpaElevatedWorkflow"
)

$ErrorActionPreference = "Stop"

$scheduledTaskName = $TaskName
if (-not $scheduledTaskName.StartsWith("\")) {
    $scheduledTaskName = "\$scheduledTaskName"
}

& schtasks.exe "/Run" "/TN" $scheduledTaskName
if ($LASTEXITCODE -ne 0) {
    throw "Failed to start scheduled task: $scheduledTaskName. schtasks.exe exit code: $LASTEXITCODE"
}

Write-Host "Started scheduled task: $scheduledTaskName"
