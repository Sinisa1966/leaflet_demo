#!/usr/bin/env python3
"""Računa statistiku iz postojećeg raster fajla za parcelu"""
import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.mask import mask

from download_ndvi_parcel import fetch_parcel_bbox
from download_ndvi_parcel_csv_old import fetch_parcel_geometry


def compute_stats_from_tif(tif_path: Path, parcel_geometry: dict, index_type: str = "NDVI") -> dict:
    """Računa statistiku iz GeoTIFF fajla za parcelu"""
    if not tif_path.exists():
        raise FileNotFoundError(f"Raster file not found: {tif_path}")
    
    with rasterio.open(tif_path) as src:
        print(f"[INFO] Raster info: {src.count} bands, {src.width}x{src.height} pixels")
        print(f"[INFO] CRS: {src.crs}, Bounds: {src.bounds}")
        
        # Maskiraj raster na parcelu
        out_image, out_transform = mask(src, [parcel_geometry], crop=True)
        print(f"[INFO] After masking: shape={out_image.shape}, dtype={out_image.dtype}")
        
        # Uzmi prvi band (index vrednosti)
        index_values = out_image[0]
        
        # Konvertuj u float32 ako nije već float
        if index_values.dtype != np.float32 and index_values.dtype != np.float64:
            index_values = index_values.astype(np.float32)
            # Maskiraj 0 vrednosti kao invalid (ako je uint8, 0 može biti nodata)
            if index_values.dtype == np.uint8 or str(index_values.dtype).startswith('uint'):
                # Ne maskiram 0 jer to mogu biti validne vrednosti
                pass
        
        # Filtriraj validne piksele (finite i ne NaN)
        valid = np.isfinite(index_values)
        values = index_values[valid]
        
        print(f"[INFO] Valid pixels: {values.size} / {index_values.size} ({100*values.size/index_values.size:.1f}%)")
        
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
        
        print(f"[INFO] Value range: min={values.min():.6f}, max={values.max():.6f}, mean={values.mean():.6f}")
        
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


def main():
    if len(sys.argv) < 4:
        print("Usage: python compute_stats_from_raster_file.py <TIF_PATH> <PARCEL_ID> <INDEX_TYPE>")
        print("Example: python compute_stats_from_raster_file.py satelite/ndvi_parcel_1427_2.tif 1427/2 NDVI")
        sys.exit(1)
    
    tif_path = Path(sys.argv[1])
    parcel_id = sys.argv[2]
    index_type = sys.argv[3].upper()
    
    # Učitaj env
    script_dir = Path(__file__).resolve().parent
    from download_and_publish import get_env, load_env
    load_env(script_dir / ".env")
    
    geoserver_url = get_env("GEOSERVER_URL", "http://localhost:8083/geoserver").rstrip("/")
    workspace = get_env("GEOSERVER_WORKSPACE", "moj_projekat")
    parcel_layer = get_env("PARCEL_LAYER", "KovinDKP")
    parcel_attr = get_env("PARCEL_ATTR", "brparcele")
    
    # Dobij geometriju parcele
    parcel_geometry = fetch_parcel_geometry(geoserver_url, workspace, parcel_layer, parcel_attr, parcel_id)
    
    # Računaj statistiku
    stats = compute_stats_from_tif(tif_path, parcel_geometry, index_type)
    
    print(f"\n[RESULTS] Statistics for {index_type}:")
    print(f"  SampleCount: {stats['sampleCount']}")
    print(f"  Mean: {stats['mean']:.6f}" if stats['mean'] else "  Mean: None")
    print(f"  Median: {stats['median']:.6f}" if stats['median'] else "  Median: None")
    print(f"  P10: {stats['p10']:.6f}" if stats['p10'] else "  P10: None")
    print(f"  P90: {stats['p90']:.6f}" if stats['p90'] else "  P90: None")
    print(f"  Min: {stats['min']:.6f}" if stats['min'] else "  Min: None")
    print(f"  Max: {stats['max']:.6f}" if stats['max'] else "  Max: None")
    
    print(f"\n[JSON] {json.dumps(stats, indent=2, default=str)}")


if __name__ == "__main__":
    main()
