#!/bin/bash
# Setup GeoServer za LOKALNI Docker (Windows Git Bash / WSL / Linux)
# Pokretanje: bash scripts/setup_geoserver_local.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

# Učitaj Postgres kredencijale iz ndvi_auto/.env
if [ -f ndvi_auto/.env ]; then
  set -a
  # shellcheck source=/dev/null
  . ndvi_auto/.env
  set +a
fi
: "${POSTGRES_USER:=admin}"
: "${POSTGRES_DB:=moj_gis}"
: "${POSTGRES_PASS:=admin123}"
: "${GEOSERVER_USER:=admin}"
: "${GEOSERVER_PASSWORD:=geoserver}"

# Preko nginx proxy (8088) - radi i kad GeoServer nije izložen na 8083 (npr. docker-compose.hetzner)
GS="http://localhost:8088/geoserver"
AUTH="${GEOSERVER_USER}:${GEOSERVER_PASSWORD}"

echo "=== Setup GeoServer (lokalno) - $PROJECT_DIR ==="

if ! docker ps | grep -q gis_db; then
  echo "GREŠKA: gis_db nije pokrenut. Pokreni: docker-compose up -d"
  exit 1
fi

echo "=== 1. Kopiranje shapefile-ova ==="
docker cp DKP-Kovin gis_db:/tmp/ 2>/dev/null || true
docker cp DKP-Vrsac gis_db:/tmp/ 2>/dev/null || true
docker cp PancevoDKP gis_db:/tmp/PancevoDKP 2>/dev/null || true
docker cp opstine gis_db:/tmp/opstine 2>/dev/null || true

echo "=== 2. Import u PostgreSQL (georeferencirano u WGS84) ==="
PG="PG:host=127.0.0.1 dbname=${POSTGRES_DB} user=${POSTGRES_USER} password=${POSTGRES_PASS}"
docker exec gis_db ogr2ogr -f PostgreSQL "$PG" /tmp/DKP-Kovin/KovinDKP.shp -nln public.kovin_dkp_pg -nlt PROMOTE_TO_MULTI -t_srs EPSG:4326 -overwrite 2>/dev/null && echo "  kovin OK" || true
docker exec gis_db ogr2ogr -f PostgreSQL "$PG" /tmp/DKP-Vrsac/VrsacDKP.shp -nln public.vrsac_dkp_pg -nlt PROMOTE_TO_MULTI -t_srs EPSG:4326 -overwrite 2>/dev/null && echo "  vrsac OK" || true
docker exec gis_db ogr2ogr -f PostgreSQL "$PG" /tmp/PancevoDKP/PancevoDKP.shp -nln public.pancevo_dkp_pg -nlt PROMOTE_TO_MULTI -t_srs EPSG:4326 -overwrite 2>/dev/null && echo "  pancevo OK" || true
docker exec gis_db ogr2ogr -f PostgreSQL "$PG" /tmp/opstine/Op_Lat.shp -nln public.katop_lat -nlt PROMOTE_TO_MULTI -t_srs EPSG:4326 -overwrite 2>/dev/null && echo "  opstine (KatOp_Lat) OK" || true

echo "=== 3. GeoServer - workspace moj_projekat ==="
curl -s -u "$AUTH" -X POST -H "Content-type: application/json" -d '{"workspace":{"name":"moj_projekat"}}' "$GS/rest/workspaces" 2>/dev/null || true

echo "=== 3b. Ukljuci WFS za workspace (da vraca JSON, ne XML) ==="
GEOSERVER_REST="$GS/rest" python3 scripts/enable_wfs_workspace.py 2>/dev/null && echo "  WFS ukljucen" || true

echo "=== 4. GeoServer - PostGIS datastore ==="
for STORE in kovin_dkp_pg vrsac_dkp_pg pancevo_dkp_pg katop_lat; do
  curl -s -u "$AUTH" -X POST -H "Content-type: application/json" \
    -d "{\"dataStore\":{\"name\":\"$STORE\",\"type\":\"PostGIS\",\"enabled\":true,\"connectionParameters\":{\"entry\":[{\"@key\":\"host\",\"$\":\"db\"},{\"@key\":\"port\",\"$\":\"5432\"},{\"@key\":\"database\",\"$\":\"${POSTGRES_DB}\"},{\"@key\":\"user\",\"$\":\"${POSTGRES_USER}\"},{\"@key\":\"passwd\",\"$\":\"${POSTGRES_PASS}\"},{\"@key\":\"schema\",\"$\":\"public\"},{\"@key\":\"dbtype\",\"$\":\"postgis\"}]}}}" \
    "$GS/rest/workspaces/moj_projekat/datastores" 2>/dev/null && echo "  $STORE ok" || true
done

echo "=== 5. Publish feature types ==="
for LAYER in kovin_dkp_pg vrsac_dkp_pg pancevo_dkp_pg; do
  curl -s -u "$AUTH" -X POST -H "Content-type: application/json" \
    -d "{\"featureType\":{\"name\":\"$LAYER\",\"nativeName\":\"$LAYER\",\"enabled\":true,\"srs\":\"EPSG:4326\",\"nativeBoundingBox\":{\"minx\":19,\"maxx\":23,\"miny\":42,\"maxy\":46}}}" \
    "$GS/rest/workspaces/moj_projekat/datastores/$LAYER/featuretypes" 2>/dev/null && echo "  $LAYER ok" || true
done
# Opštine: publish kao KatOp_Lat (ime koje leaflet_demo očekuje)
curl -s -u "$AUTH" -X POST -H "Content-type: application/json" \
  -d "{\"featureType\":{\"name\":\"KatOp_Lat\",\"nativeName\":\"katop_lat\",\"enabled\":true,\"srs\":\"EPSG:4326\",\"nativeBoundingBox\":{\"minx\":18,\"maxx\":23,\"miny\":42,\"maxy\":47}}}" \
  "$GS/rest/workspaces/moj_projekat/datastores/katop_lat/featuretypes" 2>/dev/null && echo "  KatOp_Lat (opstine) ok" || true

echo "=== 6. WFS max features ==="
GEOSERVER_REST="$GS/rest" python3 scripts/setup_wfs_maxfeatures.py 2>/dev/null || true

echo ""
echo "=== Gotovo! Otvori: http://localhost:8088/leaflet_demo.html ==="
