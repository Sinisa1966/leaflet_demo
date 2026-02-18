#!/usr/bin/env python3
"""
Preuzima NDVI, NDMI, NDRE iz GeoServer WMS i čuva kao PNG za web2.
Koristi: http://localhost:8083/geoserver/moj_projekat/wms
Parcela 1427/2 bounds: 21.1986, 44.8142, 21.2021, 44.8182 (lng,lat)
"""
import urllib.parse
import urllib.request
from pathlib import Path

GEOSERVER_WMS = "http://localhost:8083/geoserver/moj_projekat/wms"
WORKSPACE = "moj_projekat"
BOUNDS = (21.1986, 44.8142, 21.2021, 44.8182)  # minx, miny, maxx, maxy
WIDTH = 512
HEIGHT = 512
WEB2_DATA = Path(__file__).resolve().parent / "data"


def wms_get_map(layer: str, style: str = "index_rgb_style") -> bytes:
    """WMS GetMap za layer u moj_projekat workspace."""
    params = {
        "service": "WMS",
        "version": "1.3.0",
        "request": "GetMap",
        "layers": f"{WORKSPACE}:{layer}",
        "styles": style,
        "crs": "EPSG:4326",
        "bbox": ",".join(str(b) for b in BOUNDS),
        "width": str(WIDTH),
        "height": str(HEIGHT),
        "format": "image/png",
        "transparent": "true",
    }
    url = f"{GEOSERVER_WMS}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=30) as resp:
        return resp.read()


def main():
    WEB2_DATA.mkdir(parents=True, exist_ok=True)

    # NDVI i NDMI iz GeoServer WMS. NDRE koristi export_rasters_to_png (iz TIF-a).
    targets = [
        ("ndvi_1427_2.png", ["ndvi_parcela_1427_2", "ndvi_srbija"]),
        ("ndmi_1427_2.png", ["ndmi_parcela_1427_2", "ndmi_srbija"]),
    ]

    for png_name, layer_candidates in targets:
        for layer_name in layer_candidates:
            try:
                data = wms_get_map(layer_name)
                if len(data) < 100:
                    print(f"[WARN] {layer_name}: odgovor previše mali")
                    continue
                (WEB2_DATA / png_name).write_bytes(data)
                print(f"[OK] {layer_name} -> {png_name}")
                break
            except Exception as e:
                print(f"[SKIP] {layer_name}: {e}")
        else:
            print(f"[FAIL] {png_name}: nijedan layer nije uspeo")


if __name__ == "__main__":
    main()
