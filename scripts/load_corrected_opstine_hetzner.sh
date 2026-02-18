#!/bin/bash
# Ucitaj ispravljene slojeve opstine i kat_opstine u Postgres na Hetzneru (zameni postojece).
# Pokrenuti na serveru: bash scripts/load_corrected_opstine_hetzner.sh

set -e
cd "$(dirname "$0")/.."
[ -f ndvi_auto/.env ] && set -a && . ndvi_auto/.env && set +a
: "${POSTGRES_USER:=admin}"
: "${POSTGRES_DB:=moj_gis}"
: "${POSTGRES_PASS:=}"

if [ -z "$POSTGRES_PASS" ]; then
  echo "POSTGRES_PASS nije u ndvi_auto/.env"
  exit 1
fi

PG="PG:host=127.0.0.1 dbname=${POSTGRES_DB} user=${POSTGRES_USER} password=${POSTGRES_PASS}"

echo "Kopiranje opstine i kat-opstine u kontejner..."
docker cp opstine gis_db:/tmp/opstine
docker cp kat-opstine gis_db:/tmp/kat-opstine

echo "Import katop_lat (opstine) - overwrite..."
docker exec gis_db ogr2ogr -f PostgreSQL "$PG" /tmp/opstine/Op_Lat.shp -nln public.katop_lat -nlt PROMOTE_TO_MULTI -t_srs EPSG:4326 -overwrite

echo "Import kat_opstine (kat. opstine) - overwrite..."
docker exec gis_db ogr2ogr -f PostgreSQL "$PG" /tmp/kat-opstine/KatOp_Lat.shp -nln public.kat_opstine -nlt PROMOTE_TO_MULTI -t_srs EPSG:4326 -overwrite

echo "Gotovo. Oba sloja zamenjena ispravljenim podacima."