#!/bin/bash
# Menja GeoServer admin šifru preko REST API (stara=geoserver, nova=iz .env).
set -e
ENV_FILE="/root/kopernikus-gis/ndvi_auto/.env"
NEWPASS=$(grep 'GEOSERVER_PASSWORD=' "$ENV_FILE" 2>/dev/null | sed 's/^[^=]*=//' | tr -d '\r\n' | sed "s/^['\"]//;s/['\"]$//" | sed 's/^ *//;s/ *$//')
[ -z "$NEWPASS" ] && NEWPASS=$(grep 'GEOSERVER_ADMIN_PASSWORD=' "$ENV_FILE" 2>/dev/null | sed 's/^[^=]*=//' | tr -d '\r\n' | sed "s/^['\"]//;s/['\"]$//" | sed 's/^ *//;s/ *$//')
[ -z "$NEWPASS" ] && echo "GEOSERVER_PASSWORD nije u .env" && exit 1
GS="http://localhost:8088/geoserver"
BODY=$(python3 -c "import json,sys; print(json.dumps({'oldPassword':'geoserver','newPassword':sys.argv[1]}))" "$NEWPASS") || exit 1
HTTP=$(curl -s -o /tmp/gs_pw_resp.txt -w "%{http_code}" -u "admin:geoserver" -X PUT -H "Content-type: application/json" -d "$BODY" "$GS/rest/security/self/password")
if [ "$HTTP" = "200" ]; then
  echo "GeoServer admin šifra uspešno promenjena."
else
  echo "HTTP $HTTP"; cat /tmp/gs_pw_resp.txt
fi
rm -f /tmp/gs_pw_resp.txt
