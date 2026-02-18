import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from download_and_publish import (
    build_evalscript_ndvi,
    compute_output_size,
    download_index_for_date,
    download_with_fallback,
    geoserver_put,
    get_env,
    get_parcel_layer_suffix,
    get_token,
    load_env,
)


def fetch_parcel_bbox(
    geoserver_url: str,
    workspace: str,
    layer: str,
    parcel_attr: str,
    parcel_id: str,
    *,
    kat_opstina: str | None = None,
) -> tuple[float, float, float, float]:
    """Dohvata bbox parcele. Ako KO filter ne pronađe ništa, pokušava bez njega."""
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
        except Exception:
            continue
        features = data.get("features", [])
        if not features:
            continue
        coords = features[0]["geometry"]["coordinates"]
        mins = [1e18, 1e18]
        maxs = [-1e18, -1e18]

        def walk(c):
            if isinstance(c[0], (int, float)):
                x, y = c[0], c[1]
                mins[0] = min(mins[0], x)
                mins[1] = min(mins[1], y)
                maxs[0] = max(maxs[0], x)
                maxs[1] = max(maxs[1], y)
            else:
                for cc in c:
                    walk(cc)

        walk(coords)
        return mins[0], mins[1], maxs[0], maxs[1]
    raise RuntimeError(f"Parcel {parcel_id} not found in {workspace}:{layer}")


def bbox_to_polygon(minx, miny, maxx, maxy) -> dict:
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [minx, miny],
                [maxx, miny],
                [maxx, maxy],
                [minx, maxy],
                [minx, miny],
            ]
        ],
    }


def main() -> None:
    script_dir = Path(__file__).resolve().parent
    load_env(script_dir / ".env")

    client_id = get_env("CDSE_CLIENT_ID", required=True)
    client_secret = get_env("CDSE_CLIENT_SECRET", required=True)

    geoserver_url = get_env("GEOSERVER_URL", "http://localhost:8083/geoserver").rstrip("/")
    geoserver_user = get_env("GEOSERVER_USER", "admin")
    geoserver_password = get_env("GEOSERVER_PASSWORD", "geoserver")
    workspace = get_env("GEOSERVER_WORKSPACE", "moj_projekat")

    parcel_layer = get_env("PARCEL_LAYER", "VrsacDKP")
    parcel_attr = get_env("PARCEL_ATTR", "brparcele")
    parcel_id = get_env("PARCEL_ID", "25991")
    kat_opstina = get_env("PARCEL_KAT_OPSTINA", "").strip() or None

    minx, miny, maxx, maxy = fetch_parcel_bbox(
        geoserver_url, workspace, parcel_layer, parcel_attr, parcel_id,
        kat_opstina=kat_opstina,
    )
    geometry = bbox_to_polygon(minx, miny, maxx, maxy)
    print(f"[INFO] Parcel {parcel_id} bbox: {minx}, {miny}, {maxx}, {maxy}")

    days_back = int(get_env("PARCEL_DAYS_BACK", get_env("DAYS_BACK", "30")))
    max_cloud = int(get_env("PARCEL_MAX_CLOUD", get_env("MAX_CLOUD_COVER", "80")))
    min_bytes = int(get_env("PARCEL_MIN_TIFF_BYTES", get_env("MIN_TIFF_BYTES", "50000")))
    fallback_days = int(
        get_env("PARCEL_FALLBACK_DAYS_BACK", get_env("FALLBACK_DAYS_BACK", "120"))
    )
    fallback_cloud = int(
        get_env("PARCEL_FALLBACK_MAX_CLOUD", get_env("FALLBACK_MAX_CLOUD", "100"))
    )
    resolution_m = float(get_env("RESOLUTION_M", "10"))
    max_pixels = int(get_env("MAX_PIXELS", "4096"))
    width, height = compute_output_size(geometry, resolution_m, max_pixels)
    print(f"[INFO] Output size {width}x{height} (res {resolution_m}m, max {max_pixels}px)")

    token = get_token(client_id, client_secret)
    parcel_date = get_env("PARCEL_DATE", "").strip()
    evalscript = build_evalscript_ndvi()
    if parcel_date:
        ndvi_bytes, ndvi_from, ndvi_to = download_index_for_date(
            token, geometry, parcel_date, width, height, max_cloud,
            evalscript, f"NDVI_PARCEL_{parcel_id}",
        )
        ndvi_fb = False
        if ndvi_bytes is None or len(ndvi_bytes) < min_bytes:
            print(f"[WARN] Nema dovoljno podataka za datum {parcel_date}, koristim mostRecent")
            ndvi_bytes, ndvi_from, ndvi_to, ndvi_fb = download_with_fallback(
                token, geometry, days_back, width, height,
                max_cloud, min_bytes, fallback_days, fallback_cloud,
                evalscript, f"NDVI_PARCEL_{parcel_id}",
            )
    else:
        ndvi_bytes, ndvi_from, ndvi_to, ndvi_fb = download_with_fallback(
            token,
            geometry,
            days_back,
            width,
            height,
            max_cloud,
            min_bytes,
            fallback_days,
            fallback_cloud,
            evalscript,
            f"NDVI_PARCEL_{parcel_id}",
        )

    # Isto kao NDMI: satelite/ kad nije Docker, inače OUTPUT_DIR ili data
    if Path("/.dockerenv").exists() and Path("/app/data").exists():
        default_dir = "/app/data"
    else:
        default_dir = str((script_dir.parent / "satelite").resolve())
    output_dir = Path(get_env("OUTPUT_DIR", default_dir))
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_parcel_id = get_parcel_layer_suffix(parcel_id, kat_opstina)
    output_name = get_env("OUTPUT_FILENAME_PARCEL", f"ndvi_parcel_{safe_parcel_id}.tif")
    output_path = output_dir / output_name
    output_path.write_bytes(ndvi_bytes)
    print(f"[INFO] Saved NDVI GeoTIFF: {output_path}")

    store = get_env("GEOSERVER_PARCEL_STORE", f"ndvi_parcela_{safe_parcel_id}")
    layer = get_env("GEOSERVER_PARCEL_LAYER", store)
    style = get_env("GEOSERVER_PARCEL_STYLE", "raster")

    upload_url = (
        f"{geoserver_url}/rest/workspaces/{workspace}/coveragestores/{store}/file.geotiff?configure=all"
    )
    geoserver_put(upload_url, geoserver_user, geoserver_password, ndvi_bytes, "image/tiff")
    print(f"[INFO] Uploaded to GeoServer store: {workspace}:{store}")

    style_xml = f"<layer><defaultStyle><name>{style}</name></defaultStyle></layer>".encode("utf-8")
    style_url = f"{geoserver_url}/rest/layers/{workspace}:{layer}"
    geoserver_put(style_url, geoserver_user, geoserver_password, style_xml, "text/xml")
    print(f"[INFO] Applied style: {style}")
    print(f"[INFO] NDVI date range: {ndvi_from} -> {ndvi_to} (fallback={ndvi_fb})")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[ERROR] {exc}")
        sys.exit(1)
