import sys
from pathlib import Path

from download_and_publish import (
    adaptive_min_bytes,
    build_evalscript_ndre_value,
    compute_output_size,
    download_index_for_date,
    download_with_fallback,
    geoserver_put,
    geoserver_request,
    get_env,
    get_parcel_layer_suffix,
    get_token,
    load_env,
    mask_raster_to_parcel,
)
from download_ndvi_parcel import fetch_parcel_bbox, fetch_parcel_geometry, bbox_to_polygon
from download_ndvi_parcel_csv import get_latest_date_with_data
from download_ndre_parcel_csv import build_evalscript_ndre_stats


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
    fallback_days = int(
        get_env("PARCEL_FALLBACK_DAYS_BACK", get_env("FALLBACK_DAYS_BACK", "120"))
    )
    fallback_cloud = int(
        get_env("PARCEL_FALLBACK_MAX_CLOUD", get_env("FALLBACK_MAX_CLOUD", "100"))
    )
    resolution_m = float(get_env("RESOLUTION_M", "10"))
    max_pixels = int(get_env("MAX_PIXELS", "4096"))
    width, height = compute_output_size(geometry, resolution_m, max_pixels)
    min_bytes = adaptive_min_bytes(width, height, bands=1, sample_bytes=4)
    print(f"[INFO] Output size {width}x{height} (res {resolution_m}m, max {max_pixels}px, min_bytes={min_bytes})")
    print(f"VALUE_RASTER_WIDTH={width}")
    print(f"VALUE_RASTER_HEIGHT={height}")

    token = get_token(client_id, client_secret)
    parcel_date = get_env("PARCEL_DATE", "").strip()
    image_criterion = get_env("PARCEL_CRITERION", "").strip()  # iz frontenda ako je prosleđen
    evalscript = build_evalscript_ndre_value()

    if not parcel_date:
        # Poslednji datum po kriterijumu (50%+/≥100 px, pa 30%+/≥50 px)
        parcel_date, image_criterion = get_latest_date_with_data(
            token, geometry, days_back, max_cloud,
            evalscript=build_evalscript_ndre_stats(), label="NDRE",
        )
        if parcel_date:
            print(f"[INFO] Korišćen poslednji datum sa podacima: {parcel_date}")

    if parcel_date:
        ndre_bytes, ndre_from, ndre_to = download_index_for_date(
            token, geometry, parcel_date, width, height, max_cloud,
            evalscript, f"NDRE_VALUE_PARCEL_{parcel_id}",
        )
        ndre_fb = False
        if ndre_bytes is None or len(ndre_bytes) < min_bytes:
            print(f"[WARN] Nema podataka za datum {parcel_date}, koristim mostRecent")
            ndre_bytes, ndre_from, ndre_to, ndre_fb = download_with_fallback(
                token, geometry, days_back, width, height,
                max_cloud, min_bytes, fallback_days, fallback_cloud,
                evalscript, f"NDRE_VALUE_PARCEL_{parcel_id}",
            )
    else:
        ndre_bytes, ndre_from, ndre_to, ndre_fb = download_with_fallback(
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
            f"NDRE_VALUE_PARCEL_{parcel_id}",
        )

    parcel_geom = fetch_parcel_geometry(
        geoserver_url, workspace, parcel_layer, parcel_attr, parcel_id,
        kat_opstina=kat_opstina,
    )
    if parcel_geom:
        ndre_bytes = mask_raster_to_parcel(ndre_bytes, parcel_geom, nodata=-999)

    output_dir = Path(get_env("OUTPUT_DIR", str(script_dir / "data")))
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_parcel_id = get_parcel_layer_suffix(parcel_id, kat_opstina)
    output_name = get_env("OUTPUT_FILENAME_NDRE_VALUE_PARCEL", f"ndre_value_parcel_{safe_parcel_id}.tif")
    output_path = output_dir / output_name
    output_path.write_bytes(ndre_bytes)
    print(f"[INFO] Saved NDRE Value GeoTIFF: {output_path}")

    store = get_env("GEOSERVER_PARCEL_NDRE_VALUE_STORE", f"ndre_value_parcela_{safe_parcel_id}")
    layer = get_env("GEOSERVER_PARCEL_NDRE_VALUE_LAYER", store)
    style = get_env("GEOSERVER_PARCEL_NDRE_VALUE_STYLE", "raster")

    import urllib.parse
    zone_style = "ndre_zones_percentile_style"
    sld_path = script_dir / f"{zone_style}.sld"
    if sld_path.exists():
        sld_bytes = sld_path.read_bytes()
        ws_post = f"{geoserver_url}/rest/workspaces/{workspace}/styles?name={urllib.parse.quote(zone_style)}"
        st, _ = geoserver_request("POST", ws_post, geoserver_user, geoserver_password, sld_bytes, "application/vnd.ogc.sld+xml")
        if st not in (200, 201) and st != 409:
            ws_put = f"{geoserver_url}/rest/workspaces/{workspace}/styles/{zone_style}?raw=true"
            geoserver_put(ws_put, geoserver_user, geoserver_password, sld_bytes, "application/vnd.ogc.sld+xml")

    upload_url = (
        f"{geoserver_url}/rest/workspaces/{workspace}/coveragestores/{store}/file.geotiff?configure=all"
    )
    geoserver_put(upload_url, geoserver_user, geoserver_password, ndre_bytes, "image/tiff")
    print(f"[INFO] Uploaded to GeoServer store: {workspace}:{store}")

    style_xml = f"<layer><defaultStyle><name>{style}</name></defaultStyle></layer>".encode("utf-8")
    style_url = f"{geoserver_url}/rest/layers/{workspace}:{layer}"
    geoserver_put(style_url, geoserver_user, geoserver_password, style_xml, "text/xml")
    print(f"[INFO] Applied style: {style}")
    print(f"[INFO] NDRE Value date range: {ndre_from} -> {ndre_to} (fallback={ndre_fb})")
    if ndre_from:
        print(f"IMAGE_DATE={ndre_from.split('T')[0]}")
    if image_criterion:
        print(f"IMAGE_CRITERION={image_criterion}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[ERROR] {exc}")
        sys.exit(1)
