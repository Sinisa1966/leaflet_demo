"""
Vraća vrednost indeksa (NDVI/NDMI/NDRE) za jednu tačku (lat, lon) za dati datum.
Koristi Statistics API – isti evalscript i logika kao CSV – da vrednost bude u istom opsegu (npr. Min: 0.184, Max: 0.430).
Ispis: VALUE=<broj> ili prazno ako nema podataka.
"""
import datetime as dt
import os
import sys
from pathlib import Path

from download_and_publish import get_env, get_token, load_env
from download_ndvi_parcel import bbox_to_polygon
from download_ndvi_parcel_csv import (
    build_evalscript_ndvi_stats,
    pick_output_band,
    post_stats,
)
from download_ndmi_parcel_csv import build_evalscript_ndmi_stats
from download_ndre_parcel_csv import build_evalscript_ndre_stats


# ~10 m u stepenima (približno za Srbiju)
DELTA_DEG = 0.00009


def main() -> None:
    script_dir = Path(__file__).resolve().parent
    load_env(script_dir / ".env")

    lat_s = os.environ.get("LAT", "").strip()
    lon_s = os.environ.get("LON", "").strip()
    date_s = os.environ.get("DATE", "").strip()
    index = (os.environ.get("INDEX", "NDVI") or "NDVI").strip().upper()

    if not lat_s or not lon_s or not date_s:
        print("VALUE=")
        sys.exit(0)
    try:
        lat = float(lat_s)
        lon = float(lon_s)
    except ValueError:
        print("VALUE=")
        sys.exit(0)
    try:
        d = dt.datetime.strptime(date_s[:10], "%Y-%m-%d")
    except ValueError:
        print("VALUE=")
        sys.exit(0)

    date_from = d.replace(tzinfo=dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    date_to = (d + dt.timedelta(days=1)).replace(tzinfo=dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    geometry = bbox_to_polygon(
        lon - DELTA_DEG, lat - DELTA_DEG,
        lon + DELTA_DEG, lat + DELTA_DEG,
    )

    if index == "NDVI":
        evalscript = build_evalscript_ndvi_stats()
        label = "NDVI"
    elif index == "NDRE":
        evalscript = build_evalscript_ndre_stats()
        label = "NDRE"
    elif index == "NDMI":
        evalscript = build_evalscript_ndmi_stats()
        label = "NDMI"
    else:
        evalscript = build_evalscript_ndvi_stats()
        label = "NDVI"

    client_id = get_env("CDSE_CLIENT_ID", required=True)
    client_secret = get_env("CDSE_CLIENT_SECRET", required=True)
    max_cloud = int(get_env("PARCEL_MAX_CLOUD", get_env("MAX_CLOUD_COVER", "80")))
    res_m = float(get_env("PARCEL_STATS_RES", "10"))

    token = get_token(client_id, client_secret)
    payload = post_stats(token, geometry, date_from, date_to, max_cloud, res_m, evalscript=evalscript, label=label)

    data_items = payload.get("data", [])
    if not data_items:
        print("VALUE=")
        return
    band = pick_output_band(data_items[0].get("outputs") or {})
    stats = band.get("stats") or {}
    mean_val = stats.get("mean")
    if mean_val is None or (isinstance(mean_val, float) and (mean_val != mean_val or abs(mean_val) > 10)):
        print("VALUE=")
        return
    print("VALUE=" + str(mean_val))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        sys.stderr.write(str(e) + "\n")
        print("VALUE=")
        sys.exit(1)
