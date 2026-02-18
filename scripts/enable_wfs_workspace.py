#!/usr/bin/env python3
"""Ukljuci WFS za workspace moj_projekat (GeoServer REST)."""
import json
import os
from urllib.request import Request, urlopen
from urllib.error import HTTPError

REST = os.environ.get("GEOSERVER_REST", "http://localhost:8083/geoserver/rest")
AUTH = ("admin", "geoserver")
WS = "moj_projekat"

def req(method, path, data=None):
    import base64
    url = REST.rstrip("/") + path
    r = Request(url, method=method)
    r.add_header("Content-Type", "application/json")
    r.add_header("Accept", "application/json")
    cred = base64.b64encode(f"{AUTH[0]}:{AUTH[1]}".encode()).decode()
    r.add_header("Authorization", f"Basic {cred}")
    if data is not None:
        r.data = json.dumps(data).encode("utf-8")
    with urlopen(r, timeout=10) as res:
        return res.status, res.read().decode()

def main():
    try:
        status, body = req("GET", f"/services/wfs/workspaces/{WS}/settings.json")
    except HTTPError as e:
        if e.code == 404:
            print("WFS workspace settings nisu dostupni (404) - mozda WFS vec ukljucen globalno.")
            return 0
        raise
    if status != 200:
        print("GET WFS settings failed:", status)
        return 1
    data = json.loads(body)
    data["wfs"]["enabled"] = True
    status, body = req("PUT", f"/services/wfs/workspaces/{WS}/settings.json", data)
    if status != 200:
        print("PUT WFS settings failed:", status, body[:200])
        return 1
    print("WFS ukljucen za workspace", WS)
    return 0

if __name__ == "__main__":
    exit(main())
