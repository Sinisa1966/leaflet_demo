#!/bin/bash
# Restore Hetzner kontejnera iz full backup-a (db + GeoServer + .env).
# Upotreba: cd /root/kopernikus-gis && bash scripts/restore_hetzner.sh hetzner-full-backup-YYYYMMDD_HHMMSS.tar.gz
# Ili:     bash scripts/restore_hetzner.sh /root/kopernikus-gis/backups/hetzner-full-backup-....tar.gz

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

if [ -z "$1" ]; then
  echo "Upotreba: bash scripts/restore_hetzner.sh <backup-arhiva>"
  echo "Primer:   bash scripts/restore_hetzner.sh hetzner-full-backup-20260215_123456.tar.gz"
  echo "          (fajl može biti u backups/ ili puna putanja)"
  exit 1
fi

ARCHIVE="$1"
if [ ! -f "$ARCHIVE" ]; then
  # Možda je u backups/
  if [ -f "$PROJECT_ROOT/backups/$ARCHIVE" ]; then
    ARCHIVE="$PROJECT_ROOT/backups/$ARCHIVE"
  else
    echo "Greška: arhiva nije pronađena: $1"
    exit 1
  fi
fi

RESTORE_DIR="$PROJECT_ROOT/restore_temp"
BACKUP_NAME=$(basename "$ARCHIVE" .tar.gz)

echo "=== Restore iz backup-a ==="
echo "Arhiva:   $ARCHIVE"
echo "Projekat: $PROJECT_ROOT"
echo ""

# Ekstrakcija
echo "[1/6] Ekstrahujem arhivu..."
rm -rf "$RESTORE_DIR"
mkdir -p "$RESTORE_DIR"
tar -xzf "$ARCHIVE" -C "$RESTORE_DIR"
RESTORE_CONTENT="$RESTORE_DIR/$BACKUP_NAME"
if [ ! -d "$RESTORE_CONTENT" ]; then
  RESTORE_CONTENT="$RESTORE_DIR"
fi
echo "       OK"

# Zaustavi kontejnere
echo "[2/6] Zaustavljam kontejnere..."
docker compose -f docker-compose.hetzner.yml down
echo "       OK"

# Pokreni samo bazu
echo "[3/6] Pokrećem PostgreSQL..."
docker compose -f docker-compose.hetzner.yml up -d db
echo "       Čekam 10s da baza ustane..."
sleep 10

# Restore baze (drop + create + restore) – šifra iz backup .env
POSTGRES_PASS=""
if [ -f "$RESTORE_CONTENT/ndvi_auto_env.txt" ]; then
  POSTGRES_PASS=$(grep -E "^POSTGRES_PASS=" "$RESTORE_CONTENT/ndvi_auto_env.txt" 2>/dev/null | cut -d= -f2- | tr -d '"' | tr -d "'" || true)
fi
echo "[4/6] Restore PostgreSQL (moj_gis)..."
docker exec -e PGPASSWORD="$POSTGRES_PASS" gis_db psql -h 127.0.0.1 -U admin -d postgres -c "DROP DATABASE IF EXISTS moj_gis;"
docker exec -e PGPASSWORD="$POSTGRES_PASS" gis_db psql -h 127.0.0.1 -U admin -d postgres -c "CREATE DATABASE moj_gis;"
docker exec -e PGPASSWORD="$POSTGRES_PASS" -i gis_db psql -h 127.0.0.1 -U admin moj_gis < "$RESTORE_CONTENT/db_moj_gis.sql"
echo "       OK"

# Restore GeoServer data u volume
echo "[5/6] Restore GeoServer data..."
GEOSERVER_VOL=$(docker volume ls -q --filter name=geoserver_data | head -1)
if [ -z "$GEOSERVER_VOL" ]; then
  echo "       Upozorenje: volume geoserver_data nije pronađen (compose ga kreira pri prvom up). Preskačem."
else
  docker run --rm \
    -v "$GEOSERVER_VOL:/opt/geoserver_data" \
    -v "$RESTORE_CONTENT:/in:ro" \
    alpine sh -c "rm -rf /opt/geoserver_data/* /opt/geoserver_data/.[!.]* 2>/dev/null; tar xzf /in/geoserver_data.tar.gz -C /opt/geoserver_data; echo OK"
  echo "       OK"
fi

# .env
if [ -f "$RESTORE_CONTENT/ndvi_auto_env.txt" ]; then
  echo "       Kopiram ndvi_auto/.env iz backup-a..."
  cp "$RESTORE_CONTENT/ndvi_auto_env.txt" ndvi_auto/.env
  chmod 600 ndvi_auto/.env
fi

# Ponovo podigni sve
echo "[6/6] Pokrećem sve kontejnere..."
docker compose -f docker-compose.hetzner.yml up -d
rm -rf "$RESTORE_DIR"

echo ""
echo "========================================"
echo "  Restore uspešan!"
echo "========================================"
echo ""
echo "  Provera: http://89.167.39.148:8088/leaflet_demo.html"
echo "  Ako WFS slojevi nedostaju, ponovo pokreni: bash scripts/setup_geoserver_hetzner.sh"
echo ""
