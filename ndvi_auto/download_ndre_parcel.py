import sys
from pathlib import Path

from download_and_publish import (
    build_evalscript_ndre,
    compute_output_size,
    download_index_for_date,
    download_with_fallback,
    geoserver_put,
    get_env,
    get_parcel_layer_suffix,
    get_token,
    load_env,
)
from download_ndvi_parcel import fetch_parcel_bbox, bbox_to_polygon


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
    evalscript = build_evalscript_ndre()
    if parcel_date:
        ndre_bytes, ndre_from, ndre_to = download_index_for_date(
            token, geometry, parcel_date, width, height, max_cloud,
            evalscript, f"NDRE_PARCEL_{parcel_id}",
        )
        ndre_fb = False
        if ndre_bytes is None or len(ndre_bytes) < min_bytes:
            print(f"[WARN] Nema dovoljno podataka za datum {parcel_date}, koristim mostRecent")
            ndre_bytes, ndre_from, ndre_to, ndre_fb = download_with_fallback(
                token, geometry, days_back, width, height,
                max_cloud, min_bytes, fallback_days, fallback_cloud,
                evalscript, f"NDRE_PARCEL_{parcel_id}",
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
            f"NDRE_PARCEL_{parcel_id}",
        )

    output_dir = Path(get_env("OUTPUT_DIR", str(script_dir / "data")))
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_parcel_id = get_parcel_layer_suffix(parcel_id, kat_opstina)
    output_name = get_env("OUTPUT_FILENAME_NDRE_PARCEL", f"ndre_parcel_{safe_parcel_id}.tif")
    output_path = output_dir / output_name
    output_path.write_bytes(ndre_bytes)
    print(f"[INFO] Saved NDRE GeoTIFF: {output_path}")

    store = get_env("GEOSERVER_PARCEL_NDRE_STORE", f"ndre_parcela_{safe_parcel_id}")
    layer = get_env("GEOSERVER_PARCEL_NDRE_LAYER", store)
    style = get_env("GEOSERVER_PARCEL_NDRE_STYLE", "raster")

    upload_url = (
        f"{geoserver_url}/rest/workspaces/{workspace}/coveragestores/{store}/file.geotiff?configure=all"
    )
    geoserver_put(upload_url, geoserver_user, geoserver_password, ndre_bytes, "image/tiff")
    print(f"[INFO] Uploaded to GeoServer store: {workspace}:{store}")

    style_xml = f"<layer><defaultStyle><name>{style}</name></defaultStyle></layer>".encode("utf-8")
    style_url = f"{geoserver_url}/rest/layers/{workspace}:{layer}"
    geoserver_put(style_url, geoserver_user, geoserver_password, style_xml, "text/xml")
    print(f"[INFO] Applied style: {style}")
    print(f"[INFO] NDRE date range: {ndre_from} -> {ndre_to} (fallback={ndre_fb})")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[ERROR] {exc}")
        sys.exit(1)
