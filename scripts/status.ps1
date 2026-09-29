<#
.SYNOPSIS
    Show the state of the gcp-proof-platform always-on stack + est. monthly cost.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'SilentlyContinue'
$here = $PSScriptRoot
$tfDir = [System.IO.Path]::GetFullPath((Join-Path $here '..\infra\terraform\environments\dev'))

$url = (terraform -chdir=$tfDir output -raw url 2>$null).Trim()
if (-not $url) {
    Write-Host "==> No stack found - cost ~$0/month."
    Write-Host "    Bring it up with:  .\up.ps1"
    return
}

Write-Host "==> ALWAYS-ON STACK IS UP"
Write-Host "    Gateway : $url"
try {
    $ip = ($url -replace '^http://' -replace ':3002$')
    $resp = Invoke-WebRequest -Uri "http://${ip}:3002/health" -TimeoutSec 10 -UseBasicParsing
    Write-Host "    Health  : $($resp.StatusCode) $($resp.Content)"
}
catch {
    Write-Warning "    Health  : UNREACHABLE (still booting or budget-stopped)"
}
Write-Host "    Est cost: ~USD 12-14/month always-on (within the USD 20 budget)"