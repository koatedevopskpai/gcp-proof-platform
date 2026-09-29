<#
.SYNOPSIS
    Tear down the gcp-proof-platform always-on stack (back to ~$0/month).

.PARAMETER Force
    Skip the confirmation prompt.
#>
[CmdletBinding()]
param([switch]$Force)

$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
$tfDir = [System.IO.Path]::GetFullPath((Join-Path $here '..\infra\terraform\environments\dev'))

Write-Host "==> gcp-proof-platform DOWN"

if (-not $Force) {
    $answer = Read-Host "==> This DESTROYS the VM, BigQuery dataset tables, Cloud Run job and budget resources. Continue? [y/N]"
    if ($answer -notin @('y','Y')) { Write-Host "Aborted."; return }
}

Push-Location $tfDir
try {
    $varFile = Join-Path $tfDir 'terraform.tfvars'
    $args = @("destroy", "-auto-approve")
    if (Test-Path $varFile) { $args += "-var-file=$varFile" }
    terraform @args
    if ($LASTEXITCODE -ne 0) { throw "terraform destroy failed" }
}
finally { Pop-Location }

Write-Host "==> gcp-proof-platform DOWN - cost back to ~$0/month. Bring it back with .\up.ps1"