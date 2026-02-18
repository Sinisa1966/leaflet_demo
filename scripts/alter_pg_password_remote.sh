#!/bin/bash
set -e
ENV_FILE="/root/kopernikus-gis/ndvi_auto/.env"
if [ ! -f "$ENV_FILE" ]; then
  echo "Nema .env na serveru."
  exit 1
fi
NEWPASS=$(grep 'POSTGRES_PASS=' "$ENV_FILE" | sed 's/^[^=]*=//' | tr -d '\r\n' | sed "s/^['\"]//;s/['\"]$//" | sed 's/^ *//;s/ *$//')
if [ -z "$NEWPASS" ]; then
  echo "POSTGRES_PASS je prazan ili nije u .env"
  exit 1
fi
# Escape single quotes for SQL: ' -> ''
NEWPASS_SQL="${NEWPASS//\'/\'\'}"
docker exec -e PGPASSWORD=admin123 gis_db psql -h 127.0.0.1 -U admin -d moj_gis -c "ALTER USER admin WITH PASSWORD '${NEWPASS_SQL}';"
echo "ALTER USER admin uspesno izvrsen."
