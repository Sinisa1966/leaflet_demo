"""
Nova verzija koja koristi Process API i lokalno računa statistiku iz svih piksela.
Ovo daje tačne statistike (mean, median, p10, p90) sa svih piksela u parceli.
"""
import csv
import datetime as dt
import json
import sys
import urllib.request
import urllib.error
from io import BytesIO
from pathlib import Path

import numpy as np
import rasterio
from rasterio.mask import mask

from download_and_publish import (
    compute_output_size,
    get_env,
    get_token,
    load_env,
    PROCESS_URL,
)
from download_ndvi_parcel import bbox_to_polygon, fetch_parcel_bbox
from download_ndvi_parcel_csv import fetch_parcel_geometry


def build_evalscript_ndre_stats() -> str:
    """Evalscript koji vraća NDRE vrednosti (FLOAT32) za Process API"""
    return """//VERSION=3
function setup() {
  return {
    input: ["B05", "B08", "SCL", "dataMask"],
    output: { bands: 1, sampleType: "FLOAT32" }
  };
}

function evaluatePixel(sample) {
  if (sample.dataMask === 0) return [NaN];
  let scl = sample.SCL;
  if (scl === 0 || scl === 1 || scl === 2 || scl === 3 || 
      scl === 8 || scl === 9 || scl === 10 || scl === 11) {
    return [NaN];
  }
  if (sample.B05 === undefined || sample.B08 === undefined || 
      !isFinite(sample.B05) || !isFinite(sample.B08) ||
      sample.B05 <= 0 || sample.B08 <= 0) {
    return [NaN];
  }
  let ndre = (sample.B08 - sample.B05) / (sample.B08 + sample.B05);
  if (!isFinite(ndre) || isNaN(ndre)) return [NaN];
  return [ndre];
}
"""


def build_evalscript_ndre_stats_for_api() -> str:
    """Evalscript za Stats API - zahteva dataMask band"""
    return """//VERSION=3
function setup() {
  return {
    input: ["B05", "B08", "SCL", "dataMask"],
    output: [
      { id: "default", bands: 1, sampleType: "FLOAT32" },
      { id: "dataMask", bands: 1 }
    ]
  };
}

function evaluatePixel(sample) {
  if (sample.dataMask === 0) return { default: [0], dataMask: [0] };
  let scl = sample.SCL;
  if (scl === 0 || scl === 1 || scl === 2 || scl === 3 || 
      scl === 8 || scl === 9 || scl === 10 || scl === 11) {
    return { default: [0], dataMask: [0] };
  }
  if (sample.B05 === undefined || sample.B08 === undefined || 
      !isFinite(sample.B05) || !isFinite(sample.B08) ||
      sample.B05 <= 0 || sample.B08 <= 0) {
    return { default: [0], dataMask: [0] };
  }
  let ndre = (sample.B08 - sample.B05) / (sample.B08 + sample.B05);
  if (!isFinite(ndre) || isNaN(ndre)) return { default: [0], dataMask: [0] };
  return { default: [ndre], dataMask: [1] };
}
"""


def download_raster_for_date(
    token: str,
    geometry: dict,
    date_from: str,
    date_to: str,
    width: int,
    height: int,
    max_cloud: int,
    evalscript: str,
) -> bytes:
    """Download raster za određeni datum koristeći Process API"""
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
                        "timeRange": {"from": date_from, "to": date_to},
                        "maxCloudCoverage": 100,
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
        "evalscript": evalscript,
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(PROCESS_URL, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=300) as resp:
        return resp.read()


def compute_stats_from_raster(tif_bytes: bytes, parcel_geometry: dict) -> dict:
    """Računa statistiku iz rastera za parcelu"""
    with rasterio.open(BytesIO(tif_bytes)) as src:
        out_image, _ = mask(src, [parcel_geometry], crop=True, nodata=np.nan)
        ndre = out_image[0]
        valid = np.isfinite(ndre)
        values = ndre[valid]
        if values.size == 0:
            return {
                "min": None, "max": None, "mean": None, "stDev": None,
                "sampleCount": 0, "noDataCount": int((~valid).sum()),
                "median": None, "p10": None, "p90": None,
            }
        return {
            "min": float(values.min()),
            "max": float(values.max()),
            "mean": float(values.mean()),
            "stDev": float(values.std()),
            "sampleCount": int(values.size),
            "noDataCount": int((~valid).sum()),
            "median": float(np.percentile(values, 50)),
            "p10": float(np.percentile(values, 10)),
            "p90": float(np.percentile(values, 90)),
        }


def get_available_dates(
    token: str, geometry: dict, date_from: str, date_to: str, max_cloud: int
) -> dict[str, str]:
    """Dobija listu dostupnih datuma iz Stats API"""
    STATS_URL = "https://sh.dataspace.copernicus.eu/api/v1/statistics"
    payload = {
        "input": {
            "bounds": {"geometry": geometry},
            "data": [{"type": "sentinel-2-l2a", "dataFilter": {"maxCloudCoverage": 100}}],
        },
        "aggregation": {
            "timeRange": {"from": date_from, "to": date_to},
            "aggregationInterval": {"of": "P1D"},
            "evalscript": build_evalscript_ndre_stats_for_api(),
            "resx": 10.0,
            "resy": 10.0,
        },
        "calculations": {
            "default": {
                "statistics": {"default": {"percentiles": {"k": [10, 50, 90]}}},
            }
        },
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(STATS_URL, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    date_groups: dict[str, list[str]] = {}
    for item in result.get("data", []):
        timestamp = item.get("interval", {}).get("from", "")
        if not timestamp:
            continue
        date_key = dt.datetime.fromisoformat(timestamp.replace("Z", "+00:00")).strftime("%Y-%m-%d")
        if date_key not in date_groups:
            date_groups[date_key] = []
        date_groups[date_key].append(timestamp)
    best_snapshots = {}
    for date_key, snapshots in date_groups.items():
        snapshots.sort(reverse=True)
        best_snapshots[date_key] = snapshots[0]
    return best_snapshots


def main() -> None:
    script_dir = Path(__file__).resolve().parent
    load_env(script_dir / ".env")

    client_id = get_env("CDSE_CLIENT_ID", required=True)
    client_secret = get_env("CDSE_CLIENT_SECRET", required=True)

    geoserver_url = get_env("GEOSERVER_URL", "http://localhost:8083/geoserver").rstrip("/")
    workspace = get_env("GEOSERVER_WORKSPACE", "moj_projekat")
    parcel_layer = get_env("PARCEL_LAYER", "VrsacDKP")
    parcel_attr = get_env("PARCEL_ATTR", "brparcele")
    parcel_id = get_env("PARCEL_ID", "25991")

    days_back = int(get_env("PARCEL_DAYS_BACK", "30"))
    max_cloud = int(get_env("PARCEL_MAX_CLOUD", "80"))
    resolution_m = float(get_env("RESOLUTION_M", "10.0"))
    max_pixels = int(get_env("MAX_PIXELS", "4096"))

    parcel_geometry = fetch_parcel_geometry(geoserver_url, workspace, parcel_layer, parcel_attr, parcel_id)
    minx, miny, maxx, maxy = fetch_parcel_bbox(
        geoserver_url, workspace, parcel_layer, parcel_attr, parcel_id
    )
    bbox_geometry = bbox_to_polygon(minx, miny, maxx, maxy)

    width, height = compute_output_size(bbox_geometry, resolution_m, max_pixels)

    now = dt.datetime.now(dt.timezone.utc)
    start = now - dt.timedelta(days=days_back)
    date_from = start.isoformat().replace("+00:00", "Z")
    date_to = now.isoformat().replace("+00:00", "Z")

    token = get_token(client_id, client_secret)
    date_snapshots = get_available_dates(token, bbox_geometry, date_from, date_to, max_cloud)
    sorted_dates = sorted(date_snapshots.items())

    rows = []
    evalscript = build_evalscript_ndre_stats()

    for date_key, best_timestamp in sorted_dates:
        date_obj = dt.datetime.fromisoformat(best_timestamp.replace("Z", "+00:00"))
        date_from_day = date_obj.replace(hour=0, minute=0, second=0, microsecond=0).isoformat().replace("+00:00", "Z")
        date_to_day = date_obj.replace(hour=23, minute=59, second=59, microsecond=999999).isoformat().replace("+00:00", "Z")
        try:
            raster_bytes = download_raster_for_date(
                token, bbox_geometry, date_from_day, date_to_day, width, height, max_cloud, evalscript
            )
            stats = compute_stats_from_raster(raster_bytes, parcel_geometry)
            sample_count = stats.get("sampleCount", 0)
            mean_val = stats.get("mean")
            if sample_count == 0 or mean_val is None:
                continue
            rows.append({
                "C0/date": best_timestamp,
                "C0/min": stats.get("min"),
                "C0/max": stats.get("max"),
                "C0/mean": stats.get("mean"),
                "C0/stDev": stats.get("stDev"),
                "C0/sampleCount": stats.get("sampleCount"),
                "C0/noDataCount": stats.get("noDataCount"),
                "C0/median": stats.get("median"),
                "C0/p10": stats.get("p10"),
                "C0/p90": stats.get("p90"),
                "C0/cloudCoveragePercent": None,
            })
        except Exception as exc:
            print(f"[WARN] Failed {date_key}: {exc}")
            continue

    if Path("/app/data").exists():
        default_dir = "/app/data"
    else:
        default_dir = str((script_dir.parent / "satelite").resolve())
    output_dir = Path(get_env("PARCEL_CSV_DIR", get_env("OUTPUT_DIR", default_dir)))
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_parcel_id = parcel_id.replace("/", "_").replace("\\", "_")
    output_path = output_dir / f"parcela_{safe_parcel_id}_NDRE.csv"

    header = [
        "C0/date", "C0/min", "C0/max", "C0/mean", "C0/stDev",
        "C0/sampleCount", "C0/noDataCount", "C0/median", "C0/p10", "C0/p90",
        "C0/cloudCoveragePercent",
    ]
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=header)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    print(f"[INFO] Saved parcel NDRE CSV: {output_path}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[ERROR] {exc}")
        sys.exit(1)
