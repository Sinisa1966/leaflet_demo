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
    print(f"[DEBUG] GeoServer WFS URL: {url}")
    try:
        with urllib.request.urlopen(url, timeout=60) as resp:
            status_code = resp.getcode()
            response_text = resp.read().decode("utf-8")
            print(f"[DEBUG] GeoServer response status: {status_code}, length: {len(response_text)} bytes")
            
            if status_code != 200:
                print(f"[ERROR] GeoServer returned status {status_code}: {response_text[:500]}")
                raise RuntimeError(f"GeoServer error {status_code}: {response_text[:200]}")
            
            if not response_text.strip():
                print(f"[ERROR] GeoServer returned empty response")
                raise RuntimeError(f"GeoServer returned empty response for parcel {parcel_id}")
            
            # Proveri da li je XML greška (ServiceExceptionReport)
            if response_text.strip().startswith("<?xml") or "ServiceExceptionReport" in response_text:
                print(f"[ERROR] GeoServer returned XML error: {response_text[:500]}")
                # Pokušaj da ekstraktuj poruku greške iz XML-a
                import re
                error_match = re.search(r"<ServiceException[^>]*>(.*?)</ServiceException>", response_text, re.DOTALL)
                error_msg = error_match.group(1).strip() if error_match else "Unknown GeoServer error"
                raise RuntimeError(f"GeoServer error: {error_msg}")
            
            try:
                data = json.loads(response_text)
            except json.JSONDecodeError as e:
                print(f"[ERROR] GeoServer returned invalid JSON: {response_text[:500]}")
                raise RuntimeError(f"GeoServer returned invalid JSON: {e}") from e
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="ignore")
        print(f"[ERROR] GeoServer HTTP error {exc.code}: {error_body[:500]}")
        raise RuntimeError(f"GeoServer HTTP error {exc.code}: {error_body[:200]}") from exc
    except urllib.error.URLError as exc:
        print(f"[ERROR] GeoServer URL error: {exc}")
        raise RuntimeError(f"GeoServer URL error: {exc}") from exc
    
    features = data.get("features", [])
    if not features:
        # Pokušaj alternativni parcel ID (zameni "/" sa "_")
        alt_parcel_id = parcel_id.replace("/", "_")
        print(f"[DEBUG] Trying alternative parcel ID: {alt_parcel_id}")
        cql_alt = f"{parcel_attr}='{alt_parcel_id}'"
        params_alt = params.copy()
        params_alt["CQL_FILTER"] = cql_alt
        url_alt = f"{geoserver_url.rstrip('/')}/{workspace}/ows?{urllib.parse.urlencode(params_alt)}"
        try:
            with urllib.request.urlopen(url_alt, timeout=60) as resp_alt:
                data_alt = json.loads(resp_alt.read().decode("utf-8"))
                features_alt = data_alt.get("features", [])
                if features_alt:
                    print(f"[INFO] Found parcel with alternative ID: {alt_parcel_id}")
                    return features_alt[0]["geometry"]
        except Exception:
            pass
        raise RuntimeError(f"Parcel {parcel_id} not found in {workspace}:{layer}")
    return features[0]["geometry"]


def build_evalscript_ndvi_stats() -> str:
    return """//VERSION=3
function setup() {
  return {
    input: ["B04", "B08", "dataMask"],
    output: [
      { id: "default", bands: 1, sampleType: "FLOAT32" },
      { id: "dataMask", bands: 1 }
    ]
  };
}

function evaluatePixel(sample) {
  if (sample.dataMask === 0) {
    return { default: [0], dataMask: [0] };
  }
  let ndvi = (sample.B08 - sample.B04) / (sample.B08 + sample.B04);
  return { default: [ndvi], dataMask: [1] };
}
"""


def isoformat_z(value: dt.datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.timezone.utc)
    text = value.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat()
    return text.replace("+00:00", "Z")


def post_stats(token: str, geometry: dict, date_from: str, date_to: str, max_cloud: int, res_m: float) -> dict:
    payload = {
        "input": {
            "bounds": {"geometry": geometry},
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

    now = dt.datetime.now(dt.timezone.utc)
    start = now - dt.timedelta(days=days_back)
    date_from = isoformat_z(start)
    date_to = isoformat_z(now)
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

    # Koristi /app/data ako je postavljeno, inače koristi satelite folder
    output_dir = Path(get_env("PARCEL_CSV_DIR", "/app/data"))
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_parcel_id = parcel_id.replace("/", "_").replace("\\", "_")
    output_path = output_dir / f"parcela_{safe_parcel_id}_NDVI.csv"
    write_csv(rows, output_path)
    print(f"[INFO] Saved parcel NDVI CSV: {output_path}")
    # Proveri da li fajl zaista postoji
    if output_path.exists():
        print(f"[INFO] CSV fajl potvrđen: {output_path} ({output_path.stat().st_size} bytes)")
    else:
        print(f"[ERROR] CSV fajl nije kreiran: {output_path}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[ERROR] {exc}")
        sys.exit(1)
