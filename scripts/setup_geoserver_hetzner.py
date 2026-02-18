#!/usr/bin/env python3
"""
Setup GeoServer na Hetzner - workspace, PostGIS stores, layere.
Pokretati na serveru: python3 scripts/setup_geoserver_hetzner.py
"""
import json
import os
import sys
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

# Učitaj ndvi_auto/.env (POSTGRES_USER, POSTGRES_PASS, POSTGRES_DB)
_env_path = os.path.join(os.path.dirname(__file__), "..", "ndvi_auto", ".env")
if os.path.isfile(_env_path):
    with open(_env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip().strip("'\"")

POSTGRES_USER = os.environ.get("POSTGRES_USER", "admin")
POSTGRES_PASS = os.environ.get("POSTGRES_PASS", "")
POSTGRES_DB = os.environ.get("POSTGRES_DB", "moj_gis")
GEOSERVER_USER = os.environ.get("GEOSERVER_USER", "admin")
GEOSERVER_PASSWORD = os.environ.get("GEOSERVER_PASSWORD", "")
if not POSTGRES_PASS:
    print("Greška: POSTGRES_PASS nije postavljen u ndvi_auto/.env")
    sys.exit(1)
if not GEOSERVER_PASSWORD:
    print("Greška: GEOSERVER_PASSWORD nije postavljen u ndvi_auto/.env")
    sys.exit(1)

# GeoServer kroz nginx proxy (port 8088) – direktan 8083 više nije izložen
GS_URL = "http://localhost:8088/geoserver/rest"
AUTH = (GEOSERVER_USER, GEOSERVER_PASSWORD)

def rest(method, path, data=None):
    url = f"{GS_URL}{path}"
    req = Request(url, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    import base64
    cred = base64.b64encode(f"{AUTH[0]}:{AUTH[1]}".encode()).decode()
    req.add_header("Authorization", f"Basic {cred}")
    if data:
        req.data = json.dumps(data).encode("utf-8")
    try:
        with urlopen(req, timeout=30) as r:
            return r.status, r.read().decode()
    except HTTPError as e:
        return e.code, e.read().decode() if e.fp else ""
    except URLError as e:
        print(f"  Greška: {e}")
        return 0, ""

def main():
    # 1. Workspace
    print("1. Workspace moj_projekat...")
    code, _ = rest("POST", "/workspaces", {"workspace": {"name": "moj_projekat"}})
    if code in (201, 409):
        print("   OK")
    else:
        print(f"   Kod {code}")

    # 2. PostGIS stores
    stores = [
        ("kovin_dkp_pg", "kovin_dkp_pg"),
        ("vrsac_dkp_pg", "vrsac_dkp_pg"),
        ("pancevo_dkp_pg", "pancevo_dkp_pg"),
    ]
    for name, table in stores:
        print(f"2. Store {name}...")
        data = {
            "dataStore": {
                "name": name,
                "type": "PostGIS",
                "enabled": True,
                "connectionParameters": {
                    "entry": [
                        {"@key": "host", "$": "db"},
                        {"@key": "port", "$": "5432"},
                        {"@key": "database", "$": POSTGRES_DB},
                        {"@key": "user", "$": POSTGRES_USER},
                        {"@key": "passwd", "$": POSTGRES_PASS},
                        {"@key": "schema", "$": "public"},
                        {"@key": "dbtype", "$": "postgis"},
                    ]
                },
            }
        }
        code, body = rest("POST", f"/workspaces/moj_projekat/datastores", data)
        if code in (201, 409):
            print("   OK")
        else:
            print(f"   Kod {code}: {body[:200]}")

    # 3. Feature types (publish layers)
    for name in ["kovin_dkp_pg", "vrsac_dkp_pg", "pancevo_dkp_pg"]:
        print(f"3. Layer {name}...")
        data = {
            "featureType": {
                "name": name,
                "nativeName": name,
                "enabled": True,
                "srs": "EPSG:4326",
            }
        }
        code, body = rest("POST", f"/workspaces/moj_projekat/datastores/{name}/featuretypes", data)
        if code in (201, 409):
            print("   OK")
        else:
            print(f"   Kod {code}: {body[:200] if body else ''}")

    print("\nGotovo! Test: http://89.167.39.148:8088/leaflet_demo.html")

if __name__ == "__main__":
    main()
