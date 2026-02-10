"""
Nova verzija koja koristi Process API i lokalno računa statistiku iz svih piksela.
Ovo daje tačne statistike (mean, median, p10, p90) sa svih piksela u parceli.
"""
import csv
import datetime as dt
import json
import sys
import urllib.parse
import urllib.request
from io import BytesIO
from pathlib import Path

import numpy as np
import rasterio
from rasterio.mask import mask

from download_and_publish import (
    build_evalscript_ndvi,
    compute_output_size,
    get_env,
    get_token,
    load_env,
    PROCESS_URL,
)
from download_ndvi_parcel import bbox_to_polygon, fetch_parcel_bbox
from download_ndvi_parcel_csv_old import fetch_parcel_geometry


def build_evalscript_ndvi_stats() -> str:
    """Evalscript koji vraća NDVI vrednosti (FLOAT32) za Process API
    Koristi SCL (Scene Classification Layer) za bolje maskiranje oblaka i senki
    Vraća samo jedan band sa NaN za invalid piksele
    """
    return """//VERSION=3
function setup() {
  return {
    input: ["B04", "B08", "SCL", "dataMask"],
    output: { bands: 1, sampleType: "FLOAT32" }
  };
}

function evaluatePixel(sample) {
  // Ako nema podataka, vrati NaN
  if (sample.dataMask === 0) {
    return [NaN];
  }
  
  // Koristi SCL za maskiranje oblaka, senki, cirusa, saturiranih piksela
  // SCL vrednosti: 0=no data, 1=saturated/defective, 2=dark area, 3=cloud shadow,
  //                4=vegetation, 5=bare soil, 6=water, 7=unclassified, 8=cloud medium,
  //                9=cloud high, 10=thin cirrus, 11=snow/ice
  // MANJE AGRESIVNO MASKIRANJE: Prihvatamo više piksela, maskiramo samo očigledno oblačne
  // Prihvatamo: 2 (dark area), 3 (cloud shadow - možda validan), 4-7 (validni), 10 (thin cirrus - možda validan)
  // Maskiraj samo: 0 (no data), 1 (saturated), 8-9 (cloud medium/high), 11 (snow/ice)
  let scl = sample.SCL;
  if (scl !== undefined && scl !== null) {
    // Maskiraj samo očigledno oblačne i nevalidne piksele
    // Prihvatamo: 2 (dark area), 3 (cloud shadow - možda validan), 4-7 (validni), 10 (thin cirrus - možda validan)
    if (scl === 0 || scl === 1 || scl === 8 || scl === 9 || scl === 11) {
      return [NaN];
    }
    // Prihvatamo: 2 (dark area), 3 (cloud shadow), 4 (vegetation), 5 (bare soil), 6 (water), 7 (unclassified), 10 (thin cirrus)
  }
  
  // Proveri da li su B04 i B08 dostupni i validni
  if (sample.B04 === undefined || sample.B08 === undefined || 
      !isFinite(sample.B04) || !isFinite(sample.B08) ||
      sample.B04 <= 0 || sample.B08 <= 0) {
    return [NaN];
  }
  
  // Računaj NDVI
  let ndvi = (sample.B08 - sample.B04) / (sample.B08 + sample.B04);
  
  // Proveri da li je rezultat validan (finite i nije NaN)
  if (!isFinite(ndvi) || isNaN(ndvi)) {
    return [NaN];
  }
  
  // Vrati NDVI vrednost
  return [ndvi];
}
"""


def build_evalscript_ndvi_stats_for_api() -> str:
    """Evalscript koji vraća NDVI vrednosti za Stats API
    Stats API zahteva da se vraća i dataMask band
    """
    return """//VERSION=3
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
  // Ako nema podataka, vrati 0 i dataMask=0
  if (sample.dataMask === 0) {
    return { default: [0], dataMask: [0] };
  }
  
  // Koristi SCL za maskiranje oblaka, senki, cirusa, saturiranih piksela
  // Ako SCL nije dostupan, prihvatamo piksel (fallback)
  let scl = sample.SCL;
  if (scl !== undefined && scl !== null) {
    // Maskiraj samo očigledno oblačne i nevalidne piksele
    if (scl === 0 || scl === 1 || scl === 3 || scl === 8 || scl === 9 || scl === 10 || scl === 11) {
      return { default: [0], dataMask: [0] };
    }
    // Prihvatamo: 2 (dark area - možda senka), 4 (vegetation), 5 (bare soil), 6 (water), 7 (unclassified)
  }
  
  // Proveri da li su B04 i B08 dostupni i validni
  if (sample.B04 === undefined || sample.B08 === undefined || 
      !isFinite(sample.B04) || !isFinite(sample.B08) ||
      sample.B04 <= 0 || sample.B08 <= 0) {
    return { default: [0], dataMask: [0] };
  }
  
  // Računaj NDVI
  let ndvi = (sample.B08 - sample.B04) / (sample.B08 + sample.B04);
  
  // Proveri da li je rezultat validan
  if (!isFinite(ndvi) || isNaN(ndvi)) {
    return { default: [0], dataMask: [0] };
  }
  
  // Vrati NDVI vrednost sa dataMask=1
  return { default: [ndvi], dataMask: [1] };
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
                        "maxCloudCoverage": 100,  # Ukloni cloud filter - filtriraćemo lokalno po SCL
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
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Process API error {exc.code}: {error_body}") from exc


def compute_stats_from_raster(tif_bytes: bytes, parcel_geometry: dict) -> dict:
    """Računa statistiku iz rastera za parcelu"""
    with rasterio.open(BytesIO(tif_bytes)) as src:
        # Maskiraj raster na parcelu
        out_image, out_transform = mask(src, [parcel_geometry], crop=True, nodata=np.nan)
        
        # Evalscript vraća samo jedan band sa NDVI vrednostima (NaN za invalid piksele)
        ndvi = out_image[0]
        
        # Debug: proveri raster pre maskiranja
        print(f"    [DEBUG] Raster bands count: {src.count}")
        print(f"    [DEBUG] Raster width: {src.width}, height: {src.height}")
        print(f"    [DEBUG] After masking - shape: {out_image.shape}, dtype: {out_image.dtype}")
        
        # Proveri NaN i infinite vrednosti
        nan_count = np.isnan(ndvi).sum()
        inf_count = np.isinf(ndvi).sum()
        finite_count = np.isfinite(ndvi).sum()
        zero_count = (ndvi == 0).sum()
        print(f"    [DEBUG] NDVI statistics: NaN={nan_count}, Inf={inf_count}, Finite={finite_count}, Zero={zero_count}, Total={ndvi.size}")
        
        # Filtriraj validne piksele (finite i ne NaN)
        valid = np.isfinite(ndvi)
        values = ndvi[valid]
        
        if values.size > 0:
            print(f"    [DEBUG] Valid values: {values.size}, min: {values.min():.6f}, max: {values.max():.6f}, mean: {values.mean():.6f}")
        else:
            print(f"    [DEBUG] WARNING: No valid values after filtering!")
        
        if values.size == 0:
            return {
                "min": None,
                "max": None,
                "mean": None,
                "stDev": None,
                "sampleCount": 0,
                "noDataCount": int((~valid).sum()),
                "median": None,
                "p10": None,
                "p90": None,
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
    """Dobija listu dostupnih datuma iz Sentinel-2 podataka koristeći Stats API
    Grupiše snimke po datumu (YYYY-MM-DD) i vraća najbolji snimak za svaki datum
    (najviše validnih piksela).
    
    Returns:
        dict: {date_key: best_timestamp} gde je date_key "YYYY-MM-DD" format
    """
    STATS_URL = "https://sh.dataspace.copernicus.eu/api/v1/statistics"
    payload = {
        "input": {
            "bounds": {"geometry": geometry},
            "data": [
                {
                    "type": "sentinel-2-l2a",
                    "dataFilter": {"maxCloudCoverage": 100},  # Ukloni cloud filter da dobijemo SVE datume
                }
            ],
        },
        "aggregation": {
            "timeRange": {"from": date_from, "to": date_to},
            "aggregationInterval": {"of": "P1D"},
            "evalscript": build_evalscript_ndvi_stats_for_api(),  # Stats API zahteva dataMask band
            "resx": 10.0,  # Veća rezolucija samo za listu datuma (brže)
            "resy": 10.0,
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
    req = urllib.request.Request(STATS_URL, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {token}")
    print(f"[DEBUG] Stats API request URL: {STATS_URL}")
    print(f"[DEBUG] Stats API payload size: {len(data)} bytes")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            status_code = resp.getcode()
            response_text = resp.read().decode("utf-8")
            print(f"[DEBUG] Stats API response status: {status_code}")
            print(f"[DEBUG] Stats API response length: {len(response_text)} bytes")
            
            if status_code != 200:
                print(f"[ERROR] Stats API returned status {status_code}: {response_text[:500]}")
                raise RuntimeError(f"Stats API returned status {status_code}: {response_text[:200]}")
            
            if not response_text.strip():
                print(f"[WARN] Stats API returned empty response")
                return {}
            
            try:
                result = json.loads(response_text)
                print(f"[DEBUG] Stats API returned {len(result.get('data', []))} data items")
            except json.JSONDecodeError as e:
                print(f"[ERROR] Stats API returned invalid JSON (status {status_code}): {response_text[:500]}")
                raise RuntimeError(f"Stats API returned invalid JSON: {e}") from e
            # Grupiši snimke po datumu (bez vremena)
            date_groups: dict[str, list[str]] = {}  # {date_key: [timestamp, ...]}
            
            for item in result.get("data", []):
                interval = item.get("interval", {})
                timestamp = interval.get("from", "")
                if not timestamp:
                    continue
                
                # Ekstraktuj datum (YYYY-MM-DD) iz timestamp-a
                date_obj = dt.datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                date_key = date_obj.strftime("%Y-%m-%d")
                
                if date_key not in date_groups:
                    date_groups[date_key] = []
                date_groups[date_key].append(timestamp)
            
            # Za svaki datum, uzmi najnoviji snimak (najnoviji timestamp)
            # Kasnije ćemo preuzeti raster i proveriti sampleCount lokalno
            best_snapshots: dict[str, str] = {}
            for date_key, snapshots in date_groups.items():
                # Sortiraj po timestamp (opadajuće - najnoviji prvi)
                snapshots.sort(reverse=True)
                best_timestamp = snapshots[0]
                best_snapshots[date_key] = best_timestamp
                if len(snapshots) > 1:
                    print(f"    [DEBUG] Date {date_key}: Stats API returned {len(snapshots)} intervals for this day (probably different tiles/timestamps), using latest: {best_timestamp}")
                else:
                    print(f"    [DEBUG] Date {date_key}: 1 snapshot found: {best_timestamp}")
            
            return best_snapshots
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="ignore")
        print(f"[ERROR] Stats API HTTP error {exc.code}: {error_body[:500]}")
        raise RuntimeError(f"Stats API error {exc.code}: {error_body[:200]}") from exc
    except urllib.error.URLError as exc:
        print(f"[ERROR] Stats API URL error: {exc}")
        raise RuntimeError(f"Stats API URL error: {exc}") from exc
    except Exception as exc:
        print(f"[ERROR] Unexpected error in get_available_dates: {exc}")
        raise


def main() -> None:
    script_dir = Path(__file__).resolve().parent
    load_env(script_dir / ".env")

    client_id = get_env("CDSE_CLIENT_ID", required=True)
    client_secret = get_env("CDSE_CLIENT_SECRET", required=True)

    geoserver_url = get_env("GEOSERVER_URL", "http://localhost:8083/geoserver").rstrip("/")
    workspace = get_env("GEOSERVER_WORKSPACE", "moj_projekat")
    parcel_layer = get_env("PARCEL_LAYER", "kovin_dkp_pg")  # Default layer za parcelu 1427/2
    parcel_attr = get_env("PARCEL_ATTR", "brparcele")
    parcel_id = get_env("PARCEL_ID", "25991")

    days_back = int(get_env("PARCEL_DAYS_BACK", "60"))  # Prošireno na 60 dana za trend analizu
    max_cloud = int(get_env("PARCEL_MAX_CLOUD", "80"))
    resolution_m = float(get_env("RESOLUTION_M", "10.0"))  # Stvarna rezolucija Sentinel-2 (10m) za NDVI (B04, B08)
    max_pixels = int(get_env("MAX_PIXELS", "4096"))

    # Dobij geometriju parcele
    parcel_geometry = fetch_parcel_geometry(geoserver_url, workspace, parcel_layer, parcel_attr, parcel_id)
    minx, miny, maxx, maxy = fetch_parcel_bbox(
        geoserver_url, workspace, parcel_layer, parcel_attr, parcel_id
    )
    bbox_geometry = bbox_to_polygon(minx, miny, maxx, maxy)
    print(f"[INFO] Parcel {parcel_id} bbox: {minx}, {miny}, {maxx}, {maxy}")

    width, height = compute_output_size(bbox_geometry, resolution_m, max_pixels)
    print(f"[INFO] Output size {width}x{height} (res {resolution_m}m, max {max_pixels}px)")

    now = dt.datetime.now(dt.timezone.utc)
    start = now - dt.timedelta(days=days_back)
    date_from = start.isoformat().replace("+00:00", "Z")
    date_to = now.isoformat().replace("+00:00", "Z")
    print(f"[INFO] Requesting data from {date_from} to {date_to} (last {days_back} days, max cloud {max_cloud}%)")

    token = get_token(client_id, client_secret)
    
    # Dobij listu dostupnih datuma (grupisano po danu, najbolji snimak po danu)
    print("[INFO] Getting available dates (grouped by day, best snapshot per day)...")
    date_snapshots = get_available_dates(token, bbox_geometry, date_from, date_to, max_cloud)
    print(f"[INFO] Found {len(date_snapshots)} unique dates with valid snapshots")
    
    # Dodaj datume koje Stats API možda nije vratio (npr. zbog oblaka, ali satelit je ipak preleteo)
    # Generiši sve datume u opsegu i pokušaj da preuzmeš podatke i za njih
    additional_dates = {}
    current_date = dt.datetime.fromisoformat(date_from.replace("Z", "+00:00"))
    end_date = dt.datetime.fromisoformat(date_to.replace("Z", "+00:00"))
    while current_date <= end_date:
        date_key = current_date.strftime("%Y-%m-%d")
        if date_key not in date_snapshots:
            # Dodaj timestamp za početak dana (možda će Process API naći snimak)
            additional_dates[date_key] = current_date.replace(hour=12, minute=0, second=0, microsecond=0).isoformat().replace("+00:00", "Z")
        current_date += dt.timedelta(days=1)
    
    if additional_dates:
        print(f"[INFO] Found {len(additional_dates)} additional dates to try (not returned by Stats API): {list(additional_dates.keys())}")
        date_snapshots.update(additional_dates)
    
    # Sortiraj datume (najstariji prvi, za trend analizu)
    sorted_dates = sorted(date_snapshots.items())
    
    # Za svaki datum, download raster i računaj statistiku
    rows = []
    evalscript = build_evalscript_ndvi_stats()
    processed_dates = set()  # Da ne dupliramo datume
    
    for i, (date_key, best_timestamp) in enumerate(sorted_dates):
        print(f"[INFO] Processing date {i+1}/{len(sorted_dates)}: {date_key} (best snapshot: {best_timestamp})")
        # Konvertuj datum u početak i kraj dana (00:00:00 do 23:59:59)
        date_obj = dt.datetime.fromisoformat(best_timestamp.replace("Z", "+00:00"))
        date_from_day = date_obj.replace(hour=0, minute=0, second=0, microsecond=0).isoformat().replace("+00:00", "Z")
        date_to_day = date_obj.replace(hour=23, minute=59, second=59, microsecond=999999).isoformat().replace("+00:00", "Z")
        print(f"    [DEBUG] Using date range: {date_from_day} to {date_to_day}")
        
        try:
            raster_bytes = download_raster_for_date(
                token, bbox_geometry, date_from_day, date_to_day, width, height, max_cloud, evalscript
            )
            stats = compute_stats_from_raster(raster_bytes, parcel_geometry)
            
            sample_count = stats.get("sampleCount", 0)
            mean_val = stats.get('mean')
            
            # Ako nema validnih piksela, traži unazad do prvog validnog snimka
            if sample_count == 0 or mean_val is None:
                print(f"  [WARN] No valid pixels for {date_key} (sampleCount={sample_count}, mean={mean_val}) - searching backwards for valid snapshot...")
                
                # Traži unazad do prvog datuma sa validnim pikselima
                found_valid = False
                search_date = date_obj - dt.timedelta(days=1)
                search_limit = 30  # Maksimalno 30 dana unazad
                days_searched = 0
                
                while days_searched < search_limit and search_date >= dt.datetime.fromisoformat(date_from.replace("Z", "+00:00")):
                    search_date_key = search_date.strftime("%Y-%m-%d")
                    search_from = search_date.replace(hour=0, minute=0, second=0, microsecond=0).isoformat().replace("+00:00", "Z")
                    search_to = search_date.replace(hour=23, minute=59, second=59, microsecond=999999).isoformat().replace("+00:00", "Z")
                    
                    # Preskoči ako smo već obradili ovaj datum
                    if search_date_key in processed_dates:
                        search_date -= dt.timedelta(days=1)
                        days_searched += 1
                        continue
                    
                    print(f"    [SEARCH] Trying {search_date_key} ({days_searched+1} days back)...")
                    try:
                        search_raster_bytes = download_raster_for_date(
                            token, bbox_geometry, search_from, search_to, width, height, max_cloud, evalscript
                        )
                        search_stats = compute_stats_from_raster(search_raster_bytes, parcel_geometry)
                        search_sample_count = search_stats.get("sampleCount", 0)
                        search_mean_val = search_stats.get('mean')
                        
                        if search_sample_count > 0 and search_mean_val is not None:
                            # Našli smo validan snimak!
                            found_valid = True
                            actual_timestamp = search_date.replace(hour=12, minute=0, second=0, microsecond=0).isoformat().replace("+00:00", "Z")
                            print(f"  [FOUND] Valid snapshot found for {search_date_key} (used for requested date {date_key})")
                            print(f"  [INFO] Actual snapshot date: {search_date_key}, Requested date: {date_key}")
                            
                            row = {
                                "C0/date": actual_timestamp,  # Koristi datum validnog snimka
                                "C0/min": search_stats.get("min"),
                                "C0/max": search_stats.get("max"),
                                "C0/mean": search_stats.get("mean"),
                                "C0/stDev": search_stats.get("stDev"),
                                "C0/sampleCount": search_stats.get("sampleCount"),
                                "C0/noDataCount": search_stats.get("noDataCount"),
                                "C0/median": search_stats.get("median"),
                                "C0/p10": search_stats.get("p10"),
                                "C0/p90": search_stats.get("p90"),
                                "C0/cloudCoveragePercent": None,
                            }
                            rows.append(row)
                            processed_dates.add(search_date_key)
                            median_val = search_stats.get('median')
                            mean_str = f"{search_mean_val:.3f}" if search_mean_val is not None else "N/A"
                            median_str = f"{median_val:.3f}" if median_val is not None else "N/A"
                            print(f"  [OK] sampleCount: {search_sample_count}, mean: {mean_str}, median: {median_str}")
                            break
                    except Exception as search_exc:
                        print(f"    [SEARCH] Failed to process {search_date_key}: {search_exc}")
                    
                    search_date -= dt.timedelta(days=1)
                    days_searched += 1
                
                if not found_valid:
                    print(f"  [SKIP] No valid snapshot found within {search_limit} days backwards from {date_key}")
                continue
            
            # Ako ima validnih piksela, koristi originalni datum
            if date_key not in processed_dates:
                row = {
                    "C0/date": best_timestamp,  # Koristi originalni timestamp za tačnost
                    "C0/min": stats.get("min"),
                    "C0/max": stats.get("max"),
                    "C0/mean": stats.get("mean"),
                    "C0/stDev": stats.get("stDev"),
                    "C0/sampleCount": stats.get("sampleCount"),
                    "C0/noDataCount": stats.get("noDataCount"),
                    "C0/median": stats.get("median"),
                    "C0/p10": stats.get("p10"),
                    "C0/p90": stats.get("p90"),
                    "C0/cloudCoveragePercent": None,  # Nema cloud coverage info iz Process API
                }
                rows.append(row)
                processed_dates.add(date_key)
                median_val = stats.get('median')
                mean_str = f"{mean_val:.3f}" if mean_val is not None else "N/A"
                median_str = f"{median_val:.3f}" if median_val is not None else "N/A"
                print(f"  [OK] sampleCount: {sample_count}, mean: {mean_str}, median: {median_str}")
        except Exception as exc:
            print(f"[WARN] Failed to process {date_key} ({best_timestamp}): {exc}")
            continue

    print(f"[INFO] Processed {len(rows)} dates successfully")

    # Koristi /app/data ako je postavljeno (Docker), inače koristi ../satelite folder (jedan nivo iznad ndvi_auto)
    # U Docker kontejneru, ./satelite se montira na /app/data
    if Path("/app/data").exists():
        default_dir = "/app/data"
    else:
        # Lokalno: ../satelite (jedan nivo iznad ndvi_auto foldera) - APSOLUTNA PUTANJA
        default_dir = str((script_dir.parent / "satelite").resolve())
    output_dir = Path(get_env("PARCEL_CSV_DIR", get_env("OUTPUT_DIR", default_dir)))
    print(f"[INFO] CSV output directory: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_parcel_id = parcel_id.replace("/", "_").replace("\\", "_")
    output_path = output_dir / f"parcela_{safe_parcel_id}_NDVI.csv"
    
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
    print(f"[INFO] Saved parcel NDVI CSV: {output_path}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        import traceback
        print(f"[ERROR] {exc}")
        print(f"[ERROR] Traceback:")
        traceback.print_exc()
        sys.exit(1)
