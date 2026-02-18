import sys
from pathlib import Path

from download_and_publish import get_env, get_parcel_layer_suffix, get_token, load_env
from download_ndvi_parcel_csv import (
    fetch_parcel_geometry,
    get_latest_date_and_criterion,
    get_row_metadata_for_date,
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
    stats_res_m = float(get_env("PARCEL_STATS_RES", "10"))

    geometry = fetch_parcel_geometry(geoserver_url, workspace, parcel_layer, parcel_attr, parcel_id, kat_opstina=kat_opstina)
    date_from, date_to = time_range_midnight_utc(days_back)
    print(f"[INFO] Requesting NDRE stats from {date_from} to {date_to} (last {days_back} days, max cloud {max_cloud}%)")

    # Koristi ISTI post_stats kao NDVI – samo sa NDRE evalscript-om
    payload = post_stats(
        get_token(client_id, client_secret),
        geometry,
        date_from,
        date_to,
        max_cloud,
        stats_res_m,
        evalscript=build_evalscript_ndre_stats(),
        label="NDRE",
    )
    print(f"[INFO] Received {len(payload.get('data', []))} data items from API")
    rows = stats_to_rows(payload)
    print(f"[INFO] Converted to {len(rows)} CSV rows")
    # Debug: prikaži sampleCount za prvih nekoliko redova
    if rows:
        print(f"[DEBUG] Prvih 3 reda sampleCount:")
        for i, row in enumerate(rows[:3]):
            print(f"  {i+1}. Date: {row.get('C0/date', 'N/A')}, sampleCount: {row.get('C0/sampleCount', 'N/A')}, mean: {row.get('C0/mean', 'N/A')}")

    # Isto kao NDVI: satelite/ kad nije Docker, inače PARCEL_CSV_DIR ili /app/data
    if Path("/.dockerenv").exists() and Path("/app/data").exists():
        default_dir = "/app/data"
    else:
        default_dir = str((script_dir.parent / "satelite").resolve())
    output_dir = Path(get_env("PARCEL_CSV_DIR", get_env("OUTPUT_DIR", default_dir)))
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_parcel_id = get_parcel_layer_suffix(parcel_id, kat_opstina)
    output_path = output_dir / f"parcela_{safe_parcel_id}_NDRE.csv"
    write_csv(rows, output_path)
    print(f"[INFO] Saved parcel NDRE CSV: {output_path}")
    latest_date, latest_criterion = get_latest_date_and_criterion(rows)
    if latest_date:
        print(f"LATEST_DATE={latest_date}")
    if latest_criterion:
        print(f"LATEST_CRITERION={latest_criterion}")
    meta = get_row_metadata_for_date(rows, latest_date) if latest_date else None
    if meta:
        print(f"LATEST_VALID_PIXELS={meta['valid_pixels']}")
        print(f"LATEST_TOTAL_PIXELS={meta['total_pixels']}")
        print(f"LATEST_VALID_PCT={meta['valid_pct']}")
        if meta.get("cloud_pct") is not None:
            print(f"LATEST_CLOUD_PCT={meta['cloud_pct']}")
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
