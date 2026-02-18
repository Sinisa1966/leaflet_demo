#!/usr/bin/env python3
"""Jednokratno postavljanje ndre_zones_style za postojeći layer na GeoServer-u."""
import sys
from pathlib import Path

script_dir = Path(__file__).resolve().parent
from download_and_publish import geoserver_put, get_env, geoserver_request, load_env

load_env(script_dir / ".env")
geoserver_url = get_env("GEOSERVER_URL", "http://localhost:8083/geoserver").rstrip("/")
geoserver_user = get_env("GEOSERVER_USER", "admin")
geoserver_password = get_env("GEOSERVER_PASSWORD", "geoserver")
workspace = get_env("GEOSERVER_WORKSPACE", "moj_projekat")
style = "ndre_zones_style"
layer = "ndre_zones_parcela_1427_2"

print(f"[INFO] Uploadujem stil {style}...")
sld_path = script_dir / f"{style}.sld"
if not sld_path.exists():
    print(f"[ERROR] {sld_path} ne postoji")
    sys.exit(1)
sld_bytes = sld_path.read_bytes()
# Kreiraj styl u workspace-u
import urllib.parse
ws_style_url = f"{geoserver_url}/rest/workspaces/{workspace}/styles"
post_url = f"{ws_style_url}?name={urllib.parse.quote(style)}"
status, body = geoserver_request("POST", post_url, geoserver_user, geoserver_password, sld_bytes, "application/vnd.ogc.sld+xml")
if status in (200, 201):
    print("  Stil kreiran (POST)")
elif status == 409:
    print("  Stil postoji, ažuriram (PUT)...")
    put_url = f"{geoserver_url}/rest/workspaces/{workspace}/styles/{style}?raw=true"
    status2, body2 = geoserver_request("PUT", put_url, geoserver_user, geoserver_password, sld_bytes, "application/vnd.ogc.sld+xml")
    if status2 not in (200, 201):
        print(f"[ERROR] Style update failed ({status2}): {body2[:800]}")
        sys.exit(1)
else:
    print(f"[ERROR] Style create failed ({status}): {body[:800]}")
    sys.exit(1)
print(f"[INFO] Postavljam defaultStyle za layer {workspace}:{layer}...")
# Referenciraj workspace:style
style_xml = f"<layer><defaultStyle><name>{workspace}:{style}</name></defaultStyle></layer>".encode("utf-8")
style_url = f"{geoserver_url}/rest/layers/{workspace}:{layer}"
geoserver_put(style_url, geoserver_user, geoserver_password, style_xml, "text/xml")
print("[INFO] Gotovo!")
