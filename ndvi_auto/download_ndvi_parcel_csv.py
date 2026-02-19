import csv
import datetime as dt
import json
import math
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from download_and_publish import get_env, get_parcel_layer_suffix, get_token, load_env


STATS_URL = "https://sh.dataspace.copernicus.eu/api/v1/statistics"


def fetch_parcel_geometry(
    geoserver_url: str,
    workspace: str,
    layer: str,
    parcel_attr: str,
    parcel_id: str,
    *,
    kat_opstina: str | None = None,
) -> dict:
    """Dohvata geometriju parcele iz GeoServer WFS. Ako KO filter ne pronađe ništa, pokušava bez njega."""
    safe_id = parcel_id.replace("'", "''")
    cql_variants = [f"{parcel_attr}='{safe_id}'"]
    if kat_opstina and kat_opstina.strip():
        safe_kat = kat_opstina.strip().replace("'", "''")
        cql_variants.insert(0, f"{parcel_attr}='{safe_id}' AND kat_opst_1 ILIKE '{safe_kat}'")
        cql_variants.append(f"{parcel_attr}='{safe_id}' AND ImeKOLatV ILIKE '{safe_kat}'")
    for cql in cql_variants:
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
        try:
            with urllib.request.urlopen(url, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            continue
        features = data.get("features", [])
        if features:
            return features[0]["geometry"]
    raise RuntimeError(f"Parcel {parcel_id} not found in {workspace}:{layer}")


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


_UTM_CRS = "http://www.opengis.net/def/crs/EPSG/0/32634"


def _geometry_to_utm_geom(geometry: dict) -> tuple[dict, str]:
    """Transformiše GeoJSON geometriju iz EPSG:4326 u UTM 34N, zadržavajući oblik poligona."""
    from rasterio.warp import transform_geom
    geom_utm = transform_geom("EPSG:4326", "EPSG:32634", geometry)
    return geom_utm, _UTM_CRS


def post_stats(token: str, geometry: dict, date_from: str, date_to: str, max_cloud: int, res_m: float, evalscript=None, label: str = "NDVI") -> dict:
    """Poziva Sentinel Hub Statistics API sa pravom geometrijom parcele (ne bbox).

    Parameters
    ----------
    evalscript : str | None
        Evalscript za statistiku.  Ako nije prosleđen koristi se podrazumevani NDVI.
    label : str
        Oznaka za debug ispis (NDVI / NDMI / NDRE).
    """
    if evalscript is None:
        evalscript = build_evalscript_ndvi_stats()
    geom_utm, crs = _geometry_to_utm_geom(geometry)
    payload = {
        "input": {
            "bounds": {"geometry": geom_utm, "properties": {"crs": crs}},
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
            "evalscript": evalscript,
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
    print(f"[DEBUG] {label} Stats API payload - resx: {res_m}m, resy: {res_m}m, geometry type: {geom_utm.get('type')}")
    req = urllib.request.Request(STATS_URL, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            # Debug: prikaži detaljne informacije iz odgovora
            data_items = result.get("data", [])
            print(f"[DEBUG] {label} API vratio {len(data_items)} data stavki")
            if data_items:
                first_item = data_items[0]
                outputs = first_item.get("outputs", {})
                if outputs:
                    band = pick_output_band(outputs)
                    stats = band.get("stats", {})
                    sample_count = stats.get("sampleCount") or band.get("sampleCount")
                    no_data_count = stats.get("noDataCount") or band.get("noDataCount")
                    print(f"[DEBUG] {label} API odgovor - sampleCount: {sample_count}, noDataCount: {no_data_count}")
                    print(f"[DEBUG] {label} Stats keys: {list(stats.keys())}")
                    print(f"[DEBUG] {label} Band keys: {list(band.keys())}")
                else:
                    print(f"[DEBUG] {label} API odgovor - outputs prazan: {first_item}")
            else:
                print(f"[DEBUG] {label} API vratio prazan data niz! Odgovor: {json.dumps(result)[:500]}")
            return result
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"{label} Stats API error {exc.code}: {detail}") from exc


def pick_output_band(outputs: dict) -> dict:
    if not outputs:
        return {}
    first_output = next(iter(outputs.values()))
    bands = first_output.get("bands") or {}
    if not bands:
        return {}
    return next(iter(bands.values()))


def _is_valid_number(value) -> bool:
    """Vraća True ako je vrednost validan (ne-NaN) broj."""
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().lower() not in ("nan", "inf", "-inf", "")
    if isinstance(value, (int, float)) and (math.isnan(float(value)) or math.isinf(float(value))):
        return False
    return True


def stats_to_rows(payload: dict) -> list[dict]:
    rows = []
    for item in payload.get("data", []):
        interval = item.get("interval") or {}
        date_value = interval.get("from") or ""
        band = pick_output_band(item.get("outputs") or {})
        stats = band.get("stats") or {}
        percentiles = stats.get("percentiles") or band.get("percentiles") or {}
        mean_val = stats.get("mean")
        # Preskoči datume gde su svi pikseli noData (mean je NaN)
        if not _is_valid_number(mean_val):
            continue
        row = {
            "C0/date": date_value,
            "C0/min": stats.get("min"),
            "C0/max": stats.get("max"),
            "C0/mean": mean_val,
            "C0/stDev": stats.get("stDev") or stats.get("stdDev"),
            "C0/sampleCount": stats.get("sampleCount") or band.get("sampleCount"),
            "C0/noDataCount": stats.get("noDataCount") or band.get("noDataCount"),
            "C0/median": percentiles.get("50.0") or percentiles.get("p50") or percentiles.get("50"),
            "C0/p10": percentiles.get("10.0") or percentiles.get("p10") or percentiles.get("10"),
            "C0/p90": percentiles.get("90.0") or percentiles.get("p90") or percentiles.get("90"),
            "C0/cloudCoveragePercent": None,
        }
        quality = item.get("qualityIndicators") or {}
        if "cloudCoverage" in quality:
            row["C0/cloudCoveragePercent"] = quality.get("cloudCoverage")
        elif "cloudCoveragePercent" in quality:
            row["C0/cloudCoveragePercent"] = quality.get("cloudCoveragePercent")
        rows.append(row)
    return rows


# Kriterijumi za "poslednji validan datum" (Sentinel-2) – prioritet u %
# % kriterijum omogućava i male i velike parcele. Minimalan broj px štiti od šuma.
# NDVI/NDRE: prag može biti niži (≥40–50%); NDMI: bolje strože (≥60%) jer oblaci utiču na SWIR.
MIN_VALID_PCT_STRICT = 0.60   # ≥60% (pogodno i za NDMI)
MIN_VALID_PCT_STRONG = 0.50   # ≥50% (preporuka, precizna poljoprivreda)
MIN_VALID_PCT_RELAXED = 0.40  # ≥40% (NDVI/NDRE trendovi; za NDMI koristiti oprezno)
MIN_VALID_PX_FLOOR = 10       # minimalan broj px (za male parcele); % je glavni kriterijum

CRITERION_STRICT = "≥60% validnih (min 10 px, pogodno i za NDMI)"
CRITERION_STRONG = "≥50% validnih (min 10 px, preporuka)"
CRITERION_RELAXED = "≥40% validnih (min 10 px, prihvatljivo za trendove)"


def _valid_pixels(row: dict) -> tuple[int, int]:
    """Vraća (validni_pikseli, ukupno). validni = sampleCount - noDataCount."""
    try:
        sc = row.get("C0/sampleCount")
        nd = row.get("C0/noDataCount")
        total = int(float(sc)) if sc is not None and str(sc).strip() else 0
        no_data = int(float(nd)) if nd is not None and str(nd).strip() else 0
    except (TypeError, ValueError):
        return 0, 0
    valid = max(0, total - no_data)
    return valid, total


def get_row_metadata_for_date(rows: list[dict], date_yyyymmdd: str) -> dict | None:
    """Za dati datum (YYYY-MM-DD) vraća metapodatke scene: valid_pixels, total_pixels, valid_pct, cloud_pct."""
    for row in rows:
        d = row.get("C0/date") or ""
        if str(d).startswith(date_yyyymmdd):
            valid, total = _valid_pixels(row)
            valid_pct = round(100 * valid / total, 1) if total else 0
            cloud = row.get("C0/cloudCoveragePercent")
            if cloud is not None:
                try:
                    v = float(cloud)
                    cloud_pct = round(100 * v, 1) if 0 <= v <= 1 else round(v, 1)
                except (TypeError, ValueError):
                    cloud_pct = None
            else:
                cloud_pct = None
            return {
                "valid_pixels": valid,
                "total_pixels": total,
                "valid_pct": valid_pct,
                "cloud_pct": cloud_pct,
            }
    return None


def get_latest_date_and_criterion(
    rows: list[dict],
    min_pct_strict: float = MIN_VALID_PCT_STRICT,
    min_pct_strong: float = MIN_VALID_PCT_STRONG,
    min_pct_relaxed: float = MIN_VALID_PCT_RELAXED,
    min_px_floor: int = MIN_VALID_PX_FLOOR,
) -> tuple[str | None, str | None]:
    """Iz liste redova (Stats API) vraća (datum YYYY-MM-DD, kriterijum_tekst).
    Kriterijum je u % (60%, 50%, 40%) sa minimalnim brojem px – radi i za male i velike parcele."""
    with_date = [r for r in rows if r.get("C0/date")]
    with_date.sort(key=lambda r: r["C0/date"], reverse=True)
    for row in with_date:
        valid, total = _valid_pixels(row)
        if total <= 0:
            continue
        pct = valid / total
        if valid >= min_px_floor and pct >= min_pct_strict:
            return str(row["C0/date"]).split("T")[0], CRITERION_STRICT
    for row in with_date:
        valid, total = _valid_pixels(row)
        if total <= 0:
            continue
        pct = valid / total
        if valid >= min_px_floor and pct >= min_pct_strong:
            return str(row["C0/date"]).split("T")[0], CRITERION_STRONG
    for row in with_date:
        valid, total = _valid_pixels(row)
        if total <= 0:
            continue
        pct = valid / total
        if valid >= min_px_floor and pct >= min_pct_relaxed:
            return str(row["C0/date"]).split("T")[0], CRITERION_RELAXED
    return None, None


def get_latest_date_with_data(
    token: str,
    geometry: dict,
    days_back: int,
    max_cloud: int,
    evalscript: str | None = None,
    label: str = "STATS",
    res_m: float = 10.0,
) -> tuple[str | None, str | None]:
    """Vraća (poslednji_validan_datum YYYY-MM-DD, kriterijum_tekst).
    Redom: 60%+ (NDMI), 50%+ (standard), 40%+ (trendovi)."""
    date_from, date_to = time_range_midnight_utc(days_back)
    payload = post_stats(
        token, geometry, date_from, date_to, max_cloud, res_m,
        evalscript=evalscript, label=label,
    )
    rows = stats_to_rows(payload)
    return get_latest_date_and_criterion(rows)


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
    kat_opstina = get_env("PARCEL_KAT_OPSTINA", "").strip() or None

    days_back = int(get_env("PARCEL_DAYS_BACK", "30"))
    max_cloud = int(get_env("PARCEL_MAX_CLOUD", "80"))
    stats_res_m = float(get_env("PARCEL_STATS_RES", "10"))  # 10m - stvarne vrednosti Sentinel-2

    geometry = fetch_parcel_geometry(geoserver_url, workspace, parcel_layer, parcel_attr, parcel_id, kat_opstina=kat_opstina)

    date_from, date_to = time_range_midnight_utc(days_back)
    print(f"[INFO] Requesting NDVI stats from {date_from} to {date_to} (last {days_back} days, max cloud {max_cloud}%)")
    payload = post_stats(
        get_token(client_id, client_secret),
        geometry,
        date_from,
        date_to,
        max_cloud,
        stats_res_m,
        label="NDVI",
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
    safe_parcel_id = get_parcel_layer_suffix(parcel_id, kat_opstina)
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
