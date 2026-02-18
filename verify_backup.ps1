# Verification Script - Kopernikus-GIS Backup
# Run this after extracting ZIP to verify all required files are present

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "KOPERNIKUS-GIS BACKUP VERIFICATION" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$currentDir = Get-Location

# Required files
$requiredFiles = @(
    "docker-compose.yml",
    "leaflet_demo.html",
    "INSTALACIJA_NOVI_RACUNAR.md",
    "WORKING_VERSION_2026-02-09.md",
    "CHANGELOG_2026-02.md",
    "QUICK_START.md",
    "ndvi_auto\env.example",
    "ndvi_auto\parcel_server.py",
    "ndvi_auto\download_and_publish.py",
    "ndvi_auto\download_ndre_parcel.py",
    "ndvi_auto\download_ndre_zones_parcel.py",
    "ndvi_auto\download_ndre_value_parcel.py"
)

# Required directories
$requiredDirs = @(
    "ndvi_auto",
    "ndvi_auto\data",
    "satelite"
)

$missingFiles = @()
$missingDirs = @()

Write-Host "Checking required files..." -ForegroundColor Yellow
foreach ($file in $requiredFiles) {
    $fullPath = Join-Path $currentDir $file
    if (Test-Path $fullPath) {
        Write-Host "  [OK] $file" -ForegroundColor Green
    } else {
        Write-Host "  [MISSING] $file" -ForegroundColor Red
        $missingFiles += $file
    }
}

Write-Host ""
Write-Host "Checking required directories..." -ForegroundColor Yellow
foreach ($dir in $requiredDirs) {
    $fullPath = Join-Path $currentDir $dir
    if (Test-Path $fullPath) {
        Write-Host "  [OK] $dir/" -ForegroundColor Green
    } else {
        Write-Host "  [MISSING] $dir/" -ForegroundColor Red
        $missingDirs += $dir
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan

if ($missingFiles.Count -eq 0 -and $missingDirs.Count -eq 0) {
    Write-Host "VERIFICATION PASSED!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "All required files and directories are present." -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Yellow
    Write-Host "1. Read INSTALACIJA_NOVI_RACUNAR.md" -ForegroundColor White
    Write-Host "2. Install Docker Desktop" -ForegroundColor White
    Write-Host "3. Create .env file from env.example" -ForegroundColor White
    Write-Host "4. Run: docker-compose up -d" -ForegroundColor White
} else {
    Write-Host "VERIFICATION FAILED!" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
    Write-Host ""
    if ($missingFiles.Count -gt 0) {
        Write-Host "Missing files:" -ForegroundColor Red
        foreach ($file in $missingFiles) {
            Write-Host "  - $file" -ForegroundColor Red
        }
    }
    if ($missingDirs.Count -gt 0) {
        Write-Host "Missing directories:" -ForegroundColor Red
        foreach ($dir in $missingDirs) {
            Write-Host "  - $dir" -ForegroundColor Red
        }
    }
    Write-Host ""
    Write-Host "Please re-extract the ZIP archive or contact support." -ForegroundColor Yellow
}

Write-Host ""
