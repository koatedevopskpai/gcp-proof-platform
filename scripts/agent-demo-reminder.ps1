<#
.SYNOPSIS
    Persistent on-screen reminder to tear down the five-day agent demo.

.DESCRIPTION
    The scheduled task starts this script at 06:00 on 28 November 2026. The window is
    topmost and stays until you choose an action. "Tear down now" runs
    scripts/agent-demo-down.ps1 -Force in a visible PowerShell window.

    Run with -SelfTest to check the paths without showing the window.
#>
[CmdletBinding()]
param(
    [switch]$SelfTest
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$here = $PSScriptRoot
$down = Join-Path $here "agent-demo-down.ps1"
$reminder = Join-Path $here "agent-demo-reminder.ps1"
$tfDir = [System.IO.Path]::GetFullPath((Join-Path $here "..\infra\terraform\environments\agent-demo"))

if ($SelfTest) {
    foreach ($path in @($down, $tfDir)) {
        if (-not (Test-Path $path)) {
            throw "missing $path"
        }
    }
    Write-Host "self-test ok: $down"
    return
}

if (-not (Test-Path $down)) {
    [System.Windows.Forms.MessageBox]::Show(
        "Cannot find the teardown script: $down",
        "Reminder error",
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Error
    ) | Out-Null
    return
}

$form = New-Object System.Windows.Forms.Form
$form.Text = "Agent demo teardown - due 28 November 2026"
$form.ClientSize = New-Object System.Drawing.Size(520, 250)
$form.StartPosition = "CenterScreen"
$form.TopMost = $true
$form.MaximizeBox = $false
$form.MinimizeBox = $false
$form.FormBorderStyle = "FixedDialog"
$form.BackColor = [System.Drawing.Color]::FromArgb(255, 248, 220)

$title = New-Object System.Windows.Forms.Label
$title.Text = "The five-day ADK demo is still running"
$title.Font = New-Object System.Drawing.Font("Segoe UI", 13, [System.Drawing.FontStyle]::Bold)
$title.AutoSize = $true
$title.Location = New-Object System.Drawing.Point(20, 18)
$form.Controls.Add($title)

$body = New-Object System.Windows.Forms.Label
$body.Text = "Cloud SQL bills while it is idle. The demo was scheduled for teardown on 28 November 2026.`n`nTear it down now, snooze for an hour, or dismiss this reminder."
$body.Font = New-Object System.Drawing.Font("Segoe UI", 10)
$body.AutoSize = $false
$body.Size = New-Object System.Drawing.Size(475, 90)
$body.Location = New-Object System.Drawing.Point(20, 60)
$form.Controls.Add($body)

$tearDown = New-Object System.Windows.Forms.Button
$tearDown.Text = "Tear down now"
$tearDown.Size = New-Object System.Drawing.Size(140, 38)
$tearDown.Location = New-Object System.Drawing.Point(20, 175)
$tearDown.BackColor = [System.Drawing.Color]::FromArgb(176, 0, 32)
$tearDown.ForeColor = [System.Drawing.Color]::White
$tearDown.FlatStyle = "Flat"
$form.Controls.Add($tearDown)

$snooze = New-Object System.Windows.Forms.Button
$snooze.Text = "Snooze 1 hour"
$snooze.Size = New-Object System.Drawing.Size(140, 38)
$snooze.Location = New-Object System.Drawing.Point(180, 175)
$form.Controls.Add($snooze)

$dismiss = New-Object System.Windows.Forms.Button
$dismiss.Text = "Dismiss"
$dismiss.Size = New-Object System.Drawing.Size(100, 38)
$dismiss.Location = New-Object System.Drawing.Point(340, 175)
$form.Controls.Add($dismiss)

$tearDown.Add_Click({
    $answer = [System.Windows.Forms.MessageBox]::Show(
        "Destroy Cloud SQL, Cloud Run, the VPC, the demo BigQuery datasets and secrets?`n`nThis cannot be undone.",
        "Confirm teardown",
        [System.Windows.Forms.MessageBoxButtons]::YesNo,
        [System.Windows.Forms.MessageBoxIcon]::Warning
    )
    if ($answer -ne [System.Windows.Forms.DialogResult]::Yes) {
        return
    }

    $form.Hide()
    $process = Start-Process -FilePath "powershell.exe" -ArgumentList @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-NoExit",
        "-File", "`"$down`"",
        "-Force"
    ) -Wait -PassThru

    if ($process.ExitCode -eq 0) {
        [System.Windows.Forms.MessageBox]::Show(
            "Teardown finished. The demo resources are gone.",
            "Done",
            [System.Windows.Forms.MessageBoxButtons]::OK,
            [System.Windows.Forms.MessageBoxIcon]::Information
        ) | Out-Null
    } else {
        [System.Windows.Forms.MessageBox]::Show(
            "Teardown exited with code $($process.ExitCode). Read the console window, then re-run scripts\agent-demo-down.ps1.",
            "Teardown failed",
            [System.Windows.Forms.MessageBoxButtons]::OK,
            [System.Windows.Forms.MessageBoxIcon]::Error
        ) | Out-Null
    }
    $form.Close()
})

$snooze.Add_Click({
    try {
        $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument (
            "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$reminder`""
        )
        $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddHours(1)
        $principal = New-ScheduledTaskPrincipal `
            -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) `
            -LogonType Interactive -RunLevel Limited
        $settings = New-ScheduledTaskSettingsSet `
            -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

        Register-ScheduledTask `
            -TaskName "Agent demo teardown reminder (snooze)" `
            -Action $action -Trigger $trigger -Principal $principal -Settings $settings `
            -Force | Out-Null

        [System.Windows.Forms.MessageBox]::Show(
            "Snoozed. This window will return in one hour.",
            "Snoozed",
            [System.Windows.Forms.MessageBoxButtons]::OK,
            [System.Windows.Forms.MessageBoxIcon]::Information
        ) | Out-Null
        $form.Close()
    } catch {
        [System.Windows.Forms.MessageBox]::Show(
            "Could not schedule the snooze: $($_.Exception.Message)",
            "Snooze failed",
            [System.Windows.Forms.MessageBoxButtons]::OK,
            [System.Windows.Forms.MessageBoxIcon]::Error
        ) | Out-Null
    }
})

$dismiss.Add_Click({ $form.Close() })
$form.Add_Shown({ $form.Activate() })

[System.Windows.Forms.Application]::Run($form)
