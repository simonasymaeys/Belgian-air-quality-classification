"""Build the hourly PM2.5 input for hourly_to_daily.py from the official Belgian E1a XML reports.

Run from the project root:  python src/e1a_to_hourly.py [xml_folder]
  1. Downloads the E1a files listed in data/official_source_manifest.json into xml_folder
     (default: data/e1a_xml/, about 1.1 GB) unless they are already there.
  2. Verifies every file against its SHA-256 hash in the manifest.
  3. Extracts hourly PM2.5 (pollutant 6001, primaryObservation/hour) for the stations in
     data/station_mapping.csv and writes data/pm25_hourly_reconciled.csv.gz.

Only official E1a values, verification and validity flags are used; quality filtering is left to
hourly_to_daily.py. Official values are authoritative, so the comparison with the IRCEL API
(columns api_nonnegative_rejected_hours / official_value_differences in the bundled daily file)
is documentation only and is not needed to reproduce the modelling input.
Source data: IRCEL-CELINE / Belgian E1a reporting via Eionet CDR, CC BY 4.0.
"""
import gzip
import hashlib
import json
import re
import sys
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
XML_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else DATA / "e1a_xml"
START, END = pd.Timestamp("2021-12-31 23:00", tz="UTC"), pd.Timestamp("2025-12-31 23:00", tz="UTC")

manifest = [m for m in json.loads((DATA / "official_source_manifest.json").read_text()) if m.get("hourly_pm25_observation_blocks")]
mapping = pd.read_csv(DATA / "station_mapping.csv", dtype={"series_id": str})
code_to_station = mapping.set_index("official_station_code")[["series_id", "station"]]

OBS = re.compile(r"<om:OM_Observation\b(.*?)</om:OM_Observation>", re.S)
PROP = re.compile(r'observedProperty xlink:href="[^"]*/pollutant/(\d+)"')
SPO = re.compile(r'SamplingPoint"/>\s*<om:value xlink:href="[^"]*SPO-([^"_]+)_([^"]+)"')
DEF = re.compile(r'<swe:Quantity definition="[^"]*/primaryObservation/(\w+)"')
VALUES = re.compile(r"<swe:values>(.*?)</swe:values>", re.S)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


XML_DIR.mkdir(parents=True, exist_ok=True)
frames = []
for entry in manifest:
    path = XML_DIR / entry["file"]
    if not path.exists():
        print("Downloading", entry["url"])
        urllib.request.urlretrieve(entry["url"], path)
    assert sha256(path) == entry["sha256"], f"SHA-256 mismatch for {path.name}"
    text = path.read_text(encoding="utf-8")
    kept = 0
    for obs in OBS.finditer(text):
        body = obs.group(1)
        prop, spo, definition = PROP.search(body), SPO.search(body), DEF.search(body)
        if not (prop and prop.group(1) == "6001" and spo and definition and definition.group(1) == "hour"):
            continue
        code = spo.group(1)
        if code not in code_to_station.index:
            continue
        rows = [r.split(",") for r in VALUES.search(body).group(1).strip().split("@@") if r.strip()]
        df = pd.DataFrame(rows, columns=["start", "end", "verification", "validity", "official_pm25"])
        df["official_station_code"] = code
        df["sampling_point"] = spo.group(2)
        df["source_file"] = entry["file"]
        frames.append(df)
        kept += 1
    print(f"{entry['file']}: hash OK, {kept} hourly PM2.5 blocks for mapped stations")

hourly = pd.concat(frames, ignore_index=True)
hourly["interval_start_utc"] = pd.to_datetime(hourly.start, utc=True, format="ISO8601")
hourly = hourly[(hourly.interval_start_utc >= START) & (hourly.interval_start_utc < END)]
hourly["official_pm25"] = pd.to_numeric(hourly.official_pm25, errors="coerce")
hourly["verification"] = pd.to_numeric(hourly.verification, errors="coerce").astype("Int64")
hourly["validity"] = pd.to_numeric(hourly.validity, errors="coerce").astype("Int64")
duplicates = hourly.duplicated(["official_station_code", "interval_start_utc"], keep=False)
assert not duplicates.any(), f"{int(duplicates.sum())} duplicated station-hours across files/sampling points"
hourly = hourly.join(code_to_station, on="official_station_code")
hourly["interval_start_utc"] = hourly.interval_start_utc.dt.strftime("%Y-%m-%dT%H:%M:%SZ")
columns = ["series_id", "station", "official_station_code", "interval_start_utc", "official_pm25", "verification", "validity", "sampling_point", "source_file"]
hourly = hourly[columns].sort_values(["series_id", "interval_start_utc"])
output = DATA / "pm25_hourly_reconciled.csv.gz"
with gzip.open(output, "wt", compresslevel=9, newline="") as f:
    hourly.to_csv(f, index=False)
print("Saved", output, "| rows:", len(hourly), "| stations:", hourly.series_id.nunique())
