# Radna verzija - 9. Februar 2026 ✅

## Status: Sve radi kako treba! 🎉

### Šta radi:
- ✅ NDVI, NDMI, NDRE rasteri (RGB vizualizacija)
- ✅ NDRE Zones sa 3 boje (crvena/žuta/zelena)
- ✅ NDRE Value raster (FLOAT32 za tačne vrednosti)
- ✅ CSV podaci sa SCL filterom (filtrira oblake)
- ✅ Info balon prikazuje prave vrednosti pri kliku (0.105-0.255)
- ✅ Frontend: Kovin, parcela 1427/2

---

## Ključne izmene

### 1. SCL Filter (Cloud Masking)
**Problem:** CSV i raster imali različite vrednosti jer raster nije filtrirao oblake.

**Rešenje:** Dodao SCL filter u SVE evalscripte:
```javascript
// U setup():
input: ["B05", "B08", "SCL", "dataMask"]

// U evaluatePixel():
var scl = sample.SCL;
if (scl === 0 || scl === 1 || scl === 8 || scl === 9) {
  return [0, 0, 0];  // Filtriraj: no data, saturated, oblaci
}
```

**Fajlovi:**
- `ndvi_auto/download_and_publish.py`:
  - `build_evalscript_ndre()`
  - `build_evalscript_ndre_zones()`
  - `build_evalscript_ndre_gradient()`
  - `build_evalscript_ndre_value()` ← NOVO!

---

### 2. Dual-Layer Pristup (RGB + Value)
**Problem:** RGB raster ne može da vrati originalne NDRE vrednosti pri GetFeatureInfo upitu.

**Rešenje:** Kreirano 2 rastera:
- **RGB raster** (`ndre_parcela_1427_2`) → vidljiv, boje
- **Value raster** (`ndre_value_parcela_1427_2`) → nevidljiv, FLOAT32

**Novi fajlovi:**
- `ndvi_auto/download_ndre_value_parcel.py` ← NOVO!
- `ndvi_auto/download_and_publish.py` → dodato `build_evalscript_ndre_value()`

**Frontend izmene:**
- `leaflet_demo.html`:
  - Definisan `ndreValueParcelWms` layer
  - `getActiveIndexLayer()` vraća value layer za GetFeatureInfo
  - `setNdreLayerForParcel()` postavlja oba layera
  - `setNdreZonesLayerForParcel()` postavlja oba layera

---

### 3. NDRE Zone Pragovi (Azotna Prihrana)
**Novi pragovi:**
- **< 0.14** → Crvena (više azota - može manje đubrenja)
- **0.14 - 0.19** → Žuta (standardna količina azota)
- **≥ 0.19** → Zelena (manje azota - može više đubrenja)

**Izmenjeno:**
- `ndvi_auto/download_and_publish.py` → `build_evalscript_ndre_zones()`
- `leaflet_demo.html` → `getNdreZone()` funkcija
- `leaflet_demo.html` → Legenda (HTML)

---

## Docker Setup

### Kontejneri:
```bash
docker ps
# gis_db - PostgreSQL/PostGIS
# geoserver - GeoServer
# ndvi_updater - Background NDVI updater
# parcel_server - HTTP server za generisanje parcela
# ndvi_web - Nginx (frontend)
```

### Kako pokrenuti:
```bash
cd C:\Kopernikus-GIS
docker-compose up -d
```

### Ako treba rebuild:
```bash
docker-compose build parcel_server ndvi_updater
docker-compose up -d parcel_server ndvi_updater
```

---

## Generisanje podataka za parcelu

### Kovin, parcela 1427/2:
```bash
# NDRE RGB raster
docker exec -e PARCEL_ID="1427/2" -e PARCEL_LAYER="kovin_dkp_pg" parcel_server python /app/download_ndre_parcel.py

# NDRE Value raster (FLOAT32)
docker exec -e PARCEL_ID="1427/2" -e PARCEL_LAYER="kovin_dkp_pg" parcel_server python /app/download_ndre_value_parcel.py

# NDRE Zones raster
docker exec -e PARCEL_ID="1427/2" -e PARCEL_LAYER="kovin_dkp_pg" parcel_server python /app/download_ndre_zones_parcel.py

# CSV podaci (90 dana)
docker exec -e PARCEL_ID="1427/2" -e PARCEL_LAYER="kovin_dkp_pg" -e PARCEL_DAYS_BACK="90" parcel_server python /app/download_ndre_parcel_csv.py
docker exec -e PARCEL_ID="1427/2" -e PARCEL_LAYER="kovin_dkp_pg" -e PARCEL_DAYS_BACK="90" parcel_server python /app/download_ndvi_parcel_csv.py
docker exec -e PARCEL_ID="1427/2" -e PARCEL_LAYER="kovin_dkp_pg" -e PARCEL_DAYS_BACK="90" parcel_server python /app/download_ndmi_parcel_csv.py
```

### Layer names u GeoServeru:
- Opština **Kovin**: `kovin_dkp_pg`
- Opština **Vršac**: `vrsac_dkp_pg`
- Opština **Pančevo**: `pancevo_dkp_pg`

---

## Testiranje

### Frontend:
```
http://localhost:8088/leaflet_demo.html
```

1. Izaberi **Kovin**
2. Unesi parcelu **1427/2**
3. Prikaži NDRE / NDRE Zones
4. Klikni na različite delove parcele

**Očekivano:**
- NDRE vrednosti: **0.105 - 0.255** (puni opseg)
- NDRE Zones: 3 boje (crvena/žuta/zelena)
- CSV podaci: 8 redova (90 dana)

### GeoServer Layers:
```
# RGB vizualizacije
moj_projekat:ndre_parcela_1427_2
moj_projekat:ndre_zones_parcela_1427_2

# Value layer (FLOAT32)
moj_projekat:ndre_value_parcela_1427_2
```

### CSV fajlovi (na hostu):
```
C:\Kopernikus-GIS\satelite\parcela_1427_2_NDRE.csv
C:\Kopernikus-GIS\satelite\parcela_1427_2_NDVI.csv
C:\Kopernikus-GIS\satelite\parcela_1427_2_NDMI.csv
```

---

## Arhitektura

### Kako rade vrednosti pri kliku:

```
Klik na mapu
    ↓
Frontend detektuje NDRE layer aktivan
    ↓
GetFeatureInfo → ndre_value_parcela_1427_2 (FLOAT32)
    ↓
GeoServer vraća sirovu vrednost
    ↓
Info balon prikazuje 0.105 - 0.255
```

### SCL Filter Flow:

```
Copernicus Sentinel-2 Data
    ↓
SCL band (Scene Classification)
    ↓
Filter: scl === 0, 1, 8, 9 → odbaci piksel
    ↓
Validni pikseli → NDRE kalkulacija
    ↓
Raster (RGB ili FLOAT32) ili CSV
```

---

## Ključni Fajlovi

### Backend (Python):
- `ndvi_auto/download_and_publish.py` - evalscripti
- `ndvi_auto/download_ndre_parcel.py` - NDRE RGB
- `ndvi_auto/download_ndre_value_parcel.py` - NDRE Value ← NOVO!
- `ndvi_auto/download_ndre_zones_parcel.py` - NDRE Zones
- `ndvi_auto/download_ndre_parcel_csv.py` - CSV podaci
- `ndvi_auto/parcel_server.py` - HTTP server

### Frontend:
- `leaflet_demo.html` - glavna aplikacija

### Docker:
- `docker-compose.yml` - kontejneri
- `ndvi_auto/Dockerfile` - Python environment

### Konfiguracija:
- `ndvi_auto/.env` - Copernicus credentials

---

## Environment Variables

### `.env` fajl:
```bash
CDSE_CLIENT_ID=sh-27d0e6ae-c65c-4254-b7c8-010edeabf269
CDSE_CLIENT_SECRET=gKytKoyL6Ockc767dKDKeUbXtI8TQmYj
```

### Runtime variables:
```bash
PARCEL_ID="1427/2"          # Parcela ID
PARCEL_LAYER="kovin_dkp_pg" # GeoServer layer
PARCEL_DAYS_BACK="90"       # Koliko dana unazad
PARCEL_MAX_CLOUD="80"       # Maksimalno oblaka (%)
```

---

## Troubleshooting

### Problem: GetFeatureInfo vraća 0.20-0.25 umesto 0.105-0.255
**Rešenje:** Regeneriši NDRE value raster sa novim SCL filterom.

### Problem: CSV prazan (0 data items)
**Rešenje:** Povećaj `PARCEL_DAYS_BACK` na 90 ili 120 dana.

### Problem: NDRE Zones ne pokazuje 3 boje
**Rešenje:** Regeneriši zones raster sa `download_ndre_zones_parcel.py`.

### Problem: Docker kontejner ne startuje
**Rešenje:** 
```bash
docker-compose down
docker-compose up -d
```

---

## Backup Komande

### Backup GeoServer data:
```bash
docker exec geoserver tar czf /tmp/geoserver_backup.tar.gz /opt/geoserver_data
docker cp geoserver:/tmp/geoserver_backup.tar.gz ./backups/
```

### Backup PostgreSQL:
```bash
docker exec gis_db pg_dump -U admin moj_gis > ./backups/db_backup.sql
```

### Backup CSV fajlovi:
```bash
# Već na hostu u: C:\Kopernikus-GIS\satelite\
```

---

## Git Status (pre commit-a)

```
M leaflet_demo.html
M ndvi_auto/download_and_publish.py
M ndvi_auto/Dockerfile
A ndvi_auto/download_ndre_value_parcel.py
```

---

## Sledeći Koraci (opciono)

- [ ] Dodati NDMI i NDVI value rastere za konzistentnost
- [ ] Kreirati automatski script za generisanje svih layera
- [ ] Dodati caching za GeoServer GetFeatureInfo upite
- [ ] Implementirati batch processing za više parcela
- [ ] Kreirati API endpoint za azotne preporuke

---

**Verzija:** 2026-02-09  
**Status:** ✅ Sve radi kako treba!  
**Testirana parcela:** Kovin 1427/2  
**Commit hash:** (dodati nakon git commit-a)
