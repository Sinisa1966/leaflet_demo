#!/bin/bash
# Primeni pomeraj -0.0052 ( ~410m ulevo) na katop_lat i kat_opstine u Postgres na Hetzneru,
# zatim osvezi GeoServer (reload).
# Pokrenuti na serveru: bash scripts/apply_opstine_shift_hetzner.sh

set -e
cd "$(dirname "$0")/.."
[ -f ndvi_auto/.env ] && set -a && . ndvi_auto/.env && set +a
: "${POSTGRES_USER:=admin}"
: "${POSTGRES_DB:=moj_gis}"
: "${POSTGRES_PASS:=}"
: "${GEOSERVER_USER:=admin}"
: "${GEOSERVER_PASSWORD:=}"

if [ -z "$POSTGRES_PASS" ]; then
  echo "POSTGRES_PASS nije u ndvi_auto/.env"
  exit 1
fi

echo "1. UPDATE katop_lat i kat_opstine (pomeraj -0.0052)..."
docker exec -e PGPASSWORD="$POSTGRES_PASS" gis_db psql -h 127.0.0.1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "UPDATE katop_lat SET wkb_geometry = ST_Translate(wkb_geometry, -0.0052, 0);"
docker exec -e PGPASSWORD="$POSTGRES_PASS" gis_db psql -h 127.0.0.1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "UPDATE kat_opstine SET wkb_geometry = ST_Translate(wkb_geometry, -0.0052, 0);"

echo "2. GeoServer reload..."
GS="http://localhost:8088/geoserver"
curl -s -u "${GEOSERVER_USER}:${GEOSERVER_PASSWORD}" -X POST "${GS}/rest/reload" || true

echo "Gotovo. Osvezi mapu (Ctrl+F5) i ukljuci slojeve Opstine i Katastarske opstine."

