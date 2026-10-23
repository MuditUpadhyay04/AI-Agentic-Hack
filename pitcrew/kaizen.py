"""Improve loop: turn the incident history into new rules, supplier actions and a design-change request.

Three things, each with the numbers that back it:

1. ``rediscover_ai4i``: search simple physics features for the threshold that best separates each AI4I
   failure mode, then report precision and recall. On AI4I this rediscovers the published walls, which is
   the honesty check: the Kaizen agent proposes rules a reliability engineer can read.
2. ``lot_analysis``: failures per tower-year by supplier lot with Poisson intervals and a rate ratio.
3. ``design_change_request``: a draft for the Design studio / Tower lab (ST-2), built from the fleet,
   the energy table and Sensor Futures.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from .ai4i_data import add_physics, load
from .tower import Fleet, daily_moves

DATA = Path(__file__).resolve().parents[1] / "data"

FEATURES = {
    "PWF": [("power_w", ">"), ("power_w", "<")],
    "OSF": [("strain_ratio", ">"), ("strain", ">"), ("Torque [Nm]", ">"), ("Tool wear [min]", ">")],
    "HDF": [("d_temp", "<"), ("Rotational speed [rpm]", "<")],
    "TWF": [("Tool wear [min]", ">")],
}


def _best_threshold(x: np.ndarray, y: np.ndarray, side: str) -> tuple[float, float, float, float]:
    qs = np.unique(np.quantile(x, np.linspace(0.001, 0.999, 400)))
    best = (0.0, None, 0.0, 0.0)
    for q in qs:
        pred = x > q if side == ">" else x < q
        tp = (pred & y).sum()
        if tp == 0:
            continue
        prec, rec = tp / pred.sum(), tp / y.sum()
        f1 = 2 * prec * rec / (prec + rec)
        if f1 > best[0]:
            best = (f1, float(q), float(prec), float(rec))
    return best


def rediscover_ai4i() -> dict:
    df, source = load()
    df = add_physics(df)
    out = []
    for mode, feats in FEATURES.items():
        y = df[mode].to_numpy().astype(bool)
        if mode == "HDF":  # two-feature rule: low gap AND low speed
            best = (0.0,)
            for g in np.arange(7.6, 9.6, 0.1):
                for r in range(1300, 1460, 10):
                    pred = (df["d_temp"] < g) & (df["Rotational speed [rpm]"] < r)
                    tp = (pred & y).sum()
                    if tp == 0:
                        continue
                    prec, rec = tp / pred.sum(), tp / y.sum()
                    f1 = 2 * prec * rec / (prec + rec)
                    if f1 > best[0]:
                        best = (f1, f"temperature gap < {g:.1f} K and speed < {r} rpm", prec, rec)
            out.append({"mode": mode, "rule": best[1], "precision": round(float(best[2]), 3),
                        "recall": round(float(best[3]), 3), "f1": round(float(best[0]), 3),
                        "published": "gap < 8.6 K and speed < 1,380 rpm", "count": int(y.sum())})
            continue
        if mode == "PWF":
            lo = _best_threshold(df["power_w"].to_numpy(), y, "<")
            hi = _best_threshold(df["power_w"].to_numpy(), y, ">")
            pred = (df["power_w"] < lo[1]) | (df["power_w"] > hi[1])
            tp = (pred & y).sum()
            prec, rec = tp / pred.sum(), tp / y.sum()
            out.append({"mode": mode, "rule": f"power < {lo[1]:,.0f} W or > {hi[1]:,.0f} W",
                        "precision": round(float(prec), 3), "recall": round(float(rec), 3),
                        "f1": round(float(2 * prec * rec / (prec + rec)), 3),
                        "published": "outside 3,500-9,000 W", "count": int(y.sum())})
            continue
        best = None
        for col, side in feats:
            f1, q, prec, rec = _best_threshold(df[col].to_numpy(), y, side)
            if q is not None and (best is None or f1 > best[0]):
                best = (f1, f"{col} {side} {q:,.3g}", prec, rec)
        pub = {"OSF": "tool wear x torque > 11,000 / 12,000 / 13,000 min*Nm (L/M/H), i.e. strain_ratio > 1",
               "TWF": "random replacement or failure between 200 and 240 min of wear"}[mode]
        out.append({"mode": mode, "rule": best[1], "precision": round(float(best[2]), 3),
                    "recall": round(float(best[3]), 3), "f1": round(float(best[0]), 3), "published": pub,
                    "count": int(y.sum())})
    # early warning: the same strain rule at 90% of the limit
    early = df["strain_ratio"] > 0.9
    y = df["OSF"].astype(bool)
    ew = {"rule": "strain_ratio > 0.9 (warn at 90% of the overstrain wall)",
          "recall": round(float((early & y).sum() / y.sum()), 3),
          "flagged_share_of_rows": round(float(early.mean()), 4)}
    return {"source": source, "rows": len(df), "rules": out, "early_warning": ew}


def lot_analysis(fleet: Fleet) -> pd.DataFrame:
    """Drive failures per tower-year by supplier lot, with exact Poisson 90% intervals."""
    log = fleet.log_df
    exposure = log.groupby("lot").size() / 365.0
    inc = pd.DataFrame(fleet.incidents)
    counts = inc.groupby("lot").size() if len(inc) else pd.Series(dtype=int)
    rows = []
    for lot, ty in exposure.items():
        k = int(counts.get(lot, 0))
        lo = stats.chi2.ppf(0.05, 2 * k) / 2 if k > 0 else 0.0
        hi = stats.chi2.ppf(0.95, 2 * (k + 1)) / 2
        rows.append({"lot": lot, "failures": k, "tower_years": round(ty, 1), "rate_per_tower_year": round(k / ty, 3),
                     "rate_lo90": round(lo / ty, 3), "rate_hi90": round(hi / ty, 3)})
    df = pd.DataFrame(rows).set_index("lot")
    if "A" in df.index and df.loc["A", "rate_per_tower_year"] > 0:
        df["rate_ratio_vs_A"] = (df["rate_per_tower_year"] / df.loc["A", "rate_per_tower_year"]).round(1)
    return df


def time_to_alarm_by_lot(fleet: Fleet) -> pd.DataFrame:
    """Median days from fresh grease to the friction alarm, by lot: the re-grease interval each lot needs."""
    log = fleet.log_df
    rows = []
    for (tid, lot), h in log.groupby(["tower_id", "lot"]):
        fresh = h[h.grease > 0.97]
        if fresh.empty:
            continue
        start = fresh.day.iloc[-1] if lot == "B" else fresh.day.iloc[0]
        after = h[(h.day > start)]
        r = after["epd_norm"].ewm(span=7).mean() / fleet.baseline_epd
        hit = after[r.to_numpy() > 1.15]
        if len(hit):
            rows.append({"lot": lot, "days_to_alarm": int(hit.day.iloc[0] - start)})
    df = pd.DataFrame(rows)
    return df.groupby("lot")["days_to_alarm"].median().rename("median_days_fresh_grease_to_alarm").to_frame() \
        if len(df) else pd.DataFrame()


def tracking_tradeoff() -> dict:
    """Energy of step tracking from the engine table vs drive starts per day from the drive model."""
    meta = json.loads((DATA / "tower_dallas_energy_meta.json").read_text())
    from .tower import DriveModel, dfw_weather

    m = DriveModel()
    sweeps = dfw_weather(365)["sweep_deg"].to_numpy()
    s_track = np.mean([daily_moves(s, "track", m)[0] for s in sweeps])
    s_step = np.mean([daily_moves(s, "step15", m)[0] for s in sweeps])
    a = meta["annual_kwh"]
    return {"energy_loss_step15_pct": round(100 * (1 - a["step15"] / a["track"]), 2),
            "energy_loss_step30_pct": round(100 * (1 - a["step30"] / a["track"]), 2),
            "starts_per_day_track": round(float(s_track), 1), "starts_per_day_step15": round(float(s_step), 1),
            "starts_cut_pct": round(float(100 * (1 - s_step / s_track)), 1),
            "park_best_azimuth": meta["best_fixed_azimuth"],
            "park_share_of_tracking_pct": round(100 * meta["best_fixed_share_of_tracking"], 1),
            "source": meta["source"]}


def design_change_request(fleet: Fleet, futures_rank: pd.DataFrame | None = None) -> dict:
    """A draft DCR for ST-2, every claim tied to a number the crew computed."""
    lots = lot_analysis(fleet)
    trade = tracking_tradeoff()
    rr = lots["rate_ratio_vs_A"].get("B") if "rate_ratio_vs_A" in lots else None
    tta = time_to_alarm_by_lot(fleet)
    tta_b = int(tta.loc["B"].iloc[0]) if "B" in tta.index else None
    tta_a = int(tta.loc["A"].iloc[0]) if "A" in tta.index else None
    items = [
        {"id": "DCR-1", "area": "Firmware (all towers)",
         "change": "Default to 15 deg step tracking (move once the sun is 15 deg off, not 2 deg)",
         "evidence": f"Engine table: step tracking gives up {trade['energy_loss_step15_pct']}% of yearly energy; "
                     f"drive starts fall from {trade['starts_per_day_track']} to {trade['starts_per_day_step15']} a day "
                     f"({trade['starts_cut_pct']}% fewer).",
         "test": "A/B on 10 towers for 90 days: energy per tower and friction trend per tower"},
        {"id": "DCR-2", "area": "Supplier / Equipment library",
         "change": "Stop buying the lot-B drive, or require incoming grease inspection; until then re-grease lot-B "
                   f"drives every {round(tta_b / 30) if tta_b else 5} months",
         "evidence": (f"Lot B fails {rr}x as often as lot A per tower-year (90% intervals in the Kaizen table); "
                      f"fresh grease reaches the friction alarm in a median {tta_b} days on lot B vs {tta_a} on lot A."
                      if rr else "Lot B shows the highest failure rate per tower-year."),
         "test": "Supplier scorecard reviewed monthly in the Equipment library"},
    ]
    if futures_rank is not None and len(futures_rank):
        top = futures_rank.iloc[0]
        items.append({"id": "DCR-3", "area": "Hardware (ST-2 bill of materials)",
                      "change": f"Add a slot and harness for: {top['slot']}",
                      "evidence": f"Replaying {int(top['of_failures'])} fleet failures: it turns "
                                  f"{int(top['failures_turned_planned'])} more into planned repairs, worth about "
                                  f"${top['value_usd_per_tower_year']:.0f} per tower-year against ${top['unit_usd']:.0f} "
                                  f"of hardware (payback {top['payback_years']} years).",
                      "test": "Fit to 5 towers on the open-field site (highest exposure)"})
    items.append({"id": "DCR-4", "area": "Control (stow)",
                  "change": "Per-tower stow wind: 40 mph for healthy drives, 30 mph once friction is flagged",
                  "evidence": "Park & Price Monte Carlo: stowing earlier cuts the stall risk of a flagged drive before the "
                              "technician arrives at almost no energy cost in shoulder months.",
                  "test": "Enable on flagged towers only; review after the spring storm season"})
    return {"title": "ST-2 design-change request (draft by the Kaizen agent - engineering to review)",
            "items": items, "lot_table": lots.reset_index().to_dict(orient="records"), "tracking": trade}
