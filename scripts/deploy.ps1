<#
.SYNOPSIS
    Redeploy the app to the always-on VM over gcloud SSH (git pull + docker compose up).

.DESCRIPTION
    Uses `gcloud compute ssh` with your current credentials - no SSH key to manage.
    Requires roles/compute.osLogin or the instanceAdmin/SSH-key permissions.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
$tfDir = [System.IO.Path]::GetFullPath((Join-Path $here '..\infra\terraform\environments\dev'))

$zone = (terraform -chdir=$tfDir output -raw ssh_command 2>$null) -replace '.*--zone (\S+).*', '$1'
$vm = (terraform -chdir=$tfDir output -raw ssh_command 2>$null) -replace '.*compute ssh (\S+).*', '$1'
if (-not $vm) { throw "VM not found - run .\up.ps1 first." }

Write-Host "==> Deploying to $vm (zone $zone)"
gcloud compute ssh $vm --zone $zone --quiet --command @"
set -e
cd /opt/gcp-proof-platform
git pull --ff-only || true
sudo docker compose up -d --build
sleep 10
curl -fsS http://localhost:3002/health && echo ""
echo 'DEPLOY OK'
"@

if ($LASTEXITCODE -ne 0) { throw "deploy failed (exit $LASTEXITCODE)" }
Write-Host "==> DEPLOY OK"