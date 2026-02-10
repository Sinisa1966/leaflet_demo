#!/usr/bin/env python3
"""Privremena skripta za dobijanje podataka za specifičan datum"""
import csv
import datetime as dt
import json
import sys
from pathlib import Path

from download_and_publish import get_env, get_token, load_env
from download_ndvi_parcel_csv_old import (
    build_evalscript_ndvi_stats,
    fetch_parcel_geometry,
    isoformat_z,
    pick_output_band,
    post_stats,
    stats_to_rows,
    write_csv,
)
from download_ndmi_parcel_csv_old import (
    build_evalscript_ndmi_stats,
    post_stats_ndmi,
    stats_to_rows_ndmi,
)
from download_ndre_parcel_csv_old import (
    build_evalscript_ndre_stats,
    post_stats_ndre,
    stats_to_rows_ndre,
)


def get_data_for_date(index_type: str, parcel_id: str, target_date: str):
    """Dobija podatke za specifičan datum"""
    script_dir = Path(__file__).resolve().parent
    load_env(script_dir / ".env")

    client_id = get_env("CDSE_CLIENT_ID", required=True)
    client_secret = get_env("CDSE_CLIENT_SECRET", required=True)

    geoserver_url = get_env("GEOSERVER_URL", "http://localhost:8083/geoserver").rstrip("/")
    workspace = get_env("GEOSERVER_WORKSPACE", "moj_projekat")
    parcel_layer = get_env("PARCEL_LAYER", "KovinDKP")
    parcel_attr = get_env("PARCEL_ATTR", "brparcele")
    max_cloud = 100  # Ukloni cloud filter
    stats_res_m = 10.0  # 10m - stvarne vrednosti Sentinel-2

    geometry = fetch_parcel_geometry(geoserver_url, workspace, parcel_layer, parcel_attr, parcel_id)
    
    # Konvertuj target_date u date_from i date_to (širi opseg: ±3 dana)
    date_obj = dt.datetime.fromisoformat(target_date.replace("Z", "+00:00"))
    date_from = (date_obj - dt.timedelta(days=3)).replace(hour=0, minute=0, second=0, microsecond=0)
    date_to = (date_obj + dt.timedelta(days=3)).replace(hour=23, minute=59, second=59, microsecond=999999)
    date_from_str = isoformat_z(date_from)
    date_to_str = isoformat_z(date_to)
    
    print(f"[INFO] Requesting {index_type} data for {target_date}")
    print(f"[INFO] Date range: {date_from_str} to {date_to_str}")
    
    token = get_token(client_id, client_secret)
    
    if index_type == "NDVI":
        payload = post_stats(token, geometry, date_from_str, date_to_str, max_cloud, stats_res_m)
        rows = stats_to_rows(payload)
    elif index_type == "NDMI":
        payload = post_stats_ndmi(token, geometry, date_from_str, date_to_str, max_cloud, stats_res_m)
        rows = stats_to_rows_ndmi(payload)
    elif index_type == "NDRE":
        payload = post_stats_ndre(token, geometry, date_from_str, date_to_str, max_cloud, stats_res_m)
        rows = stats_to_rows_ndre(payload)
    else:
        raise ValueError(f"Unknown index type: {index_type}")
    
    if rows:
        print(f"[INFO] Found {len(rows)} data points in range {date_from_str} to {date_to_str}")
        # Filtriraj samo one blizu target datuma
        target_date_obj = dt.datetime.fromisoformat(target_date.replace("Z", "+00:00"))
        filtered_rows = []
        for row in rows:
            row_date_str = row['C0/date']
            if row_date_str:
                row_date = dt.datetime.fromisoformat(row_date_str.replace("Z", "+00:00"))
                if abs((row_date - target_date_obj).days) <= 1:  # ±1 dan
                    filtered_rows.append(row)
                    print(f"\n  Date: {row['C0/date']}")
                    print(f"  Mean: {row['C0/mean']}")
                    print(f"  SampleCount: {row['C0/sampleCount']}")
                    print(f"  Median: {row['C0/median']}")
                    print(f"  P10: {row['C0/p10']}, P90: {row['C0/p90']}")
                    print(f"  CloudCoverage: {row['C0/cloudCoveragePercent']}")
        if not filtered_rows:
            print(f"[WARN] No data found within ±1 day of {target_date}")
            print(f"[INFO] All available dates in range:")
            for row in rows:
                print(f"  - {row['C0/date']}")
    else:
        print(f"[WARN] No data found in range {date_from_str} to {date_to_str}")
    
    return rows


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python get_single_date.py <INDEX_TYPE> <PARCEL_ID> <DATE>")
        print("Example: python get_single_date.py NDVI 1427/2 2025-12-28")
        sys.exit(1)
    
    index_type = sys.argv[1].upper()
    parcel_id = sys.argv[2]
    target_date = sys.argv[3]
    
    if not target_date.endswith("Z"):
        target_date = target_date + "T00:00:00Z"
    
    rows = get_data_for_date(index_type, parcel_id, target_date)
    
    if rows:
        print(f"\n[SUCCESS] Data retrieved for {target_date}")
        print(json.dumps(rows, indent=2, default=str))
    else:
        print(f"\n[FAILED] No data found for {target_date}")
