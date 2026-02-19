import sys
from pathlib import Path

from download_and_publish import (
    adaptive_min_bytes,
    build_evalscript_ndvi_value,
    download_index_for_date,
    download_with_fallback,
    geoserver_put,
    get_env,
    get_parcel_layer_suffix,
    get_token,
    load_env,
    mask_raster_to_parcel,
)
from download_ndvi_parcel import fetch_parcel_bbox, fetch_parcel_geometry, bbox_to_polygon
from download_ndvi_parcel_csv import _geometry_to_utm_bbox, get_latest_date_with_data


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
    print(f"[INFO] Parcel {parcel_id} bbox WGS84: {minx}, {miny}, {maxx}, {maxy}")

    # UTM ista mreža kao Statistics API (CSV) – da vrednosti piksela odgovaraju min/max iz CSV
    utm_bbox, utm_crs = _geometry_to_utm_bbox(geometry)
    resolution_m = float(get_env("RESOLUTION_M", "10"))
    max_pixels = int(get_env("MAX_PIXELS", "4096"))
    width_m = utm_bbox[2] - utm_bbox[0]
    height_m = utm_bbox[3] - utm_bbox[1]
    width = max(1, min(max_pixels, int(round(width_m / resolution_m))))
    height = max(1, min(max_pixels, int(round(height_m / resolution_m))))
    print(f"[INFO] UTM bbox: {utm_bbox}, output {width}x{height} (res {resolution_m}m)")

    days_back = int(get_env("PARCEL_DAYS_BACK", get_env("DAYS_BACK", "30")))
    max_cloud = int(get_env("PARCEL_MAX_CLOUD", get_env("MAX_CLOUD_COVER", "80")))
    fallback_days = int(
        get_env("PARCEL_FALLBACK_DAYS_BACK", get_env("FALLBACK_DAYS_BACK", "120"))
    )
    fallback_cloud = int(
        get_env("PARCEL_FALLBACK_MAX_CLOUD", get_env("FALLBACK_MAX_CLOUD", "100"))
    )
    min_bytes = adaptive_min_bytes(width, height, bands=1, sample_bytes=4)
    print(f"VALUE_RASTER_WIDTH={width}")
    print(f"VALUE_RASTER_HEIGHT={height}")
    print(f"[INFO] min_bytes={min_bytes}")

    token = get_token(client_id, client_secret)
    parcel_date = get_env("PARCEL_DATE", "").strip()
    evalscript = build_evalscript_ndvi_value()

    if not parcel_date:
        parcel_date, _ = get_latest_date_with_data(
            token, geometry, days_back, max_cloud, evalscript=None, label="NDVI",
        )
        if parcel_date:
            print(f"[INFO] Korišćen poslednji datum sa podacima: {parcel_date}")

    if parcel_date:
        ndvi_bytes, ndvi_from, ndvi_to = download_index_for_date(
            token, geometry, parcel_date, width, height, max_cloud,
            evalscript, f"NDVI_VALUE_PARCEL_{parcel_id}",
            bbox=utm_bbox, crs=utm_crs,
        )
        ndvi_fb = False
        if ndvi_bytes is None or len(ndvi_bytes) < min_bytes:
            print(f"[WARN] Nema podataka za datum {parcel_date}, koristim mostRecent")
            ndvi_bytes, ndvi_from, ndvi_to, ndvi_fb = download_with_fallback(
                token, geometry, days_back, width, height,
                max_cloud, min_bytes, fallback_days, fallback_cloud,
                evalscript, f"NDVI_VALUE_PARCEL_{parcel_id}",
                bbox=utm_bbox, crs=utm_crs,
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
            f"NDVI_VALUE_PARCEL_{parcel_id}",
            bbox=utm_bbox,
            crs=utm_crs,
        )

    parcel_geom = fetch_parcel_geometry(
        geoserver_url, workspace, parcel_layer, parcel_attr, parcel_id,
        kat_opstina=kat_opstina,
    )
    if parcel_geom:
        ndvi_bytes = mask_raster_to_parcel(ndvi_bytes, parcel_geom, nodata=-999)

    output_dir = Path(get_env("OUTPUT_DIR", str(script_dir / "data")))
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_parcel_id = get_parcel_layer_suffix(parcel_id, kat_opstina)
    output_name = get_env("OUTPUT_FILENAME_NDVI_VALUE_PARCEL", f"ndvi_value_parcel_{safe_parcel_id}.tif")
    output_path = output_dir / output_name
    output_path.write_bytes(ndvi_bytes)
    print(f"[INFO] Saved NDVI Value GeoTIFF: {output_path}")

    store = get_env("GEOSERVER_PARCEL_NDVI_VALUE_STORE", f"ndvi_value_parcela_{safe_parcel_id}")
    layer = get_env("GEOSERVER_PARCEL_NDVI_VALUE_LAYER", store)
    style = get_env("GEOSERVER_PARCEL_NDVI_VALUE_STYLE", "raster")

    upload_url = (
        f"{geoserver_url}/rest/workspaces/{workspace}/coveragestores/{store}/file.geotiff?configure=all"
    )
    geoserver_put(upload_url, geoserver_user, geoserver_password, ndvi_bytes, "image/tiff")
    print(f"[INFO] Uploaded to GeoServer store: {workspace}:{store}")

    style_xml = f"<layer><defaultStyle><name>{style}</name></defaultStyle></layer>".encode("utf-8")
    style_url = f"{geoserver_url}/rest/layers/{workspace}:{layer}"
    geoserver_put(style_url, geoserver_user, geoserver_password, style_xml, "text/xml")
    print(f"[INFO] Applied style: {style}")
    print(f"[INFO] NDVI Value date range: {ndvi_from} -> {ndvi_to} (fallback={ndvi_fb})")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[ERROR] {exc}")
        sys.exit(1)
