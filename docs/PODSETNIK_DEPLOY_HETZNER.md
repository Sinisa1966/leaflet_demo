# Podsetnik: deploy na Hetzner (ovakav slučaj)

Kad radiš deploy Kopernikus-GIS na Hetzner i treba da rade **WFS slojevi** (Opštine, Katastarske opštine, DKP) na **istom portu** kao mapa (8088), koristi ovaj redosled. Bez nginx proxy za `/geoserver/` frontend dobija **HTTP 404** jer nginx samo servira statičke fajlove.

---

## Šta mora biti na serveru

1. **Nginx proxy** – zahtevi na `http://SERVER:8088/geoserver/...` moraju ići do GeoServer kontejnera; zahtevi na `http://SERVER:8088/parcel/...` moraju ići do parcel_server kontejnera (port 5010). Inače frontend dobija 404 za NDVI/NDMI/NDRE kada se unese broj parcele.
2. **docker-compose.hetzner.yml** – na serveru se koristi ovaj fajl (ne obični docker-compose.yml): web servis mountuje `./nginx/conf.d`, GeoServer nije izložen na 8083.
3. **Setup skripta** – uvozi shapefile-ove u PostGIS i kreira GeoServer workspace, datastore-ove i slojeve. Mora se pokrenuti **posle** što kontejneri rade, da REST API za GeoServer stigne preko nginx-a (localhost:8088/geoserver).

---

## Koraci za deploy (redom)

### 1. Lokalno (Windows): pokreni deploy

```powershell
.\deploy_to_hetzner.ps1
```

- Pravi arhivu projekta (bez web, web2, .git), šalje je SCP-om na server, ekstrahuje u `/root/kopernikus-gis`.
- Preduslov: SSH ključ `$env:USERPROFILE\.ssh\hetzner_key`, server dostupan (npr. 89.167.39.148 – vrednost u skripti).

### 2. Na serveru: postavi šifru za PostgreSQL i pokreni kontejnere

- **Obavezno:** u `ndvi_auto/.env` postavi **jake šifre** (ne ostavljaj prazno):
  ```bash
  nano /root/kopernikus-gis/ndvi_auto/.env
  # POSTGRES_USER=admin
  # POSTGRES_PASS=tvoja_jaka_sifra_za_bazu
  # POSTGRES_DB=moj_gis
  # GEOSERVER_USER=admin
  # GEOSERVER_PASSWORD=tvoja_jaka_sifra_za_geoserver
  # GEOSERVER_ADMIN_PASSWORD=tvoja_jaka_sifra_za_geoserver   (ista vrednost kao GEOSERVER_PASSWORD)
  ```
  Bez ovih šifri kontejneri i setup skripte neće raditi ispravno.

```bash
ssh -i ~/.ssh/hetzner_key root@89.167.39.148
cd /root/kopernikus-gis
docker compose -f docker-compose.hetzner.yml up -d
```

- Podiže: db, geoserver, ndvi_updater, parcel_server, **web** (nginx sa proxy za `/geoserver/`).
- Sačekaj ~20–30 sekundi da GeoServer ustane.

### 3. Na serveru: pokreni GeoServer setup (opštine, kat-opstine, DKP)

```bash
cd /root/kopernikus-gis
bash scripts/setup_geoserver_hetzner.sh
```

- Kopira `opstine`, `kat-opstine`, DKP foldere u kontejner, uvozi u PostGIS, kreira workspace, datastore-ove, objavljuje slojeve (KatOp_Lat, KatOp_Kat, vrsac_dkp_pg, itd.).
- **Važno:** skripta koristi `GS="http://localhost:8088/geoserver"` – zato nginx proxy mora biti aktivan pre ovog koraka, inače REST vraća 403/404 i slojevi se ne kreiraju.

### 4. Provera

- Mapa: **http://89.167.39.148:8088/leaflet_demo.html**
- Uključi slojeve „Opštine” i „Katastarske opštine” – trebalo bi da se učitaju bez 404.

---

## Ako frontend i dalje dobija 404 za Opštine / WFS

1. **Proveri da li nginx prosleđuje `/geoserver/`**
   - U projektu mora postojati **`nginx/conf.d/default.conf`** sa:
  - `location /geoserver/ { proxy_pass http://geoserver:8080/geoserver/; ... }`
  - `location /parcel/ { proxy_pass http://parcel_server:5010; ... }` (za NDVI/NDMI/NDRE po broju parcele)
   - U **`docker-compose.hetzner.yml`** web servis mora imati:  
     `- ./nginx/conf.d:/etc/nginx/conf.d:ro`

2. **Na serveru ponovo podigni web sa pravim compose fajlom**
   ```bash
   cd /root/kopernikus-gis
   docker compose -f docker-compose.hetzner.yml up -d --force-recreate web
   ```

3. **Ponovo pokreni setup** (da se slojevi zaista kreiraju u GeoServeru preko REST-a):
   ```bash
   bash scripts/setup_geoserver_hetzner.sh
   ```

4. Ako je 404 sa **GeoServera** (u odgovoru piše npr. „Apache Tomcat”), a ne od nginx-a – proxy radi, problem je što sloj/workspace ne postoji ili WFS nije uključen; rešenje je korak 3 (ponovni setup).

---

## Backup kontejnera (disaster recovery)

Na serveru pokreni **jedan** full backup (PostgreSQL + GeoServer data + .env):

```bash
cd /root/kopernikus-gis
bash scripts/backup_hetzner.sh
```

Arhiva se kreira u `backups/hetzner-full-backup-YYYYMMDD_HHMMSS.tar.gz`. Čuvaj je negde sigurno (preuzmi na PC ili drugi server).

**Restore** (ako nešto krupno pukne):

```bash
cd /root/kopernikus-gis
bash scripts/restore_hetzner.sh hetzner-full-backup-YYYYMMDD_HHMMSS.tar.gz
```

Posle restore-a, ako WFS slojevi nedostaju, ponovo: `bash scripts/setup_geoserver_hetzner.sh`.

---

## Kratka tabela

| Šta | Gde / kako |
|-----|------------|
| Deploy skripta | `deploy_to_hetzner.ps1` (lokalno) |
| Compose na serveru | `docker-compose.hetzner.yml` (ne obični docker-compose.yml) |
| Nginx config | `nginx/conf.d/default.conf` – proxy za `/geoserver/` |
| Setup na serveru | `bash scripts/setup_geoserver_hetzner.sh` (posle `docker compose up`) |
| Backup na serveru | `bash scripts/backup_hetzner.sh` → `backups/hetzner-full-backup-*.tar.gz` |
| Restore | `bash scripts/restore_hetzner.sh <backup-arhiva>` |
| Mapa | http://SERVER_IP:8088/leaflet_demo.html |

---

## Novi WFS sloj (npr. još jedan shapefile)

- U **`scripts/setup_geoserver_hetzner.sh`** dodaj: kopiranje foldera, ogr2ogr u novu tabelu, datastore, feature type (v. **PODSETNIK_NOVI_WFS_SLOJ.md**).
- U **`leaflet_demo.html`** dodaj WFS URL, sloj, učitavanje, overlay (isto kao za Opštine).
- Deploy pa na serveru: `docker compose -f docker-compose.hetzner.yml up -d` (ako treba), pa `bash scripts/setup_geoserver_hetzner.sh`.
