<#
.SYNOPSIS
    Destroy the five-day agent demo.

.DESCRIPTION
    Removes the agent-demo Cloud Run services/job, Cloud SQL instance, VPC, secrets,
    service accounts and the agent_demo_* BigQuery datasets. The dev environment and
    the evaluation path are separate and untouched.
#>
[CmdletBinding()]
param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$tfDir = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\infra\terraform\environments\agent-demo"))

if (-not $Force) {
    $answer = Read-Host "Destroy the agent demo (Cloud SQL, Cloud Run, demo BigQuery, secrets)? Type destroy to continue"
    if ($answer -ne "destroy") {
        Write-Host "aborted"
        exit 1
    }
}

terraform -chdir=$tfDir destroy -auto-approve
