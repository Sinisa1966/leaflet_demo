# Changelog - Februar 2026

## [2026-02-09] - NDRE Sistem Potpuno Funkcionalan ✅

### Dodato
- **NDRE Value Raster** - novi layer sa FLOAT32 vrednostima za tačne GetFeatureInfo upite
  - Novi fajl: `ndvi_auto/download_ndre_value_parcel.py`
  - Nova funkcija: `build_evalscript_ndre_value()` u `download_and_publish.py`
  - Frontend: `ndreValueParcelWms` layer (nevidljiv, samo za GetFeatureInfo)

- **SCL Filter (Cloud Masking)** - filtrira oblake i loše piksele u SVIM evalscriptima
  - Dodato u: `build_evalscript_ndre()`
  - Dodato u: `build_evalscript_ndre_zones()`
  - Dodato u: `build_evalscript_ndre_gradient()`
  - Dodato u: `build_evalscript_ndre_value()`
  - SCL vrednosti filtrirane: 0 (no data), 1 (saturated), 8 (oblaci), 9 (oblaci)

- **Nove NDRE Zone Pragove** - agronomski značajne za azotnu prihranu
  - **< 0.14** → Crvena (više azota - može manje đubrenja)
  - **0.14 - 0.19** → Žuta (standardna količina azota)
  - **≥ 0.19** → Zelena (manje azota - može više đubrenja)

- **Docker sistemske biblioteke** - `libexpat1` i `libgdal-dev` u Dockerfile
  - Rešava: `libexpat.so.1: cannot open shared object file` grešku

### Izmenjeno
- **Frontend Dual-Layer Logika** (`leaflet_demo.html`)
  - `getActiveIndexLayer()` → vraća value layer umesto RGB rastera
  - `setNdreLayerForParcel()` → postavlja RGB i value layer
  - `setNdreZonesLayerForParcel()` → postavlja zones i value layer
  - `getNdreZone()` → nove zone i opisi

- **Legenda NDRE Zones** - ažurirane boje i tekst za nove pragove
  - Dodato: "azotna prihrana" u naslovu
  - Ažurirani opisi zona

- **Dockerfile** - optimizacija COPY komandi
  - Uklonjeno: `|| true` sintaksa koja ne radi u Docker-u
  - Dodato: `COPY . /app/` za sve fajlove odjednom

### Ispravljeno
- **GetFeatureInfo vrednosti** - sada vraća puni opseg (0.105-0.255) umesto samo (0.20-0.25)
  - Uzrok: RGB raster vraćao procesovane vrednosti
  - Rešenje: Value raster sa FLOAT32 output-om

- **CSV i Raster konzistentnost** - iste vrednosti u CSV-u i na rastertru
  - Uzrok: CSV imao SCL filter, raster nije
  - Rešenje: SCL filter u svim evalscriptima

- **libexpat greška** pri CSV generisanju
  - Uzrok: Nedostajuća sistemska biblioteka
  - Rešenje: Instaliran `libexpat1` u Docker image-u

### Testirano
- ✅ Kovin, parcela 1427/2
- ✅ NDRE vrednosti: 0.105 - 0.255 (puni opseg)
- ✅ NDRE Zones: 3 boje (crvena/žuta/zelena)
- ✅ CSV podaci: 8 redova (90 dana)
- ✅ Info balon: tačne vrednosti pri kliku
- ✅ GetFeatureInfo: FLOAT32 vrednosti iz value rastera

---

## [2026-02-08] - Inicijalni Docker Setup

### Dodato
- Docker Compose konfiguracija sa 6 kontejnera
- GeoServer, PostGIS, Nginx, Parcel Server, NDVI Updater
- Python skripti za NDVI, NDMI, NDRE generisanje
- Frontend: Leaflet mapa sa WMS layerima
- CSV statistike za parcele

### Poznati Problemi (rešeni u 2026-02-09)
- ❌ GetFeatureInfo vraćao samo 0.20-0.25 umesto punog opsega
- ❌ Različite vrednosti u CSV-u i rasteru
- ❌ Oblaci nisu bili filtrirani u rasterima

---

## Kako vratiti na ovu verziju

### Git:
```bash
# Commit trenutno stanje
git add .
git commit -m "NDRE sistem kompletan - dual layer + SCL filter"
git tag v1.0-working-2026-02-09

# Ako treba vratiti kasnije:
git checkout v1.0-working-2026-02-09
```

### Docker:
```bash
# Rebuild sa trenutnim kodom
docker-compose build
docker-compose up -d

# Regeneriši podatke za Kovin 1427/2
docker exec -e PARCEL_ID="1427/2" -e PARCEL_LAYER="kovin_dkp_pg" parcel_server python /app/download_ndre_parcel.py
docker exec -e PARCEL_ID="1427/2" -e PARCEL_LAYER="kovin_dkp_pg" parcel_server python /app/download_ndre_value_parcel.py
docker exec -e PARCEL_ID="1427/2" -e PARCEL_LAYER="kovin_dkp_pg" parcel_server python /app/download_ndre_zones_parcel.py
```

---

**Autor:** AI Assistant + Sinisa  
**Datum:** 9. Februar 2026  
**Status:** ✅ Production Ready
