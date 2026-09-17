<#
.SYNOPSIS
  Baut aus dem aktuellen Git-HEAD ein Release-Tarball, laedt es auf die VPS
  hoch und deployt es -- in einem Rutsch, damit der scp-Schritt nicht mehr
  vergessen werden kann (ist im Sept. 2026 zweimal passiert: deploy_staging.sh
  meldete "OK", deployte aber ein veraltetes, schon laenger auf dem Server
  liegendes Tarball, weil der Upload-Schritt zwischen "git archive" und dem
  ssh-Aufruf ausgelassen wurde).

.PARAMETER Target
  "staging" (Default, ungefaehrlich) oder "prod" (fragt vor dem eigentlichen
  Deploy noch einmal explizit nach, DB-Backup + Auto-Rollback laufen serverseitig
  ueber release.sh wie gewohnt).

.EXAMPLE
  .\deploy\local_deploy.ps1
  .\deploy\local_deploy.ps1 -Target prod
#>
param(
    [ValidateSet("staging", "prod")]
    [string]$Target = "staging"
)

$ErrorActionPreference = "Stop"

$repoRoot = "C:\Users\wechs\Desktop\openmyconet"
$sshKey   = "$HOME\.ssh\omn_deploy"
$server   = "omn@77.42.64.162"
$tarball  = "$env:TEMP\omn-release.tar.gz"

Set-Location $repoRoot

$commit = git rev-parse --short HEAD
$branch = git rev-parse --abbrev-ref HEAD
$dirty  = git status --porcelain -- openmyconet_server

if ($dirty) {
    Write-Warning "Working tree hat uncommittete Aenderungen unter openmyconet_server/ -- die werden NICHT mitdeployed, nur der committete Stand (HEAD)."
}

Write-Host "==> Baue Tarball aus Commit $commit ($branch) ..." -ForegroundColor Cyan
git archive --format=tar.gz -o $tarball HEAD:openmyconet_server

Write-Host "==> Lade Tarball auf die VPS hoch ..." -ForegroundColor Cyan
scp -i $sshKey $tarball "${server}:/home/omn/incoming/release.tar.gz"

if ($Target -eq "prod") {
    Write-Host ""
    Write-Host "==> ACHTUNG: Deploy auf PROD, Commit $commit ($branch)" -ForegroundColor Red
    $confirm = Read-Host "Wirklich auf PROD deployen? (ja/nein)"
    if ($confirm -ne "ja") {
        Write-Host "Abgebrochen -- Tarball liegt bereits auf dem Server, falls du es dir anders ueberlegst." -ForegroundColor Yellow
        exit 1
    }
    ssh -i $sshKey $server "bash /home/omn/app/deploy/release.sh /home/omn/incoming/release.tar.gz"
    ssh -i $sshKey $server "bash /home/omn/app/deploy/status.sh"
} else {
    Write-Host "==> Deploy auf STAGING, Commit $commit ($branch) ..." -ForegroundColor Cyan
    ssh -i $sshKey $server "bash /home/omn/app-staging/deploy/deploy_staging.sh /home/omn/incoming/release.tar.gz"
}
