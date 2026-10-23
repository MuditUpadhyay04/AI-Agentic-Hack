"""The milling machine: AI4I 2020's published failure rules as walls, and Lift & Coast.

AI4I 2020 (UCI dataset 601) generates its failures from physical rules, so a failure is a wall in
operating space that a judge can check by hand:

- PWF power failure: torque x angular speed outside 3,500-9,000 W
- OSF overstrain: tool wear x torque above 11,000 / 12,000 / 13,000 min*Nm for L / M / H products
- HDF heat dissipation: speed under 1,380 rpm while process minus air temperature is under 8.6 K
- TWF tool wear: the tool is replaced or fails between 200 and 240 min of wear

``margins`` gives the headroom to each wall, ``parts_until_wall`` projects a torque creep forward, and
``lift_and_coast`` finds the fastest operating point that still reaches the planned stop with a margin.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

OSF_LIMIT = {"L": 11000.0, "M": 12000.0, "H": 13000.0}  # tool wear x torque, min*Nm
WEAR_PER_PART = {"L": 2.0, "M": 3.0, "H": 5.0}  # min of tool wear added per part (AI4I)
PWF_MIN_W, PWF_MAX_W = 3500.0, 9000.0
HDF_RPM, HDF_DT_K = 1380.0, 8.6
TWF_WINDOW = (200.0, 240.0)

WALL_NAMES = {
    "PWF_high": "Power ceiling (9.0 kW)",
    "PWF_low": "Power floor (3.5 kW)",
    "OSF": "Overstrain (wear x torque)",
    "HDF": "Heat dissipation (<1,380 rpm, gap <8.6 K)",
    "TWF": "Tool-wear window opens (200 min)",
}


def omega(rpm: float) -> float:
    return rpm * 2.0 * math.pi / 60.0


def margins(rpm: float, torque: float, wear: float, d_temp: float, variant: str = "L") -> dict:
    """Headroom left to each wall as a fraction (<= 0 means that wall is crossed)."""
    p = torque * omega(rpm)
    return {
        "PWF_high": (PWF_MAX_W - p) / PWF_MAX_W,
        "PWF_low": (p - PWF_MIN_W) / PWF_MIN_W,
        "OSF": (OSF_LIMIT[variant] - wear * torque) / OSF_LIMIT[variant],
        "HDF": 1.0 if (rpm >= HDF_RPM or d_temp >= HDF_DT_K) else -1.0,
        "TWF": (TWF_WINDOW[0] - wear) / TWF_WINDOW[0],
    }


def parts_until_wall(rpm: float, torque: float, wear: float, d_temp: float, creep: float = 0.3,
                     variant: str = "L", horizon: int = 300) -> tuple[int, list]:
    """Parts until the first wall is crossed, with torque creeping ``creep`` Nm per part."""
    dwear = WEAR_PER_PART[variant]
    for n in range(horizon):
        m = margins(rpm, torque + creep * n, wear + dwear * n, d_temp, variant)
        hit = [k for k, v in m.items() if v <= 0]
        if hit:
            return n, hit
    return horizon, []


@dataclass
class Option:
    key: str
    title: str
    rpm: float | None
    torque: float | None
    parts_to_wall: int | None
    nearest_wall: str | None
    p_fail_before_window: float
    cost_usd: float
    detail: str
    margins_at_window: dict = field(default_factory=dict)


def lift_and_coast(torque: float, wear: float, d_temp: float, parts_needed: int, min_margin: float = 0.08,
                   creep: float = 0.3, variant: str = "L", rpm_range=(1380, 1601, 20), max_cut: int = 16):
    """Fastest operating point (highest cutting power) that reaches the window with ``min_margin`` left."""
    dwear = WEAR_PER_PART[variant]
    best = None
    for rpm in range(*rpm_range):
        for t in [torque - k for k in range(max_cut)]:
            n, _ = parts_until_wall(rpm, t, wear, d_temp, creep, variant)
            if n <= parts_needed:
                continue
            m = margins(rpm, t + creep * parts_needed, wear + dwear * parts_needed, d_temp, variant)
            worst = min(v for k, v in m.items() if k != "TWF")
            if worst < min_margin:
                continue
            power = t * omega(rpm)
            if best is None or power > best["power_w"]:
                best = {"rpm": rpm, "torque": float(t), "power_w": round(power), "parts_to_wall": n,
                        "margins_at_window": {k: round(v, 3) for k, v in m.items()}}
    return best


def p_fail_before(rpm: float, torque: float, wear: float, d_temp: float, parts_needed: int, creep: float,
                  variant: str = "L", creep_sd: float = 0.08, runs: int = 400, seed: int = 7) -> tuple[float, list]:
    """Monte Carlo over the creep rate: share of runs that cross a wall before ``parts_needed`` parts."""
    rng = np.random.default_rng(seed)
    hits, ns = 0, []
    for c in rng.normal(creep, creep_sd, runs).clip(min=0.0):
        n, _ = parts_until_wall(rpm, torque, wear, d_temp, float(c), variant, horizon=parts_needed + 60)
        ns.append(n)
        hits += n < parts_needed
    return hits / runs, ns


@dataclass
class MillEconomics:
    """Assumptions to replace with the plant's own numbers (all USD)."""

    contribution_per_hour: float = 6000.0  # lost margin per hour the cell is down (assumption)
    cycle_min: float = 4.0  # minutes per part
    planned_tool_change_min: float = 15.0  # at shift change, crew already there
    midshift_tool_change_min: float = 45.0  # stop now: find the setter, change, re-qualify
    unplanned_failure_min: float = 240.0  # crash, scrap, spindle check
    scrap_usd: float = 800.0
    insert_usd: float = 42.0


def mill_options(state: dict, econ: MillEconomics = MillEconomics()) -> list[Option]:
    """Price stop-now, run-as-is and Lift & Coast for the current machine state."""
    rpm, torque, wear = state["rpm"], state["torque"], state["wear"]
    d_temp, creep, variant, need = state["d_temp"], state["creep"], state["variant"], state["parts_to_window"]
    per_min = econ.contribution_per_hour / 60.0
    fail_cost = econ.unplanned_failure_min * per_min + econ.scrap_usd
    out = []
    n, walls = parts_until_wall(rpm, torque, wear, d_temp, creep, variant)
    p, _ = p_fail_before(rpm, torque, wear, d_temp, need, creep, variant)
    out.append(Option("run_as_is", "Run as-is", rpm, torque, n, walls[0] if walls else None, p,
                      round(p * fail_cost + econ.planned_tool_change_min * per_min * (1 - p)),
                      f"Crosses {WALL_NAMES.get(walls[0], walls[0]) if walls else 'no wall'} in ~{n} parts "
                      f"(~{round(n * econ.cycle_min)} min)."))
    out.append(Option("stop_now", "Stop now", None, None, None, None, 0.0,
                      round(econ.midshift_tool_change_min * per_min + econ.insert_usd),
                      f"Mid-shift tool change, ~{econ.midshift_tool_change_min:.0f} min of lost output."))
    lc = lift_and_coast(torque, wear, d_temp, need, creep=creep, variant=variant)
    if lc:
        p2, _ = p_fail_before(lc["rpm"], lc["torque"], wear, d_temp, need, creep, variant)
        slow = 1.0 - lc["power_w"] / (torque * omega(rpm))  # output lost while coasting (power as a proxy)
        coast_cost = slow * need * econ.cycle_min * per_min
        wall_n, wall_k = parts_until_wall(lc["rpm"], lc["torque"], wear, d_temp, creep, variant)
        out.append(Option("lift_and_coast", "Lift & Coast", lc["rpm"], lc["torque"], wall_n,
                          wall_k[0] if wall_k else None, p2,
                          round(p2 * fail_cost + coast_cost + econ.planned_tool_change_min * per_min
                                + econ.insert_usd),
                          f"{lc['rpm']} rpm and feed cut to {lc['torque']:.0f} Nm ({lc['power_w'] / 1000:.1f} kW): "
                          f"nearest wall {wall_n} parts away vs {need} to the shift change; tool change at "
                          f"shift change.", lc["margins_at_window"]))
    return out


def creep_scenario(steps: int = 60, start_wear: float = 120.0, onset: int = 20, seed: int = 3) -> list[dict]:
    """A normal window, then a harder steel lot: torque creeps 0.3 Nm per part from ``onset``."""
    rng = np.random.default_rng(seed)
    rows, wear, torque = [], start_wear - 2.0 * onset, 40.0
    for i in range(steps):
        creeping = i >= onset
        torque = (56.0 + 0.3 * (i - onset) if creeping and i > onset else (40.0 if not creeping else 56.0))
        t = torque + rng.normal(0, 0.4)
        rpm = 1500 + rng.normal(0, 4)
        air = 300.5 + rng.normal(0, 0.1)
        proc = air + (10.2 if not creeping else 8.2) + rng.normal(0, 0.1)  # gap closes with the hard lot
        rows.append({"part": i, "rpm": rpm, "torque": t, "power_w": t * omega(rpm), "wear": wear,
                     "strain": wear * t, "air_k": air, "process_k": proc, "creeping": creeping})
        wear += 2.0
    return rows
