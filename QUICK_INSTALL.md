# QUICK INSTALL - Kopernikus-GIS

⚡ **Za iskusne korisnike** - brza instalacija u 5 minuta

---

## ✅ Preduslovi

- Docker Desktop instaliran i pokrenut
- 8+ GB RAM
- 50 GB disk space

---

## 🚀 Instalacija - 5 Koraka

### **1. Ekstraktuj ZIP**
```bash
# Windows: Desni klik → Extract All
# Linux: unzip kopernikus-gis-backup-*.zip
```

### **2. Konfiguriši .env**
```bash
cd ndvi_auto
copy env.example .env    # Windows
# cp env.example .env    # Linux

# Edituj .env i popuni:
# CDSE_CLIENT_ID=tvoj-client-id
# CDSE_CLIENT_SECRET=tvoj-client-secret
```

**Nabavi credentials:** https://dataspace.copernicus.eu/ → Register → OAuth Client

### **3. Pokreni Docker**
```bash
cd ..  # Nazad u root
docker-compose up -d
```

Sačekaj 2-3 minuta da se kontejneri pokrenu.

### **4. Učitaj Parcele**
```bash
# Ako imaš shapefile-ove:
docker cp DKP-Kovin postgis:/tmp/
docker exec -it postgis bash
shp2pgsql -I -s 4326 /tmp/DKP-Kovin/*.shp public.kovin_dkp_pg | psql -U postgres -d gis
exit
```

### **5. Konfiguriši GeoServer**
```
1. Otvori: http://localhost:8080/geoserver/web
2. Login: admin / geoserver
3. Stores → Add PostGIS Store:
   - Host: postgis
   - Database: gis
   - User: postgres
   - Pass: postgres
4. Publish layere: kovin_dkp_pg, vrsac_dkp_pg
5. Upload styles:
   cd ndvi_auto
   python upload_ndre_zones_style.py
```

---

## ✅ Test

Otvori: http://localhost:8088/leaflet_demo.html

- Trebalo bi da vidiš mapu
- Izaberi parcelu iz dropdown-a
- Klikni "Refresh NDRE"
- Sačekaj 30-60 sek
- Klikni na mapu → vidiš NDRE vrednost

---

## 📖 Detaljnije?

Za korak-po-korak vodič sa screenshots-ima i troubleshooting-om:  
👉 **INSTALACIJA_NOVI_RACUNAR.md**

---

## 🆘 Problem?

```bash
# Proveri status kontejnera:
docker-compose ps

# Proveri log-ove:
docker-compose logs geoserver
docker-compose logs parcel_server
docker-compose logs postgis

# Restartuj sve:
docker-compose down
docker-compose up -d
```

---

**Za production deployment:** Pročitaj **Mitigation Plan** u `CHANGELOG_2026-02.md`
