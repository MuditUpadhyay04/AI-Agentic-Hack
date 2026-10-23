"""Export the tower energy table PitCrew prices its decisions with.

Writes ``data/tower_dallas_daily_kwh.csv`` (kWh per tower per day: tracking, step tracking, parked at each
azimuth) and ``data/tower_dallas_hourly_track_kw.csv`` (tracked power by hour, for pricing an earlier stow).

    python scripts/export_energy_table.py                      # clear sky, Dallas, ST-1 with 8 x 445 W

Clear sky overstates a real year (cloud), so absolute kWh are an upper bound; the ratios between options,
which is what the decisions use, hold. For a real table, rerun with a PVGIS/NSRDB typical year.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pitcrew.solar_face import TowerFace, clearsky_year, daily_energy_table, face_power_kw  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--out", default=str(ROOT / "data"))
    a = ap.parse_args()
    tower = TowerFace()
    sun = clearsky_year(a.year)
    daily = daily_energy_table(sun, tower)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    daily.round(4).to_csv(out / "tower_dallas_daily_kwh.csv")
    hourly = pd.Series(face_power_kw(sun, sun["az"].to_numpy(), tower) * sun["hours"], index=sun.index)
    hourly = hourly.groupby(hourly.index.floor("h")).sum()
    hourly.index = hourly.index.tz_localize(None)
    hourly.round(4).rename("track_kwh").to_csv(out / "tower_dallas_hourly_track_kwh.csv", index_label="hour")
    annual = daily.sum()
    park_cols = [c for c in daily.columns if c.startswith("park_")]
    best_park = annual[park_cols].idxmax()
    meta = {
        "source": "Clear sky (Ineichen), Dallas TX, 10-min steps, year %d; ST-1 face (60 deg tilt, wings 20 deg), "
                  "8 x 445 W = 3.56 kWdc, SAPM open-rack glass/polymer, other losses 0.90 (placeholder)" % a.year,
        "upper_bound_note": "Clear sky has no clouds: absolute kWh are an upper bound, ratios between options hold.",
        "annual_kwh": {k: round(float(v), 1) for k, v in annual[["track", "step10", "step15", "step30"]].items()},
        "annual_kwh_per_kw_tracking": round(float(annual["track"]) / tower.rated_kw, 1),
        "best_fixed_azimuth": int(best_park.split("_")[1]),
        "best_fixed_kwh": round(float(annual[best_park]), 1),
        "best_fixed_share_of_tracking": round(float(annual[best_park] / annual["track"]), 4),
    }
    (out / "tower_dallas_energy_meta.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
