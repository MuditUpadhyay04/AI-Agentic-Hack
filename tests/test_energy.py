import json
from pathlib import Path

import pandas as pd

from pitcrew.decide import window_energy
from pitcrew.solar_face import TowerFace, clearsky_year, face_power_kw, step_azimuth

DATA = Path(__file__).resolve().parents[1] / "data"


def test_table_exists_and_is_consistent():
    df = pd.read_csv(DATA / "tower_dallas_daily_kwh.csv", index_col=0)
    meta = json.loads((DATA / "tower_dallas_energy_meta.json").read_text())
    assert len(df) == 365
    assert abs(df["track"].sum() - meta["annual_kwh"]["track"]) < 1
    assert (df["track"] >= df["step15"] - 1e-6).all()  # stepping never beats tracking
    park = df[[c for c in df.columns if c.startswith("park_")]]
    assert (park.max(axis=1) <= df["track"] + 1e-6).all()


def test_step_tracking_costs_well_under_one_percent():
    meta = json.loads((DATA / "tower_dallas_energy_meta.json").read_text())
    a = meta["annual_kwh"]
    assert 1 - a["step15"] / a["track"] < 0.005
    assert meta["best_fixed_azimuth"] == 180


def test_tracking_face_equals_sun_azimuth_power():
    sun = clearsky_year(step_min=60).iloc[:200]
    p_track = face_power_kw(sun, sun["az"].to_numpy())
    p_step = face_power_kw(sun, step_azimuth(sun["az"].to_numpy(), 1.0))
    assert abs(p_track.sum() - p_step.sum()) / p_track.sum() < 0.001


def test_window_energy_october():
    import datetime as dt
    e = window_energy(dt.date(2026, 10, 24), 6)
    assert e["park_azimuth"] == 180
    assert 0.75 < e["park"] / e["track"] < 0.85  # parking in late October gives up ~20%
