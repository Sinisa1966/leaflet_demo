import csv
import datetime as dt
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from download_and_publish import get_env, get_token, load_env
from download_ndvi_parcel_csv import (
    fetch_parcel_geometry,
    pick_output_band,
    post_stats,
    stats_to_rows,
    time_range_midnight_utc,
    write_csv,
)


def build_evalscript_ndre_stats() -> str:
    return """//VERSION=3
// SCL: 0=no data, 1=saturated, 8=cloud medium, 9=cloud high
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
  var scl = sample.SCL;
  if (scl !== undefined && scl !== null) {
    if (scl === 0 || scl === 1 || scl === 8 || scl === 9) return { default: [0], dataMask: [0] };
  }
  var sum = sample.B08 + sample.B05;
  if (sum <= 0 || !isFinite(sample.B08) || !isFinite(sample.B05)) return { default: [0], dataMask: [0] };
  var ndre = (sample.B08 - sample.B05) / sum;
  return isFinite(ndre) ? { default: [ndre], dataMask: [1] } : { default: [0], dataMask: [0] };
}
"""


def _geometry_to_utm_bbox(geometry: dict) -> tuple[list, str]:
    """Vraća (bbox, crs) u UTM za Srbiju (zone 34N)."""
    from rasterio.warp import transform_geom
    geom_utm = transform_geom("EPSG:4326", "EPSG:32634", geometry)
    coords = geom_utm.get("coordinates", [])
    if geom_utm.get("type") == "Polygon":
        ring = coords[0]
    elif geom_utm.get("type") == "MultiPolygon":
        ring = coords[0][0]
    else:
        ring = []
    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    return [min(xs), min(ys), max(xs), max(ys)], "http://www.opengis.net/def/crs/EPSG/0/32634"


def post_stats_ndre(token: str, geometry: dict, date_from: str, date_to: str, max_cloud: int, res_m: float) -> dict:
    bbox, crs = _geometry_to_utm_bbox(geometry)
    payload = {
        "input": {
            "bounds": {"bbox": bbox, "properties": {"crs": crs}},
            "data": [
                {
                    "type": "sentinel-2-l2a",
                    "dataFilter": {"maxCloudCoverage": max_cloud},
                }
            ],
        },
        "aggregation": {
            "timeRange": {"from": date_from, "to": date_to},
            "aggregationInterval": {"of": "P1D"},
            "evalscript": build_evalscript_ndre_stats(),
            "resx": res_m,
            "resy": res_m,
        },
        "calculations": {
            "default": {
                "statistics": {
                    "default": {
                        "percentiles": {"k": [10, 50, 90]},
                    }
                }
            }
        },
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request("https://sh.dataspace.copernicus.eu/api/v1/statistics", data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Stats API error {exc.code}: {detail}") from exc


def stats_to_rows_ndre(payload: dict) -> list[dict]:
    rows = []
    for item in payload.get("data", []):
        interval = item.get("interval") or {}
        date_value = interval.get("from") or ""
        band = pick_output_band(item.get("outputs") or {})
        stats = band.get("stats") or {}
        percentiles = band.get("percentiles") or {}
        row = {
            "C0/date": date_value,
            "C0/min": stats.get("min"),
            "C0/max": stats.get("max"),
            "C0/mean": stats.get("mean"),
            "C0/stDev": stats.get("stDev") or stats.get("stdDev"),
            "C0/sampleCount": stats.get("sampleCount") or band.get("sampleCount"),
            "C0/noDataCount": stats.get("noDataCount") or band.get("noDataCount"),
            "C0/median": percentiles.get("p50") or percentiles.get("50"),
            "C0/p10": percentiles.get("p10") or percentiles.get("10"),
            "C0/p90": percentiles.get("p90") or percentiles.get("90"),
            "C0/cloudCoveragePercent": None,
        }
        quality = item.get("qualityIndicators") or {}
        if "cloudCoverage" in quality:
            row["C0/cloudCoveragePercent"] = quality.get("cloudCoverage")
        elif "cloudCoveragePercent" in quality:
            row["C0/cloudCoveragePercent"] = quality.get("cloudCoveragePercent")
        rows.append(row)
    return rows


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
    stats_res_m = float(get_env("PARCEL_STATS_RES", "10"))  # 10m - UTM bbox daje prave piksel statistike

    geometry = fetch_parcel_geometry(geoserver_url, workspace, parcel_layer, parcel_attr, parcel_id)
    date_from, date_to = time_range_midnight_utc(days_back)
    print(f"[INFO] Requesting NDRE stats from {date_from} to {date_to} (last {days_back} days, max cloud {max_cloud}%)")
    payload = post_stats_ndre(
        get_token(client_id, client_secret),
        geometry,
        date_from,
        date_to,
        max_cloud,
        stats_res_m,
    )
    print(f"[INFO] Received {len(payload.get('data', []))} data items from API")
    rows = stats_to_rows_ndre(payload)
    print(f"[INFO] Converted to {len(rows)} CSV rows")

    # Isto kao NDVI: satelite/ kad nije Docker, inače PARCEL_CSV_DIR ili /app/data
    if Path("/.dockerenv").exists() and Path("/app/data").exists():
        default_dir = "/app/data"
    else:
        default_dir = str((script_dir.parent / "satelite").resolve())
    output_dir = Path(get_env("PARCEL_CSV_DIR", get_env("OUTPUT_DIR", default_dir)))
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_parcel_id = parcel_id.replace("/", "_").replace("\\", "_")
    output_path = output_dir / f"parcela_{safe_parcel_id}_NDRE.csv"
    write_csv(rows, output_path)
    print(f"[INFO] Saved parcel NDRE CSV: {output_path}")
    # Proveri da li fajl zaista postoji
    if output_path.exists():
        print(f"[INFO] CSV fajl sacuvan: {output_path} ({output_path.stat().st_size} bytes)")
    else:
        print(f"[ERROR] CSV fajl nije kreiran: {output_path}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)
