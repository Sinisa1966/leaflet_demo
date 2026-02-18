# Preuzimanje kompletnog backup-a sa Hetznera u lokalni folder BACKUP.
# Bez parametra: pokrece backup na serveru pa preuzima (moze da traje 5-10 min).
# -DownloadOnly: preuzima samo najnoviji postojeci .tar.gz (bez pokretanja backup-a).

param([switch]$DownloadOnly)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ServerIP = "89.167.39.148"
$SSHKey = "$env:USERPROFILE\.ssh\hetzner_key"
$RemoteDir = "/root/kopernikus-gis"
$LocalBackupDir = Join-Path $ProjectRoot "BACKUP"

if (-not (Test-Path $SSHKey)) {
    Write-Host "Greska: SSH kljuc nije nadjen: $SSHKey" -ForegroundColor Red
    exit 1
}

Write-Host "=== Download Hetzner backup ===" -ForegroundColor Cyan
Write-Host "Server: $ServerIP" -ForegroundColor Gray
Write-Host "Lokalni folder: $LocalBackupDir" -ForegroundColor Gray
if ($DownloadOnly) { Write-Host "Rezim: samo preuzimanje (ne pokrece backup na serveru)" -ForegroundColor Gray }
Write-Host ""

if (-not (Test-Path $LocalBackupDir)) {
    New-Item -ItemType Directory -Path $LocalBackupDir -Force | Out-Null
    Write-Host "Kreiran folder: $LocalBackupDir" -ForegroundColor Gray
}

if (-not $DownloadOnly) {
    Write-Host "[1/3] Pokretanje backup-a na serveru (pg_dump + GeoServer + .env)... moze da traje 5-10 min" -ForegroundColor Cyan
    $fixCrlf = "sed -i 's/\r$//' $RemoteDir/scripts/backup_hetzner.sh 2>/dev/null; true"
    & ssh -i $SSHKey -o StrictHostKeyChecking=no "root@$ServerIP" $fixCrlf | Out-Null
    $runBackup = "cd $RemoteDir && bash scripts/backup_hetzner.sh"
    & ssh -i $SSHKey -o StrictHostKeyChecking=no "root@$ServerIP" $runBackup
    if ($LASTEXITCODE -ne 0) { throw "Backup na serveru nije uspeo." }
    Write-Host ""
}

Write-Host "[2/3] Pronalazim najnoviji backup fajl na serveru..." -ForegroundColor Cyan
$latestName = & ssh -i $SSHKey -o StrictHostKeyChecking=no "root@$ServerIP" "ls -t $RemoteDir/backups/hetzner-full-backup-*.tar.gz 2>/dev/null | head -1 | xargs basename"
$latestName = $latestName.Trim()
if (-not $latestName) {
    Write-Host "Greska: nijedan backup fajl nije nadjen na serveru." -ForegroundColor Red
    exit 1
}
Write-Host "      Fajl: $latestName" -ForegroundColor Gray

$RemoteFile = "$RemoteDir/backups/$latestName"
$LocalFile = Join-Path $LocalBackupDir $latestName

Write-Host ""
Write-Host "[3/3] Preuzimanje u $LocalBackupDir ..." -ForegroundColor Cyan
& scp -i $SSHKey -o StrictHostKeyChecking=no "root@${ServerIP}:$RemoteFile" $LocalFile
if ($LASTEXITCODE -ne 0) { throw "SCP preuzimanje nije uspelo." }

$SizeMB = [math]::Round((Get-Item $LocalFile).Length / 1MB, 2)
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Backup preuzet!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Lokacija: $LocalFile" -ForegroundColor White
Write-Host "  Velicina: $SizeMB MB" -ForegroundColor White
Write-Host ""
Write-Host "  Restore na serveru: bash scripts/restore_hetzner.sh $latestName" -ForegroundColor Gray
Write-Host ""
