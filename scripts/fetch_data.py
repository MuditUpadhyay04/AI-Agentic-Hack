"""Download the open datasets PitCrew can use (run in the workshop account, which has internet).

    python scripts/fetch_data.py                 # AI4I 2020 (510 KB) + DFW wind from Iowa Mesonet (small)
    python scripts/fetch_data.py --all           # + NASA IMS bearings (~1 GB, optional)

Everything lands in data/. PitCrew prefers data/ai4i2020.csv (the real file) over its replica as soon as it
exists. Nothing here needs credentials. The tracker motor-current set (DuraMAT) and the EDP wind farm
failure log need a browser click; their pages are printed at the end.
"""
from __future__ import annotations

import argparse
import io
import sys
import urllib.request
import zipfile
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"

AI4I = [
    "https://archive.ics.uci.edu/ml/machine-learning-databases/00601/ai4i2020.csv",
    "https://archive.ics.uci.edu/static/public/601/ai4i+2020+predictive+maintenance+dataset.zip",
]
# Iowa Environmental Mesonet ASOS download service (no key). If the parameters drift, build the query in
# the web form at https://mesonet.agron.iastate.edu/request/download.phtml?network=TX_ASOS and paste it here.
DFW_WIND = ("https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?station=DFW&data=sknt&data=gust&data=drct"
            "&data=tmpf&year1=2025&month1=10&day1=1&year2=2026&month2=10&day2=23&tz=America%2FChicago"
            "&format=onlycomma&latlon=no&missing=M&trace=T&direct=no&report_type=3")
IMS = "https://phm-datasets.s3.amazonaws.com/NASA/4.+Bearings.zip"
BY_HAND = {
    "DuraMAT emulated single-axis tracker faults (motor current, 27.9 MiB parquet)":
        "https://datahub.duramat.org/dataset/time-series-from-emulated-pv-single-axis-tracker-faults-data-and-resources",
    "EDP Wind Farm 1 with failure log (CC BY 4.0, 173.7 MB)": "https://data.mendeley.com/datasets/zjxjnjp3xs/2",
    "JUST slewing-bearing vibration + AE (CC BY 4.0)": "https://data.mendeley.com/datasets/hwg8v5j8t6/1",
}


def get(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "pitcrew-hackathon/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def fetch_ai4i() -> bool:
    out = DATA / "ai4i2020.csv"
    if out.exists():
        print(f"ok   {out.name} already here")
        return True
    for url in AI4I:
        try:
            b = get(url)
            if url.endswith(".zip"):
                z = zipfile.ZipFile(io.BytesIO(b))
                name = next(n for n in z.namelist() if n.endswith(".csv"))
                b = z.read(name)
            out.write_bytes(b)
            print(f"ok   AI4I 2020 -> {out} ({len(b) / 1024:.0f} KB) from {url}")
            return True
        except Exception as exc:  # try the next mirror
            print(f"miss {url}: {exc}")
    print("FAIL AI4I: download it from https://archive.ics.uci.edu/dataset/601 into data/ai4i2020.csv")
    return False


def fetch_wind() -> bool:
    out = DATA / "dfw_asos.csv"
    try:
        b = get(DFW_WIND, timeout=120)
        out.write_bytes(b)
        print(f"ok   DFW ASOS wind/temperature -> {out} ({len(b) / 1024:.0f} KB)")
        return True
    except Exception as exc:
        print(f"FAIL DFW wind: {exc}. The fleet keeps its synthetic DFW-shaped weather.")
        return False


def fetch_ims() -> bool:
    out = DATA / "nasa_ims_bearings.zip"
    try:
        b = get(IMS, timeout=600)
        out.write_bytes(b)
        print(f"ok   NASA IMS bearings -> {out} ({len(b) / 1e6:.0f} MB)")
        return True
    except Exception as exc:
        print(f"FAIL IMS: {exc}")
        return False


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    DATA.mkdir(exist_ok=True)
    ok = fetch_ai4i()
    fetch_wind()
    if a.all:
        fetch_ims()
    print("\nBy hand (open in a browser, download into data/):")
    for k, v in BY_HAND.items():
        print(f"  - {k}: {v}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
