# Povuci podatke za poslednjih 5 godina (Copernicus API) i exportuj u Supabase
# Za parcelu 1427/2 - Koristi .env iz ndvi_auto i web2

$ErrorActionPreference = "Stop"
# web2 je u Kopernikus-GIS\web2, ndvi_auto je u Kopernikus-GIS\ndvi_auto
$ProjectRoot = Split-Path -Parent $PSScriptRoot
if (-not $ProjectRoot) { $ProjectRoot = "C:\Kopernikus-GIS" }

$NdviAuto = Join-Path $ProjectRoot "ndvi_auto"
$Web2 = Join-Path $ProjectRoot "web2"
$SateliteDir = Join-Path $NdviAuto "satelite"  # ovde export_to_supabase traži CSV

# 5 godina u danima; parcela za web2 (mora da odgovara export_to_supabase.py DEFAULT_PARCEL)
$DaysBack = 5 * 365
$ParcelId = "1427/2"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  POVLAČENJE PODATAKA ZA 5 GODINA" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "PARCEL_ID = $ParcelId" -ForegroundColor Yellow
Write-Host "PARCEL_DAYS_BACK = $DaysBack (5 godina)" -ForegroundColor Yellow
Write-Host "PARCEL_CSV_DIR = $SateliteDir" -ForegroundColor Yellow
Write-Host "ndvi_auto: $NdviAuto" -ForegroundColor Gray
Write-Host ""

# 1) Preuzmi CSV za 5 godina (NDVI, NDRE, NDMI) za parcelu 1427/2 (Kovin)
$env:PARCEL_DAYS_BACK = $DaysBack
$env:PARCEL_ID = $ParcelId
$env:PARCEL_CSV_DIR = $SateliteDir
$env:PARCEL_LAYER = "kovin_dkp_pg"   # parcela 1427/2 je u Kovinu

Push-Location $NdviAuto

Write-Host "[1/4] NDVI CSV (poslednjih 5 godina)..." -ForegroundColor Yellow
& python download_ndvi_parcel_csv.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "  NDVI failed. Proveri GEOSERVER_URL, PARCEL_LAYER, PARCEL_ID u ndvi_auto\.env" -ForegroundColor Red
    Pop-Location
    exit 1
}

Write-Host "[2/4] NDRE CSV (poslednjih 5 godina)..." -ForegroundColor Yellow
& python download_ndre_parcel_csv.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "  NDRE failed." -ForegroundColor Red
    Pop-Location
    exit 1
}

Write-Host "[3/4] NDMI CSV (poslednjih 5 godina)..." -ForegroundColor Yellow
& python download_ndmi_parcel_csv.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "  NDMI failed." -ForegroundColor Red
    Pop-Location
    exit 1
}

Pop-Location

# 2) Učitaj web2 .env za Supabase i pokreni export
if (Test-Path (Join-Path $Web2 ".env")) {
    Get-Content (Join-Path $Web2 ".env") | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
            [System.Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
        }
    }
}

Write-Host "[4/4] Export u Supabase..." -ForegroundColor Yellow
Push-Location $Web2
& python export_to_supabase.py
Pop-Location

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  GOTOVO" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host "Osveži web aplikaciju da vidiš vremensku seriju za 5 godina." -ForegroundColor Cyan
