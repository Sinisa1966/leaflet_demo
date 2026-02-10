# Quick Start - NDRE Sistem

## 🚀 Pokretanje Sistema (5 minuta)

### 1. Pokreni Docker
```bash
cd C:\Kopernikus-GIS
docker-compose up -d
```

**Proveri status:**
```bash
docker ps
# Trebalo bi da vidiš: gis_db, geoserver, parcel_server, ndvi_updater, ndvi_web
```

---

### 2. Otvori Frontend
```
http://localhost:8088/leaflet_demo.html
```

---

### 3. Testiraj Radnu Parcelu (Kovin 1427/2)

1. **Dropdown:** Izaberi **Kovin**
2. **Parcela:** Unesi **1427/2**
3. **Dugme:** Prikaži NDRE / NDRE Zones
4. **Klik:** Klikni na različite delove parcele

**Očekivano:**
- NDRE vrednosti: **0.105 - 0.255**
- Zone: **Crvena/Žuta/Zelena**
- CSV: **8 redova** (90 dana)

---

## 🔄 Regenerisanje Podataka (Nova Parcela)

### Primer: Vršac, parcela 2511

```bash
# 1. NDRE RGB raster (vizualizacija)
docker exec -e PARCEL_ID="2511" -e PARCEL_LAYER="vrsac_dkp_pg" parcel_server python /app/download_ndre_parcel.py

# 2. NDRE Value raster (tačne vrednosti)
docker exec -e PARCEL_ID="2511" -e PARCEL_LAYER="vrsac_dkp_pg" parcel_server python /app/download_ndre_value_parcel.py

# 3. NDRE Zones (3 boje)
docker exec -e PARCEL_ID="2511" -e PARCEL_LAYER="vrsac_dkp_pg" parcel_server python /app/download_ndre_zones_parcel.py

# 4. CSV podaci (90 dana)
docker exec -e PARCEL_ID="2511" -e PARCEL_LAYER="vrsac_dkp_pg" -e PARCEL_DAYS_BACK="90" parcel_server python /app/download_ndre_parcel_csv.py
```

**Opciono: NDVI i NDMI**
```bash
docker exec -e PARCEL_ID="2511" -e PARCEL_LAYER="vrsac_dkp_pg" -e PARCEL_DAYS_BACK="90" parcel_server python /app/download_ndvi_parcel_csv.py
docker exec -e PARCEL_ID="2511" -e PARCEL_LAYER="vrsac_dkp_pg" -e PARCEL_DAYS_BACK="90" parcel_server python /app/download_ndmi_parcel_csv.py
```

---

## 📍 Layer Names (Opštine)

| Opština | Layer Name | Primer Parcele |
|---------|------------|----------------|
| Kovin | `kovin_dkp_pg` | 1427/2 |
| Vršac | `vrsac_dkp_pg` | 2511 |
| Pančevo | `pancevo_dkp_pg` | - |

---

## 🔧 Troubleshooting

### Problem: Docker ne radi
```bash
# Proveri Docker Desktop
# Ako ne radi, pokreni GUI aplikaciju: Docker Desktop

# Restart kontejnera
docker-compose down
docker-compose up -d
```

### Problem: Vrednosti 0.20-0.25 umesto 0.105-0.255
```bash
# Regeneriši value raster
docker exec -e PARCEL_ID="1427/2" -e PARCEL_LAYER="kovin_dkp_pg" parcel_server python /app/download_ndre_value_parcel.py
```

### Problem: CSV prazan (0 data)
```bash
# Povećaj period na 90 ili 120 dana
docker exec -e PARCEL_ID="1427/2" -e PARCEL_LAYER="kovin_dkp_pg" -e PARCEL_DAYS_BACK="120" parcel_server python /app/download_ndre_parcel_csv.py
```

### Problem: Zone nisu crvena/žuta/zelena
```bash
# Regeneriši zones raster
docker exec -e PARCEL_ID="1427/2" -e PARCEL_LAYER="kovin_dkp_pg" parcel_server python /app/download_ndre_zones_parcel.py
```

---

## 🛠️ Rebuild Docker (posle izmena koda)

```bash
cd C:\Kopernikus-GIS

# Build
docker-compose build parcel_server ndvi_updater

# Restart
docker-compose up -d parcel_server ndvi_updater
```

---

## 📊 NDRE Zone Značenje

| Boja | NDRE Vrednost | Azot Status | Akcija |
|------|---------------|-------------|--------|
| 🔴 Crvena | < 0.14 | Više azota | Može manje đubrenja |
| 🟡 Žuta | 0.14 - 0.19 | Standardno | Normalna količina |
| 🟢 Zelena | ≥ 0.19 | Manje azota | Može više đubrenja |

---

## 📁 Gde se Nalaze Podaci

### CSV fajlovi (Host):
```
C:\Kopernikus-GIS\satelite\parcela_1427_2_NDRE.csv
C:\Kopernikus-GIS\satelite\parcela_1427_2_NDVI.csv
C:\Kopernikus-GIS\satelite\parcela_1427_2_NDMI.csv
```

### Raster fajlovi (Docker):
```
/app/data/ndre_parcel_1427_2.tif         → RGB
/app/data/ndre_value_parcel_1427_2.tif   → FLOAT32
/app/data/ndre_zones_parcel_1427_2.tif   → Zones
```

### GeoServer Layers:
```
moj_projekat:ndre_parcela_1427_2         → RGB vizualizacija
moj_projekat:ndre_value_parcela_1427_2   → Value (GetFeatureInfo)
moj_projekat:ndre_zones_parcela_1427_2   → Zones (3 boje)
```

---

## 🌐 URL-ovi

| Servis | URL | Credentials |
|--------|-----|-------------|
| Frontend | http://localhost:8088/leaflet_demo.html | - |
| GeoServer | http://localhost:8083/geoserver | admin / geoserver |
| Parcel Server | http://localhost:5010 | - |
| PostgreSQL | localhost:5434 | admin / admin123 |

---

## 💾 Backup / Restore

### Backup trenutne verzije:
```bash
# 1. Git commit
git add .
git commit -m "Radna verzija - NDRE sistem"
git tag v1.0-2026-02-09

# 2. CSV backup (već na hostu)
# C:\Kopernikus-GIS\satelite\

# 3. GeoServer backup
docker exec geoserver tar czf /tmp/geoserver.tar.gz /opt/geoserver_data
docker cp geoserver:/tmp/geoserver.tar.gz ./backups/
```

### Restore:
```bash
# Git
git checkout v1.0-2026-02-09

# Docker rebuild
docker-compose build
docker-compose up -d

# Regeneriši podatke
# (koristi komande iz sekcije "Regenerisanje Podataka")
```

---

**Verzija:** 2026-02-09  
**Status:** ✅ Production Ready  
**Testirana parcela:** Kovin 1427/2
