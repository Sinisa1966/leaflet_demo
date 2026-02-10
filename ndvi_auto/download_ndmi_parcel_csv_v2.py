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


def build_evalscript_ndmi_stats() -> str:
    """Evalscript za Process API - NDMI (B08-B11)/(B08+B11).
    B08 i B11 su 10m i 20m - Process API resampluje na output rezoluciju.
    Koristi DEFAULT units (reflektansa 0-1).
    """
    return """//VERSION=3
function setup() {
  return {
    input: ["B08", "B11"],
    output: { bands: 1, sampleType: "FLOAT32" }
  };
}

function evaluatePixel(sample) {
  var b08 = sample.B08;
  var b11 = sample.B11;
  if (b08 === undefined || b11 === undefined || !isFinite(b08) || !isFinite(b11)) {
    return [NaN];
  }
  var sum = b08 + b11;
  if (sum <= 0) return [NaN];
  var ndmi = (b08 - b11) / sum;
  return isFinite(ndmi) ? [ndmi] : [NaN];
}
"""


def build_evalscript_ndmi_stats_for_api() -> str:
    """Evalscript za Stats API - zahteva dataMask band. Samo dataMask kao NDVI."""
    return """//VERSION=3
function setup() {
  return {
    input: ["B08", "B11", "dataMask"],
    output: [
      { id: "default", bands: 1, sampleType: "FLOAT32" },
      { id: "dataMask", bands: 1 }
    ]
  };
}

function evaluatePixel(sample) {
  if (sample.dataMask === 0) return { default: [0], dataMask: [0] };
  if (sample.B08 === undefined || sample.B11 === undefined ||
      !isFinite(sample.B08) || !isFinite(sample.B11) ||
      sample.B08 <= 0 || sample.B11 <= 0) {
    return { default: [0], dataMask: [0] };
  }
  let ndmi = (sample.B08 - sample.B11) / (sample.B08 + sample.B11);
  if (!isFinite(ndmi) || isNaN(ndmi)) return { default: [0], dataMask: [0] };
  return { default: [ndmi], dataMask: [1] };
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
    """Računa statistiku iz rastera za parcelu - ista logika kao NDVI v2"""
    with rasterio.open(BytesIO(tif_bytes)) as src:
        from rasterio.warp import transform_geom
        geom_to_use = parcel_geometry
        geom_crs = src.crs
        if geom_crs and str(geom_crs) != "EPSG:4326":
            geom_to_use = transform_geom("EPSG:4326", str(geom_crs), parcel_geometry)
        out_image, _ = mask(src, [geom_to_use], crop=True, nodata=np.nan, all_touched=True)
        ndmi = out_image[0]
        valid = np.isfinite(ndmi)
        values = ndmi[valid]
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
            "evalscript": build_evalscript_ndmi_stats_for_api(),
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
    print(f"[INFO] Found {len(sorted_dates)} dates to process")

    rows = []
    evalscript = build_evalscript_ndmi_stats()

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

    print(f"[INFO] Processed {len(rows)} dates successfully")

    if Path("/.dockerenv").exists() and Path("/app/data").exists():
        default_dir = "/app/data"
    else:
        default_dir = str((script_dir.parent / "satelite").resolve())
    output_dir = Path(get_env("PARCEL_CSV_DIR", get_env("OUTPUT_DIR", default_dir)))
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_parcel_id = parcel_id.replace("/", "_").replace("\\", "_")
    output_path = output_dir / f"parcela_{safe_parcel_id}_NDMI.csv"

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
    print(f"[INFO] Saved parcel NDMI CSV: {output_path}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[ERROR] {exc}")
        sys.exit(1)
