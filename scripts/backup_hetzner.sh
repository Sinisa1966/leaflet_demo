#!/bin/bash
# Backup Hetzner kontejnera (PostgreSQL + GeoServer data + .env) za disaster recovery.
# Pokretati na serveru: cd /root/kopernikus-gis && bash scripts/backup_hetzner.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

BACKUPS_DIR="$PROJECT_ROOT/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="hetzner-full-backup-$TIMESTAMP"
BACKUP_DIR="$BACKUPS_DIR/$BACKUP_NAME"
ARCHIVE="$BACKUPS_DIR/$BACKUP_NAME.tar.gz"

echo "=== Backup Hetzner (PostgreSQL + GeoServer + .env) ==="
echo "Projekat: $PROJECT_ROOT"
echo "Backup:   $BACKUP_NAME"
echo ""

mkdir -p "$BACKUP_DIR"

# Učitaj POSTGRES_PASS iz .env (za pg_dump u kontejneru)
POSTGRES_PASS=""
if [ -f ndvi_auto/.env ]; then
  POSTGRES_PASS=$(grep -E "^POSTGRES_PASS=" ndvi_auto/.env 2>/dev/null | cut -d= -f2- | tr -d '"' | tr -d "'" || true)
fi

# 1. PostgreSQL dump
echo "[1/4] PostgreSQL dump (gis_db -> moj_gis)..."
docker exec -e PGPASSWORD="$POSTGRES_PASS" gis_db pg_dump -h 127.0.0.1 -U admin moj_gis > "$BACKUP_DIR/db_moj_gis.sql"
echo "       OK ($(wc -l < "$BACKUP_DIR/db_moj_gis.sql") linija)"

# 2. GeoServer data dir
echo "[2/4] GeoServer data (geoserver -> /opt/geoserver_data)..."
docker exec geoserver tar czf /tmp/geoserver_data_backup.tar.gz -C /opt/geoserver_data .
docker cp geoserver:/tmp/geoserver_data_backup.tar.gz "$BACKUP_DIR/geoserver_data.tar.gz"
docker exec geoserver rm -f /tmp/geoserver_data_backup.tar.gz
echo "       OK ($(du -h "$BACKUP_DIR/geoserver_data.tar.gz" | cut -f1))"

# 3. .env (potreban za restore)
echo "[3/4] ndvi_auto/.env..."
if [ -f ndvi_auto/.env ]; then
  cp ndvi_auto/.env "$BACKUP_DIR/ndvi_auto_env.txt"
  echo "       OK (sačuvano kao ndvi_auto_env.txt)"
else
  echo "       Nema .env – posle restore kopiraj ručno iz env.example i popuni šifre"
fi

# 4. Manifest
echo "[4/4] Manifest..."
cat > "$BACKUP_DIR/MANIFEST.txt" << EOF
Hetzner full backup – Kopernikus-GIS
====================================
Datum:    $(date -Iseconds)
Hostname: $(hostname)
Backup:   $BACKUP_NAME

Sadržaj:
- db_moj_gis.sql       – PostgreSQL dump (baza moj_gis)
- geoserver_data.tar.gz – GeoServer /opt/geoserver_data
- ndvi_auto_env.txt    – kopija ndvi_auto/.env (ako postoji)
- MANIFEST.txt        – ovaj fajl

Restore:
  cd /root/kopernikus-gis
  bash scripts/restore_hetzner.sh $BACKUP_NAME.tar.gz

Ili ručno: docs/PODSETNIK_DEPLOY_HETZNER.md + restore_hetzner.sh komentari.
EOF
echo "       OK"

# Pakovanje u jedan arhiv
echo ""
echo "Pakovanje u $ARCHIVE ..."
tar -czf "$ARCHIVE" -C "$BACKUPS_DIR" "$BACKUP_NAME"
rm -rf "$BACKUP_DIR"
SIZE=$(du -h "$ARCHIVE" | cut -f1)
echo ""
echo "========================================"
echo "  Backup uspešan!"
echo "========================================"
echo ""
echo "  Fajl:  $ARCHIVE"
echo "  Veličina: $SIZE"
echo ""
echo "  Restore: bash scripts/restore_hetzner.sh $BACKUP_NAME.tar.gz"
echo ""
