import sys
from pathlib import Path
from download_and_publish import load_env, get_env, ensure_style

def main() -> None:
    script_dir = Path(__file__).resolve().parent
    load_env(script_dir / ".env")

    geoserver_url = get_env("GEOSERVER_URL", "http://localhost:8083/geoserver").rstrip("/")
    geoserver_user = get_env("GEOSERVER_USER", "admin")
    geoserver_password = get_env("GEOSERVER_PASSWORD", "geoserver")

    style_name = "ndre_gradient_style"
    sld_path = script_dir / f"{style_name}.sld"

    print(f"[INFO] Uploading style '{style_name}' to GeoServer at {geoserver_url}")
    ensure_style(geoserver_url, geoserver_user, geoserver_password, style_name, sld_path)
    print(f"[INFO] Style '{style_name}' updated successfully")
    print("[INFO] Done!")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[ERROR] {exc}")
        sys.exit(1)
