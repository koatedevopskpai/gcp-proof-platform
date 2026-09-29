<#
.SYNOPSIS
    Bring the gcp-proof-platform always-on stack UP on GCP.

.DESCRIPTION
    Runs terraform apply for infra/terraform/environments/dev, then prints the
    always-on URLs. Provisioning is ~4-6 minutes; the VM then clones the repo and
    builds the stack via its startup script (allow a few more minutes).

.PARAMETER EnableGke
    Also provision the optional ephemeral GKE cluster (NOT part of the $20 budget).
#>
[CmdletBinding()]
param([switch]$EnableGke, [switch]$SkipApply)

$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
$tfDir = [System.IO.Path]::GetFullPath((Join-Path $here '..\infra\terraform\environments\dev'))

if (-not (Get-Command terraform -ErrorAction SilentlyContinue)) { throw "terraform not on PATH" }
if (-not (Get-Command gcloud -ErrorAction SilentlyContinue)) { throw "gcloud not on PATH" }

Write-Host "==> gcp-proof-platform UP (account: $((gcloud config get-value account 2>&1)))"
gcloud config get-value project 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) { throw "gcloud not authenticated" }

if (-not $SkipApply) {
    Push-Location $tfDir
    try {
        if (-not (Test-Path (Join-Path $tfDir '.terraform'))) { terraform init -input=false }
        $varFile = Join-Path $tfDir 'terraform.tfvars'
        $args = @("apply", "-auto-approve")
        if (Test-Path $varFile) { $args += "-var-file=$varFile" }
        if ($EnableGke) { $args += "-var=enable_gke=true" }
        terraform @args
        if ($LASTEXITCODE -ne 0) { throw "terraform apply failed" }
    }
    finally { Pop-Location }
}

$url = (terraform -chdir=$tfDir output -raw url).Trim()
$health = (terraform -chdir=$tfDir output -raw health_url).Trim()
$ssh = (terraform -chdir=$tfDir output -raw ssh_command).Trim()

Write-Host ""
Write-Host "==> ALWAYS-ON ENVIRONMENT IS UP"
Write-Host "    Gateway : $url"
Write-Host "    Health  : $health"
Write-Host ""
Write-Host "    First boot clones the repo and builds the stack (a few minutes)."
Write-Host "    Check readiness:  curl -s $health"
Write-Host "    SSH:              $ssh"
Write-Host "    Redeploy:         .\deploy.ps1   |   Teardown: .\down.ps1"