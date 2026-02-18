# Simple Backup Script - Kopernikus-GIS
# Creates ZIP archive excluding unnecessary files

$projectRoot = "C:\Kopernikus-GIS"
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupName = "kopernikus-gis-backup-$timestamp"
$desktopPath = [Environment]::GetFolderPath("Desktop")
$tempDir = Join-Path $env:TEMP $backupName
$outputZip = Join-Path $desktopPath "$backupName.zip"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "KOPERNIKUS-GIS BACKUP CREATOR" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Source: $projectRoot" -ForegroundColor Gray
Write-Host "Output: $outputZip" -ForegroundColor Gray
Write-Host ""

# Create temp directory
Write-Host "[1/4] Creating temporary directory..." -ForegroundColor Yellow
if (Test-Path $tempDir) {
    Remove-Item $tempDir -Recurse -Force
}
New-Item -ItemType Directory -Path $tempDir -Force | Out-Null

# Exclude patterns
$excludeDirs = @(
    ".git",
    "pgdata",
    "__pycache__",
    "node_modules",
    ".vscode",
    ".idea",
    "terminals"
)

$excludeFiles = @(
    "*.pyc",
    "*.pyo",
    "*.log"
)

Write-Host "[2/4] Copying files..." -ForegroundColor Yellow
Write-Host "Excluding:" -ForegroundColor Gray
foreach ($dir in $excludeDirs) {
    Write-Host "  - $dir/" -ForegroundColor DarkGray
}

# Copy all items
$allItems = Get-ChildItem -Path $projectRoot -Recurse -Force
$copiedCount = 0

foreach ($item in $allItems) {
    $shouldExclude = $false
    
    # Check if in excluded directory
    foreach ($excludeDir in $excludeDirs) {
        if ($item.FullName -like "*\$excludeDir\*" -or $item.Name -eq $excludeDir) {
            $shouldExclude = $true
            break
        }
    }
    
    # Check if excluded file pattern
    if (-not $shouldExclude -and -not $item.PSIsContainer) {
        foreach ($pattern in $excludeFiles) {
            if ($item.Name -like $pattern) {
                $shouldExclude = $true
                break
            }
        }
    }
    
    if (-not $shouldExclude) {
        $relativePath = $item.FullName.Substring($projectRoot.Length + 1)
        $destPath = Join-Path $tempDir $relativePath
        
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
            $copiedCount++
        }
    }
}

Write-Host "Copied $copiedCount files" -ForegroundColor Green
Write-Host ""

# Create manifest
Write-Host "[3/4] Creating manifest..." -ForegroundColor Yellow
$manifestContent = @"
{
  "backup_id": "$timestamp",
  "created_at": "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')",
  "version": "2026-02-09",
  "source_path": "$projectRoot",
  "total_files": $copiedCount,
  "instructions": "See INSTALACIJA_NOVI_RACUNAR.md"
}
"@
Set-Content -Path (Join-Path $tempDir "backup_manifest.json") -Value $manifestContent

# Copy README
Copy-Item (Join-Path $projectRoot "README_BACKUP.txt") (Join-Path $tempDir "README.txt") -Force

Write-Host "Manifest and README created" -ForegroundColor Green
Write-Host ""

# Create ZIP
Write-Host "[4/4] Creating ZIP archive..." -ForegroundColor Yellow
if (Test-Path $outputZip) {
    Remove-Item $outputZip -Force
}

Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory($tempDir, $outputZip, [System.IO.Compression.CompressionLevel]::Optimal, $false)

$zipSize = (Get-Item $outputZip).Length / 1MB
Write-Host "ZIP created: $([math]::Round($zipSize, 2)) MB" -ForegroundColor Green
Write-Host ""

# Cleanup
Remove-Item $tempDir -Recurse -Force

# Summary
Write-Host "========================================" -ForegroundColor Green
Write-Host "BACKUP COMPLETED!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Location: $outputZip" -ForegroundColor Cyan
Write-Host "Size: $([math]::Round($zipSize, 2)) MB" -ForegroundColor Cyan
Write-Host "Files: $copiedCount" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Copy ZIP to new computer" -ForegroundColor White
Write-Host "2. Extract archive" -ForegroundColor White
Write-Host "3. Read INSTALACIJA_NOVI_RACUNAR.md" -ForegroundColor White
Write-Host "4. Follow installation steps" -ForegroundColor White
Write-Host ""
