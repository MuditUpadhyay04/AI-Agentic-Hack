"""Sensor Futures: what hardware the next tower should carry, priced by the failures it would have caught.

For every drive failure in the fleet's history, the crew replays the tower's last 120 days twice: with the
sensors the ST-1 has today, and with one future hardware slot added. A slot is worth something when it
moves the first alarm early enough to turn an unplanned failure into a planned repair (the part arrives
and the batched route reaches the tower before it fails). Value per tower-year, against the slot's cost,
is the hardware roadmap R&D gets from the fleet.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .decide import FIXES, TowerEconomics, failure_cost, planned_cost
from .tower import DETECTORS, Fleet, detect


@dataclass(frozen=True)
class Slot:
    key: str
    name: str
    detectors: tuple
    unit_usd: float  # hardware + fitting per tower (assumption)
    note: str


SLOTS = [
    Slot("grease", "Grease condition sensor (water + iron)", ("grease_water", "grease_iron"), 85.0,
         "Sees water past a seal on day one and grease wear before friction shows in the motor current"),
    Slot("acoustic", "Acoustic emission on the slewing bearing", ("acoustic",), 180.0,
         "The only way to hear a raceway defect at under 1.5 rpm; flagged failure ~15 months ahead in a slew-bearing test"),
    Slot("vibration", "Worm-side MEMS accelerometer", ("vibration",), 25.0,
         "Cheap; the worm turns ~85x faster than the output, so vibration is readable there"),
    Slot("torque", "In-drive torque sensor (worm axial displacement)", ("torque",), 140.0,
         "Separates friction from wind load directly (patent US12253157 warns at 0.7-1.3 mm)"),
]


def _required_lead(mode: str) -> tuple[str, int]:
    """(fix key, days of warning needed for a planned repair: route cadence, plus a drive's lead time)."""
    if mode.startswith("backlash"):
        return "backlash", 21
    if mode.startswith("bearing"):
        return "acoustic", 21
    return "friction", 7


def replay(fleet: Fleet, e: TowerEconomics = TowerEconomics()) -> pd.DataFrame:
    """One row per historical failure: first alarm with today's sensors and with each slot, and the value."""
    log = fleet.log_df
    rows = []
    daily_kwh = 26.9  # annual mean tracked kWh/day of a ST-1 (data/tower_dallas_energy_meta.json / 365)
    fcost = failure_cost(e, daily_kwh)
    for inc in fleet.incidents:
        h = log[(log.tower_id == inc["tower_id"]) & (log.day <= inc["day"]) & (log.day > inc["day"] - 120)]
        if len(h) < 10:
            continue
        fix_key, need = _required_lead(inc["mode"])
        parts_usd = 1200.0 + 25.0 if fix_key in ("backlash", "acoustic") else 40.0
        saving = fcost - planned_cost(e, fix_key if fix_key in FIXES else "friction", parts_usd)

        def lead(slots=()):
            found = detect(h, fleet.baseline_epd, slots)
            return (inc["day"] - min(f["first_day"] for f in found)) if found else 0

        base = lead()
        row = {**inc, "fix": fix_key, "needed_days": need, "lead_today": base, "saved_today": base >= need,
               "saving_usd": round(saving)}
        for s in SLOTS:
            ls = lead(s.detectors)
            row[f"lead_{s.key}"] = ls
            row[f"gain_{s.key}"] = (ls >= need) and not (base >= need)
        rows.append(row)
    return pd.DataFrame(rows)


def ranking(fleet: Fleet, e: TowerEconomics = TowerEconomics()) -> tuple[pd.DataFrame, pd.DataFrame, float]:
    """(per-slot ranking, per-incident replay, tower-years observed)."""
    rp = replay(fleet, e)
    tower_years = fleet.log_df.groupby("tower_id").size().sum() / 365.0
    out = []
    for s in SLOTS:
        if rp.empty:
            break
        caught = rp[rp[f"gain_{s.key}"]]
        extra_days = (rp[f"lead_{s.key}"] - rp["lead_today"]).clip(lower=0)
        value_ty = caught["saving_usd"].sum() / tower_years
        out.append({"slot": s.name, "key": s.key, "unit_usd": s.unit_usd,
                    "failures_turned_planned": int(len(caught)), "of_failures": int(len(rp)),
                    "median_extra_warning_days": float(np.median(extra_days)) if len(extra_days) else 0.0,
                    "value_usd_per_tower_year": round(value_ty, 1),
                    "payback_years": round(s.unit_usd / value_ty, 1) if value_ty > 0 else None,
                    "note": s.note})
    df = pd.DataFrame(out).sort_values("value_usd_per_tower_year", ascending=False) if out else pd.DataFrame()
    return df, rp, tower_years
