@echo off
REM Povuci podatke za 5 godina i exportuj u Supabase
REM Za parcelu iz ndvi_auto\.env (PARCEL_ID, PARCEL_LAYER)

set PROJECT_ROOT=%~dp0..
set NDVI_AUTO=%PROJECT_ROOT%\ndvi_auto
set WEB2=%~dp0
set SATELITE_DIR=%NDVI_AUTO%\satelite

set PARCEL_DAYS_BACK=1825
set PARCEL_ID=1427/2
set PARCEL_CSV_DIR=%SATELITE_DIR%
set PARCEL_LAYER=kovin_dkp_pg

echo ============================================
echo   POVLACENJE PODATAKA ZA 5 GODINA (parcela 1427/2)
echo ============================================
echo.

echo [1/4] NDVI CSV...
cd /d "%NDVI_AUTO%"
set PARCEL_DAYS_BACK=1825
set PARCEL_ID=1427/2
python download_ndvi_parcel_csv.py
if errorlevel 1 goto err

echo [2/4] NDRE CSV...
python download_ndre_parcel_csv.py
if errorlevel 1 goto err

echo [3/4] NDMI CSV...
python download_ndmi_parcel_csv.py
if errorlevel 1 goto err

echo [4/4] Export u Supabase...
cd /d "%WEB2%"
if exist .env for /f "usebackq tokens=1,* delims==" %%a in (".env") do set "%%a=%%b"
python export_to_supabase.py
if errorlevel 1 goto err

echo.
echo ============================================
echo   GOTOVO
echo ============================================
echo Osvezi web aplikaciju da vidis 5 godina podataka.
exit /b 0

:err
echo Greška. Proveri ndvi_auto\.env (GEOSERVER_URL, PARCEL_LAYER, PARCEL_ID) i web2\.env (SUPABASE_*).
exit /b 1
