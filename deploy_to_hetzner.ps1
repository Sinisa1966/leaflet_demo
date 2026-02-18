# Deploy Kopernikus-GIS na Hetzner server
# Iskljucuje: web, web2, .git

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot
$ServerIP = "89.167.39.148"
$SSHKey = "$env:USERPROFILE\.ssh\hetzner_key"
$RemoteDir = "/root/kopernikus-gis"

Write-Host "[1/4] Pravim arhivu (bez web, web2, .git)..." -ForegroundColor Cyan
$TempDir = Join-Path $env:TEMP "kopernikus-deploy"
if (Test-Path $TempDir) { Remove-Item $TempDir -Recurse -Force }
New-Item -ItemType Directory -Path $TempDir | Out-Null

# Kopiraj sve osim web, web2, .git
$Exclude = @("web", "web2", ".git", "__pycache__", ".cursor", "*.pyc")
Get-ChildItem $ProjectRoot -Force | Where-Object {
    $item = $_
    $excluded = $false
    foreach ($e in $Exclude) {
        if ($e -like "*.*") {
            if ($item.Name -like $e) { $excluded = $true; break }
        } elseif ($item.Name -eq $e) { $excluded = $true; break }
    }
    -not $excluded
} | ForEach-Object {
    $dest = Join-Path $TempDir $_.Name
    Copy-Item $_.FullName -Destination $dest -Recurse -Force -ErrorAction SilentlyContinue
}

# Ukloni __pycache__ iz kopiranih foldera
Get-ChildItem $TempDir -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force

Write-Host "[2/4] Kompresujem..." -ForegroundColor Cyan
$ArchivePath = Join-Path $env:TEMP "kopernikus-deploy.tar.gz"
if (Test-Path $ArchivePath) { Remove-Item $ArchivePath -Force }

# Koristi tar (Windows 10+ ima ugrađen)
Push-Location $TempDir
& tar -czvf $ArchivePath *
Pop-Location
Remove-Item $TempDir -Recurse -Force

$SizeMB = [math]::Round((Get-Item $ArchivePath).Length / 1MB, 2)
Write-Host "      Arhiva: $SizeMB MB" -ForegroundColor Gray

Write-Host "[3/4] Kopiram na server preko SCP..." -ForegroundColor Cyan
& scp -i $SSHKey -o StrictHostKeyChecking=no $ArchivePath "root@${ServerIP}:/tmp/kopernikus-deploy.tar.gz"
if ($LASTEXITCODE -ne 0) { throw "SCP failed" }

Write-Host "[4/4] Ekstrahujem na serveru..." -ForegroundColor Cyan
$Cmd = "mkdir -p $RemoteDir; tar -xzf /tmp/kopernikus-deploy.tar.gz -C $RemoteDir; rm -f /tmp/kopernikus-deploy.tar.gz; if [ ! -f $RemoteDir/ndvi_auto/.env ]; then cp $RemoteDir/ndvi_auto/env.example $RemoteDir/ndvi_auto/.env; echo 'Kreiran .env iz env.example'; fi; chmod 600 $RemoteDir/ndvi_auto/.env 2>/dev/null; echo ''; ls -la $RemoteDir"
& ssh -i $SSHKey -o StrictHostKeyChecking=no "root@$ServerIP" $Cmd

Remove-Item $ArchivePath -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Deploy uspesan!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Sledeci koraci:" -ForegroundColor Yellow
Write-Host "  1. SSH: ssh -i `$env:USERPROFILE\.ssh\hetzner_key root@$ServerIP" -ForegroundColor White
Write-Host "  2. Uredi .env: nano $RemoteDir/ndvi_auto/.env  (CDSE_CLIENT_ID, CDSE_CLIENT_SECRET)" -ForegroundColor White
Write-Host "  3. Pokreni: cd $RemoteDir && docker compose -f docker-compose.hetzner.yml up -d" -ForegroundColor White
Write-Host "  4. Posle ~30s: bash scripts/setup_geoserver_hetzner.sh  (opstine, kat-opstine, WFS)" -ForegroundColor White
Write-Host ""
Write-Host "  Podsetnik: docs/PODSETNIK_DEPLOY_HETZNER.md" -ForegroundColor Gray
Write-Host ""
