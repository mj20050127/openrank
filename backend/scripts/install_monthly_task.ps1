param(
    [string]$TaskName = "OpenSage Monthly OpenDigger Sync",
    [string]$StartTime = "03:00"
)

$ErrorActionPreference = "Stop"
$Runner = (Resolve-Path (Join-Path $PSScriptRoot "run_monthly_task.ps1")).Path
$Quote = [char]34
$TaskCommand = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Quote$Runner$Quote"

schtasks.exe /Create /TN $TaskName /TR $TaskCommand /SC MONTHLY /D 3 /ST $StartTime /F | Out-Host
if ($LASTEXITCODE -ne 0) { throw "Unable to create scheduled task." }

$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 30) -ExecutionTimeLimit (New-TimeSpan -Hours 12)
Set-ScheduledTask -TaskName $TaskName -Settings $Settings | Out-Null

Write-Output "Installed '$TaskName': monthly on day 3 at $StartTime, with missed-run recovery and retries."