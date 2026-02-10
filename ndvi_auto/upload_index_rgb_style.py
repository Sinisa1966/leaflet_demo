#!/usr/bin/env python3
"""
Upload index_rgb_style.sld to GeoServer
"""
import os
import sys
from pathlib import Path
import urllib.parse
import urllib.request
import base64


def load_env(env_path: Path) -> None:
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if value:
            os.environ[key] = value


def get_env(name: str, default=None, required: bool = False) -> str:
    value = os.getenv(name, default)
    if required and not value:
        print(f"[ERROR] Missing env var: {name}")
        sys.exit(1)
    return value


def geoserver_request(
    method: str, url: str, user: str, password: str, data: bytes, content_type: str
) -> tuple[int, str]:
    creds = base64.b64encode(f"{user}:{password}".encode("utf-8")).decode("ascii")
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Basic {creds}")
    req.add_header("Content-Type", content_type)
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            return resp.status, resp.read().decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="ignore")


def ensure_style(
    geoserver_url: str,
    user: str,
    password: str,
    name: str,
    sld_path: Path,
) -> None:
    if not sld_path.exists():
        print(f"[WARN] Style file missing: {sld_path}")
        return
    sld_bytes = sld_path.read_bytes()
    put_url = f"{geoserver_url}/rest/styles/{name}?raw=true"
    status, _ = geoserver_request(
        "PUT", put_url, user, password, sld_bytes, "application/vnd.ogc.sld+xml"
    )
    if status == 404:
        post_url = f"{geoserver_url}/rest/styles?name={urllib.parse.quote(name)}"
        status, body = geoserver_request(
            "POST", post_url, user, password, sld_bytes, "application/vnd.ogc.sld+xml"
        )
        if status not in (200, 201):
            print(f"[ERROR] Style create failed ({status}): {body}")
            sys.exit(1)
        print(f"[INFO] Style '{name}' created successfully")
    elif status not in (200, 201):
        print(f"[ERROR] Style update failed ({status})")
        sys.exit(1)
    else:
        print(f"[INFO] Style '{name}' updated successfully")


def main() -> None:
    script_dir = Path(__file__).resolve().parent
    load_env(script_dir / ".env")

    geoserver_url = get_env("GEOSERVER_URL", "http://localhost:8083/geoserver").rstrip("/")
    geoserver_user = get_env("GEOSERVER_USER", "admin")
    geoserver_password = get_env("GEOSERVER_PASSWORD", "geoserver")

    sld_path = script_dir / "index_rgb_style.sld"
    style_name = "index_rgb_style"

    print(f"[INFO] Uploading style '{style_name}' to GeoServer at {geoserver_url}")
    ensure_style(geoserver_url, geoserver_user, geoserver_password, style_name, sld_path)
    print(f"[INFO] Done!")


if __name__ == "__main__":
    main()
