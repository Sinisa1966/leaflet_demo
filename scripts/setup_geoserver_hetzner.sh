#!/bin/bash
# Setup GeoServer na Hetzner serveru - učitaj parcele i konfiguriši WFS layere
# Pokrenuti na serveru: bash setup_geoserver_hetzner.sh
# Mora biti u /root/kopernikus-gis

set -e
PROJECT_DIR="/root/kopernikus-gis"
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
: "${GEOSERVER_USER:=admin}"
: "${GEOSERVER_PASSWORD:=}"
if [ -z "${POSTGRES_PASS}" ]; then
  echo "Greška: POSTGRES_PASS nije postavljen u ndvi_auto/.env"
  exit 1
fi
if [ -z "${GEOSERVER_PASSWORD}" ]; then
  echo "Greška: GEOSERVER_PASSWORD nije postavljen u ndvi_auto/.env"
  exit 1
fi

echo "=== 1. Kopiranje shapefile-ova u PostgreSQL kontejner ==="
docker cp DKP-Kovin gis_db:/tmp/
docker cp DKP-Vrsac gis_db:/tmp/
docker cp PancevoDKP gis_db:/tmp/PancevoDKP 2>/dev/null || true
docker cp "Pancevo-adrese" gis_db:/tmp/Pancevo-adrese 2>/dev/null || true
docker cp opstine gis_db:/tmp/opstine 2>/dev/null || true
docker cp kat-opstine gis_db:/tmp/kat-opstine 2>/dev/null || true

echo "=== 2. Import u PostgreSQL (ogr2ogr) - VAŽNO: -t_srs EPSG:4326 za lat/lon ==="
PG="PG:host=127.0.0.1 dbname=${POSTGRES_DB} user=${POSTGRES_USER} password=${POSTGRES_PASS}"
# Shapefile-ovi u UTM/SRB07; reprojektuj u WGS84
docker exec gis_db ogr2ogr -f PostgreSQL "$PG" /tmp/DKP-Kovin/KovinDKP.shp -nln public.kovin_dkp_pg -nlt PROMOTE_TO_MULTI -t_srs EPSG:4326 -overwrite
docker exec gis_db ogr2ogr -f PostgreSQL "$PG" /tmp/DKP-Vrsac/VrsacDKP.shp -nln public.vrsac_dkp_pg -nlt PROMOTE_TO_MULTI -t_srs EPSG:4326 -overwrite
docker exec gis_db ogr2ogr -f PostgreSQL "$PG" /tmp/PancevoDKP/PancevoDKP.shp -nln public.pancevo_dkp_pg -nlt PROMOTE_TO_MULTI -t_srs EPSG:4326 -overwrite 2>/dev/null || true
docker exec gis_db ogr2ogr -f PostgreSQL "$PG" /tmp/opstine/Op_Lat.shp -nln public.katop_lat -nlt PROMOTE_TO_MULTI -t_srs EPSG:4326 -overwrite 2>/dev/null && echo "  opstine OK" || true
docker exec gis_db ogr2ogr -f PostgreSQL "$PG" /tmp/kat-opstine/KatOp_Lat.shp -nln public.kat_opstine -nlt PROMOTE_TO_MULTI -t_srs EPSG:4326 -overwrite 2>/dev/null && echo "  kat_opstine OK" || true
docker exec gis_db ogr2ogr -f PostgreSQL "$PG" /tmp/Pancevo-adrese/PancevoDKP.shp -nln public.pancevo_adrese -nlt PROMOTE_TO_MULTI -t_srs EPSG:4326 -overwrite 2>/dev/null && echo "  pancevo_adrese OK" || true
# Opstine i kat_opstine: shapefile-ovi u repou su vec ispravljeni (~410m ulevo), nema UPDATE

echo "=== 3. Provera tabela ==="
docker exec gis_db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "\dt public.*dkp*" 2>/dev/null || true

echo "=== 4. GeoServer REST API - kreiraj workspace moj_projekat ==="
# GeoServer preko nginx proxy (8088) - port 8083 više nije izložen
GS="http://localhost:8088/geoserver"
AUTH="${GEOSERVER_USER}:${GEOSERVER_PASSWORD}"

curl -s -u "$AUTH" -X POST -H "Content-type: application/json" \
  -d '{"workspace":{"name":"moj_projekat"}}' \
  "$GS/rest/workspaces" 2>/dev/null || echo "(workspace možda već postoji)"

echo ""
echo "=== 5. GeoServer - kreiraj PostGIS datastore ==="
# Jedan shared store koji vidi sve scheme, ili posebni store po tabeli
# Koristimo posebne store-ove kovin_dkp_pg, vrsac_dkp_pg da odgovaraju leaflet_demo
for STORE in kovin_dkp_pg vrsac_dkp_pg pancevo_dkp_pg katop_lat kat_opstine pancevo_adrese; do
  TABLE="$(echo $STORE | tr '[:upper:]' '[:lower:]')"
  curl -s -u "$AUTH" -X POST -H "Content-type: application/json" \
    -d "{
      \"dataStore\": {
        \"name\": \"$STORE\",
        \"type\": \"PostGIS\",
        \"enabled\": true,
        \"connectionParameters\": {
          \"entry\": [
            {\"@key\":\"host\",\"$\":\"db\"},
            {\"@key\":\"port\",\"$\":\"5432\"},
            {\"@key\":\"database\",\"$\":\"${POSTGRES_DB}\"},
            {\"@key\":\"user\",\"$\":\"${POSTGRES_USER}\"},
            {\"@key\":\"passwd\",\"$\":\"${POSTGRES_PASS}\"},
            {\"@key\":\"schema\",\"$\":\"public\"},
            {\"@key\":\"dbtype\",\"$\":\"postgis\"}
          ]
        }
      }
    }" \
    "$GS/rest/workspaces/moj_projekat/datastores" 2>/dev/null && echo "  $STORE ok" || echo "  $STORE skip (možda postoji)"
done

echo ""
echo "=== 6. GeoServer - publish feature types ==="
for LAYER in kovin_dkp_pg vrsac_dkp_pg pancevo_dkp_pg; do
  curl -s -u "$AUTH" -X POST -H "Content-type: application/json" \
    -d "{
      \"featureType\": {
        \"name\": \"$LAYER\",
        \"nativeName\": \"$LAYER\",
        \"enabled\": true,
        \"srs\": \"EPSG:4326\",
        \"nativeBoundingBox\": {\"minx\":19,\"maxx\":23,\"miny\":42,\"maxy\":46}
      }
    }" \
    "$GS/rest/workspaces/moj_projekat/datastores/$LAYER/featuretypes" 2>/dev/null && echo "  Layer $LAYER published" || echo "  Layer $LAYER skip"
done
# Opštine: publish kao KatOp_Lat (leaflet_demo WFS typeName)
curl -s -u "$AUTH" -X POST -H "Content-type: application/json" \
  -d "{
    \"featureType\": {
      \"name\": \"KatOp_Lat\",
      \"nativeName\": \"katop_lat\",
      \"enabled\": true,
      \"srs\": \"EPSG:4326\",
      \"nativeBoundingBox\": {\"minx\":18,\"maxx\":23,\"miny\":42,\"maxy\":47}
    }
  }" \
  "$GS/rest/workspaces/moj_projekat/datastores/katop_lat/featuretypes" 2>/dev/null && echo "  Layer KatOp_Lat (opstine) published" || echo "  KatOp_Lat skip"
# Katastarske opštine
curl -s -u "$AUTH" -X POST -H "Content-type: application/json" \
  -d "{
    \"featureType\": {
      \"name\": \"KatOp_Kat\",
      \"nativeName\": \"kat_opstine\",
      \"enabled\": true,
      \"srs\": \"EPSG:4326\",
      \"nativeBoundingBox\": {\"minx\":18,\"maxx\":23,\"miny\":42,\"maxy\":47}
    }
  }" \
  "$GS/rest/workspaces/moj_projekat/datastores/kat_opstine/featuretypes" 2>/dev/null && echo "  Layer KatOp_Kat (kat. opstine) published" || echo "  KatOp_Kat skip"
# Pancevo-adrese
curl -s -u "$AUTH" -X POST -H "Content-type: application/json" \
  -d "{
    \"featureType\": {
      \"name\": \"pancevo_adrese\",
      \"nativeName\": \"pancevo_adrese\",
      \"enabled\": true,
      \"srs\": \"EPSG:4326\",
      \"nativeBoundingBox\": {\"minx\":18,\"maxx\":23,\"miny\":42,\"maxy\":47}
    }
  }" \
  "$GS/rest/workspaces/moj_projekat/datastores/pancevo_adrese/featuretypes" 2>/dev/null && echo "  Layer pancevo_adrese (Pancevo-adrese) published" || echo "  pancevo_adrese skip"

echo ""
echo "=== 7. WFS max features = 1000 (ograniči veliki GeoJSON) ==="
python3 scripts/setup_wfs_maxfeatures.py || echo "  (pokrenuti ručno: python3 scripts/setup_wfs_maxfeatures.py)"

echo ""
echo "=== Gotovo! Proveri: http://89.167.39.148:8088/geoserver ==="
echo "WFS test: curl -u admin:geoserver \"http://89.167.39.148:8088/geoserver/moj_projekat/ows?service=WFS&version=1.0.0&request=GetFeature&typeName=moj_projekat:kovin_dkp_pg&maxFeatures=1&outputFormat=json\""
