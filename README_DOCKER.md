# Docker Setup za MapStore2 NDVI Projekt

Ovaj projekat je potpuno konfigurisan za rad u Docker okruženju.

## Servisi

1. **db** - PostgreSQL sa PostGIS (port 5434)
2. **geoserver** - GeoServer (port 8083)
3. **ndvi_updater** - Automatsko ažuriranje NDVI podataka
4. **parcel_server** - HTTP server za generisanje NDVI/NDMI za parcele (port 5010)
5. **web** - Nginx web server za serviranje HTML fajlova (port 8088)

## Pokretanje

1. **Kreirajte `.env` fajl** u `ndvi_auto/` folderu:
```bash
cp ndvi_auto/env.example ndvi_auto/.env
```

2. **Uredite `.env` fajl** i dodajte svoje Copernicus API kredencijale:
```
CDSE_CLIENT_ID=your_client_id
CDSE_CLIENT_SECRET=your_client_secret
GEOSERVER_URL=http://geoserver:8080/geoserver
GEOSERVER_WORKSPACE=moj_projekat
PARCEL_LAYER=VrsacDKP
PARCEL_ATTR=brparcele
```

3. **Pokrenite sve servise**:
```bash
docker-compose up -d
```

4. **Pristupite aplikaciji**:

**Na istom računaru (localhost):**
- Web mapa: http://localhost:8088/leaflet_demo.html
- GeoServer: http://localhost:8083/geoserver
- Parcel server API: http://localhost:5010

**Na drugom računaru u mreži:**
Zamenite `localhost` sa IP adresom ili hostname-om računara gde je Docker pokrenut:
- Web mapa: http://[IP_ADRESA]:8088/leaflet_demo.html
- GeoServer: http://[IP_ADRESA]:8083/geoserver
- Parcel server API: http://[IP_ADRESA]:5010

**Primer:**
Ako je IP adresa `192.168.1.100`:
- Web mapa: http://192.168.1.100:8088/leaflet_demo.html
- GeoServer: http://192.168.1.100:8083/geoserver

**Važno:** Proverite da li firewall dozvoljava pristup ovim portovima (8088, 8083, 5010).

## Zaustavljanje

```bash
docker-compose down
```

## Logovi

```bash
# Svi servisi
docker-compose logs -f

# Samo parcel_server
docker-compose logs -f parcel_server

# Samo ndvi_updater
docker-compose logs -f ndvi_updater
```

## Prebacivanje na drugi računar

1. Kopirajte ceo projekat folder
2. Kreirajte `.env` fajl sa svojim kredencijalima
3. Pokrenite `docker-compose up -d`

## Napomene

- CSV fajlovi se čuvaju u `satelite/` folderu
- GeoTIFF fajlovi se čuvaju u `ndvi_auto/data/` folderu
- GeoServer podaci se čuvaju u Docker volumenu `geoserver_data`
- PostgreSQL podaci se čuvaju u Docker volumenu `postgres_data`
