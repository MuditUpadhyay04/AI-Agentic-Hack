"""Download the open datasets PitCrew can use (run in the workshop account, which has internet).

    python scripts/fetch_data.py                 # AI4I 2020 (510 KB)

It lands in data/. PitCrew prefers data/ai4i2020.csv (the real file) over its replica as soon as it exists.
Nothing here needs credentials. (Matthew's failure model ships its own copy in failure_model/.)
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


def main() -> None:
    argparse.ArgumentParser().parse_args()
    DATA.mkdir(exist_ok=True)
    sys.exit(0 if fetch_ai4i() else 1)


if __name__ == "__main__":
    main()
