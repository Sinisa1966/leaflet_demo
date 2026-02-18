#!/usr/bin/env python3
"""
Eksportuje NDVI, NDMI, NDRE parcela TIF u PNG za L.imageOverlay (bez GeoServer-a).
1. Parcela-specifični: ndvi_parcel_1427_2.tif, ndmi_parcel_1427_2.tif, ndre_zones_parcel_1427_2.tif
2. Fallback: ndvi_latest.tif, ndmi_latest.tif (crop na parcel bounds)
"""
from pathlib import Path
import json
import numpy as np

try:
    import rasterio
    from rasterio.warp import transform_bounds
    from rasterio.crs import CRS
except ImportError:
    print("Instaliraj: pip install rasterio")
    raise

PARCEL_BOUNDS = {"1427_2": [21.1986, 44.8142, 21.2021, 44.8182]}
NDVI_AUTO_DATA = Path(__file__).resolve().parent.parent / "ndvi_auto" / "data"
WEB2_DATA = Path(__file__).resolve().parent / "data"
WGS84 = CRS.from_epsg(4326)


def read_and_crop(src_path, min_lng, min_lat, max_lng, max_lat):
    """Čita raster i cropuje na WGS84 bounds."""
    with rasterio.open(src_path) as src:
        bounds_wgs84 = (min_lng, min_lat, max_lng, max_lat)
        if src.crs and src.crs != WGS84:
            bounds_proj = transform_bounds(WGS84, src.crs, *bounds_wgs84)
        else:
            bounds_proj = bounds_wgs84
        try:
            window = rasterio.windows.from_bounds(*bounds_proj, src.transform)
        except Exception:
            return None
        data = src.read(window=window)
        return data


def export_tif_to_png(parcel_id: str = "1427_2") -> dict:
    result = {"bounds": None, "exported": []}
    min_lng, min_lat, max_lng, max_lat = PARCEL_BOUNDS.get(parcel_id, [0, 0, 1, 1])
    result["bounds"] = {"south": min_lat, "west": min_lng, "north": max_lat, "east": max_lng}
    WEB2_DATA.mkdir(parents=True, exist_ok=True)

    # 1. Parcela-specifični
    parcel_layers = [
        ("ndvi", f"ndvi_parcel_{parcel_id}.tif", f"ndvi_{parcel_id}.png"),
        ("ndmi", f"ndmi_parcel_{parcel_id}.tif", f"ndmi_{parcel_id}.png"),
        ("ndre", f"ndre_zones_parcel_{parcel_id}.tif", f"ndre_zones_{parcel_id}.png"),
    ]
    for layer_name, tif_name, png_name in parcel_layers:
        src_path = NDVI_AUTO_DATA / tif_name
        dst_path = WEB2_DATA / png_name
        if not src_path.exists():
            continue
        try:
            data = rasterio.open(src_path).read()
            _write_rgb_png(data, dst_path)
            result["exported"].append(layer_name)
            print(f"[OK] {tif_name} -> {png_name}")
        except Exception as e:
            print(f"[ERR] {tif_name}: {e}")

    # 2. Fallback: ndvi_latest, ndmi_latest (crop na parcel)
    for layer_name, tif_name, png_name in [("ndvi", "ndvi_latest.tif", f"ndvi_{parcel_id}.png"),
                                            ("ndmi", "ndmi_latest.tif", f"ndmi_{parcel_id}.png")]:
        if layer_name in result["exported"]:
            continue
        src_path = NDVI_AUTO_DATA / tif_name
        dst_path = WEB2_DATA / png_name
        if not src_path.exists():
            print(f"[SKIP] {tif_name} ne postoji")
            continue
        try:
            data = read_and_crop(src_path, min_lng, min_lat, max_lng, max_lat)
            if data is not None and data.size > 0:
                _write_rgb_png(data, dst_path)
                result["exported"].append(layer_name)
                print(f"[OK] {tif_name} (crop) -> {png_name}")
        except Exception as e:
            print(f"[ERR] {tif_name}: {e}")

    return result


def _write_rgb_png(data, dst_path):
    if data.ndim == 3 and data.shape[0] >= 3:
        rgb = np.transpose(data[:3], (1, 2, 0))
    elif data.ndim == 2:
        rgb = np.stack([data, data, data], axis=-1)
    else:
        rgb = np.stack([data[0], data[0], data[0]], axis=-1)
    if rgb.dtype != np.uint8:
        rgb = np.clip(rgb, 0, 255).astype(np.uint8)
    from PIL import Image
    Image.fromarray(rgb).save(dst_path)


def trigger_parcel_server(parcel_id: str = "1427/2") -> bool:
    """Poziva parcel server da generiše NDVI i NDMI za parcelu (ako radi na :5010)."""
    import urllib.request
    base = "http://localhost:5010"
    for endpoint, name in [("/run", "NDVI"), ("/ndmi", "NDMI")]:
        try:
            url = f"{base}{endpoint}?parcel={urllib.parse.quote(parcel_id)}&layer=kovin_dkp_pg"
            with urllib.request.urlopen(url, timeout=120) as _:
                print(f"[OK] Parcel server: {name} generisan")
        except Exception as e:
            print(f"[SKIP] Parcel server {endpoint}: {e}")
            return False
    return True


def main():
    import sys
    if "--fetch" in sys.argv:
        print("Pozivam parcel server za NDVI/NDMI...")
        trigger_parcel_server("1427/2")
    print("Export rasters -> PNG za web2...")
    r = export_tif_to_png("1427_2")
    bounds_path = WEB2_DATA / "parcel_1427_2_bounds.json"
    bounds_path.write_text(json.dumps(r["bounds"], indent=2))
    print(f"Bounds: {bounds_path}")
    print(f"Exported: {r['exported']}")
    if "ndvi" not in r["exported"] or "ndmi" not in r["exported"]:
        print("Za NDVI/NDMI: pokreni 'python export_rasters_to_png.py --fetch' (parcel server na :5010)")


if __name__ == "__main__":
    main()
