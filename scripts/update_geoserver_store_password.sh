#!/bin/bash
# Ažurira šifru PostGIS u svim postojećim GeoServer store-ovima (PUT).
# Pokrenuti na serveru posle ALTER USER.
set -e
ENV_FILE="/root/kopernikus-gis/ndvi_auto/.env"
[ -f "$ENV_FILE" ] && set -a && . "$ENV_FILE" && set +a
POSTGRES_USER="${POSTGRES_USER:-admin}"
POSTGRES_DB="${POSTGRES_DB:-moj_gis}"
GEOSERVER_USER="${GEOSERVER_USER:-admin}"
GEOSERVER_PASSWORD="${GEOSERVER_PASSWORD:-}"
[ -z "$POSTGRES_PASS" ] && echo "POSTGRES_PASS nije setovan." && exit 1
[ -z "$GEOSERVER_PASSWORD" ] && echo "GEOSERVER_PASSWORD nije setovan." && exit 1

GS="http://localhost:8088/geoserver"
AUTH="${GEOSERVER_USER}:${GEOSERVER_PASSWORD}"

for STORE in kovin_dkp_pg vrsac_dkp_pg pancevo_dkp_pg katop_lat kat_opstine pancevo_adrese; do
  curl -s -u "$AUTH" -X PUT -H "Content-type: application/json" \
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
    "$GS/rest/workspaces/moj_projekat/datastores/$STORE" && echo "  $STORE ažuriran" || echo "  $STORE skip"
done
echo "Gotovo."
