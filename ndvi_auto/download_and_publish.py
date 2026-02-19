import base64
import datetime as dt
import json
import os
from pathlib import Path
import sys
import urllib.parse
import urllib.request


import io
import tempfile

TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
PROCESS_URL = "https://sh.dataspace.copernicus.eu/api/v1/process"


def load_env(env_path: Path) -> None:
    """Učitava .env; NE prepisuje promenljive koje su već postavljene (npr. od parcel servera)."""
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key in os.environ:
            continue  # Pozivatelj (parcel server itd.) već postavio – ne prepisuj
        value = value.strip().strip('"').strip("'")
        if value:
            os.environ[key] = value


def get_env(name: str, default=None, required: bool = False) -> str:
    value = os.getenv(name, default)
    if required and not value:
        print(f"[ERROR] Missing env var: {name}")
        sys.exit(1)
    return value


def get_parcel_layer_suffix(parcel_id: str, kat_opstina: str | None) -> str:
    """Vraća suffix za layer/store naziv: '1146' ili '1146_DUBOVAC' kad je KO setovan (Opština/KO/Parcela)."""
    safe = parcel_id.replace("/", "_").replace("\\", "_")
    if kat_opstina and kat_opstina.strip():
        ko = kat_opstina.strip().upper().replace(" ", "_").replace("/", "_").replace("'", "")[:50]
        safe = safe + "_" + ko
    return safe


def get_token(client_id: str, client_secret: str) -> str:
    data = urllib.parse.urlencode(
        {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        }
    ).encode("utf-8")
    req = urllib.request.Request(TOKEN_URL, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return payload["access_token"]


def read_geometry(aoi_path: Path) -> dict:
    geo = json.loads(aoi_path.read_text(encoding="utf-8"))
    if geo.get("type") == "FeatureCollection":
        return geo["features"][0]["geometry"]
    if geo.get("type") == "Feature":
        return geo["geometry"]
    return geo


def geometry_bounds(geometry: dict) -> tuple[float, float, float, float]:
    coords = geometry.get("coordinates", [])
    if geometry.get("type") == "Polygon":
        ring = coords[0]
    elif geometry.get("type") == "MultiPolygon":
        ring = coords[0][0]
    else:
        raise ValueError("Unsupported geometry type for bounds")

    lons = [pt[0] for pt in ring]
    lats = [pt[1] for pt in ring]
    return min(lons), min(lats), max(lons), max(lats)


def compute_output_size(
    geometry: dict, resolution_m: float, max_pixels: int
) -> tuple[int, int]:
    api_limit = 2500
    max_pixels = min(max_pixels, api_limit)
    min_lon, min_lat, max_lon, max_lat = geometry_bounds(geometry)
    center_lat = (min_lat + max_lat) / 2.0
    meters_per_deg_lat = 111320.0
    meters_per_deg_lon = 111320.0 * max(
        0.1, abs(__import__("math").cos(__import__("math").radians(center_lat)))
    )

    width_m = (max_lon - min_lon) * meters_per_deg_lon
    height_m = (max_lat - min_lat) * meters_per_deg_lat

    width_px = max(1, int(width_m / resolution_m))
    height_px = max(1, int(height_m / resolution_m))

    width_px = min(width_px, max_pixels)
    height_px = min(height_px, max_pixels)
    return width_px, height_px


def adaptive_min_bytes(width: int, height: int, bands: int = 3, sample_bytes: int = 1, floor: int = 500) -> int:
    """Izračunava minimalan očekivan broj bajtova GeoTIFF-a na osnovu dimenzija.

    Za male parcele (npr. 100x62 px) fiksni prag od 50000 je prevelik,
    jer pun nekompresovan raster može biti manji od toga.
    Vraća ~30% nekompresovane veličine kao prag, ali nikad manje od floor.
    """
    raw = width * height * bands * sample_bytes
    threshold = max(floor, int(raw * 0.3))
    return threshold


def mask_raster_to_parcel(tiff_bytes: bytes, parcel_geojson: dict, nodata=0) -> bytes:
    """Maskira piksele van granice parcele na nodata.

    Args:
        tiff_bytes: sirovi GeoTIFF bajti (sa bbox rastera)
        parcel_geojson: GeoJSON geometry dict parcele (EPSG:4326)
        nodata: vrednost za piksele van parcele (0 za RGB, -999 za FLOAT32)

    Returns:
        Maskirani GeoTIFF bajti
    """
    try:
        import numpy as np
        import rasterio
        from rasterio.mask import mask as rio_mask
        from shapely.geometry import shape
    except ImportError as e:
        print(f"[WARN] mask_raster_to_parcel: missing dependency ({e}), skipping mask")
        return tiff_bytes

    try:
        parcel_shape = shape(parcel_geojson)
        if parcel_shape.is_empty or not parcel_shape.is_valid:
            print("[WARN] Invalid parcel geometry, skipping mask")
            return tiff_bytes
    except Exception as e:
        print(f"[WARN] Cannot parse parcel geometry ({e}), skipping mask")
        return tiff_bytes

    tmp_in = None
    tmp_out = None
    try:
        tmp_in = tempfile.NamedTemporaryFile(suffix=".tif", delete=False)
        tmp_in.write(tiff_bytes)
        tmp_in.close()

        with rasterio.open(tmp_in.name) as src:
            raster_crs = src.crs

            geom_for_mask = parcel_geojson
            if raster_crs and str(raster_crs) != "EPSG:4326":
                from pyproj import Transformer
                from shapely.ops import transform as shp_transform
                transformer = Transformer.from_crs("EPSG:4326", raster_crs, always_xy=True)
                parcel_projected = shp_transform(transformer.transform, parcel_shape)
                geom_for_mask = parcel_projected.__geo_interface__

            out_image, out_transform = rio_mask(
                src,
                [geom_for_mask],
                crop=False,
                nodata=nodata,
                filled=True,
            )

            out_meta = src.meta.copy()
            out_meta.update({
                "nodata": nodata,
                "transform": out_transform,
            })

        tmp_out = tempfile.NamedTemporaryFile(suffix=".tif", delete=False)
        tmp_out.close()

        with rasterio.open(tmp_out.name, "w", **out_meta) as dst:
            dst.write(out_image)

        masked_bytes = Path(tmp_out.name).read_bytes()
        print(f"[INFO] Raster masked to parcel boundary ({len(tiff_bytes)} -> {len(masked_bytes)} bytes)")
        return masked_bytes

    except Exception as e:
        print(f"[WARN] mask_raster_to_parcel failed ({e}), returning original")
        return tiff_bytes
    finally:
        import os as _os
        if tmp_in:
            try: _os.unlink(tmp_in.name)
            except OSError: pass
        if tmp_out:
            try: _os.unlink(tmp_out.name)
            except OSError: pass


def build_evalscript_ndvi() -> str:
    return """//VERSION=3
function setup() {
  return {
    input: ["B04", "B08", "dataMask"],
    output: { bands: 3, sampleType: "UINT8" }
  };
}

function evaluatePixel(sample) {
  if (sample.dataMask === 0) {
    return [0, 0, 0];
  }
  let ndvi = (sample.B08 - sample.B04) / (sample.B08 + sample.B04);
  
  // Kontrast stretching - normalizacija na opseg 0-1 sa pojačanjem razlika
  // Pretpostavljamo da su vrednosti u opsegu -0.2 do 0.8 (tipično za parcele)
  let minVal = -0.2;
  let maxVal = 0.8;
  
  // Normalizacija na 0-1 opseg
  let normalized = (ndvi - minVal) / (maxVal - minVal);
  normalized = Math.max(0, Math.min(1, normalized));
  
  // Primena kontrast stretching funkcije (gamma korekcija + pojačanje)
  // Koristimo kvadratnu funkciju za pojačanje razlika u srednjem opsegu
  let stretched = Math.pow(normalized, 0.7); // Gamma < 1 pojačava tamnije vrednosti
  stretched = stretched * 1.2 - 0.1; // Dodatno pojačanje i pomeranje
  stretched = Math.max(0, Math.min(1, stretched));
  
  // Povećane razlike u zelenim nijansama sa više koraka za bolji kontrast
  let rgb = colorBlend(
    stretched,
    [0.0, 0.15, 0.3, 0.45, 0.6, 0.75, 0.9, 1.0],
    [
      [94, 79, 162],
      [50, 136, 189],
      [102, 194, 165],
      [140, 210, 130],  // Svetlija zelena
      [80, 190, 70],    // Srednja-svetlija zelena
      [40, 160, 40],    // Srednja zelena
      [20, 130, 20],    // Tamnija zelena
      [10, 100, 10]     // Tamna zelena
    ]
  );
  
  // Agresivno pojačanje kontrasta RGB kanala za maksimalne razlike
  let contrastBoost = 1.5;
  rgb[0] = Math.max(0, Math.min(255, (rgb[0] - 128) * contrastBoost + 128));
  rgb[1] = Math.max(0, Math.min(255, (rgb[1] - 128) * contrastBoost + 128));
  rgb[2] = Math.max(0, Math.min(255, (rgb[2] - 128) * contrastBoost + 128));
  
  return [rgb[0], rgb[1], rgb[2]];
}
"""


def build_evalscript_ndvi_value() -> str:
    """Generiše raster sa sirovim NDVI vrednostima (FLOAT32) za GetFeatureInfo.
    Bez SCL filtera — isto kao vizuelni evalscript, jer SCL na malim parcelama
    često pogrešno klasifikuje sve piksele kao oblak/senku."""
    return """//VERSION=3
function setup() {
  return {
    input: ["B04", "B08", "dataMask"],
    output: { bands: 1, sampleType: "FLOAT32" }
  };
}

function evaluatePixel(sample) {
  if (sample.dataMask === 0) {
    return [-999];
  }
  var sum = sample.B04 + sample.B08;
  if (sum <= 0 || !isFinite(sample.B04) || !isFinite(sample.B08)) {
    return [-999];
  }
  var ndvi = (sample.B08 - sample.B04) / sum;
  return isFinite(ndvi) ? [ndvi] : [-999];
}
"""


def build_evalscript_ndmi() -> str:
    return """//VERSION=3
function setup() {
  return {
    input: ["B08", "B11", "dataMask"],
    output: { bands: 3, sampleType: "UINT8" }
  };
}

function evaluatePixel(sample) {
  if (sample.dataMask === 0) {
    return [0, 0, 0];
  }
  let ndmi = (sample.B08 - sample.B11) / (sample.B08 + sample.B11);
  
  // Kontrast stretching - normalizacija na opseg 0-1
  let minVal = -0.3;
  let maxVal = 0.6;
  
  // Normalizacija na 0-1 opseg
  let normalized = (ndmi - minVal) / (maxVal - minVal);
  normalized = Math.max(0, Math.min(1, normalized));
  
  // Primena kontrast stretching
  let stretched = Math.pow(normalized, 0.7);
  stretched = stretched * 1.2 - 0.1;
  stretched = Math.max(0, Math.min(1, stretched));
  
  let rgb = colorBlend(
    stretched,
    [0.0, 0.15, 0.3, 0.45, 0.6, 0.75, 0.9, 1.0],
    [
      [8, 29, 88],
      [37, 52, 148],
      [34, 94, 168],
      [29, 145, 192],
      [65, 182, 196],
      [127, 205, 187],
      [199, 233, 180],
      [237, 248, 217]
    ]
  );
  
  // Agresivno pojačanje kontrasta RGB kanala
  let contrastBoost = 1.5;
  rgb[0] = Math.max(0, Math.min(255, (rgb[0] - 128) * contrastBoost + 128));
  rgb[1] = Math.max(0, Math.min(255, (rgb[1] - 128) * contrastBoost + 128));
  rgb[2] = Math.max(0, Math.min(255, (rgb[2] - 128) * contrastBoost + 128));
  
  return [rgb[0], rgb[1], rgb[2]];
}
"""


def build_evalscript_ndre() -> str:
    return """//VERSION=3
// Isto kao NDVI/NDMI - bez SCL filtera da bi raster bio vidljiv (SCL može davati crno)
function setup() {
  return {
    input: ["B05", "B08", "dataMask"],
    output: { bands: 3, sampleType: "UINT8" }
  };
}

function evaluatePixel(sample) {
  if (sample.dataMask === 0) {
    return [0, 0, 0];
  }
  let ndre = (sample.B08 - sample.B05) / (sample.B08 + sample.B05);
  
  // Kontrast stretching - normalizacija na opseg 0-1
  let minVal = -0.2;
  let maxVal = 0.7;
  
  // Normalizacija na 0-1 opseg
  let normalized = (ndre - minVal) / (maxVal - minVal);
  normalized = Math.max(0, Math.min(1, normalized));
  
  // Primena kontrast stretching
  let stretched = Math.pow(normalized, 0.7);
  stretched = stretched * 1.2 - 0.1;
  stretched = Math.max(0, Math.min(1, stretched));
  
  let rgb = colorBlend(
    stretched,
    [0.0, 0.15, 0.3, 0.45, 0.6, 0.75, 0.9, 1.0],
    [
      [94, 79, 162],
      [50, 136, 189],
      [102, 194, 165],
      [171, 221, 164],
      [230, 245, 152],
      [254, 224, 139],
      [253, 174, 97],
      [213, 62, 79]
    ]
  );
  
  // Agresivno pojačanje kontrasta RGB kanala
  let contrastBoost = 1.5;
  rgb[0] = Math.max(0, Math.min(255, (rgb[0] - 128) * contrastBoost + 128));
  rgb[1] = Math.max(0, Math.min(255, (rgb[1] - 128) * contrastBoost + 128));
  rgb[2] = Math.max(0, Math.min(255, (rgb[2] - 128) * contrastBoost + 128));
  
  return [rgb[0], rgb[1], rgb[2]];
}
"""


def build_evalscript_evi() -> str:
    return """//VERSION=3
function setup() {
  return {
    input: ["B02", "B04", "B08", "dataMask"],
    output: { bands: 3, sampleType: "UINT8" }
  };
}

function evaluatePixel(sample) {
  if (sample.dataMask === 0) {
    return [0, 0, 0];
  }
  let evi = 2.5 * (sample.B08 - sample.B04) / (sample.B08 + 6.0 * sample.B04 - 7.5 * sample.B02 + 1.0);
  let rgb = colorBlend(
    evi,
    [-1.0, -0.5, 0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
    [
      [94, 79, 162],
      [50, 136, 189],
      [102, 194, 165],
      [171, 221, 164],
      [230, 245, 152],
      [254, 224, 139],
      [253, 174, 97],
      [213, 62, 79]
    ]
  );
  return [rgb[0], rgb[1], rgb[2]];
}
"""


def build_evalscript_ndre_zones() -> str:
    """Ista struktura kao build_evalscript_ndre() - parcel NDRE radi bez SCL."""
    return """//VERSION=3
function setup() {
  return {
    input: ["B05", "B08", "dataMask"],
    output: { bands: 3, sampleType: "UINT8" }
  };
}

function evaluatePixel(sample) {
  if (sample.dataMask === 0) {
    return [0, 0, 0];
  }
  var sum = sample.B08 + sample.B05;
  if (sum <= 0 || !isFinite(sample.B08) || !isFinite(sample.B05)) {
    return [0, 0, 0];
  }
  let ndre = (sample.B08 - sample.B05) / sum;
  
  // NDRE zone za azotnu prihranu:
  // Niska vrednost NDRE → biljke imaju više azota (tamnija vegetacija)
  // Visoka vrednost NDRE → biljke imaju manje azota (svetlija vegetacija)
  // 
  // Zone za agronomsku primenu:
  // < 0.14: Crvena zona - biljke imaju VIŠE azota, može manje đubrenja
  // 0.14 - 0.19: Žuta zona - standardna količina azota
  // ≥ 0.19: Zelena zona - biljke imaju MANJE azota, može više đubrenja
  
  if (ndre < 0.14) {
    // CRVENA zona - više azota potrebno
    return [255, 0, 0];  // Čista crvena
  }
  if (ndre < 0.19) {
    // ŽUTA zona - standard
    return [255, 255, 0];  // Čista žuta
  }
  // ZELENA zona - može malo manje azota
  return [0, 255, 0];  // Čista zelena
}
"""


def build_evalscript_ndre_gradient() -> str:
    """Generiše raster sa zelenim gradijentom baziranim na NDRE vrednostima
    Koristi pun opseg zelenih nijansi (50-255) za maksimalnu vidljivost razlika
    Lako primenljivo na sve parcele - koristi adaptivne granice bazirane na tipičnim NDRE vrednostima
    Sistem koristi colorBlend sa više koraka za nežne prelaze između zelenih nijansi
    """
    return """//VERSION=3
// SCL: 0=no data, 1=saturated, 8=cloud medium, 9=cloud high
function setup() {
  return {
    input: ["B05", "B08", "SCL", "dataMask"],
    output: { bands: 3, sampleType: "UINT8" }
  };
}

function evaluatePixel(sample) {
  if (sample.dataMask === 0) {
    return [0, 0, 0];
  }
  // Filtriraj oblake i loše piksele kao u CSV evalscriptu
  var scl = sample.SCL;
  if (scl !== undefined && scl !== null) {
    if (scl === 0 || scl === 1 || scl === 8 || scl === 9) {
      return [0, 0, 0];
    }
  }
  let ndre = (sample.B08 - sample.B05) / (sample.B08 + sample.B05);
  
  // Normalizacija NDRE vrednosti na opseg 0-1
  // Koristimo už opseg baziran na realnim vrednostima za parcele: -0.05 do 0.15
  // Ovo je univerzalno i radi dobro za sve parcele, maksimalno pojačava kontrast
  let minVal = -0.05;  // Tipičan minimum za parcele
  let maxVal = 0.15;    // Tipičan maksimum za parcele
  let normalized = (ndre - minVal) / (maxVal - minVal);
  normalized = Math.max(0, Math.min(1, normalized));
  
  // Kontrast stretching za maksimalno pojačanje razlika
  // Koristimo blagu gamma korekciju za pojačanje razlika bez gubitka opsega
  let stretched = Math.pow(normalized, 0.8); // Gamma 0.8 - blago pojačanje
  stretched = Math.max(0, Math.min(1, stretched));
  
  // Generiši zelene nijanse od najtamnije do najsvetlije koristeći colorBlend
  // Koristimo 10 koraka za nežne prelaze kroz sve zelene nijanse
  // Pun opseg zelenih nijansi (50-255) za maksimalnu vidljivost razlika
  // Bez contrast boost-a da ne smanjimo opseg - direktno mapiranje
  let rgb = colorBlend(
    stretched,
    [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.85, 1.0],
    [
      [0, 50, 0],      // Najtamnija zelena
      [0, 80, 0],      // Tamna zelena
      [0, 110, 0],     // Srednje-tamna zelena
      [30, 140, 30],   // Srednje-tamna zelena
      [60, 170, 60],   // Srednja zelena
      [90, 200, 90],   // Srednje-svetla zelena
      [120, 220, 120], // Svetla zelena
      [150, 235, 150], // Veoma svetla zelena
      [180, 248, 180], // Ekstremno svetla zelena
      [200, 255, 200]  // Najsvetlija zelena
    ]
  );
  
  return [rgb[0], rgb[1], rgb[2]];
}
"""




def build_evalscript_ndmi_value() -> str:
    """Generiše raster sa sirovim NDMI vrednostima (FLOAT32) za GetFeatureInfo.
    Bez SCL filtera — isto kao vizuelni evalscript."""
    return """//VERSION=3
function setup() {
  return {
    input: ["B08", "B11", "dataMask"],
    output: { bands: 1, sampleType: "FLOAT32" }
  };
}

function evaluatePixel(sample) {
  if (sample.dataMask === 0) {
    return [-999];
  }
  var sum = sample.B08 + sample.B11;
  if (sum <= 0 || !isFinite(sample.B08) || !isFinite(sample.B11)) {
    return [-999];
  }
  var ndmi = (sample.B08 - sample.B11) / sum;
  return isFinite(ndmi) ? [ndmi] : [-999];
}
"""


def build_evalscript_ndre_value() -> str:
    """Generiše raster sa sirovim NDRE vrednostima (FLOAT32) za GetFeatureInfo.
    Bez SCL filtera — isto kao vizuelni evalscript."""
    return """//VERSION=3
function setup() {
  return {
    input: ["B05", "B08", "dataMask"],
    output: { bands: 1, sampleType: "FLOAT32" }
  };
}

function evaluatePixel(sample) {
  if (sample.dataMask === 0) {
    return [-999];
  }
  var sum = sample.B08 + sample.B05;
  if (sum <= 0 || !isFinite(sample.B08) || !isFinite(sample.B05)) {
    return [-999];
  }
  var ndre = (sample.B08 - sample.B05) / sum;
  return isFinite(ndre) ? [ndre] : [-999];
}
"""


def build_evalscript_drought_zones() -> str:
    return """//VERSION=3
function setup() {
  return {
    input: ["B08", "B11", "dataMask"],
    output: { bands: 3, sampleType: "UINT8" }
  };
}

function evaluatePixel(sample) {
  if (sample.dataMask === 0) {
    return [0, 0, 0];
  }
  let ndmi = (sample.B08 - sample.B11) / (sample.B08 + sample.B11);
  // Zones:
  // <= 0.2  : High stress (red)
  // <= 0.4  : Medium stress (orange)
  // >  0.4  : Low stress (green)
  if (ndmi <= 0.2) {
    return [215, 48, 39];
  }
  if (ndmi <= 0.4) {
    return [252, 141, 89];
  }
  return [91, 183, 98];
}
"""


def download_index(
    token: str,
    geometry: dict,
    time_from: str,
    time_to: str,
    width: int,
    height: int,
    max_cloud: int,
    evalscript: str,
    *,
    bbox: list | None = None,
    crs: str | None = None,
) -> bytes:
    """Preuzmi raster. Ako su bbox i crs dati, koristi ih (npr. UTM); inače geometry u WGS84."""
    if bbox is not None and crs is not None:
        bounds = {"bbox": bbox, "properties": {"crs": crs}}
    else:
        bounds = {
            "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/4326"},
            "geometry": geometry,
        }
    payload = {
        "input": {
            "bounds": bounds,
            "data": [
                {
                    "type": "sentinel-2-l2a",
                    "dataFilter": {
                        "timeRange": {"from": time_from, "to": time_to},
                        "maxCloudCoverage": max_cloud,
                        "mosaickingOrder": "mostRecent",
                    },
                }
            ],
        },
        "output": {
            "width": width,
            "height": height,
            "responses": [{"identifier": "default", "format": {"type": "image/tiff"}}],
        },
        "evalscript": evalscript,
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(PROCESS_URL, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="ignore")
        print(f"[ERROR] Process API failed: {exc.code} {exc.reason}")
        print(error_body)
        sys.exit(1)


def download_index_for_date(
    token: str,
    geometry: dict,
    date_str: str,
    width: int,
    height: int,
    max_cloud: int,
    evalscript: str,
    label: str,
    *,
    bbox: list | None = None,
    crs: str | None = None,
) -> tuple[bytes, str, str]:
    """Preuzmi raster za tačan datum (npr. 2026-02-04) – isti snimak kao CSV."""
    try:
        d = dt.datetime.strptime(date_str.strip()[:10], "%Y-%m-%d")
    except ValueError:
        return None, "", ""
    time_from = d.replace(tzinfo=dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    time_to = (d + dt.timedelta(days=1)).replace(tzinfo=dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[INFO] Request {label} za datum {date_str} -> {time_from} do {time_to}")
    kw = {}
    if bbox is not None and crs is not None:
        kw["bbox"] = bbox
        kw["crs"] = crs
    tiff_bytes = download_index(token, geometry, time_from, time_to, width, height, max_cloud, evalscript, **kw)
    return tiff_bytes, time_from, time_to


def download_with_fallback(
    token: str,
    geometry: dict,
    days_back: int,
    width: int,
    height: int,
    max_cloud: int,
    min_bytes: int,
    fallback_days: int,
    fallback_cloud: int,
    evalscript: str,
    label: str,
    *,
    bbox: list | None = None,
    crs: str | None = None,
) -> tuple[bytes, str, str, bool]:
    kw = {}
    if bbox is not None and crs is not None:
        kw["bbox"] = bbox
        kw["crs"] = crs
    now = dt.datetime.utcnow()
    start = now - dt.timedelta(days=days_back)
    time_from = start.strftime("%Y-%m-%dT%H:%M:%SZ")
    time_to = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[INFO] Request {label} {time_from} -> {time_to}")
    tiff_bytes = download_index(token, geometry, time_from, time_to, width, height, max_cloud, evalscript, **kw)
    if len(tiff_bytes) >= min_bytes:
        return tiff_bytes, time_from, time_to, False

    print(
        f"[WARN] Small GeoTIFF ({len(tiff_bytes)} bytes). "
        f"Retry with {fallback_days} days and cloud {fallback_cloud}%."
    )
    start_fb = now - dt.timedelta(days=fallback_days)
    time_from_fb = start_fb.strftime("%Y-%m-%dT%H:%M:%SZ")
    time_to_fb = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    tiff_fb = download_index(token, geometry, time_from_fb, time_to_fb, width, height, fallback_cloud, evalscript, **kw)
    return tiff_fb, time_from_fb, time_to_fb, True


def geoserver_put(url: str, user: str, password: str, data: bytes, content_type: str) -> None:
    creds = base64.b64encode(f"{user}:{password}".encode("utf-8")).decode("ascii")
    req = urllib.request.Request(url, data=data, method="PUT")
    req.add_header("Authorization", f"Basic {creds}")
    req.add_header("Content-Type", content_type)
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            if resp.status not in (200, 201):
                print(f"[ERROR] GeoServer response: {resp.status}")
                sys.exit(1)
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="ignore")
        print(f"[ERROR] GeoServer failed: {exc.code} {exc.reason}")
        print(error_body)
        sys.exit(1)


def geoserver_request(
    method: str, url: str, user: str, password: str, data: bytes, content_type: str
) -> tuple[int, str]:
    creds = base64.b64encode(f"{user}:{password}".encode("utf-8")).decode("ascii")
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Basic {creds}")
    req.add_header("Content-Type", content_type)
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            return resp.status, resp.read().decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="ignore")


def ensure_style(
    geoserver_url: str,
    user: str,
    password: str,
    name: str,
    sld_path: Path,
) -> None:
    if not sld_path.exists():
        print(f"[WARN] Style file missing: {sld_path}")
        return
    sld_bytes = sld_path.read_bytes()
    put_url = f"{geoserver_url}/rest/styles/{name}?raw=true"
    status, _ = geoserver_request(
        "PUT", put_url, user, password, sld_bytes, "application/vnd.ogc.sld+xml"
    )
    if status == 404:
        post_url = f"{geoserver_url}/rest/styles?name={urllib.parse.quote(name)}"
        status, body = geoserver_request(
            "POST", post_url, user, password, sld_bytes, "application/vnd.ogc.sld+xml"
        )
        if status not in (200, 201):
            print(f"[ERROR] Style create failed ({status}): {body}")
            sys.exit(1)
    elif status not in (200, 201):
        print(f"[ERROR] Style update failed ({status})")
        sys.exit(1)


def main() -> None:
    script_dir = Path(__file__).resolve().parent
    load_env(script_dir / ".env")

    client_id = get_env("CDSE_CLIENT_ID", required=True)
    client_secret = get_env("CDSE_CLIENT_SECRET", required=True)

    aoi_file = Path(get_env("AOI_FILE", str(script_dir / "serbia_aoi.geojson")))
    geometry = read_geometry(aoi_file)

    days_back = int(get_env("DAYS_BACK", "1"))
    max_cloud = int(get_env("MAX_CLOUD_COVER", "20"))
    min_bytes = int(get_env("MIN_TIFF_BYTES", "50000"))
    fallback_days = int(get_env("FALLBACK_DAYS_BACK", "7"))
    fallback_cloud = int(get_env("FALLBACK_MAX_CLOUD", "80"))
    resolution_m = float(get_env("RESOLUTION_M", "10"))
    max_pixels = int(get_env("MAX_PIXELS", "4096"))
    width, height = compute_output_size(geometry, resolution_m, max_pixels)
    print(f"[INFO] Output size {width}x{height} (res {resolution_m}m, max {max_pixels}px)")

    token = get_token(client_id, client_secret)
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
        build_evalscript_ndvi(),
        "NDVI",
    )

    output_dir = Path(get_env("OUTPUT_DIR", str(script_dir / "data")))
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / get_env("OUTPUT_FILENAME", "ndvi_latest.tif")
    output_path.write_bytes(ndvi_bytes)
    print(f"[INFO] Saved NDVI GeoTIFF: {output_path}")

    geoserver_url = get_env("GEOSERVER_URL", "http://localhost:8083/geoserver").rstrip("/")
    geoserver_user = get_env("GEOSERVER_USER", "admin")
    geoserver_password = get_env("GEOSERVER_PASSWORD", "geoserver")
    workspace = get_env("GEOSERVER_WORKSPACE", "moj_projekat")
    store = get_env("GEOSERVER_STORE", "ndvi_srbija")
    layer = get_env("GEOSERVER_LAYER", "ndvi_srbija")
    style = get_env("GEOSERVER_STYLE", "ndvi_srbija_style")
    index_style = get_env("GEOSERVER_INDEX_STYLE", "raster")

    upload_url = f"{geoserver_url}/rest/workspaces/{workspace}/coveragestores/{store}/file.geotiff?configure=all"
    geoserver_put(upload_url, geoserver_user, geoserver_password, ndvi_bytes, "image/tiff")
    print(f"[INFO] Uploaded to GeoServer store: {workspace}:{store}")

    style_xml = f"<layer><defaultStyle><name>{style}</name></defaultStyle></layer>".encode("utf-8")
    style_url = f"{geoserver_url}/rest/layers/{workspace}:{layer}"
    geoserver_put(style_url, geoserver_user, geoserver_password, style_xml, "text/xml")
    print(f"[INFO] Applied style: {style}")

    ndmi_store = get_env("GEOSERVER_NDMI_STORE", "ndmi_srbija")
    ndmi_layer = get_env("GEOSERVER_NDMI_LAYER", "ndmi_srbija")
    ndmi_style = get_env("GEOSERVER_NDMI_STYLE", index_style)

    ndmi_bytes, ndmi_from, ndmi_to, ndmi_fb = download_with_fallback(
        token,
        geometry,
        days_back,
        width,
        height,
        max_cloud,
        min_bytes,
        fallback_days,
        fallback_cloud,
        build_evalscript_ndmi(),
        "NDMI",
    )
    ndmi_path = output_dir / get_env("OUTPUT_FILENAME_NDMI", "ndmi_latest.tif")
    ndmi_path.write_bytes(ndmi_bytes)
    print(f"[INFO] Saved NDMI GeoTIFF: {ndmi_path}")

    ndmi_upload_url = f"{geoserver_url}/rest/workspaces/{workspace}/coveragestores/{ndmi_store}/file.geotiff?configure=all"
    geoserver_put(ndmi_upload_url, geoserver_user, geoserver_password, ndmi_bytes, "image/tiff")
    print(f"[INFO] Uploaded to GeoServer store: {workspace}:{ndmi_store}")

    ndmi_style_xml = f"<layer><defaultStyle><name>{ndmi_style}</name></defaultStyle></layer>".encode("utf-8")
    ndmi_style_url = f"{geoserver_url}/rest/layers/{workspace}:{ndmi_layer}"
    geoserver_put(ndmi_style_url, geoserver_user, geoserver_password, ndmi_style_xml, "text/xml")
    print(f"[INFO] Applied style: {ndmi_style}")

    ndre_store = get_env("GEOSERVER_NDRE_STORE", "ndre_srbija")
    ndre_layer = get_env("GEOSERVER_NDRE_LAYER", "ndre_srbija")
    ndre_style = get_env("GEOSERVER_NDRE_STYLE", index_style)

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
        build_evalscript_ndre(),
        "NDRE",
    )
    ndre_path = output_dir / get_env("OUTPUT_FILENAME_NDRE", "ndre_latest.tif")
    ndre_path.write_bytes(ndre_bytes)
    print(f"[INFO] Saved NDRE GeoTIFF: {ndre_path}")

    ndre_upload_url = f"{geoserver_url}/rest/workspaces/{workspace}/coveragestores/{ndre_store}/file.geotiff?configure=all"
    geoserver_put(ndre_upload_url, geoserver_user, geoserver_password, ndre_bytes, "image/tiff")
    print(f"[INFO] Uploaded to GeoServer store: {workspace}:{ndre_store}")

    ndre_style_xml = f"<layer><defaultStyle><name>{ndre_style}</name></defaultStyle></layer>".encode("utf-8")
    ndre_style_url = f"{geoserver_url}/rest/layers/{workspace}:{ndre_layer}"
    geoserver_put(ndre_style_url, geoserver_user, geoserver_password, ndre_style_xml, "text/xml")
    print(f"[INFO] Applied style: {ndre_style}")

    evi_store = get_env("GEOSERVER_EVI_STORE", "evi_srbija")
    evi_layer = get_env("GEOSERVER_EVI_LAYER", "evi_srbija")
    evi_style = get_env("GEOSERVER_EVI_STYLE", index_style)

    evi_bytes, evi_from, evi_to, evi_fb = download_with_fallback(
        token,
        geometry,
        days_back,
        width,
        height,
        max_cloud,
        min_bytes,
        fallback_days,
        fallback_cloud,
        build_evalscript_evi(),
        "EVI",
    )
    evi_path = output_dir / get_env("OUTPUT_FILENAME_EVI", "evi_latest.tif")
    evi_path.write_bytes(evi_bytes)
    print(f"[INFO] Saved EVI GeoTIFF: {evi_path}")

    evi_upload_url = f"{geoserver_url}/rest/workspaces/{workspace}/coveragestores/{evi_store}/file.geotiff?configure=all"
    geoserver_put(evi_upload_url, geoserver_user, geoserver_password, evi_bytes, "image/tiff")
    print(f"[INFO] Uploaded to GeoServer store: {workspace}:{evi_store}")

    evi_style_xml = f"<layer><defaultStyle><name>{evi_style}</name></defaultStyle></layer>".encode("utf-8")
    evi_style_url = f"{geoserver_url}/rest/layers/{workspace}:{evi_layer}"
    geoserver_put(evi_style_url, geoserver_user, geoserver_password, evi_style_xml, "text/xml")
    print(f"[INFO] Applied style: {evi_style}")

    drought_store = get_env("GEOSERVER_DROUGHT_STORE", "drought_zones")
    drought_layer = get_env("GEOSERVER_DROUGHT_LAYER", "drought_zones")
    drought_style = get_env("GEOSERVER_DROUGHT_STYLE", "raster")

    drought_bytes, drought_from, drought_to, drought_fb = download_with_fallback(
        token,
        geometry,
        days_back,
        width,
        height,
        max_cloud,
        min_bytes,
        fallback_days,
        fallback_cloud,
        build_evalscript_drought_zones(),
        "DROUGHT_ZONES",
    )
    drought_path = output_dir / get_env("OUTPUT_FILENAME_DROUGHT", "drought_zones_latest.tif")
    drought_path.write_bytes(drought_bytes)
    print(f"[INFO] Saved drought zones GeoTIFF: {drought_path}")

    drought_upload_url = f"{geoserver_url}/rest/workspaces/{workspace}/coveragestores/{drought_store}/file.geotiff?configure=all"
    geoserver_put(drought_upload_url, geoserver_user, geoserver_password, drought_bytes, "image/tiff")
    print(f"[INFO] Uploaded to GeoServer store: {workspace}:{drought_store}")

    drought_style_xml = f"<layer><defaultStyle><name>{drought_style}</name></defaultStyle></layer>".encode("utf-8")
    drought_style_url = f"{geoserver_url}/rest/layers/{workspace}:{drought_layer}"
    geoserver_put(drought_style_url, geoserver_user, geoserver_password, drought_style_xml, "text/xml")
    print(f"[INFO] Applied style: {drought_style}")

    metadata = {
        "updatedAt": dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ndvi": {"from": ndvi_from, "to": ndvi_to, "fallback": ndvi_fb},
        "ndmi": {"from": ndmi_from, "to": ndmi_to, "fallback": ndmi_fb},
        "ndre": {"from": ndre_from, "to": ndre_to, "fallback": ndre_fb},
        "evi": {"from": evi_from, "to": evi_to, "fallback": evi_fb},
        "drought": {"from": drought_from, "to": drought_to, "fallback": drought_fb},
    }
    meta_path = script_dir / "latest_metadata.json"
    meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[INFO] Wrote metadata: {meta_path}")


if __name__ == "__main__":
    main()
