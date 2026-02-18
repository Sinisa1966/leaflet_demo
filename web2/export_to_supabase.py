#!/usr/bin/env python3
"""
Export podataka iz lokalnog Kopernikus-GIS sistema u Supabase
"""

import os
import sys
import json
import csv
from datetime import datetime
from pathlib import Path

# Dodaj parent direktorijum u PATH za import
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from supabase import create_client, Client
except ImportError:
    print("[X] Missing dependencies!")
    print("Install with: pip install supabase")
    sys.exit(1)


# =============================================
# CONFIGURATION
# =============================================

# Supabase credentials (zameni sa svojim)
SUPABASE_URL = os.getenv("SUPABASE_URL", "YOUR_SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "YOUR_SUPABASE_SERVICE_KEY")  # Service role key!

# Local data paths
BASE_DIR = Path(__file__).parent.parent
SATELITE_DIR = BASE_DIR / "ndvi_auto" / "satelite"
DATA_DIR = BASE_DIR / "ndvi_auto" / "data"

# Default parcel to export
DEFAULT_PARCEL = "1427/2"


# =============================================
# SUPABASE CLIENT
# =============================================

def init_supabase() -> Client:
    """Initialize Supabase client"""
    if SUPABASE_URL == "YOUR_SUPABASE_URL":
        print("[X] Supabase credentials nisu konfigurisani!")
        print("Set environment variables:")
        print("  export SUPABASE_URL='https://your-project.supabase.co'")
        print("  export SUPABASE_KEY='your-service-role-key'")
        sys.exit(1)
    
    return create_client(SUPABASE_URL, SUPABASE_KEY)


# =============================================
# PARCEL DATA
# =============================================

def export_parcel_geometry(supabase: Client, parcel_id: str):
    """Export parcel geometry"""
    print(f"[*] Exporting parcel geometry for {parcel_id}...")
    
    # Dummy geometry for parcela 1427/2 (replace with real from PostGIS)
    geometry = {
        "type": "Polygon",
        "coordinates": [[[
            [21.1986, 44.8142],
            [21.2021, 44.8142],
            [21.2021, 44.8182],
            [21.1986, 44.8182],
            [21.1986, 44.8142]
        ]]]
    }
    
    data = {
        "parcel_id": parcel_id,
        "cadastral_id": f"Kovin_{parcel_id.replace('/', '_')}",
        "municipality": "Kovin",
        "area_ha": 0.5,
        "geometry": geometry
    }
    
    try:
        result = supabase.table("parcels").upsert(data).execute()
        print(f"  [OK] Parcel geometry exported")
        return result
    except Exception as e:
        print(f"  [X] Error: {e}")
        return None


# =============================================
# INDEX RESULTS (CSV → Supabase)
# =============================================

def export_index_results_from_csv(supabase: Client, parcel_id: str, index_type: str):
    """Export index results from CSV files"""
    print(f"[*] Exporting {index_type} results for {parcel_id}...")
    
    # Find CSV file
    safe_id = parcel_id.replace("/", "_")
    csv_file = SATELITE_DIR / f"parcela_{safe_id}_{index_type}.csv"
    
    if not csv_file.exists():
        print(f"  [!] CSV file not found: {csv_file}")
        return 0
    
    # Read CSV (podržava C0/date format iz ndvi_auto i alternativne nazive)
    results = []
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                # Parse date (C0/date ili date ili acquisition_date)
                date_str = (row.get('C0/date') or row.get('date') or row.get('acquisition_date') or '').strip()
                if not date_str:
                    continue
                # Na samo datum YYYY-MM-DD (bez vremena)
                if 'T' in date_str:
                    date_str = date_str.split('T')[0]
                
                # Polja: C0/mean, C0/min, C0/max - NaN nije JSON compliant za Supabase
                def safe_float(v, default=0):
                    try:
                        x = float(v or default)
                        return None if (x != x) else x  # NaN != NaN
                    except (TypeError, ValueError):
                        return None
                mean_val = safe_float(row.get('C0/mean') or row.get('mean'), 0)
                min_val = safe_float(row.get('C0/min') or row.get('min'), 0)
                max_val = safe_float(row.get('C0/max') or row.get('max'), 0)
                std_val = safe_float(row.get('C0/stDev') or row.get('stDev'), 0)
                valid_pixels = int(float(row.get('C0/sampleCount') or row.get('validPixels') or 0))
                cloud_pixels = int(float(row.get('C0/noDataCount') or row.get('cloudPixels') or 0))
                p10 = safe_float(row.get('C0/p10') or row.get('p10'), 0)
                p50 = safe_float(row.get('C0/median') or row.get('C0/p50') or row.get('p50'), mean_val if mean_val is not None else 0)
                p90 = safe_float(row.get('C0/p90') or row.get('p90'), 0)
                
                if mean_val is None and min_val is None and max_val is None:
                    continue
                results.append({
                    "parcel_id": parcel_id,
                    "index_type": index_type,
                    "acquisition_date": date_str,
                    "mean_value": mean_val,
                    "min_value": min_val,
                    "max_value": max_val,
                    "std_dev": std_val,
                    "valid_pixels": valid_pixels,
                    "cloud_pixels": cloud_pixels,
                    "percentile_10": p10,
                    "percentile_50": p50,
                    "percentile_90": p90
                })
            except Exception as e:
                print(f"  [!] Error parsing row: {e}")
                continue
    
    if len(results) == 0:
        print(f"  [!] No valid data found in CSV")
        return 0
    
    # Batch insert to Supabase
    try:
        supabase.table("index_results").upsert(results).execute()
        print(f"  [OK] Exported {len(results)} {index_type} records")
        return len(results)
    except Exception as e:
        print(f"  [X] Error inserting data: {e}")
        return 0


# =============================================
# ZONE CLASSIFICATIONS
# =============================================

def export_zone_classifications(supabase: Client, parcel_id: str):
    """Export NDRE zone classifications"""
    print(f"[*] Exporting NDRE zone classifications...")
    
    # Dummy zone data (calculate from latest NDRE results or hardcode)
    zones = [
        {
            "parcel_id": parcel_id,
            "index_type": "NDRE",
            "acquisition_date": "2026-02-04",
            "zone_type": "red",
            "zone_label": "Problematična zona (< 0.14)",
            "percentage": 15.0,
            "recommendation": "Dodaj više azota. NDRE vrednosti ispod 0.14 ukazuju na deficit azota."
        },
        {
            "parcel_id": parcel_id,
            "index_type": "NDRE",
            "acquisition_date": "2026-02-04",
            "zone_type": "yellow",
            "zone_label": "Umerena zona (0.14-0.19)",
            "percentage": 60.0,
            "recommendation": "Standardna obrada. NDRE u optimalnom opsegu."
        },
        {
            "parcel_id": parcel_id,
            "index_type": "NDRE",
            "acquisition_date": "2026-02-04",
            "zone_type": "green",
            "zone_label": "Dobra zona (≥ 0.19)",
            "percentage": 25.0,
            "recommendation": "Može manje azota. Odlično zdravlje useva."
        }
    ]
    
    try:
        supabase.table("zone_classifications").upsert(zones).execute()
        print(f"  [OK] Exported {len(zones)} zone classifications")
        return len(zones)
    except Exception as e:
        print(f"  [X] Error: {e}")
        return 0


# =============================================
# METADATA
# =============================================

def export_metadata(supabase: Client):
    """Export system metadata"""
    print(f"[*] Exporting metadata...")
    
    metadata = [
        {"key": "last_update", "value": datetime.now().isoformat()},
        {"key": "version", "value": "2026-02-09"},
        {"key": "total_parcels", "value": "1"},
        {"key": "data_source", "value": "Copernicus Sentinel-2"}
    ]
    
    try:
        for item in metadata:
            supabase.table("metadata").upsert(item).execute()
        print(f"  [OK] Metadata exported")
    except Exception as e:
        print(f"  [X] Error: {e}")


# =============================================
# MAIN
# =============================================

def main():
    print("=" * 60)
    print("KOPERNIKUS-GIS -> SUPABASE EXPORT")
    print("=" * 60)
    print()
    
    # Initialize Supabase
    supabase = init_supabase()
    print("[OK] Supabase client initialized")
    print()
    
    # Export parcel geometry
    export_parcel_geometry(supabase, DEFAULT_PARCEL)
    print()
    
    # Export index results (NDVI, NDMI, NDRE)
    for index_type in ['NDVI', 'NDMI', 'NDRE']:
        count = export_index_results_from_csv(supabase, DEFAULT_PARCEL, index_type)
        print()
    
    # Export zone classifications
    export_zone_classifications(supabase, DEFAULT_PARCEL)
    print()
    
    # Export metadata
    export_metadata(supabase)
    print()
    
    print("=" * 60)
    print("[OK] EXPORT COMPLETED!")
    print("=" * 60)
    print()
    print("Next steps:")
    print("1. Open web2/index.html in browser")
    print("2. Or upload web2/ folder to your hosting")
    print("3. Update js/config.js with Supabase credentials")
    print()


if __name__ == "__main__":
    main()
