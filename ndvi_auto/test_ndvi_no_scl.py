"""Test NDVI API BEZ SCL maskiranja - da vidimo sta vraca za svih 5 datuma."""
import json
import urllib.request
from pathlib import Path

from download_and_publish import get_env, get_token, load_env
from download_ndvi_parcel_csv import (
    fetch_parcel_geometry,
    time_range_midnight_utc,
    _geometry_to_utm_bbox,
)

EVALSCRIPT_NO_SCL = """//VERSION=3
function setup() {
  return {
    input: ["B04", "B08", "dataMask"],
    output: [
      { id: "default", bands: 1, sampleType: "FLOAT32" },
      { id: "dataMask", bands: 1 }
    ]
  };
}
function evaluatePixel(sample) {
  if (sample.dataMask === 0) return { default: [0], dataMask: [0] };
  var sum = sample.B08 + sample.B04;
  if (sum <= 0) return { default: [0], dataMask: [0] };
  var ndvi = (sample.B08 - sample.B04) / sum;
  return isFinite(ndvi) ? { default: [ndvi], dataMask: [1] } : { default: [0], dataMask: [0] };
}
"""


def main():
    load_env(Path(__file__).parent / ".env")
    geoserver_url = get_env("GEOSERVER_URL", "http://localhost:8083/geoserver").rstrip("/")
    geometry = fetch_parcel_geometry(
        geoserver_url,
        get_env("GEOSERVER_WORKSPACE", "moj_projekat"),
        get_env("PARCEL_LAYER", "VrsacDKP"),
        get_env("PARCEL_ATTR", "brparcele"),
        "1427/2",
    )
    bbox, crs = _geometry_to_utm_bbox(geometry)
    date_from, date_to = time_range_midnight_utc(30)
    token = get_token(
        get_env("CDSE_CLIENT_ID", required=True),
        get_env("CDSE_CLIENT_SECRET", required=True),
    )

    payload = {
        "input": {
            "bounds": {"bbox": bbox, "properties": {"crs": crs}},
            "data": [{"type": "sentinel-2-l2a", "dataFilter": {"maxCloudCoverage": 100}}],
        },
        "aggregation": {
            "timeRange": {"from": date_from, "to": date_to},
            "aggregationInterval": {"of": "P1D"},
            "evalscript": EVALSCRIPT_NO_SCL,
            "resx": 10,
            "resy": 10,
        },
        "calculations": {
            "default": {"statistics": {"default": {"percentiles": {"k": [10, 50, 90]}}}}
        },
    }

    req = urllib.request.Request(
        "https://sh.dataspace.copernicus.eu/api/v1/statistics",
        data=json.dumps(payload).encode(),
        method="POST",
    )
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=120) as r:
        result = json.loads(r.read().decode())

    print("BEZ SCL maskiranja (samo dataMask, iskljucuje samo no-data):")
    for i, item in enumerate(result.get("data", [])):
        interval = item.get("interval", {})
        date_val = interval.get("from", "")[:10]
        outs = item.get("outputs", {})
        first_out = next(iter(outs.values()), {})
        bands = first_out.get("bands", {})
        band = next(iter(bands.values()), {}) if bands else {}
        stats = band.get("stats", {})
        mean = stats.get("mean")
        sc = stats.get("sampleCount")
        ndc = stats.get("noDataCount")
        is_nan = isinstance(mean, float) and mean != mean
        mean_str = f"{mean:.3f}" if mean is not None and not is_nan else "NaN"
        print(f"  {date_val}: mean={mean_str}, sampleCount={sc}, noDataCount={ndc}")


if __name__ == "__main__":
    main()
