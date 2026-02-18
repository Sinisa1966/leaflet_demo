#!/usr/bin/env python3
"""
Omogući GeoWebCache tile caching SAMO za površine preko 1 km².
Smanjuje traffic - WMTS umesto WMS = keširani tile-ovi (~80% manje renderovanja).

PRAVILO: Tile caching samo za površine > 1 km².
        Parcele (~5 ha = 0.05 km²) ostaju WMS – ispod praga.

Pokretati na serveru: python3 scripts/setup_geowebcache_hetzner.py
"""
import base64
import sys
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import quote

# GeoServer GWC preko nginx (8088)
GS_BASE = "http://localhost:8088/geoserver"
AUTH = ("admin", "geoserver")

# Samo površine > 1 km² – parcel layeri (~5 ha) ispod praga
LAYERS = [
    "moj_projekat:ndvi_srbija",
    "moj_projekat:ndmi_srbija",
    "moj_projekat:ndre_srbija",
    "moj_projekat:evi_srbija",
    "moj_projekat:drought_zones",
]


def gwc_layer_xml(layer_name: str) -> str:
    """Minimal GeoServerLayer XML za GWC REST API."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<GeoServerLayer>
  <enabled>true</enabled>
  <name>{layer_name}</name>
  <mimeFormats>
    <string>image/png</string>
  </mimeFormats>
  <gridSubsets>
    <gridSubset>
      <gridSetName>EPSG:900913</gridSetName>
      <zoomStart>0</zoomStart>
      <zoomStop>18</zoomStop>
    </gridSubset>
    <gridSubset>
      <gridSetName>EPSG:4326</gridSetName>
      <zoomStart>0</zoomStart>
      <zoomStop>18</zoomStop>
    </gridSubset>
  </gridSubsets>
  <metaWidthHeight>
    <int>4</int>
    <int>4</int>
  </metaWidthHeight>
  <gutter>0</gutter>
  <autoCacheStyles>true</autoCacheStyles>
</GeoServerLayer>"""


def _is_parcel_layer(name: str) -> bool:
    """Layer ispod 1 km² (parcela ~5 ha) – ne keširati."""
    lower = name.lower()
    return "parcela" in lower or "parcel_" in lower


def put_gwc_layer(layer_name: str) -> bool:
    """Dodaj ili ažuriraj GWC tile layer."""
    if _is_parcel_layer(layer_name):
        print(f"  PRESKOČENO (parcela – mala površina, ne keširati)")
        return False
    url = f"{GS_BASE}/gwc/rest/layers/{quote(layer_name, safe='')}.xml"
    xml = gwc_layer_xml(layer_name)
    req = Request(url, data=xml.encode("utf-8"), method="PUT")
    req.add_header("Content-Type", "text/xml")
    cred = base64.b64encode(f"{AUTH[0]}:{AUTH[1]}".encode()).decode()
    req.add_header("Authorization", f"Basic {cred}")
    try:
        with urlopen(req, timeout=30) as r:
            return 200 <= r.status < 300
    except HTTPError as e:
        print(f"  HTTP {e.code}: {e.read().decode()[:200]}")
        return False
    except URLError as e:
        print(f"  Greška: {e}")
        return False


def main():
    print("=== GeoWebCache – omogućavanje tile caching za Serbia layere ===\n")
    ok = 0
    for layer in LAYERS:
        print(f"  {layer} ... ", end="")
        if put_gwc_layer(layer):
            print("OK")
            ok += 1
        else:
            print("FAIL (layer možda ne postoji u GeoServer-u)")
    print(f"\nRezultat: {ok}/{len(LAYERS)} layera")
    print("\nWMTS test (EPSG:900913):")
    print(f"  {GS_BASE}/gwc/service/wmts?layer=moj_projekat:ndvi_srbija&tilematrixset=EPSG:900913&Service=WMTS&Request=GetTile&Version=1.0.0&Format=image/png&TileMatrix=7&TileRow=45&TileCol=67")
    return 0 if ok > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
