#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
White-box agent za proveru koda i rezultata sa Kopernikusa.

Proverava:
1. Da li su API URL-ovi ispravni
2. Da li su evalscript-ovi ispravni (NDVI, NDMI, NDRE)
3. Da li su parametri ispravni
4. Da li su podaci ispravni (ako postoje)
5. Da li su endpoint-ovi u parcel_server.py ispravni
6. Da li su pozivi u leaflet_demo.html ispravni
"""

import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Postavi UTF-8 encoding za Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


class KopernikusVerifier:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.ndvi_auto_dir = base_dir / "ndvi_auto"
        self.web_dir = base_dir / "web"
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.info: List[str] = []

    def log_error(self, msg: str):
        self.errors.append(msg)
        print(f"[ERROR] {msg}")

    def log_warning(self, msg: str):
        self.warnings.append(msg)
        print(f"[WARNING] {msg}")

    def log_info(self, msg: str):
        self.info.append(msg)
        print(f"[INFO] {msg}")

    def verify_api_urls(self) -> bool:
        """Proverava da li su API URL-ovi ispravni."""
        self.log_info("Proveravam API URL-ove...")
        ok = True

        # Očekivani URL-ovi
        expected_urls = {
            "TOKEN_URL": "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token",
            "PROCESS_URL": "https://sh.dataspace.copernicus.eu/api/v1/process",
            "STATS_URL": "https://sh.dataspace.copernicus.eu/api/v1/statistics",
        }

        # Proveri download_and_publish.py
        download_publish = self.ndvi_auto_dir / "download_and_publish.py"
        if download_publish.exists():
            content = download_publish.read_text(encoding="utf-8")
            if expected_urls["TOKEN_URL"] not in content:
                self.log_error(f"TOKEN_URL nije pronađen u download_and_publish.py")
                ok = False
            else:
                self.log_info(f"[OK] TOKEN_URL je ispravan")

            if expected_urls["PROCESS_URL"] not in content:
                self.log_error(f"PROCESS_URL nije pronađen u download_and_publish.py")
                ok = False
            else:
                self.log_info(f"[OK] PROCESS_URL je ispravan")
        else:
            self.log_error(f"download_and_publish.py ne postoji")
            ok = False

        # Proveri CSV skripte
        csv_scripts = [
            "download_ndvi_parcel_csv.py",
            "download_ndmi_parcel_csv.py",
            "download_ndre_parcel_csv.py",
        ]
        for script_name in csv_scripts:
            script_path = self.ndvi_auto_dir / script_name
            if script_path.exists():
                content = script_path.read_text(encoding="utf-8")
                if expected_urls["STATS_URL"] not in content:
                    self.log_error(f"STATS_URL nije pronađen u {script_name}")
                    ok = False
                else:
                    self.log_info(f"[OK] STATS_URL je ispravan u {script_name}")
            else:
                self.log_warning(f"{script_name} ne postoji")

        return ok

    def verify_evalscript_ndvi(self) -> bool:
        """Proverava da li je NDVI evalscript ispravan."""
        self.log_info("Proveravam NDVI evalscript...")
        ok = True

        # Proveri download_and_publish.py
        download_publish = self.ndvi_auto_dir / "download_and_publish.py"
        if download_publish.exists():
            content = download_publish.read_text(encoding="utf-8")
            if "build_evalscript_ndvi" in content:
                # Proveri da li koristi B04 i B08
                if "B04" in content and "B08" in content:
                    # Proveri formulu NDVI
                    if "(sample.B08 - sample.B04) / (sample.B08 + sample.B04)" in content:
                        self.log_info("✓ NDVI evalscript koristi ispravnu formulu (B08-B04)/(B08+B04)")
                    else:
                        self.log_error("NDVI evalscript ne koristi ispravnu formulu")
                        ok = False
                else:
                    self.log_error("NDVI evalscript ne koristi B04 i B08 bandove")
                    ok = False
            else:
                self.log_error("build_evalscript_ndvi funkcija nije pronađena")
                ok = False

        # Proveri CSV skriptu
        csv_script = self.ndvi_auto_dir / "download_ndvi_parcel_csv.py"
        if csv_script.exists():
            content = csv_script.read_text(encoding="utf-8")
            if "build_evalscript_ndvi_stats" in content:
                if "(sample.B08 - sample.B04) / (sample.B08 + sample.B04)" in content:
                    self.log_info("[OK] NDVI stats evalscript koristi ispravnu formulu")
                else:
                    self.log_error("NDVI stats evalscript ne koristi ispravnu formulu")
                    ok = False
            else:
                self.log_warning("build_evalscript_ndvi_stats nije pronađen u CSV skripti")

        return ok

    def verify_evalscript_ndmi(self) -> bool:
        """Proverava da li je NDMI evalscript ispravan."""
        self.log_info("Proveravam NDMI evalscript...")
        ok = True

        # Proveri download_and_publish.py
        download_publish = self.ndvi_auto_dir / "download_and_publish.py"
        if download_publish.exists():
            content = download_publish.read_text(encoding="utf-8")
            if "build_evalscript_ndmi" in content:
                # Proveri da li koristi B08 i B11
                if "B08" in content and "B11" in content:
                    # Proveri formulu NDMI
                    if "(sample.B08 - sample.B11) / (sample.B08 + sample.B11)" in content:
                        self.log_info("[OK] NDMI evalscript koristi ispravnu formulu (B08-B11)/(B08+B11)")
                    else:
                        self.log_error("NDMI evalscript ne koristi ispravnu formulu")
                        ok = False
                else:
                    self.log_error("NDMI evalscript ne koristi B08 i B11 bandove")
                    ok = False
            else:
                self.log_error("build_evalscript_ndmi funkcija nije pronađena")
                ok = False

        # Proveri CSV skriptu
        csv_script = self.ndvi_auto_dir / "download_ndmi_parcel_csv.py"
        if csv_script.exists():
            content = csv_script.read_text(encoding="utf-8")
            if "build_evalscript_ndmi_stats" in content:
                if "(sample.B08 - sample.B11) / (sample.B08 + sample.B11)" in content:
                    self.log_info("[OK] NDMI stats evalscript koristi ispravnu formulu")
                else:
                    self.log_error("NDMI stats evalscript ne koristi ispravnu formulu")
                    ok = False
            else:
                self.log_warning("build_evalscript_ndmi_stats nije pronađen u CSV skripti")

        return ok

    def verify_evalscript_ndre(self) -> bool:
        """Proverava da li je NDRE evalscript ispravan."""
        self.log_info("Proveravam NDRE evalscript...")
        ok = True

        # Proveri download_and_publish.py
        download_publish = self.ndvi_auto_dir / "download_and_publish.py"
        if download_publish.exists():
            content = download_publish.read_text(encoding="utf-8")
            if "build_evalscript_ndre" in content:
                # Proveri da li koristi B05 i B08
                if "B05" in content and "B08" in content:
                    # Proveri formulu NDRE
                    if "(sample.B08 - sample.B05) / (sample.B08 + sample.B05)" in content:
                        self.log_info("[OK] NDRE evalscript koristi ispravnu formulu (B08-B05)/(B08+B05)")
                    else:
                        self.log_error("NDRE evalscript ne koristi ispravnu formulu")
                        ok = False
                else:
                    self.log_error("NDRE evalscript ne koristi B05 i B08 bandove")
                    ok = False
            else:
                self.log_warning("build_evalscript_ndre funkcija nije pronađena u download_and_publish.py")

        # Proveri CSV skriptu
        csv_script = self.ndvi_auto_dir / "download_ndre_parcel_csv.py"
        if csv_script.exists():
            content = csv_script.read_text(encoding="utf-8")
            if "build_evalscript_ndre_stats" in content:
                if "(sample.B08 - sample.B05) / (sample.B08 + sample.B05)" in content:
                    self.log_info("[OK] NDRE stats evalscript koristi ispravnu formulu")
                else:
                    self.log_error("NDRE stats evalscript ne koristi ispravnu formulu")
                    ok = False
            else:
                self.log_warning("build_evalscript_ndre_stats nije pronađen u CSV skripti")

        return ok

    def verify_parcel_server_endpoints(self) -> bool:
        """Proverava da li su endpoint-ovi u parcel_server.py ispravni."""
        self.log_info("Proveravam parcel_server.py endpoint-ove...")
        ok = True

        parcel_server = self.ndvi_auto_dir / "parcel_server.py"
        if not parcel_server.exists():
            self.log_error("parcel_server.py ne postoji")
            return False

        content = parcel_server.read_text(encoding="utf-8")
        expected_endpoints = ["/run", "/csv", "/ndmi", "/ndmi_csv", "/ndre", "/ndre_csv"]
        expected_scripts = [
            "download_ndvi_parcel.py",
            "download_ndvi_parcel_csv.py",
            "download_ndmi_parcel.py",
            "download_ndmi_parcel_csv.py",
            "download_ndre_parcel.py",
            "download_ndre_parcel_csv.py",
        ]

        for endpoint in expected_endpoints:
            if endpoint not in content:
                self.log_error(f"Endpoint {endpoint} nije pronađen u parcel_server.py")
                ok = False
            else:
                self.log_info(f"[OK] Endpoint {endpoint} je pronađen")

        for script in expected_scripts:
            if script not in content:
                self.log_error(f"Skripta {script} nije mapirana u parcel_server.py")
                ok = False
            else:
                self.log_info(f"[OK] Skripta {script} je mapirana")

        # Proveri da li port je 5010
        if "5010" in content or "PARCEL_SERVER_PORT" in content:
            self.log_info("[OK] Port konfiguracija je pronađena")
        else:
            self.log_warning("Port 5010 nije eksplicitno naveden (može biti OK ako je u env)")

        return ok

    def verify_leaflet_demo_calls(self) -> bool:
        """Proverava da li su pozivi u leaflet_demo.html ispravni."""
        self.log_info("Proveravam leaflet_demo.html pozive...")
        ok = True

        leaflet_demo = self.base_dir / "leaflet_demo.html"
        if not leaflet_demo.exists():
            self.log_error("leaflet_demo.html ne postoji")
            return False

        content = leaflet_demo.read_text(encoding="utf-8")
        expected_calls = [
            "/run?parcel=",
            "/csv?parcel=",
            "/ndmi?parcel=",
            "/ndmi_csv?parcel=",
            "/ndre?parcel=",
            "/ndre_csv?parcel=",
        ]

        for call in expected_calls:
            if call not in content:
                self.log_error(f"Poziv {call} nije pronađen u leaflet_demo.html")
                ok = False
            else:
                self.log_info(f"[OK] Poziv {call} je pronađen")

        # Proveri da li koristi localhost:5010
        if "localhost:5010" in content or "parcelServerUrl" in content:
            self.log_info("[OK] parcelServerUrl je konfigurisan")
        else:
            self.log_warning("parcelServerUrl možda nije ispravno konfigurisan")

        # Proveri da li poziva requestParcelNdvi, requestParcelNdviCsv, itd.
        expected_functions = [
            "requestParcelNdvi",
            "requestParcelNdviCsv",
            "requestParcelNdmi",
            "requestParcelNdmiCsv",
            "requestParcelNdre",
            "requestParcelNdreCsv",
        ]
        for func in expected_functions:
            if func not in content:
                self.log_error(f"Funkcija {func} nije pronađena u leaflet_demo.html")
                ok = False
            else:
                self.log_info(f"[OK] Funkcija {func} je pronađena")

        return ok

    def verify_api_payload_structure(self) -> bool:
        """Proverava da li su API payload strukture ispravne."""
        self.log_info("Proveravam API payload strukture...")
        ok = True

        csv_scripts = [
            ("download_ndvi_parcel_csv.py", "NDVI"),
            ("download_ndmi_parcel_csv.py", "NDMI"),
            ("download_ndre_parcel_csv.py", "NDRE"),
        ]

        required_fields = [
            "input",
            "aggregation",
            "calculations",
        ]

        for script_name, index_name in csv_scripts:
            script_path = self.ndvi_auto_dir / script_name
            if script_path.exists():
                content = script_path.read_text(encoding="utf-8")
                # Proveri da li payload sadrži sve potrebne polja
                for field in required_fields:
                    if field not in content:
                        self.log_error(f"{script_name} ne sadrži polje '{field}' u payload-u")
                        ok = False
                    else:
                        self.log_info(f"[OK] {script_name} sadrži polje '{field}'")

                # Proveri da li koristi sentinel-2-l2a
                if "sentinel-2-l2a" not in content:
                    self.log_error(f"{script_name} ne koristi sentinel-2-l2a")
                    ok = False
                else:
                    self.log_info(f"[OK] {script_name} koristi sentinel-2-l2a")

                # Proveri da li koristi maxCloudCoverage
                if "maxCloudCoverage" not in content:
                    self.log_warning(f"{script_name} možda ne koristi maxCloudCoverage")
                else:
                    self.log_info(f"[OK] {script_name} koristi maxCloudCoverage")

        return ok

    def verify_csv_output_structure(self) -> bool:
        """Proverava da li su CSV output strukture ispravne."""
        self.log_info("Proveravam CSV output strukture...")
        ok = True

        csv_scripts = [
            ("download_ndvi_parcel_csv.py", "NDVI"),
            ("download_ndmi_parcel_csv.py", "NDMI"),
            ("download_ndre_parcel_csv.py", "NDRE"),
        ]

        required_csv_columns = [
            "C0/date",
            "C0/min",
            "C0/max",
            "C0/mean",
            "C0/stDev",
            "C0/sampleCount",
            "C0/noDataCount",
            "C0/median",
            "C0/p10",
            "C0/p90",
            "C0/cloudCoveragePercent",
        ]

        for script_name, index_name in csv_scripts:
            script_path = self.ndvi_auto_dir / script_name
            if script_path.exists():
                content = script_path.read_text(encoding="utf-8")
                # Proveri da li CSV header sadrži sve potrebne kolone
                for col in required_csv_columns:
                    if col not in content:
                        self.log_error(f"{script_name} ne sadrži CSV kolonu '{col}'")
                        ok = False
                    else:
                        self.log_info(f"[OK] {script_name} sadrži CSV kolonu '{col}'")

        return ok

    def verify_geometry_fetch(self) -> bool:
        """Proverava da li se geometrija pravilno dohvata iz GeoServera."""
        self.log_info("Proveravam dohvatanje geometrije iz GeoServera...")
        ok = True

        csv_scripts = [
            "download_ndvi_parcel_csv.py",
            "download_ndmi_parcel_csv.py",
            "download_ndre_parcel_csv.py",
        ]

        for script_name in csv_scripts:
            script_path = self.ndvi_auto_dir / script_name
            if script_path.exists():
                content = script_path.read_text(encoding="utf-8")
                # Proveri da li koristi fetch_parcel_geometry
                if "fetch_parcel_geometry" not in content:
                    self.log_error(f"{script_name} ne koristi fetch_parcel_geometry")
                    ok = False
                else:
                    self.log_info(f"[OK] {script_name} koristi fetch_parcel_geometry")

                # Proveri da li koristi WFS za dohvatanje geometrije
                # Može biti direktno u fajlu ili importovano iz download_ndvi_parcel_csv.py
                if "WFS" in content and "GetFeature" in content:
                    self.log_info(f"[OK] {script_name} koristi WFS GetFeature direktno")
                elif "from download_ndvi_parcel_csv import" in content and "fetch_parcel_geometry" in content:
                    # Proveri da li download_ndvi_parcel_csv.py koristi WFS
                    ndvi_csv = self.ndvi_auto_dir / "download_ndvi_parcel_csv.py"
                    if ndvi_csv.exists():
                        ndvi_content = ndvi_csv.read_text(encoding="utf-8")
                        if "WFS" in ndvi_content and "GetFeature" in ndvi_content:
                            self.log_info(f"[OK] {script_name} koristi fetch_parcel_geometry koja koristi WFS GetFeature (importovano iz download_ndvi_parcel_csv.py)")
                        else:
                            self.log_error(f"{script_name} importuje fetch_parcel_geometry ali ta funkcija ne koristi WFS GetFeature")
                            ok = False
                    else:
                        self.log_warning(f"{script_name} importuje fetch_parcel_geometry ali download_ndvi_parcel_csv.py ne postoji")
                else:
                    self.log_error(f"{script_name} ne koristi WFS GetFeature za dohvatanje geometrije")
                    ok = False

        return ok

    def verify_token_authentication(self) -> bool:
        """Proverava da li se token pravilno dobija i koristi."""
        self.log_info("Proveravam autentifikaciju...")
        ok = True

        # Proveri download_and_publish.py
        download_publish = self.ndvi_auto_dir / "download_and_publish.py"
        if download_publish.exists():
            content = download_publish.read_text(encoding="utf-8")
            if "get_token" not in content:
                self.log_error("get_token funkcija nije pronađena")
                ok = False
            else:
                self.log_info("[OK] get_token funkcija je pronađena")

            if "client_credentials" not in content:
                self.log_error("client_credentials grant type nije pronađen")
                ok = False
            else:
                self.log_info("[OK] client_credentials grant type je pronađen")

            if "Bearer" not in content:
                self.log_error("Bearer token autentifikacija nije pronađena")
                ok = False
            else:
                self.log_info("[OK] Bearer token autentifikacija je pronađena")

        # Proveri CSV skripte
        csv_scripts = [
            "download_ndvi_parcel_csv.py",
            "download_ndmi_parcel_csv.py",
            "download_ndre_parcel_csv.py",
        ]
        for script_name in csv_scripts:
            script_path = self.ndvi_auto_dir / script_name
            if script_path.exists():
                content = script_path.read_text(encoding="utf-8")
                if "get_token" not in content:
                    self.log_error(f"{script_name} ne koristi get_token")
                    ok = False
                else:
                    self.log_info(f"[OK] {script_name} koristi get_token")

        return ok

    def verify_environment_variables(self) -> bool:
        """Proverava da li se koriste potrebne environment varijable."""
        self.log_info("Proveravam environment varijable...")
        ok = True

        required_vars = [
            "CDSE_CLIENT_ID",
            "CDSE_CLIENT_SECRET",
            "GEOSERVER_URL",
            "GEOSERVER_WORKSPACE",
        ]

        # Proveri download_and_publish.py
        download_publish = self.ndvi_auto_dir / "download_and_publish.py"
        if download_publish.exists():
            content = download_publish.read_text(encoding="utf-8")
            for var in required_vars:
                if var not in content:
                    self.log_warning(f"{var} možda nije korišćen u download_and_publish.py")
                else:
                    self.log_info(f"[OK] {var} je korišćen")

        # Proveri CSV skripte
        csv_scripts = [
            "download_ndvi_parcel_csv.py",
            "download_ndmi_parcel_csv.py",
            "download_ndre_parcel_csv.py",
        ]
        for script_name in csv_scripts:
            script_path = self.ndvi_auto_dir / script_name
            if script_path.exists():
                content = script_path.read_text(encoding="utf-8")
                for var in required_vars:
                    if var not in content:
                        self.log_warning(f"{var} možda nije korišćen u {script_name}")
                    else:
                        self.log_info(f"[OK] {var} je korišćen u {script_name}")

        return ok

    def verify_csv_files(self, parcel_id: Optional[str] = None) -> bool:
        """Proverava validnost CSV fajlova."""
        self.log_info("Proveravam CSV fajlove...")
        ok = True

        # Traži CSV fajlove u web/data i satelite folderima
        search_dirs = [
            self.base_dir / "web" / "data",
            self.base_dir / "web" / "satelite",
            self.base_dir / "satelite",
        ]

        csv_files = []
        for search_dir in search_dirs:
            if search_dir.exists():
                csv_files.extend(list(search_dir.glob("*.csv")))

        if not csv_files:
            self.log_warning("Nema pronađenih CSV fajlova za validaciju")
            return True  # Nije greška ako nema fajlova

        required_columns = [
            "C0/date",
            "C0/min",
            "C0/max",
            "C0/mean",
            "C0/stDev",
            "C0/sampleCount",
            "C0/noDataCount",
            "C0/median",
            "C0/p10",
            "C0/p90",
            "C0/cloudCoveragePercent",
        ]

        validated_count = 0
        for csv_file in csv_files[:10]:  # Ograniči na prvih 10 da ne bude previše
            try:
                content = csv_file.read_text(encoding="utf-8")
                lines = content.strip().split("\n")
                if len(lines) < 2:
                    self.log_warning(f"{csv_file.name} je prazan ili ima samo header")
                    continue

                headers = [h.strip() for h in lines[0].split(",")]
                missing_columns = [col for col in required_columns if col not in headers]
                if missing_columns:
                    self.log_error(f"{csv_file.name} nedostaju kolone: {', '.join(missing_columns)}")
                    ok = False
                    continue

                # Proveri da li su datumi validni
                date_col_idx = headers.index("C0/date")
                valid_rows = 0
                invalid_dates = 0
                invalid_values = 0

                for line_num, line in enumerate(lines[1:], start=2):
                    if not line.strip():
                        continue
                    cols = [c.strip() for c in line.split(",")]
                    if len(cols) <= date_col_idx:
                        continue

                    # Proveri datum
                    date_str = cols[date_col_idx]
                    try:
                        from datetime import datetime
                        datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                    except (ValueError, AttributeError):
                        invalid_dates += 1
                        if invalid_dates <= 3:  # Prikaži samo prve 3 greške
                            self.log_warning(f"{csv_file.name} linija {line_num}: neispravan datum '{date_str}'")
                        continue

                    # Proveri numeričke vrednosti
                    mean_idx = headers.index("C0/mean") if "C0/mean" in headers else -1
                    if mean_idx >= 0 and len(cols) > mean_idx:
                        mean_val = cols[mean_idx]
                        if mean_val:
                            try:
                                val = float(mean_val)
                                # Proveri opseg za NDVI/NDMI/NDRE (obično -1 do 1)
                                if "NDVI" in csv_file.name or "NDMI" in csv_file.name or "NDRE" in csv_file.name:
                                    if val < -2 or val > 2:
                                        invalid_values += 1
                                        if invalid_values <= 3:
                                            self.log_warning(f"{csv_file.name} linija {line_num}: sumnjiva vrednost mean={val}")
                            except ValueError:
                                invalid_values += 1
                                if invalid_values <= 3:
                                    self.log_warning(f"{csv_file.name} linija {line_num}: neispravna numerička vrednost '{mean_val}'")

                    valid_rows += 1

                if valid_rows > 0:
                    validated_count += 1
                    self.log_info(f"[OK] {csv_file.name}: {valid_rows} validnih redova")
                    if invalid_dates > 0:
                        self.log_warning(f"{csv_file.name}: {invalid_dates} neispravnih datuma")
                    if invalid_values > 0:
                        self.log_warning(f"{csv_file.name}: {invalid_values} neispravnih vrednosti")
                else:
                    self.log_error(f"{csv_file.name} nema validnih redova")
                    ok = False

            except Exception as e:
                self.log_error(f"Greška pri čitanju {csv_file.name}: {e}")
                ok = False

        if validated_count > 0:
            self.log_info(f"Validirano {validated_count} CSV fajlova")
        else:
            self.log_warning("Nijedan CSV fajl nije validiran")

        return ok

    def run_all_checks(self) -> Tuple[bool, Dict[str, int]]:
        """Pokreće sve provere i vraća rezultat."""
        print("=" * 80)
        print("KOPERNIKUS VERIFICATION AGENT")
        print("=" * 80)
        print()

        checks = [
            ("API URL-ovi", self.verify_api_urls),
            ("NDVI evalscript", self.verify_evalscript_ndvi),
            ("NDMI evalscript", self.verify_evalscript_ndmi),
            ("NDRE evalscript", self.verify_evalscript_ndre),
            ("Parcel server endpoint-ovi", self.verify_parcel_server_endpoints),
            ("Leaflet demo pozivi", self.verify_leaflet_demo_calls),
            ("API payload strukture", self.verify_api_payload_structure),
            ("CSV output strukture", self.verify_csv_output_structure),
            ("Dohvatanje geometrije", self.verify_geometry_fetch),
            ("Autentifikacija", self.verify_token_authentication),
            ("Environment varijable", self.verify_environment_variables),
            ("CSV fajlovi validacija", self.verify_csv_files),
        ]

        results = {}
        all_ok = True

        for check_name, check_func in checks:
            print(f"\n{'=' * 80}")
            print(f"Provera: {check_name}")
            print(f"{'=' * 80}")
            try:
                result = check_func()
                results[check_name] = 1 if result else 0
                if not result:
                    all_ok = False
            except Exception as e:
                self.log_error(f"Greška pri proveri {check_name}: {e}")
                results[check_name] = 0
                all_ok = False

        return all_ok, results

    def print_summary(self):
        """Ispisuje rezime provera."""
        print("\n" + "=" * 80)
        print("REZIME PROVERE")
        print("=" * 80)
        print(f"\nUkupno grešaka: {len(self.errors)}")
        print(f"Ukupno upozorenja: {len(self.warnings)}")
        print(f"Ukupno informacija: {len(self.info)}")

        if self.errors:
            print("\nGREŠKE:")
            for i, error in enumerate(self.errors, 1):
                print(f"  {i}. {error}")

        if self.warnings:
            print("\nUPOZORENJA:")
            for i, warning in enumerate(self.warnings, 1):
                print(f"  {i}. {warning}")

        print("\n" + "=" * 80)


def main():
    base_dir = Path(__file__).resolve().parent.parent
    verifier = KopernikusVerifier(base_dir)
    all_ok, results = verifier.run_all_checks()
    verifier.print_summary()

    print("\n" + "=" * 80)
    print("REZULTATI PO PROVERAMA:")
    print("=" * 80)
    for check_name, result in results.items():
        status = "[OK]" if result else "[FAIL]"
        print(f"  {status} - {check_name}")

    print("\n" + "=" * 80)
    if all_ok:
        print("SVE PROVERE SU PROŠLE USPEŠNO!")
    else:
        print("NEKE PROVERE NISU PROŠLE - PROVERITE GREŠKE IZNAD")
    print("=" * 80)

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
