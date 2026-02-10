import json
import os
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


SCRIPT_DIR = Path(__file__).resolve().parent
PORT = int(os.getenv("PARCEL_SERVER_PORT", "5010"))


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

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path not in {"/run", "/csv", "/ndmi", "/ndmi_csv", "/ndre", "/ndre_csv"}:
            self._send_json(404, {"error": "Not found"})
            return

        qs = parse_qs(parsed.query)
        parcel_id = (qs.get("parcel") or [""])[0].strip()
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

        try:
            if parsed.path == "/run":
                script_name = "download_ndvi_parcel.py"
            elif parsed.path == "/csv":
                script_name = "download_ndvi_parcel_csv.py"
            elif parsed.path == "/ndmi":
                script_name = "download_ndmi_parcel.py"
            elif parsed.path == "/ndre":
                script_name = "download_ndre_parcel.py"
            elif parsed.path == "/ndre_csv":
                script_name = "download_ndre_parcel_csv.py"
            elif parsed.path == "/ndmi_csv":
                script_name = "download_ndmi_parcel_csv.py"
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

        self._send_json(
            200,
            {
                "ok": True,
                "parcel": parcel_id,
                "stdout": (result.stdout or "").strip(),
                "stderr": (result.stderr or "").strip(),
            },
        )


def main() -> None:
    server = HTTPServer(("0.0.0.0", PORT), ParcelHandler)
    print(f"[INFO] Parcel server running on http://localhost:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
