"""Park & Price: what each bridge option costs a degrading tower until the technician arrives.

For a tower the crew flags, every option is priced the same way, with every input on the approval card:

    expected cost = energy given up (kWh x price) + P(fail before the visit) x cost of a failure + visit cost

- Energy comes from the ST-1 table exported from the field energy model (``data/``): tracking,
  15 deg step tracking, and parked at the best fixed azimuth *for those calendar days*.
- P(fail before the visit) is a weather Monte Carlo of the drive model under each tracking mode (``tower.project``).
- A failure costs a new drive, a crew and lift, an emergency truck roll, and the energy lost while the tower
  sits stuck for the drive's lead time.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from .tower import Fleet, detect, indicator, project, rul_days

DATA = Path(__file__).resolve().parents[1] / "data"


@dataclass
class TowerEconomics:
    """Assumptions (USD). Sources: truck rolls from Power Factors' break-even guide; the rest are placeholders
    to replace with a real price book."""

    energy_usd_per_kwh: float = 0.11  # Texas commercial energy value (assumption)
    truck_roll_local: float = 125.0  # Power Factors: local visit
    truck_roll_regional: float = 400.0  # Power Factors: regional visit (emergency next day)
    labor_hour: float = 95.0
    regrease_hours: float = 1.0
    reseal_hours: float = 2.0
    drive_swap_hours: float = 4.0
    lift_usd: float = 450.0  # lift / crane for a drive swap
    drive_lead_days: int = 21
    stuck_share_of_tracking: float = 0.55  # a stuck tower faces wherever it stopped (avg of daytime azimuths)
    batch_size: int = 5  # towers sharing the batched route visit


@lru_cache(maxsize=2)
def energy_table(path: str = str(DATA / "tower_dallas_daily_kwh.csv")) -> pd.DataFrame:
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    return df


def window_energy(start: dt.date, days: int) -> dict:
    """kWh per tower over ``days`` from ``start`` for each option, and the best parking azimuth for them."""
    df = energy_table()
    idx = pd.date_range(start, periods=days, freq="D")
    rows = df.reindex(idx.strftime("%Y-%m-%d"))
    rows.index = idx
    if rows.isna().any().any():  # table year differs: use the same calendar days
        alt = df.copy()
        alt.index = alt.index.strftime("%m-%d")
        rows = alt.loc[idx.strftime("%m-%d")]
    park_cols = [c for c in rows.columns if c.startswith("park_")]
    sums = rows.sum()
    best = sums[park_cols].idxmax()
    return {"track": float(sums["track"]), "step15": float(sums["step15"]), "park": float(sums[best]),
            "park_azimuth": int(best.split("_")[1]), "daily_track": float(rows["track"].mean()),
            "park_daily": rows[best].to_numpy(), "track_daily": rows["track"].to_numpy()}


FIXES = {
    # failure mode -> (title, parts, labour hours attr, needs new drive)
    "friction": ("Re-grease slew drive, check seals", [("GREASE-KIT-SD", 1)], "regrease_hours", False),
    "grease_water": ("Replace seals and re-grease (water in the drive)", [("SEAL-KIT-SD", 1), ("GREASE-KIT-SD", 1)],
                     "reseal_hours", False),
    "backlash": ("Replace slew drive (backlash at limit), new bolt kit", [("DRIVE-WSD14", 1), ("BOLT-KIT-SD", 1)],
                 "drive_swap_hours", True),
    "acoustic": ("Replace slew drive (bearing damage)", [("DRIVE-WSD14", 1)], "drive_swap_hours", True),
}


def failure_cost(e: TowerEconomics, daily_track_kwh: float) -> float:
    stuck = e.drive_lead_days * daily_track_kwh * (1 - e.stuck_share_of_tracking) * e.energy_usd_per_kwh
    return 1200.0 + e.lift_usd + e.drive_swap_hours * e.labor_hour + e.truck_roll_regional + stuck


def planned_cost(e: TowerEconomics, fix_key: str, parts_usd: float) -> float:
    hours = getattr(e, FIXES[fix_key][2])
    return parts_usd + hours * e.labor_hour + e.truck_roll_local / e.batch_size + (e.lift_usd if FIXES[fix_key][3] else 0)


def diagnose(fleet: Fleet, tid: int, slots: tuple = ()) -> dict:
    """What today's detectors (and any installed slots) say about a tower, with a remaining-life estimate."""
    h = fleet.history(tid, 120)
    found = detect(h, fleet.baseline_epd, slots)
    if not found:
        return {"tower_id": tid, "findings": [], "primary": None}
    order = {"acoustic": 0, "backlash": 1, "grease_water": 2, "friction": 3}
    found.sort(key=lambda f: (order.get(f["detector"], 9), f["first_day"]))
    primary = found[0]
    s = indicator(h, primary["detector"], fleet.baseline_epd)
    offset = 1.0 if primary["detector"] in ("friction", "torque") else 0.0
    rul = rul_days(s, h["day"], primary["fail_at"], offset=offset)
    return {"tower_id": tid, "findings": found, "primary": primary,
            "rul": {k: (round(v, 1) if np.isfinite(v) else None) for k, v in rul.items()},
            "series": {"day": h["day"].tolist(), "value": s.round(4).tolist(),
                       "date": [d.date().isoformat() for d in h["date"]]}}


def park_and_price(fleet: Fleet, tid: int, ops, e: TowerEconomics = TowerEconomics(), runs: int = 300,
                   slots: tuple = ()) -> dict:
    """Price every bridge option for one tower until the next batched route visit."""
    dx = diagnose(fleet, tid, slots)
    if not dx["primary"]:
        return {"tower_id": tid, "diagnosis": dx, "options": [], "recommendation": None}
    fix_key = dx["primary"]["detector"] if dx["primary"]["detector"] in FIXES else "friction"
    title, parts, _, new_drive = FIXES[fix_key]
    parts_usd = sum(ops.parts[pn].unit_usd * q for pn, q in parts)
    route = ops.next_route_day("DFW")
    visit = route["in_days"]
    # a new drive must arrive before the visit, else the visit waits for it
    if new_drive:
        q = ops.best_quote("DRIVE-WSD14", need_by_days=visit)
        stock = ops.stock("DRIVE-WSD14")["available"]
        if stock < 1 and not (q["pick"] and q["pick"]["arrives_in_days"] <= visit):
            visit = max(visit, (q["pick"] or {"arrives_in_days": e.drive_lead_days})["arrives_in_days"])
    start = dt.date.fromisoformat(fleet.weather.index[-1].date().isoformat()) + dt.timedelta(days=1)
    en = window_energy(start, visit)
    price = e.energy_usd_per_kwh
    fcost = failure_cost(e, en["daily_track"])
    pcost = planned_cost(e, fix_key, parts_usd)
    opts = []
    for mode, label, kwh in [("track", "Keep tracking", en["track"]),
                             ("coast", "Coast: 15 deg steps, stow at 30 mph", en["step15"]),
                             ("park", f"Park at {en['park_azimuth']} deg until the visit", en["park"])]:
        pr = project(fleet, tid, mode, visit, runs=runs)
        p = pr["p_fail_by"](visit)
        lost_kwh = en["track"] - kwh
        if mode == "coast":  # stowing at 30 mph instead of 40 gives up the windiest afternoons (rare in Oct)
            lost_kwh += 0.02 * en["track"]
        cost = lost_kwh * price + p * fcost + (1 - p) * pcost
        opts.append({"key": mode, "title": label, "p_fail": round(p, 3), "energy_lost_kwh": round(lost_kwh, 1),
                     "energy_lost_usd": round(lost_kwh * price, 2), "visit_in_days": visit,
                     "expected_cost_usd": round(cost, 0)})
    p1 = project(fleet, tid, "track", 1, runs=runs)["p_fail_by"](1)
    emerg = p1 * fcost + (1 - p1) * (planned_cost(e, fix_key, parts_usd) - e.truck_roll_local / e.batch_size
                                      + e.truck_roll_regional)
    opts.append({"key": "emergency", "title": "Send a technician tomorrow (regional truck roll)", "p_fail": round(p1, 3),
                 "energy_lost_kwh": 0.0, "energy_lost_usd": 0.0, "visit_in_days": 1,
                 "expected_cost_usd": round(emerg, 0)})
    rec = min(opts, key=lambda o: o["expected_cost_usd"])
    return {"tower_id": tid, "diagnosis": dx, "fix": {"key": fix_key, "title": title, "parts": parts,
            "parts_usd": parts_usd, "new_drive": new_drive}, "route": route, "visit_in_days": visit,
            "energy": {k: v for k, v in en.items() if not isinstance(v, np.ndarray)},
            "failure_cost_usd": round(fcost, 0), "planned_cost_usd": round(pcost, 0),
            "options": opts, "recommendation": rec, "economics": asdict(e)}
