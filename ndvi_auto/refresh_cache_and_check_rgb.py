#!/usr/bin/env python3
"""
Refresh GeoServer cache and check if raster has RGB channels
"""
import os
import sys
import json
from pathlib import Path
import urllib.parse
import urllib.request
import base64


def load_env(env_path: Path) -> None:
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if value:
            os.environ[key] = value


def get_env(name: str, default=None, required: bool = False) -> str:
    value = os.getenv(name, default)
    if required and not value:
        print(f"[ERROR] Missing env var: {name}")
        sys.exit(1)
    return value


def geoserver_request(
    method: str, url: str, user: str, password: str, data: bytes = None, content_type: str = None
) -> tuple[int, str]:
    creds = base64.b64encode(f"{user}:{password}".encode("utf-8")).decode("ascii")
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Basic {creds}")
    if content_type:
        req.add_header("Content-Type", content_type)
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            return resp.status, resp.read().decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="ignore")


def refresh_geoserver_cache(geoserver_url: str, user: str, password: str) -> None:
    """Refresh GeoServer cache"""
    print("[INFO] Refreshing GeoServer cache...")
    # Reset cache endpoint
    reset_url = f"{geoserver_url}/rest/reset"
    status, body = geoserver_request("POST", reset_url, user, password, b"", "application/json")
    if status in (200, 201):
        print("[INFO] GeoServer cache refreshed successfully")
    else:
        print(f"[WARN] Cache refresh returned status {status}: {body}")


def check_raster_info(geoserver_url: str, user: str, password: str, workspace: str, layer_name: str) -> None:
    """Check raster layer info through GeoServer REST API"""
    print(f"[INFO] Checking raster info for layer: {workspace}:{layer_name}")
    
    # Get layer info
    layer_url = f"{geoserver_url}/rest/workspaces/{workspace}/coverages/{layer_name}.json"
    status, body = geoserver_request("GET", layer_url, user, password)
    
    if status == 200:
        try:
            layer_info = json.loads(body)
            coverage = layer_info.get("coverage", {})
            dimensions = coverage.get("dimensions", {})
            
            print(f"[INFO] Layer: {layer_name}")
            print(f"[INFO] Dimensions: {json.dumps(dimensions, indent=2)}")
            
            # Check for bands/channels
            if "bands" in coverage:
                bands = coverage["bands"]
                print(f"[INFO] Number of bands: {len(bands)}")
                for i, band in enumerate(bands):
                    print(f"[INFO]   Band {i+1}: {band}")
            
            # Try to get coverage store info
            store_name = coverage.get("store", {}).get("name", "")
            if store_name:
                store_url = f"{geoserver_url}/rest/workspaces/{workspace}/coveragestores/{store_name}.json"
                store_status, store_body = geoserver_request("GET", store_url, user, password)
                if store_status == 200:
                    store_info = json.loads(store_body)
                    print(f"[INFO] Store: {store_name}")
                    print(f"[INFO] Store type: {store_info.get('coverageStore', {}).get('type', 'unknown')}")
        except json.JSONDecodeError as e:
            print(f"[WARN] Could not parse layer info: {e}")
    else:
        print(f"[WARN] Could not get layer info (status {status}): {body}")


def check_local_raster(data_dir: Path, parcel_id: str = None) -> None:
    """Check local raster files using gdalinfo if available"""
    print("[INFO] Checking local raster files...")
    
    # Try to find gdalinfo
    import shutil
    gdalinfo = shutil.which("gdalinfo")
    if not gdalinfo:
        print("[WARN] gdalinfo not found in PATH. Install GDAL to check raster channels.")
        return
    
    # Check for parcel rasters
    if parcel_id:
        safe_id = parcel_id.replace("/", "_").replace("\\", "_")
        patterns = [
            f"ndvi_parcel_{safe_id}.tif",
            f"ndmi_parcel_{safe_id}.tif",
            f"ndre_parcel_{safe_id}.tif",
        ]
    else:
        patterns = [
            "ndvi_latest.tif",
            "ndmi_latest.tif",
            "ndre_latest.tif",
        ]
    
    for pattern in patterns:
        raster_path = data_dir / pattern
        if raster_path.exists():
            print(f"\n[INFO] Checking {raster_path.name}...")
            import subprocess
            try:
                result = subprocess.run(
                    [gdalinfo, str(raster_path)],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode == 0:
                    output = result.stdout
                    # Check for band count
                    if "Band" in output:
                        lines = output.split("\n")
                        band_count = 0
                        for line in lines:
                            if "Band" in line and "Block=" in line:
                                band_count += 1
                        print(f"[INFO]   Number of bands: {band_count}")
                        if band_count >= 3:
                            print(f"[INFO]   ✓ Has RGB channels (3+ bands)")
                        else:
                            print(f"[WARN]   ✗ Only {band_count} band(s) - may not have RGB")
                    
                    # Check for color interpretation
                    if "ColorInterp" in output:
                        print(f"[INFO]   Color interpretation found in metadata")
                else:
                    print(f"[WARN]   gdalinfo failed: {result.stderr}")
            except Exception as e:
                print(f"[WARN]   Error running gdalinfo: {e}")
        else:
            print(f"[INFO]   {pattern} not found")


def main() -> None:
    script_dir = Path(__file__).resolve().parent
    load_env(script_dir / ".env")

    geoserver_url = get_env("GEOSERVER_URL", "http://localhost:8083/geoserver").rstrip("/")
    geoserver_user = get_env("GEOSERVER_USER", "admin")
    geoserver_password = get_env("GEOSERVER_PASSWORD", "geoserver")
    workspace = get_env("GEOSERVER_WORKSPACE", "moj_projekat")
    
    # Refresh cache
    refresh_geoserver_cache(geoserver_url, geoserver_user, geoserver_password)
    
    # Check raster info for a sample parcel layer
    sample_parcel_id = "25991"
    safe_id = sample_parcel_id.replace("/", "_").replace("\\", "_")
    
    print("\n" + "="*60)
    print("Checking raster layers in GeoServer:")
    print("="*60)
    
    layers_to_check = [
        f"ndvi_parcela_{safe_id}",
        f"ndmi_parcela_{safe_id}",
        f"ndre_parcela_{safe_id}",
    ]
    
    for layer_name in layers_to_check:
        print(f"\n--- {layer_name} ---")
        check_raster_info(geoserver_url, geoserver_user, geoserver_password, workspace, layer_name)
    
    # Check local raster files
    print("\n" + "="*60)
    print("Checking local raster files:")
    print("="*60)
    data_dir = script_dir / "data"
    if data_dir.exists():
        check_local_raster(data_dir, sample_parcel_id)
    else:
        print(f"[WARN] Data directory not found: {data_dir}")
    
    print("\n[INFO] Done!")


if __name__ == "__main__":
    main()
