# Setup GeoServer lokalno (Windows): uvezi Opštine, Katastarske opštine, kreiraj slojeve, ukljuci WFS
# Pokretanje: .\scripts\setup_geoserver_local.ps1

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$EnvFile = Join-Path $ProjectRoot "ndvi_auto\.env"
if (Test-Path $EnvFile) {
    Get-Content $EnvFile | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
            $k = $Matches[1].Trim(); $v = $Matches[2].Trim().Trim('"').Trim("'")
            Set-Item -Path "Env:$k" -Value $v
        }
    }
}
if (-not $env:POSTGRES_PASS) { $env:POSTGRES_PASS = "admin123" }
if (-not $env:POSTGRES_USER) { $env:POSTGRES_USER = "admin" }
if (-not $env:POSTGRES_DB) { $env:POSTGRES_DB = "moj_gis" }
if (-not $env:GEOSERVER_USER) { $env:GEOSERVER_USER = "admin" }
if (-not $env:GEOSERVER_PASSWORD) { $env:GEOSERVER_PASSWORD = "geoserver" }

# Preko nginx proxy (8088) - radi i kad GeoServer nije izložen na 8083
$GS = "http://localhost:8088/geoserver"
$Auth = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("$($env:GEOSERVER_USER):$($env:GEOSERVER_PASSWORD)"))

Write-Host "=== Setup GeoServer (lokalno) - Opstine + Katastarske opstine ===" -ForegroundColor Cyan
Set-Location $ProjectRoot

# 1. Provera Docker
$gisDb = docker ps --format "{{.Names}}" | Select-String "gis_db"
if (-not $gisDb) {
    Write-Host "GREŠKA: gis_db nije pokrenut. Pokreni: docker compose up -d" -ForegroundColor Red
    exit 1
}

# 2. Kopiranje opstine u kontejner
Write-Host "[1/6] Kopiranje opstine u kontejner..." -ForegroundColor Cyan
docker cp opstine gis_db:/tmp/opstine
if ($LASTEXITCODE -ne 0) { throw "docker cp opstine failed" }

# 2b. Kopiranje kat-opstine i Pancevo-adrese u kontejner
Write-Host "[2/6] Kopiranje kat-opstine i Pancevo-adrese u kontejner..." -ForegroundColor Cyan
docker cp kat-opstine gis_db:/tmp/kat-opstine
if ($LASTEXITCODE -ne 0) { throw "docker cp kat-opstine failed" }
docker cp "Pancevo-adrese" gis_db:/tmp/Pancevo-adrese
if ($LASTEXITCODE -ne 0) { throw "docker cp Pancevo-adrese failed" }

# 3. Import u PostGIS (katop_lat, kat_opstine, pancevo_adrese)
Write-Host "[3/6] Import Op_Lat.shp u PostGIS (katop_lat, WGS84)..." -ForegroundColor Cyan
# Iz kontejnera gis_db: PostGIS na localhost:5432
$pg = "PG:host=127.0.0.1 port=5432 dbname=$($env:POSTGRES_DB) user=$($env:POSTGRES_USER) password=$($env:POSTGRES_PASS)"
docker exec gis_db ogr2ogr -f PostgreSQL $pg /tmp/opstine/Op_Lat.shp -nln public.katop_lat -nlt PROMOTE_TO_MULTI -t_srs EPSG:4326 -overwrite
if ($LASTEXITCODE -ne 0) { throw "ogr2ogr opstine failed" }
Write-Host "  katop_lat OK" -ForegroundColor Green
docker exec gis_db ogr2ogr -f PostgreSQL $pg /tmp/kat-opstine/KatOp_Lat.shp -nln public.kat_opstine -nlt PROMOTE_TO_MULTI -t_srs EPSG:4326 -overwrite
if ($LASTEXITCODE -ne 0) { throw "ogr2ogr kat-opstine failed" }
Write-Host "  kat_opstine OK" -ForegroundColor Green
docker exec gis_db ogr2ogr -f PostgreSQL $pg /tmp/Pancevo-adrese/PancevoDKP.shp -nln public.pancevo_adrese -nlt PROMOTE_TO_MULTI -t_srs EPSG:4326 -overwrite
if ($LASTEXITCODE -ne 0) { throw "ogr2ogr pancevo_adrese failed" }
Write-Host "  pancevo_adrese OK" -ForegroundColor Green

# 4. GeoServer REST - workspace
Write-Host "[4/6] GeoServer workspace moj_projekat..." -ForegroundColor Cyan
$headers = @{
    "Content-Type" = "application/json"
    "Authorization" = "Basic $Auth"
}
try {
    Invoke-RestMethod -Uri "$GS/rest/workspaces" -Method Post -Headers $headers -Body '{"workspace":{"name":"moj_projekat"}}' | Out-Null
} catch {
    if ($_.Exception.Response.StatusCode -eq 409) { Write-Host "  workspace vec postoji" -ForegroundColor Gray }
    else { throw }
}

# 5. Ukljuci WFS za workspace (Python skripta)
Write-Host "[5/6] Ukljucivanje WFS za workspace..." -ForegroundColor Cyan
$env:GEOSERVER_REST = "$GS/rest"
& python "$ProjectRoot\scripts\enable_wfs_workspace.py"
if ($LASTEXITCODE -ne 0) { Write-Host "  Upozorenje: WFS enable nije uspeo (mozda vec ukljucen). Nastavljam." -ForegroundColor Yellow }
$LASTEXITCODE = 0

# 6. GeoServer - datastore katop_lat i KatOp_Lat
Write-Host "[6/6] GeoServer datastore i slojevi (KatOp_Lat, KatOp_Kat)..." -ForegroundColor Cyan
$storeBody = "{`"dataStore`":{`"name`":`"katop_lat`",`"type`":`"PostGIS`",`"enabled`":true,`"connectionParameters`":{`"entry`":[{`"@key`":`"host`",`"$`":`"db`"},{`"@key`":`"port`",`"$`":`"5432`"},{`"@key`":`"database`",`"$`":`"$($env:POSTGRES_DB)`"},{`"@key`":`"user`",`"$`":`"$($env:POSTGRES_USER)`"},{`"@key`":`"passwd`",`"$`":`"$($env:POSTGRES_PASS)`"},{`"@key`":`"schema`",`"$`":`"public`"},{`"@key`":`"dbtype`",`"$`":`"postgis`"}]}}}"
try {
    Invoke-RestMethod -Uri "$GS/rest/workspaces/moj_projekat/datastores" -Method Post -Headers $headers -Body $storeBody -ContentType "application/json" | Out-Null
    Write-Host "  datastore katop_lat OK" -ForegroundColor Green
} catch {
    if ($_.Exception.Response.StatusCode -eq 409) { Write-Host "  datastore katop_lat vec postoji" -ForegroundColor Gray }
    else { Write-Host "  datastore: $($_.Exception.Message)" -ForegroundColor Yellow }
}

# 7. Publish feature type KatOp_Lat
$ftBody = '{"featureType":{"name":"KatOp_Lat","nativeName":"katop_lat","enabled":true,"srs":"EPSG:4326","nativeBoundingBox":{"minx":18,"maxx":23,"miny":42,"maxy":47}}}'
try {
    Invoke-RestMethod -Uri "$GS/rest/workspaces/moj_projekat/datastores/katop_lat/featuretypes" -Method Post -Headers $headers -Body $ftBody -ContentType "application/json" | Out-Null
    Write-Host "  sloj KatOp_Lat (Opstine) objavljen" -ForegroundColor Green
} catch {
    if ($_.Exception.Response.StatusCode -eq 409) { Write-Host "  sloj KatOp_Lat vec postoji" -ForegroundColor Gray }
    else { Write-Host "  feature type: $($_.Exception.Message)" -ForegroundColor Yellow }
}

# 8. Datastore kat_opstine (Katastarske opstine)
$storeKatBody = "{`"dataStore`":{`"name`":`"kat_opstine`",`"type`":`"PostGIS`",`"enabled`":true,`"connectionParameters`":{`"entry`":[{`"@key`":`"host`",`"$`":`"db`"},{`"@key`":`"port`",`"$`":`"5432`"},{`"@key`":`"database`",`"$`":`"$($env:POSTGRES_DB)`"},{`"@key`":`"user`",`"$`":`"$($env:POSTGRES_USER)`"},{`"@key`":`"passwd`",`"$`":`"$($env:POSTGRES_PASS)`"},{`"@key`":`"schema`",`"$`":`"public`"},{`"@key`":`"dbtype`",`"$`":`"postgis`"}]}}}"
try {
    Invoke-RestMethod -Uri "$GS/rest/workspaces/moj_projekat/datastores" -Method Post -Headers $headers -Body $storeKatBody -ContentType "application/json" | Out-Null
    Write-Host "  datastore kat_opstine OK" -ForegroundColor Green
} catch {
    if ($_.Exception.Response.StatusCode -eq 409) { Write-Host "  datastore kat_opstine vec postoji" -ForegroundColor Gray }
    else { Write-Host "  datastore kat_opstine: $($_.Exception.Message)" -ForegroundColor Yellow }
}

# 9. Publish feature type KatOp_Kat (Katastarske opstine)
$ftKatBody = '{"featureType":{"name":"KatOp_Kat","nativeName":"kat_opstine","enabled":true,"srs":"EPSG:4326","nativeBoundingBox":{"minx":18,"maxx":23,"miny":42,"maxy":47}}}'
try {
    Invoke-RestMethod -Uri "$GS/rest/workspaces/moj_projekat/datastores/kat_opstine/featuretypes" -Method Post -Headers $headers -Body $ftKatBody -ContentType "application/json" | Out-Null
    Write-Host "  sloj KatOp_Kat (Katastarske opstine) objavljen" -ForegroundColor Green
} catch {
    if ($_.Exception.Response.StatusCode -eq 409) { Write-Host "  sloj KatOp_Kat vec postoji" -ForegroundColor Gray }
    else { Write-Host "  feature type KatOp_Kat: $($_.Exception.Message)" -ForegroundColor Yellow }
}

# 10. Datastore i sloj pancevo_adrese (Pancevo-adrese)
$storePancevoAdrBody = "{`"dataStore`":{`"name`":`"pancevo_adrese`",`"type`":`"PostGIS`",`"enabled`":true,`"connectionParameters`":{`"entry`":[{`"@key`":`"host`",`"$`":`"db`"},{`"@key`":`"port`",`"$`":`"5432`"},{`"@key`":`"database`",`"$`":`"$($env:POSTGRES_DB)`"},{`"@key`":`"user`",`"$`":`"$($env:POSTGRES_USER)`"},{`"@key`":`"passwd`",`"$`":`"$($env:POSTGRES_PASS)`"},{`"@key`":`"schema`",`"$`":`"public`"},{`"@key`":`"dbtype`",`"$`":`"postgis`"}]}}}"
try {
    Invoke-RestMethod -Uri "$GS/rest/workspaces/moj_projekat/datastores" -Method Post -Headers $headers -Body $storePancevoAdrBody -ContentType "application/json" | Out-Null
    Write-Host "  datastore pancevo_adrese OK" -ForegroundColor Green
} catch {
    if ($_.Exception.Response.StatusCode -eq 409) { Write-Host "  datastore pancevo_adrese vec postoji" -ForegroundColor Gray }
    else { Write-Host "  datastore pancevo_adrese: $($_.Exception.Message)" -ForegroundColor Yellow }
}
$ftPancevoAdrBody = '{"featureType":{"name":"pancevo_adrese","nativeName":"pancevo_adrese","enabled":true,"srs":"EPSG:4326","nativeBoundingBox":{"minx":18,"maxx":23,"miny":42,"maxy":47}}}'
try {
    Invoke-RestMethod -Uri "$GS/rest/workspaces/moj_projekat/datastores/pancevo_adrese/featuretypes" -Method Post -Headers $headers -Body $ftPancevoAdrBody -ContentType "application/json" | Out-Null
    Write-Host "  sloj pancevo_adrese (Pancevo-adrese) objavljen" -ForegroundColor Green
} catch {
    if ($_.Exception.Response.StatusCode -eq 409) { Write-Host "  sloj pancevo_adrese vec postoji" -ForegroundColor Gray }
    else { Write-Host "  feature type pancevo_adrese: $($_.Exception.Message)" -ForegroundColor Yellow }
}

Write-Host ""
Write-Host "=== Gotovo! Osvezi mapu i ukljuci slojeve (Opstine, Katastarske opstine, Pancevo-adrese): http://localhost:8088/leaflet_demo.html ===" -ForegroundColor Green
Write-Host ""
