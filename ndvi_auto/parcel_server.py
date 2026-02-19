import json
import os
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# CSV endpointi koji mogu da se keširaju lokalno (max starost u sekundama)
_CSV_ENDPOINTS = {"/csv", "/ndmi_csv", "/ndre_csv"}
_CSV_CACHE_SEC = int(os.getenv("PARCEL_CSV_CACHE_SEC", str(6 * 3600)))  # 6 sati

def _csv_path_for_endpoint(path: str, suffix: str, csv_dir: Path) -> Path | None:
    if path == "/csv":
        return csv_dir / f"parcela_{suffix}_NDVI.csv"
    if path == "/ndmi_csv":
        return csv_dir / f"parcela_{suffix}_NDMI.csv"
    if path == "/ndre_csv":
        return csv_dir / f"parcela_{suffix}_NDRE.csv"
    return None


SCRIPT_DIR = Path(__file__).resolve().parent
PORT = int(os.getenv("PARCEL_SERVER_PORT", "5010"))


def _get_csv_dir() -> Path:
    """Isti direktorijum kao u download_*_parcel_csv.py skriptama."""
    if Path("/.dockerenv").exists() and Path("/app/data").exists():
        return Path("/app/data")
    return (SCRIPT_DIR.parent / "satelite").resolve()


def _get_parcel_layer_suffix(parcel_id: str, kat_opstina: str | None) -> str:
    """Vraća suffix za layer/store: '1146' ili '1146_DUBOVAC'."""
    safe = parcel_id.replace("/", "_").replace("\\", "_")
    if kat_opstina and kat_opstina.strip():
        ko = kat_opstina.strip().upper().replace(" ", "_").replace("/", "_").replace("'", "")[:50]
        safe = safe + "_" + ko
    return safe


class ParcelHandler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _read_body(self) -> bytes:
        cl = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(cl) if cl else b""

    def _get_cookie_value(self) -> str | None:
        cookie = self.headers.get("Cookie") or ""
        for part in cookie.split(";"):
            part = part.strip()
            if part.startswith(COOKIE_NAME + "="):
                return part.split("=", 1)[1].strip()
        return None

    def _is_authenticated(self) -> bool:
        val = self._get_cookie_value()
        return val == COOKIE_SECRET if val else False

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        if path.startswith("/parcel/"):
            path = "/" + path[len("/parcel/"):].lstrip("/") or "/run"
        if path == "/check_auth":
            if self._is_authenticated():
                self._send_json(200, {"ok": True})
            else:
                self.send_response(401)
                origin = self.headers.get("Origin") or "*"
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Access-Control-Allow-Credentials", "true")
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", "0")
                self.end_headers()
            return
        if path == "/csv_file":
            qs = parse_qs(parsed.query)
            filename = (qs.get("file") or [""])[0].strip()
            if not filename:
                self._send_json(400, {"error": "Missing file parameter"})
                return
            if not all(c.isalnum() or c in "_.-" for c in filename) or ".." in filename:
                self._send_json(400, {"error": "Invalid filename"})
                return
            csv_dir = Path(os.getenv("PARCEL_CSV_DIR", os.getenv("OUTPUT_DIR", str(_get_csv_dir())))).resolve()
            file_path = (csv_dir / filename).resolve()
            if file_path.parent != csv_dir:
                self._send_json(400, {"error": "Invalid path"})
                return
            if not file_path.exists():
                self._send_json(404, {"error": "File not found"})
                return
            try:
                body = file_path.read_bytes()
            except OSError as e:
                self._send_json(500, {"error": str(e)})
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path not in {"/run", "/csv", "/ndvi_value", "/ndmi", "/ndmi_csv", "/ndmi_value", "/ndre", "/ndre_csv", "/ndre_zones", "/ndre_value", "/value_at_point"}:
            self._send_json(404, {"error": "Not found"})
            return

        qs = parse_qs(parsed.query)
        parcel_id = (qs.get("parcel") or [""])[0].strip()

        # value_at_point: lat, lon, date, index – ne zahteva parcel
        if path == "/value_at_point":
            lat_s = (qs.get("lat") or [""])[0].strip()
            lon_s = (qs.get("lon") or [""])[0].strip()
            date_s = (qs.get("date") or [""])[0].strip()
            index = (qs.get("index") or ["NDVI"])[0].strip().upper() or "NDVI"
            if not lat_s or not lon_s or not date_s:
                self._send_json(400, {"error": "Missing lat, lon or date"})
                return
            env = os.environ.copy()
            env["LAT"] = lat_s
            env["LON"] = lon_s
            env["DATE"] = date_s
            env["INDEX"] = index
            if "layer" in qs:
                env["PARCEL_LAYER"] = (qs.get("layer") or [""])[0].strip()
            try:
                result = subprocess.run(
                    [sys.executable, str(SCRIPT_DIR / "get_value_at_point.py")],
                    cwd=str(SCRIPT_DIR),
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
            except subprocess.TimeoutExpired:
                self._send_json(504, {"error": "Timeout", "value": None})
                return
            except Exception as exc:
                self._send_json(500, {"error": str(exc), "value": None})
                return
            value = None
            for line in (result.stdout or "").splitlines():
                if line.startswith("VALUE="):
                    rest = line[6:].strip()
                    if rest:
                        try:
                            value = float(rest)
                        except ValueError:
                            pass
                    break
            self._send_json(200, {"value": value, "ok": True})
            return

        if not parcel_id:
            self._send_json(400, {"error": "Missing parcel"})
            return

        env = os.environ.copy()
        env["PARCEL_ID"] = parcel_id
        if "days" in qs:
            env["PARCEL_DAYS_BACK"] = (qs.get("days") or [""])[0].strip()
        if "cloud" in qs:
            env["PARCEL_MAX_CLOUD"] = (qs.get("cloud") or [""])[0].strip()
        if "layer" in qs:
            env["PARCEL_LAYER"] = (qs.get("layer") or [""])[0].strip()
        if "kat_opstina" in qs:
            env["PARCEL_KAT_OPSTINA"] = (qs.get("kat_opstina") or [""])[0].strip()
        if "date" in qs:
            env["PARCEL_DATE"] = (qs.get("date") or [""])[0].strip()
        if "criterion" in qs:
            env["PARCEL_CRITERION"] = (qs.get("criterion") or [""])[0].strip()

        # ── CSV cache: ako fajl postoji i mlađi je od _CSV_CACHE_SEC → servira odmah ──
        # VAZNO: stdout MORA da sadrzi LATEST_DATE= inace frontend nece proslediti
        # datum value rasterima i dobicemo 120-dnevni fallback sa pogresnim vrednostima!
        if path in _CSV_ENDPOINTS:
            kat_opstina_val = (env.get("PARCEL_KAT_OPSTINA") or "").strip() or None
            suffix_now = _get_parcel_layer_suffix(parcel_id, kat_opstina_val)
            csv_dir_now = Path(os.getenv("PARCEL_CSV_DIR", os.getenv("OUTPUT_DIR", str(_get_csv_dir()))))
            cached_csv = _csv_path_for_endpoint(path, suffix_now, csv_dir_now)
            if cached_csv and cached_csv.exists():
                age = time.time() - cached_csv.stat().st_mtime
                if age < _CSV_CACHE_SEC:
                    try:
                        csv_text = cached_csv.read_text(encoding="utf-8")
                        stdout_lines = [f"[CACHE] Served {cached_csv.name} ({int(age)}s old)"]
                        import csv as csv_mod, io
                        reader = csv_mod.DictReader(io.StringIO(csv_text))
                        rows = list(reader)
                        if rows:
                            dates = [r.get("C0/date", "") for r in rows if r.get("C0/date")]
                            if dates:
                                latest = max(dates)[:10]
                                stdout_lines.append(f"LATEST_DATE={latest}")
                            last = rows[-1] if dates else None
                            if last:
                                sc = last.get("C0/sampleCount", "")
                                ndc = last.get("C0/noDataCount", "")
                                if sc:
                                    total = int(float(sc)) + int(float(ndc or 0))
                                    valid = int(float(sc))
                                    pct = round(valid / total * 100, 1) if total else 0
                                    stdout_lines.append(f"LATEST_VALID_PIXELS={valid}")
                                    stdout_lines.append(f"LATEST_TOTAL_PIXELS={total}")
                                    stdout_lines.append(f"LATEST_VALID_PCT={pct}")
                                cloud = last.get("C0/cloudCoveragePercent", "")
                                if cloud:
                                    stdout_lines.append(f"LATEST_CLOUD_PCT={cloud}")
                        self._send_json(200, {
                            "ok": True,
                            "parcel": parcel_id,
                            "cached": True,
                            "age_sec": int(age),
                            "stdout": "\n".join(stdout_lines),
                            "stderr": "",
                            "csv": csv_text,
                        })
                        return
                    except OSError:
                        pass

        try:
            if path == "/run":
                script_name = "download_ndvi_parcel.py"
            elif path == "/ndvi_value":
                script_name = "download_ndvi_value_parcel.py"
            elif path == "/csv":
                script_name = "download_ndvi_parcel_csv.py"
            elif path == "/ndmi":
                script_name = "download_ndmi_parcel.py"
            elif path == "/ndre":
                script_name = "download_ndre_parcel.py"
            elif path == "/ndre_csv":
                script_name = "download_ndre_parcel_csv.py"
            elif path == "/ndmi_csv":
                script_name = "download_ndmi_parcel_csv.py"
            elif path == "/ndre_zones":
                script_name = "download_ndre_zones_parcel.py"
            elif path == "/ndre_value":
                script_name = "download_ndre_value_parcel.py"
            elif path == "/ndmi_value":
                script_name = "download_ndmi_value_parcel.py"
            else:
                script_name = "download_ndmi_parcel_csv.py"
            result = subprocess.run(
                [sys.executable, str(SCRIPT_DIR / script_name)],
                cwd=str(SCRIPT_DIR),
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            self._send_json(
                500,
                {
                    "error": "NDVI generation failed",
                    "code": exc.returncode,
                    "stdout": (exc.stdout or "").strip(),
                    "stderr": (exc.stderr or "").strip(),
                },
            )
            return

        payload = {
            "ok": True,
            "parcel": parcel_id,
            "stdout": (result.stdout or "").strip(),
            "stderr": (result.stderr or "").strip(),
        }
        kat_opstina = (env.get("PARCEL_KAT_OPSTINA") or "").strip() or None
        suffix = _get_parcel_layer_suffix(parcel_id, kat_opstina)
        csv_dir = Path(os.getenv("PARCEL_CSV_DIR", os.getenv("OUTPUT_DIR", str(_get_csv_dir()))))
        if path == "/csv":
            csv_path = csv_dir / f"parcela_{suffix}_NDVI.csv"
        elif path == "/ndmi_csv":
            csv_path = csv_dir / f"parcela_{suffix}_NDMI.csv"
        elif path == "/ndre_csv":
            csv_path = csv_dir / f"parcela_{suffix}_NDRE.csv"
        else:
            csv_path = None
        if csv_path and csv_path.exists():
            try:
                payload["csv"] = csv_path.read_text(encoding="utf-8")
            except OSError:
                pass
        self._send_json(200, payload)


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Svaki zahtev se obrađuje u sopstvenom threadu – nema blokiranja."""
    daemon_threads = True


def main() -> None:
    server = ThreadedHTTPServer(("0.0.0.0", PORT), ParcelHandler)
    print(f"[INFO] Parcel server running on http://localhost:{PORT}")
    print("[INFO] Endpoints: /run /csv /csv_file /ndvi_value /ndmi /ndmi_csv /ndmi_value /ndre /ndre_csv /ndre_zones /ndre_value /value_at_point")
    server.serve_forever()


if __name__ == "__main__":
    main()
