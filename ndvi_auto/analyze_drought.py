import datetime as dt
import json
import os
from pathlib import Path
import sys
import urllib.parse
import urllib.request

import numpy as np
import rasterio
from rasterio.mask import mask


TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
PROCESS_URL = "https://sh.dataspace.copernicus.eu/api/v1/process"
WFS_URL = "http://localhost:8083/geoserver/moj_projekat/ows"


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


def get_token(client_id: str, client_secret: str) -> str:
    data = urllib.parse.urlencode(
        {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        }
    ).encode("utf-8")
    req = urllib.request.Request(TOKEN_URL, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return payload["access_token"]


def fetch_katop_geom(name_value: str) -> dict:
    params = {
        "service": "WFS",
        "version": "1.0.0",
        "request": "GetFeature",
        "typeName": "moj_projekat:KatOp_Lat",
        "outputFormat": "application/json",
        "cql_filter": f"ImeKOLatV='{name_value}'",
        "srsName": "EPSG:4326",
    }
    url = f"{WFS_URL}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    features = data.get("features", [])
    if not features:
        print(f"[ERROR] Nema geometrije za: {name_value}")
        sys.exit(1)
    return features[0]["geometry"]


def build_evalscript_ndmi_raw() -> str:
    return """//VERSION=3
function setup() {
  return {
    input: ["B08", "B11", "dataMask"],
    output: { bands: 2, sampleType: "FLOAT32" }
  };
}

function evaluatePixel(sample) {
  if (sample.dataMask === 0) {
    return [0.0, 0.0];
  }
  let ndmi = (sample.B08 - sample.B11) / (sample.B08 + sample.B11);
  return [ndmi, sample.dataMask];
}
"""


def download_ndmi_raw(
    token: str,
    geometry: dict,
    time_from: str,
    time_to: str,
    width: int,
    height: int,
    max_cloud: int,
) -> bytes:
    payload = {
        "input": {
            "bounds": {
                "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/4326"},
                "geometry": geometry,
            },
            "data": [
                {
                    "type": "sentinel-2-l2a",
                    "dataFilter": {
                        "timeRange": {"from": time_from, "to": time_to},
                        "maxCloudCoverage": max_cloud,
                        "mosaickingOrder": "mostRecent",
                    },
                }
            ],
        },
        "output": {
            "width": width,
            "height": height,
            "responses": [{"identifier": "default", "format": {"type": "image/tiff"}}],
        },
        "evalscript": build_evalscript_ndmi_raw(),
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(PROCESS_URL, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=300) as resp:
        return resp.read()


def compute_stats(tif_path: Path, geometry: dict) -> dict:
    with rasterio.open(tif_path) as src:
        out_image, out_transform = mask(src, [geometry], crop=True)
        ndmi = out_image[0]
        mask_band = out_image[1]
        valid = (mask_band > 0) & np.isfinite(ndmi)
        values = ndmi[valid]
        if values.size == 0:
            return {"count": 0}
        return {
            "count": int(values.size),
            "min": float(values.min()),
            "max": float(values.max()),
            "mean": float(values.mean()),
            "p25": float(np.percentile(values, 25)),
            "p50": float(np.percentile(values, 50)),
            "p75": float(np.percentile(values, 75)),
            "pct_below_0": float((values < 0.0).mean() * 100.0),
            "pct_below_0_2": float((values < 0.2).mean() * 100.0),
        }


def main() -> None:
    script_dir = Path(__file__).resolve().parent
    load_env(script_dir / ".env")

    client_id = get_env("CDSE_CLIENT_ID", required=True)
    client_secret = get_env("CDSE_CLIENT_SECRET", required=True)

    katop_name = get_env("KATOP_NAME", "ZEMUN POLJE")
    geometry = fetch_katop_geom(katop_name)

    days_back = int(get_env("DAYS_BACK", "1"))
    fallback_days = int(get_env("FALLBACK_DAYS_BACK", "7"))
    max_cloud = int(get_env("MAX_CLOUD_COVER", "20"))
    fallback_cloud = int(get_env("FALLBACK_MAX_CLOUD", "80"))
    width = int(get_env("ANALYSIS_WIDTH", "1200"))
    height = int(get_env("ANALYSIS_HEIGHT", "1200"))

    now = dt.datetime.utcnow()
    start = now - dt.timedelta(days=days_back)
    time_from = start.strftime("%Y-%m-%dT%H:%M:%SZ")
    time_to = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    token = get_token(client_id, client_secret)
    print(f"[INFO] NDMI raw {time_from} -> {time_to}")
    try:
        ndmi_bytes = download_ndmi_raw(token, geometry, time_from, time_to, width, height, max_cloud)
        if len(ndmi_bytes) < 30000:
            raise ValueError("Small NDMI response")
    except Exception:
        start_fb = now - dt.timedelta(days=fallback_days)
        time_from_fb = start_fb.strftime("%Y-%m-%dT%H:%M:%SZ")
        time_to_fb = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        print(f"[WARN] Fallback NDMI {time_from_fb} -> {time_to_fb}")
        ndmi_bytes = download_ndmi_raw(token, geometry, time_from_fb, time_to_fb, width, height, fallback_cloud)

    out_dir = Path(get_env("OUTPUT_DIR", str(script_dir / "data")))
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "ndmi_value_latest.tif"
    out_path.write_bytes(ndmi_bytes)

    stats = compute_stats(out_path, geometry)
    if stats.get("count", 0) == 0:
        print("[WARN] Nema validnih NDMI vrednosti za zadatu opštinu.")
        return

    print(f"[RESULT] Kat. Opština: {katop_name}")
    print(f"[RESULT] NDMI mean: {stats['mean']:.3f}")
    print(f"[RESULT] NDMI min/max: {stats['min']:.3f} / {stats['max']:.3f}")
    print(f"[RESULT] NDMI p25/p50/p75: {stats['p25']:.3f} / {stats['p50']:.3f} / {stats['p75']:.3f}")
    print(f"[RESULT] % NDMI < 0.2: {stats['pct_below_0_2']:.1f}%")
    print(f"[RESULT] % NDMI < 0.0: {stats['pct_below_0']:.1f}%")


if __name__ == "__main__":
    main()
