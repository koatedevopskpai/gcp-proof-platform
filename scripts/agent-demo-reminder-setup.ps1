<#
.SYNOPSIS
    Register the 06:00 teardown reminder for the five-day agent demo.

.DESCRIPTION
    Creates a one-time Scheduled Task at 28 November 2026 06:00 local time and a
    desktop shortcut for previewing the reminder. The task runs only when you are
    logged on; StartWhenAvailable covers a missed start (for example, the machine was
    off at 06:00).

    The demo was deployed on 23 November 2026 and is scheduled for destruction on
    28 November 2026. A date in the past is rejected.
#>
[CmdletBinding()]
param(
    [datetime]$At = (Get-Date -Year 2026 -Month 11 -Day 28 -Hour 6 -Minute 0 -Second 0),
    [switch]$NoShortcut
)

$ErrorActionPreference = "Stop"

if ($At -lt (Get-Date)) {
    throw "The requested reminder time ($At) is in the past. Choose a future date."
}

$reminder = Join-Path $PSScriptRoot "agent-demo-reminder.ps1"
if (-not (Test-Path $reminder)) {
    throw "missing $reminder"
}

& $reminder -SelfTest

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument (
    "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$reminder`""
)
$trigger = New-ScheduledTaskTrigger -Once -At $At
$principal = New-ScheduledTaskPrincipal `
    -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) `
    -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Days 3)

Register-ScheduledTask `
    -TaskName "Agent demo teardown reminder" `
    -Action $action -Trigger $trigger -Principal $principal -Settings $settings `
    -Force | Out-Null

if (-not $NoShortcut) {
    $desktop = [Environment]::GetFolderPath("Desktop")
    $shortcutPath = Join-Path $desktop "Agent demo teardown reminder.lnk"
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = "powershell.exe"
    $shortcut.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$reminder`""
    $shortcut.WorkingDirectory = $PSScriptRoot
    $shortcut.Description = "Tear down the five-day ADK demo"
    $shortcut.Save()
    Write-Host "shortcut: $shortcutPath"
}

$task = Get-ScheduledTask -TaskName "Agent demo teardown reminder"
$info = Get-ScheduledTaskInfo -TaskName "Agent demo teardown reminder"

Write-Host "task:     $($task.TaskName)"
Write-Host "state:    $($task.State)"
Write-Host "next run: $($info.NextRunTime)"
