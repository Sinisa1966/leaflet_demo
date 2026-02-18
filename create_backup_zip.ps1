# PowerShell Script za Kreiranje ZIP Backup-a
# Kopernikus-GIS Project Backup

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  KOPERNIKUS-GIS BACKUP CREATOR" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Priprema
$projectRoot = "C:\Kopernikus-GIS"
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupName = "kopernikus-gis-backup-$timestamp"
$tempDir = "C:\Temp\$backupName"
$outputZip = "C:\$backupName.zip"

Write-Host "[1/6] Priprema backup-a..." -ForegroundColor Yellow
Write-Host "  - Source: $projectRoot" -ForegroundColor Gray
Write-Host "  - Output: $outputZip" -ForegroundColor Gray
Write-Host ""

# Kreiraj temp direktorijum
if (Test-Path $tempDir) {
    Remove-Item $tempDir -Recurse -Force
}
New-Item -ItemType Directory -Path $tempDir -Force | Out-Null

# 2. Kopiraj fajlove (osim isključenih)
Write-Host "[2/6] Kopiranje fajlova..." -ForegroundColor Yellow

$excludePatterns = @(
    ".git",
    "pgdata",
    "geoserver_data\data",
    "__pycache__",
    "node_modules",
    "*.pyc",
    "*.pyo",
    ".vscode",
    ".idea",
    "*.log",
    "terminals"
)

Write-Host "  - Isključeni folderi/fajlovi:" -ForegroundColor Gray
foreach ($pattern in $excludePatterns) {
    Write-Host "    × $pattern" -ForegroundColor DarkGray
}

# Kopiraj sve osim isključenih
$itemsToCopy = Get-ChildItem -Path $projectRoot -Recurse | Where-Object {
    $item = $_
    $exclude = $false
    
    foreach ($pattern in $excludePatterns) {
        if ($item.FullName -like "*\$pattern\*" -or $item.FullName -like "*\$pattern") {
            $exclude = $true
            break
        }
        if ($pattern -like "*.*" -and $item.Name -like $pattern) {
            $exclude = $true
            break
        }
    }
    
    -not $exclude
}

$totalItems = $itemsToCopy.Count
$currentItem = 0

foreach ($item in $itemsToCopy) {
    $currentItem++
    $relativePath = $item.FullName.Substring($projectRoot.Length + 1)
    $destPath = Join-Path $tempDir $relativePath
    
    if ($currentItem % 50 -eq 0 -or $currentItem -eq $totalItems) {
        $percent = [math]::Round(($currentItem / $totalItems) * 100, 1)
        Write-Progress -Activity "Kopiranje fajlova" -Status "$currentItem od $totalItems ($percent%)" -PercentComplete $percent
    }
    
    if ($item.PSIsContainer) {
        if (-not (Test-Path $destPath)) {
            New-Item -ItemType Directory -Path $destPath -Force | Out-Null
        }
    } else {
        $destDir = Split-Path $destPath -Parent
        if (-not (Test-Path $destDir)) {
            New-Item -ItemType Directory -Path $destDir -Force | Out-Null
        }
        Copy-Item $item.FullName $destPath -Force
    }
}

Write-Progress -Activity "Kopiranje fajlova" -Completed
Write-Host "  ✓ Kopirano $totalItems fajlova/foldera" -ForegroundColor Green
Write-Host ""

# 3. Kreiraj README sa dodatnim informacijama
Write-Host "[3/6] Kreiranje README fajlova..." -ForegroundColor Yellow

$readmeContent = @"
# KOPERNIKUS-GIS BACKUP

**Datum kreiranja:** $(Get-Date -Format "dd.MM.yyyy HH:mm:ss")
**Verzija:** 2026-02-09 (Working Version)
**Backup ID:** $timestamp

---

## 📦 SADRŽAJ ARHIVE

Ova ZIP arhiva sadrži kompletan Kopernikus-GIS projekat spreman za instalaciju na novom računaru.

### Uključeni Folderi:
- ✅ **ndvi_auto/** - Python scripts za processing
- ✅ **web/** - Frontend files (ako postoje)
- ✅ **DKP-Kovin/** - Kovin parcel shapefiles (ako postoje)
- ✅ **DKP-Vrsac/** - Vršac parcel shapefiles (ako postoje)
- ✅ **satelite/** - CSV i GeoTIFF outputs
- ✅ **docker-compose.yml** - Docker konfiguracija
- ✅ **leaflet_demo.html** - Main web app
- ✅ **.gitignore** - Git ignore rules
- ✅ **Documentation files** (*.md)

### Isključeni Folderi (regenerišu se pri instalaciji):
- ❌ **.git/** - Git history (veliki, ne treba)
- ❌ **pgdata/** - PostgreSQL data (regeneriše se)
- ❌ **geoserver_data/data/** - GeoServer data (upload-uje se ponovo)
- ❌ **__pycache__/** - Python cache (regeneriše se)
- ❌ **node_modules/** - Node.js dependencies (ako postoje)
- ❌ **terminals/** - Cursor terminal logs

---

## 🚀 INSTALACIJA

**Pročitaj:** \`INSTALACIJA_NOVI_RACUNAR.md\` - Kompletan vodič korak-po-korak!

### Brzi Start:
1. Ekstraktuj ZIP arhivu
2. Instaliraj Docker Desktop
3. Kopiraj \`ndvi_auto/env.example\` → \`ndvi_auto/.env\`
4. Popuni Copernicus credentials u \`.env\`
5. Pokreni: \`docker-compose up -d\`
6. Učitaj parcele u PostGIS
7. Konfiguriši GeoServer layere
8. Otvori: http://localhost:8088/leaflet_demo.html

---

## 📊 STATISTIKA BACKUP-A

**Verzija sistema:** NDRE zones implemented, cloud masking, dual-layer value query
**Test parcela:** 1427/2 (Kovin)
**Implementirani indeksi:** NDVI, NDMI, NDRE, NDRE Zones

**Poznati bugovi:** Nema (sistem testiran i funkcionalan)

**Performance:**
- Male parcele (< 10 ha): 25-35 sekundi
- Srednje parcele (10-100 ha): 30-45 sekundi
- Velike parcele (> 100 ha): Preporučeno tiling ili smanjenje rezolucije

---

## 📞 SUPPORT

Za pomoć pri instalaciji, pogledaj:
- \`INSTALACIJA_NOVI_RACUNAR.md\` - Detaljan vodič
- \`WORKING_VERSION_2026-02-09.md\` - Sistemska dokumentacija
- \`CHANGELOG_2026-02.md\` - Lista promena
- \`QUICK_START.md\` - Brzi vodič za korisnike

---

## ⚠️ VAŽNE NAPOMENE

### Pre Instalacije:
1. ✅ Proveri da imaš Docker Desktop instaliran
2. ✅ Proveri da imaš minimum 8 GB RAM (preporučeno 16 GB)
3. ✅ Proveri da imaš ~50 GB slobodnog prostora
4. ✅ Nabavi Copernicus DataSpace credentials (https://dataspace.copernicus.eu/)

### Posle Instalacije:
1. ⚠️ Promeni default GeoServer password (\`admin/geoserver\`)
2. ⚠️ Promeni default PostgreSQL password (\`postgres/postgres\`)
3. ⚠️ Dodaj \`restart: always\` u docker-compose.yml (za production)
4. ⚠️ Setup backup strategiju (automatizovani backup svakog dana)

---

## ✅ CHECKLIST PRE KORIŠĆENJA NA PRODUKCIJI

- [ ] Redis cache layer implementiran
- [ ] API authentication (API keys)
- [ ] Rate limiting
- [ ] Monitoring (Prometheus/Grafana)
- [ ] Automated backups
- [ ] Health checks
- [ ] SSL/TLS certificates
- [ ] Firewall rules
- [ ] User roles/permissions

**Za produkciju, vidi: MITIGATION PLAN u \`CHANGELOG_2026-02.md\`**

---

Srećna instalacija! 🚀🌍
"@

Set-Content -Path (Join-Path $tempDir "README.txt") -Value $readmeContent -Encoding UTF8
Write-Host "  ✓ README.txt kreiran" -ForegroundColor Green
Write-Host ""

# 4. Kreiraj manifest fajl
Write-Host "[4/6] Kreiranje manifest fajla..." -ForegroundColor Yellow

$manifest = @{
    backup_id = $timestamp
    created_at = (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
    version = "2026-02-09"
    source_path = $projectRoot
    excluded_patterns = $excludePatterns
    total_files = $totalItems
    instructions = "See INSTALACIJA_NOVI_RACUNAR.md for installation steps"
} | ConvertTo-Json -Depth 3

Set-Content -Path (Join-Path $tempDir "backup_manifest.json") -Value $manifest -Encoding UTF8
Write-Host "  ✓ backup_manifest.json kreiran" -ForegroundColor Green
Write-Host ""

# 5. Kreiraj ZIP arhivu
Write-Host "[5/6] Kreiranje ZIP arhive..." -ForegroundColor Yellow
Write-Host "  - Kompresovanje..." -ForegroundColor Gray

if (Test-Path $outputZip) {
    Remove-Item $outputZip -Force
}

Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory($tempDir, $outputZip, [System.IO.Compression.CompressionLevel]::Optimal, $false)

$zipSize = (Get-Item $outputZip).Length / 1MB
Write-Host "  ✓ ZIP arhiva kreirana: $outputZip" -ForegroundColor Green
Write-Host "  ✓ Veličina: $([math]::Round($zipSize, 2)) MB" -ForegroundColor Green
Write-Host ""

# 6. Cleanup
Write-Host "[6/6] Čišćenje privremenih fajlova..." -ForegroundColor Yellow
Remove-Item $tempDir -Recurse -Force
Write-Host "  ✓ Temp direktorijum obrisan" -ForegroundColor Green
Write-Host ""

# Završetak
Write-Host "================================================" -ForegroundColor Green
Write-Host "  ✅ BACKUP USPEŠNO KREIRAN!" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Green
Write-Host ""
Write-Host "📦 ZIP Arhiva:" -ForegroundColor Cyan
Write-Host "   $outputZip" -ForegroundColor White
Write-Host ""
Write-Host "📊 Statistika:" -ForegroundColor Cyan
Write-Host "   - Broj fajlova: $totalItems" -ForegroundColor White
Write-Host "   - Veličina: $([math]::Round($zipSize, 2)) MB" -ForegroundColor White
Write-Host ""
Write-Host "📖 Sledeći koraci:" -ForegroundColor Cyan
Write-Host "   1. Kopiraj ZIP na novi računar" -ForegroundColor White
Write-Host "   2. Ekstraktuj arhivu" -ForegroundColor White
Write-Host "   3. Pročitaj INSTALACIJA_NOVI_RACUNAR.md" -ForegroundColor White
Write-Host "   4. Sledi instrukcije korak-po-korak" -ForegroundColor White
Write-Host ""
Write-Host "Pritisnite bilo koje dugme za izlaz..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
