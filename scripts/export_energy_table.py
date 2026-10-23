"""Export the tower energy table PitCrew prices its decisions with.

Writes ``data/tr08_dallas_daily_kwh.csv`` (kWh per tower per day: tracking, step tracking, parked at each
azimuth) and ``data/tr08_dallas_hourly_track_kw.csv`` (tracked power by hour, for pricing an earlier stow).

    python scripts/export_energy_table.py                      # clear sky, Dallas, TR-08 with 8 x 445 W
    python scripts/export_energy_table.py --check-engine PATH  # also compare with janta_shade's field model

Clear sky overstates a real year (cloud), so absolute kWh are an upper bound; the ratios between options,
which is what the decisions use, hold. On Janta's server, rerun with a PVGIS/NSRDB typical year by
pointing ``--weather`` at the Shadow Calculator's weather CSV.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pitcrew.solar_face import TowerFace, clearsky_year, daily_energy_table, face_power_kw  # noqa: E402


def check_against_engine(engine_path: str, sun: pd.DataFrame, tower: TowerFace) -> dict:
    """Tracking energy from janta_shade.solar.field_poa vs this module, same inputs."""
    sys.path.insert(0, engine_path)
    import pvlib
    from janta_shade.solar import FacePhysics, field_poa, wing_faces

    p = pvlib.temperature.TEMPERATURE_MODEL_PARAMETERS["sapm"]["open_rack_glass_polymer"]
    phys = FacePhysics(faces=wing_faces(tower.tilt_deg, tower.fold_deg), temp_coeff=tower.temp_coeff_per_c,
                       temp_params=(p["a"], p["b"], p["deltaT"]))
    b, s, g, _ = field_poa(sun.index.tz_convert("UTC"), sun["el"].to_numpy(), sun["az"].to_numpy(),
                           sun["dni"].to_numpy(), sun["dhi"].to_numpy(), sun["ghi"].to_numpy(), tower.albedo, phys,
                           sun["temp_air"].to_numpy(), sun["wind"].to_numpy())
    engine_kwh = float((tower.rated_kw * (b + s + g) / 1000.0 * tower.other_losses_factor * sun["hours"]).sum())
    ours_kwh = float((face_power_kw(sun, sun["az"].to_numpy(), tower) * sun["hours"]).sum())
    return {"engine_kwh_per_year": round(engine_kwh, 1), "pitcrew_kwh_per_year": round(ours_kwh, 1),
            "difference_pct": round(100 * (ours_kwh / engine_kwh - 1), 3)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--out", default=str(ROOT / "data"))
    ap.add_argument("--check-engine", default=None, help="path to janta-shadow-calculator/engine")
    a = ap.parse_args()
    tower = TowerFace()
    sun = clearsky_year(a.year)
    daily = daily_energy_table(sun, tower)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    daily.round(4).to_csv(out / "tr08_dallas_daily_kwh.csv")
    hourly = pd.Series(face_power_kw(sun, sun["az"].to_numpy(), tower) * sun["hours"], index=sun.index)
    hourly = hourly.groupby(hourly.index.floor("h")).sum()
    hourly.index = hourly.index.tz_localize(None)
    hourly.round(4).rename("track_kwh").to_csv(out / "tr08_dallas_hourly_track_kwh.csv", index_label="hour")
    annual = daily.sum()
    park_cols = [c for c in daily.columns if c.startswith("park_")]
    best_park = annual[park_cols].idxmax()
    meta = {
        "source": "Clear sky (Ineichen), Dallas TX, 10-min steps, year %d; TR-08 face (60 deg tilt, wings 20 deg), "
                  "8 x 445 W = 3.56 kWdc, SAPM open-rack glass/polymer, other losses 0.90 (DFW tower fit)" % a.year,
        "upper_bound_note": "Clear sky has no clouds: absolute kWh are an upper bound, ratios between options hold.",
        "annual_kwh": {k: round(float(v), 1) for k, v in annual[["track", "step10", "step15", "step30"]].items()},
        "annual_kwh_per_kw_tracking": round(float(annual["track"]) / tower.rated_kw, 1),
        "best_fixed_azimuth": int(best_park.split("_")[1]),
        "best_fixed_kwh": round(float(annual[best_park]), 1),
        "best_fixed_share_of_tracking": round(float(annual[best_park] / annual["track"]), 4),
    }
    if a.check_engine:
        meta["engine_check"] = check_against_engine(a.check_engine, sun, tower)
    (out / "tr08_dallas_energy_meta.json").write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
