# Instalacija Kopernikus-GIS na Novom Računaru

📦 **Verzija:** 2026-02-09 (Working Version)  
🎯 **Status:** Testiran i funkcionalan (parcela 1427/2, NDRE zone implementirane)

---

## ✅ PREDUSLOVI

### 1. Operativni Sistem
- ✅ Windows 10/11 (testiran na Win 10)
- ✅ Ili Linux (Ubuntu 20.04+, Debian 11+)
- ✅ Minimalno 8 GB RAM (preporučeno 16 GB)
- ✅ 50 GB slobodnog prostora na disku

### 2. Instalirani Programi

#### **A) Docker Desktop**
```
Download: https://www.docker.com/products/docker-desktop

Windows:
  - Docker Desktop for Windows (sa WSL2 backend)
  - Omogući Hyper-V (u Windows Features)
  
Linux:
  sudo apt-get update
  sudo apt-get install docker.io docker-compose
  sudo systemctl start docker
  sudo usermod -aG docker $USER
```

#### **B) Git (opciono, za version control)**
```
Download: https://git-scm.com/download/win

Ili:
  Windows: winget install Git.Git
  Linux: sudo apt-get install git
```

#### **C) Text Editor (opciono)**
```
- VS Code: https://code.visualstudio.com/
- Ili bilo koji drugi editor
```

---

## 📦 INSTALACIJA - KORAK PO KORAK

### **KORAK 1: Ekstraktuj ZIP Arhivu**

```bash
# Windows:
1. Desni klik na kopernikus-gis-backup-YYYYMMDD.zip
2. Extract All → Izaberi destinaciju (npr. C:\Projects\)
3. Otvori ekstraktovani folder

# Linux:
unzip kopernikus-gis-backup-YYYYMMDD.zip -d /home/username/projects/
cd /home/username/projects/Kopernikus-GIS/
```

---

### **KORAK 2: Konfiguriši Environment Variables**

#### **A) Kreiraj `.env` fajl u `ndvi_auto/` folderu:**

```bash
# Windows PowerShell:
cd Kopernikus-GIS\ndvi_auto
Copy-Item env.example .env
notepad .env

# Linux:
cd Kopernikus-GIS/ndvi_auto
cp env.example .env
nano .env
```

#### **B) Popuni `.env` sa svojim credentials:**

```bash
# Copernicus DataSpace Credentials
CDSE_CLIENT_ID=sh-27d0e6ae-c65c-4254-b7c8-010edeabf269
CDSE_CLIENT_SECRET=gKytKoyL6Ockc767dKDKeUbXtI8TQmYj

# GeoServer Config
GEOSERVER_URL=http://geoserver:8080/geoserver
GEOSERVER_USER=admin
GEOSERVER_PASSWORD=geoserver

# Parcel Server Config
PARCEL_DAYS_BACK=30
PARCEL_LAYER=kovin_dkp_pg

# PostgreSQL Config (default)
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=gis
```

**⚠️ VAŽNO:** Ako nemaš Copernicus credentials, registruj se:
```
https://dataspace.copernicus.eu/
→ Register → Create OAuth Client
```

---

### **KORAK 3: Proveri Docker**

```bash
# Proveri da li Docker radi:
docker --version
docker-compose --version

# Ako nema docker-compose, instaliraj:
# Windows: Docker Desktop već ima docker-compose
# Linux: sudo apt-get install docker-compose-plugin
```

---

### **KORAK 4: Pokreni Docker Kontejnere**

```bash
# Pozicioniraj se u root projekta:
cd C:\Kopernikus-GIS

# Pokreni sve servise:
docker-compose up -d

# Prati log-ove (opciono):
docker-compose logs -f

# Proveri status:
docker-compose ps
```

**Očekivani output:**
```
NAME                IMAGE                         STATUS
geoserver          kartoza/geoserver:2.23.0     Up (healthy)
ndvi_updater       kopernikus-gis-ndvi_updater  Up
nginx              nginx:alpine                  Up
parcel_server      kopernikus-gis-parcel_server Up
postgis            postgis/postgis:15-3.3       Up
```

---

### **KORAK 5: Učitaj Parcel Geometrije u PostGIS**

#### **A) Kopiraj shapefile-ove u PostGIS kontejner:**

```bash
# Windows PowerShell:
docker cp DKP-Kovin postgis:/tmp/
docker cp DKP-Vrsac postgis:/tmp/

# Linux:
docker cp DKP-Kovin postgis:/tmp/
docker cp DKP-Vrsac postgis:/tmp/
```

#### **B) Importuj u PostgreSQL:**

```bash
# Uđi u PostGIS kontejner:
docker exec -it postgis bash

# Importuj Kovin parcele:
shp2pgsql -I -s 4326 /tmp/DKP-Kovin/kovin_parcels.shp public.kovin_dkp_pg | psql -U postgres -d gis

# Importuj Vršac parcele:
shp2pgsql -I -s 4326 /tmp/DKP-Vrsac/vrsac_parcels.shp public.vrsac_dkp_pg | psql -U postgres -d gis

# Izađi iz kontejnera:
exit
```

**⚠️ NAPOMENA:** Ako nemaš shapefile-ove, možeš da koristiš postojeće CSV/GeoJSON fajlove ili ručno kreiraj geometrije.

---

### **KORAK 6: Konfiguriši GeoServer**

#### **A) Otvori GeoServer Web UI:**
```
URL: http://localhost:8080/geoserver/web
User: admin
Pass: geoserver
```

#### **B) Kreiraj PostGIS DataStore:**

1. **Stores → Add new Store → PostGIS**
2. Popuni:
   - **Workspace:** `moj_projekat`
   - **Data Source Name:** `kovin_dkp_pg`
   - **Host:** `postgis`
   - **Port:** `5432`
   - **Database:** `gis`
   - **User:** `postgres`
   - **Password:** `postgres`
3. **Save**

4. Ponovi za `vrsac_dkp_pg`

#### **C) Publish Layers:**

1. **Layers → Add new layer**
2. Izaberi store: `moj_projekat:kovin_dkp_pg`
3. Publish layer: `public.kovin_dkp_pg`
4. Konfiguriši:
   - **Native SRS:** `EPSG:4326`
   - **Declared SRS:** `EPSG:4326`
   - **Bounding Box:** Compute from data
5. **Save**

6. Ponovi za `vrsac_dkp_pg`

#### **D) Upload Styles:**

```bash
# Windows PowerShell:
cd ndvi_auto
python upload_ndre_zones_style.py
python upload_index_rgb_style.py

# Linux:
cd ndvi_auto
python3 upload_ndre_zones_style.py
python3 upload_index_rgb_style.py
```

---

### **KORAK 7: Testiraj Sistem**

#### **A) Proveri Web App:**
```
http://localhost:8088/leaflet_demo.html
```

**Očekivano:**
- ✅ Mapa se učitava (Leaflet)
- ✅ Vidljiv je selector za indekse (NDVI, NDMI, NDRE, NDRE Zones)
- ✅ Postoji lista parcela (dropdown)

#### **B) Testiraj Parcel Server API:**
```bash
# Health check:
curl http://localhost:5001/health

# Expected: {"status": "ok", ...}

# Generiši NDRE za test parcelu:
curl "http://localhost:5001/ndre/1427%2F2?layer=kovin_dkp_pg"

# Expected: JSON sa statusom "success" ili "processing"
```

#### **C) Testiraj NDRE Generisanje:**

1. Otvori web app: `http://localhost:8088/leaflet_demo.html`
2. Izaberi parcelu iz dropdown-a: `1427/2`
3. Klikni **"Refresh NDRE"** dugme
4. Sačekaj 30-60 sekundi
5. Indeks se prikazuje na mapi
6. Klikni na mapu → vidiš NDRE vrednost i zonu

---

## 🔧 TROUBLESHOOTING

### **Problem 1: Docker kontejneri ne startuju**

```bash
# Proveri Docker service:
# Windows: Otvori Docker Desktop → Mora biti "Running"
# Linux: sudo systemctl status docker

# Proveri log-ove:
docker-compose logs geoserver
docker-compose logs postgis
docker-compose logs parcel_server

# Restartuj kontejnere:
docker-compose down
docker-compose up -d
```

---

### **Problem 2: PostGIS - parcele nisu učitane**

```bash
# Proveri tabele u bazi:
docker exec -it postgis psql -U postgres -d gis -c "\dt"

# Expected output treba da ima:
#   public.kovin_dkp_pg
#   public.vrsac_dkp_pg

# Ako nema, ponovo importuj shapefile-ove (Korak 5)
```

---

### **Problem 3: GeoServer ne prikazuje layere**

```bash
# Proveri WFS endpoint:
curl "http://localhost:8080/geoserver/moj_projekat/wfs?service=WFS&version=2.0.0&request=GetCapabilities"

# Trebalo bi da vidiš:
#   <FeatureType>
#     <Name>moj_projekat:kovin_dkp_pg</Name>
#   </FeatureType>

# Ako nema, proveri GeoServer logs:
docker-compose logs geoserver

# Restartuj GeoServer:
docker-compose restart geoserver
```

---

### **Problem 4: Copernicus API greška (401 Unauthorized)**

```bash
# Proveri da li je .env fajl učitan:
docker exec parcel_server env | grep CDSE

# Expected:
#   CDSE_CLIENT_ID=sh-...
#   CDSE_CLIENT_SECRET=...

# Ako nema, proveri:
1. Da li je .env fajl u ndvi_auto/ folderu?
2. Da li su credentials ispravni?
3. Restartuj parcel_server:
   docker-compose restart parcel_server
```

---

### **Problem 5: Frontend - "Failed to load layer"**

```bash
# Proveri da li GeoServer radi:
curl http://localhost:8080/geoserver/web

# Proveri da li Nginx radi:
curl http://localhost:8088/leaflet_demo.html

# Proveri browser console (F12) za greške
```

---

## 📊 VERIFIKACIJA - Checklist

Kada sve radi kako treba:

- ✅ **Docker kontejneri:** Svih 5 kontejnera su `Up`
- ✅ **PostGIS:** Tabele `kovin_dkp_pg` i `vrsac_dkp_pg` postoje
- ✅ **GeoServer:** Layeri su publish-ovani i vidljivi
- ✅ **Web App:** Mapa se učitava, parcele su vidljive
- ✅ **Parcel Server:** `/health` endpoint vraća `{"status": "ok"}`
- ✅ **NDRE Generation:** Klik na "Refresh NDRE" generiše raster
- ✅ **Info Balloon:** Klik na mapu prikazuje NDRE vrednost i zonu

---

## 🚀 SLEDEĆI KORACI

### **1. Dodaj Više Parcela**
```bash
# Importuj dodatne shapefile-ove u PostGIS
# Publish kao nove layere u GeoServer
```

### **2. Konfiguriši Automated Backup**
```bash
# Kreiraj cron job za backup (Linux):
0 3 * * * /home/user/kopernikus-gis/backup.sh

# Ili Windows Task Scheduler (Windows)
```

### **3. Implementiraj Production Mitigations**
```
Vidi: CHANGELOG_2026-02.md - Sekcija "Mitigation Plan"
  - Redis cache layer
  - Monitoring (Prometheus/Grafana)
  - Authentication (API keys)
```

---

## 📞 PODRŠKA

**Dokumentacija:**
- `WORKING_VERSION_2026-02-09.md` - Detaljni opis sistema
- `CHANGELOG_2026-02.md` - Lista promena i bugfix-eva
- `QUICK_START.md` - Brzi vodič za korisnike
- `README_DOCKER.md` - Docker specifične informacije

**Kontakt:**
- Email: sinisa@example.com
- GitHub: (dodaj link ako postoji)

---

## ✅ KRAJ INSTALACIJE

Ako si uspešno prošao sve korake, sistem bi trebalo da radi! 🎉

**Test parcela:** `1427/2` (Kovin opština)  
**Test feature:** NDRE zone (crveno/žuto/zeleno)

Srećan rad! 🚀🌍📊
