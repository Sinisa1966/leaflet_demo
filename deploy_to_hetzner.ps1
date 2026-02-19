# Deploy Kopernikus-GIS na Hetzner server
# - Koristi docker-compose.hetzner.yml (ne lokalni docker-compose.yml!)
# - NIKAD ne dira geoserver/db kontejnere (--no-deps)
# - Automatski restartuje nginx nakon deploya
# - Proverava da li GeoServer workspace postoji; ako ne, pokrece setup

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot
$ServerIP = "89.167.39.148"
$SSHKey = "$env:USERPROFILE\.ssh\hetzner_key"
$RemoteDir = "/root/kopernikus-gis"
$ComposeFile = "docker-compose.hetzner.yml"
$GeoPassword = "Stojakovic2026!"

function SSH-Exec($cmd) {
    & ssh -i $SSHKey -o StrictHostKeyChecking=no "root@$ServerIP" $cmd
    if ($LASTEXITCODE -ne 0) { throw "SSH command failed: $cmd" }
}

# ── 1. Arhiva ──────────────────────────────────────────────
Write-Host "[1/6] Pravim arhivu (bez web, web2, .git)..." -ForegroundColor Cyan
$TempDir = Join-Path $env:TEMP "kopernikus-deploy"
if (Test-Path $TempDir) { Remove-Item $TempDir -Recurse -Force }
New-Item -ItemType Directory -Path $TempDir | Out-Null

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
    Copy-Item $_.FullName -Destination (Join-Path $TempDir $_.Name) -Recurse -Force -ErrorAction SilentlyContinue
}
Get-ChildItem $TempDir -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force

# ── 2. Kompresija ─────────────────────────────────────────
Write-Host "[2/6] Kompresujem..." -ForegroundColor Cyan
$ArchivePath = Join-Path $env:TEMP "kopernikus-deploy.tar.gz"
if (Test-Path $ArchivePath) { Remove-Item $ArchivePath -Force }
Push-Location $TempDir
& tar -czf $ArchivePath *
Pop-Location
Remove-Item $TempDir -Recurse -Force
$SizeMB = [math]::Round((Get-Item $ArchivePath).Length / 1MB, 2)
Write-Host "      Arhiva: $SizeMB MB" -ForegroundColor Gray

# ── 3. Upload ─────────────────────────────────────────────
Write-Host "[3/6] Kopiram na server (SCP)..." -ForegroundColor Cyan
& scp -i $SSHKey -o StrictHostKeyChecking=no $ArchivePath "root@${ServerIP}:/tmp/kopernikus-deploy.tar.gz"
if ($LASTEXITCODE -ne 0) { throw "SCP failed" }
Remove-Item $ArchivePath -Force -ErrorAction SilentlyContinue

# ── 4. Ekstrakcija + .env ─────────────────────────────────
Write-Host "[4/6] Ekstrahujem na serveru..." -ForegroundColor Cyan
SSH-Exec "mkdir -p $RemoteDir && tar -xzf /tmp/kopernikus-deploy.tar.gz -C $RemoteDir && rm -f /tmp/kopernikus-deploy.tar.gz && if [ ! -f $RemoteDir/ndvi_auto/.env ]; then cp $RemoteDir/ndvi_auto/env.example $RemoteDir/ndvi_auto/.env && echo 'Kreiran .env iz env.example'; fi && chmod 600 $RemoteDir/ndvi_auto/.env 2>/dev/null && echo 'Ekstrakcija OK'"

# ── 5. Rebuild SAMO parcel_server i ndvi_updater ──────────
# VAZNO: --no-deps = NE DIRAJ geoserver i db kontejnere!
Write-Host "[5/6] Rebuild parcel_server + ndvi_updater (BEZ geoservera)..." -ForegroundColor Cyan
SSH-Exec "cd $RemoteDir && docker compose -f $ComposeFile up -d --build --no-deps parcel_server ndvi_updater && docker restart ndvi_web && echo 'Kontejneri OK'"

# ── 6. Provera GeoServer workspace ───────────────────────
Write-Host "[6/6] Proveravam GeoServer workspace..." -ForegroundColor Cyan
Start-Sleep -Seconds 5

$wsCheck = & ssh -i $SSHKey -o StrictHostKeyChecking=no "root@$ServerIP" "curl -s -o /dev/null -w '%{http_code}' 'http://localhost:8088/geoserver/moj_projekat/ows?service=WFS&version=1.0.0&request=GetCapabilities'"
if ($wsCheck -ne "200") {
    Write-Host "      GeoServer workspace ne postoji - pokrecem setup..." -ForegroundColor Yellow
    # Sacekaj da GeoServer bude spreman
    $ready = $false
    for ($i = 0; $i -lt 12; $i++) {
        Start-Sleep -Seconds 5
        $code = & ssh -i $SSHKey -o StrictHostKeyChecking=no "root@$ServerIP" "curl -s -o /dev/null -w '%{http_code}' http://localhost:8088/geoserver/web/"
        if ($code -eq "200" -or $code -eq "302") { $ready = $true; break }
        Write-Host "      GeoServer se pokrece... ($code)" -ForegroundColor Gray
    }
    if (-not $ready) {
        Write-Host "      UPOZORENJE: GeoServer nije spreman. Pokreni rucno: bash scripts/setup_geoserver_hetzner.sh" -ForegroundColor Red
    } else {
        SSH-Exec "cd $RemoteDir && bash scripts/setup_geoserver_hetzner.sh"
    }
} else {
    Write-Host "      GeoServer workspace OK - nema potrebe za setup" -ForegroundColor Green
}

# ── Gotovo ────────────────────────────────────────────────
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Deploy zavrsen!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "  URL: http://${ServerIP}:8088/leaflet_demo_hetzner.html" -ForegroundColor White
Write-Host ""
