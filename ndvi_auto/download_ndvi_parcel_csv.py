import csv
import datetime as dt
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from download_and_publish import get_env, get_token, load_env


STATS_URL = "https://sh.dataspace.copernicus.eu/api/v1/statistics"


def fetch_parcel_geometry(
    geoserver_url: str,
    workspace: str,
    layer: str,
    parcel_attr: str,
    parcel_id: str,
) -> dict:
    cql = f"{parcel_attr}='{parcel_id}'"
    params = {
        "service": "WFS",
        "version": "1.0.0",
        "request": "GetFeature",
        "typeName": f"{workspace}:{layer}",
        "outputFormat": "application/json",
        "srsName": "EPSG:4326",
        "CQL_FILTER": cql,
    }
    url = f"{geoserver_url.rstrip('/')}/{workspace}/ows?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    features = data.get("features", [])
    if not features:
        raise RuntimeError(f"Parcel {parcel_id} not found in {workspace}:{layer}")
    return features[0]["geometry"]


def build_evalscript_ndvi_stats() -> str:
    return """//VERSION=3
// SCL: 0=no data, 1=saturated, 2=dark, 3=cloud shadow, 4=veg, 5=soil, 6=water, 7=unclassified, 8=cloud medium, 9=cloud high, 10=cirrus, 11=snow
function setup() {
  return {
    input: ["B04", "B08", "SCL", "dataMask"],
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
  var sum = sample.B08 + sample.B04;
  if (sum <= 0 || !isFinite(sample.B08) || !isFinite(sample.B04)) return { default: [0], dataMask: [0] };
  var ndvi = (sample.B08 - sample.B04) / sum;
  return isFinite(ndvi) ? { default: [ndvi], dataMask: [1] } : { default: [0], dataMask: [0] };
}
"""


def isoformat_z(value: dt.datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.timezone.utc)
    text = value.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat()
    return text.replace("+00:00", "Z")


def time_range_midnight_utc(days_back: int) -> tuple[str, str]:
    """Vraća date_from i date_to na ponoć UTC (00:00:00) da intervali odgovaraju kalendarskim danima.
    Snimak od 4. februara se prikazuje kao 4. februar, ne 3."""
    now = dt.datetime.now(dt.timezone.utc)
    start = (now - dt.timedelta(days=days_back)).replace(hour=0, minute=0, second=0, microsecond=0)
    end = (now + dt.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return isoformat_z(start), isoformat_z(end)


def _geometry_to_utm_bbox(geometry: dict) -> tuple[list, str]:
    """Vraća (bbox, crs) u UTM za Srbiju (zone 34N). Isto kao NDMI/NDRE."""
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


def post_stats(token: str, geometry: dict, date_from: str, date_to: str, max_cloud: int, res_m: float) -> dict:
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
            "evalscript": build_evalscript_ndvi_stats(),
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
    print(f"[DEBUG] Stats API payload - resx: {res_m}m, resy: {res_m}m")
    req = urllib.request.Request(STATS_URL, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            # Debug: prikaži detaljne informacije iz prvog odgovora
            if result.get("data"):
                first_item = result["data"][0]
                outputs = first_item.get("outputs", {})
                if outputs:
                    band = pick_output_band(outputs)
                    stats = band.get("stats", {})
                    sample_count = stats.get("sampleCount") or band.get("sampleCount")
                    no_data_count = stats.get("noDataCount") or band.get("noDataCount")
                    print(f"[DEBUG] API odgovor - sampleCount: {sample_count}, noDataCount: {no_data_count}")
                    print(f"[DEBUG] Stats keys: {list(stats.keys())}")
                    print(f"[DEBUG] Band keys: {list(band.keys())}")
            return result
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Stats API error {exc.code}: {detail}") from exc


def pick_output_band(outputs: dict) -> dict:
    if not outputs:
        return {}
    first_output = next(iter(outputs.values()))
    bands = first_output.get("bands") or {}
    if not bands:
        return {}
    return next(iter(bands.values()))


def stats_to_rows(payload: dict) -> list[dict]:
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


def write_csv(rows: list[dict], output_path: Path) -> None:
    header = [
        "C0/date",
        "C0/min",
        "C0/max",
        "C0/mean",
        "C0/stDev",
        "C0/sampleCount",
        "C0/noDataCount",
        "C0/median",
        "C0/p10",
        "C0/p90",
        "C0/cloudCoveragePercent",
    ]
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=header)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


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
    stats_res_m = float(get_env("PARCEL_STATS_RES", "10"))  # 10m - stvarne vrednosti Sentinel-2

    geometry = fetch_parcel_geometry(geoserver_url, workspace, parcel_layer, parcel_attr, parcel_id)

    date_from, date_to = time_range_midnight_utc(days_back)
    print(f"[INFO] Requesting stats from {date_from} to {date_to} (last {days_back} days, max cloud {max_cloud}%)")
    payload = post_stats(
        get_token(client_id, client_secret),
        geometry,
        date_from,
        date_to,
        max_cloud,
        stats_res_m,
    )
    print(f"[INFO] Received {len(payload.get('data', []))} data items from API")
    rows = stats_to_rows(payload)
    print(f"[INFO] Converted to {len(rows)} CSV rows")
    # Debug: prikaži sampleCount za prvih nekoliko redova
    if rows:
        print(f"[DEBUG] Prvih 3 reda sampleCount:")
        for i, row in enumerate(rows[:3]):
            print(f"  {i+1}. Date: {row.get('C0/date', 'N/A')}, sampleCount: {row.get('C0/sampleCount', 'N/A')}, mean: {row.get('C0/mean', 'N/A')}")

    # Isto kao NDMI: satelite/ kad nije Docker, inače PARCEL_CSV_DIR ili /app/data
    if Path("/.dockerenv").exists() and Path("/app/data").exists():
        default_dir = "/app/data"
    else:
        default_dir = str((script_dir.parent / "satelite").resolve())
    output_dir = Path(get_env("PARCEL_CSV_DIR", get_env("OUTPUT_DIR", default_dir)))
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_parcel_id = parcel_id.replace("/", "_").replace("\\", "_")
    output_path = output_dir / f"parcela_{safe_parcel_id}_NDVI.csv"
    write_csv(rows, output_path)
    print(f"[INFO] Saved parcel NDVI CSV: {output_path}")
    # Proveri da li fajl zaista postoji
    if output_path.exists():
        print(f"[INFO] CSV fajl sacuvan: {output_path} ({output_path.stat().st_size} bytes)")
    else:
        print(f"[ERROR] CSV fajl nije kreiran: {output_path}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[ERROR] {exc}")
        sys.exit(1)
