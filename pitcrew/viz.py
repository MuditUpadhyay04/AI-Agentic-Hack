"""The console's charts (matplotlib): one quiet grey, one accent, walls in red, the safe target in green."""
from __future__ import annotations

import math

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker  # noqa: E402,F401
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from . import mill as M  # noqa: E402

INK, QUIET, GRID = "#15151E", "#6B6E7B", "#EFEFF3"
ACCENT, WALL, SAFE, WARN = "#2E5BD8", "#E10600", "#00A651", "#C26A00"

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": GRID, "axes.labelcolor": INK,
    "xtick.color": QUIET, "ytick.color": QUIET, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False, "axes.titleweight": "bold", "axes.titlesize": 11,
    "axes.titlelocation": "left", "figure.dpi": 110,
})


def _fig(w=7.2, h=3.4):
    fig, ax = plt.subplots(figsize=(w, h))
    fig.subplots_adjust(left=0.09, right=0.97, top=0.86, bottom=0.15)
    return fig, ax


# ------------------------------------------------------------------ mill
def mill_signals(rows: list[dict], now: int, title: str = "", setpoint_kw: float | None = None) -> plt.Figure:
    df = pd.DataFrame(rows)
    df = df[df.part <= now]
    fig, ax = _fig(7.2, 3.0)
    fig.subplots_adjust(top=0.95, bottom=0.17)
    ax.axhspan(8.1, 9.0, color=WALL, alpha=0.07, lw=0)
    ax.axhline(9.0, color=WALL, lw=1.3, ls="--")
    ax.text(df.part.min() + 0.2, 9.1, "PWF limit 9.0 kW", color=WALL, fontsize=8.5)
    ax.plot(df.part, df.power_w / 1000, color=INK, lw=2)
    onset = df[df.creeping].part.min() if df.creeping.any() else None
    if onset is not None and not math.isnan(onset):
        ax.axvline(onset - 0.5, color=QUIET, lw=1, ls=":")
        ax.text(onset - 0.7, 5.25, "new steel lot", color=QUIET, fontsize=8.5, ha="right")
    last = df.iloc[-1]
    if setpoint_kw is not None:
        ax.plot([last.part, last.part + 2], [last.power_w / 1000, setpoint_kw], color=SAFE, lw=2)
        ax.text(last.part + 2, setpoint_kw - 0.35, f"setpoint {setpoint_kw:.1f}", color=SAFE, fontsize=8.5, ha="right")
    elif last.power_w / 1000 > 8.1:
        ax.scatter([last.part], [last.power_w / 1000], s=40, color=WALL, zorder=5, edgecolor="white")
        head = 100 * (9000 - last.power_w) / 9000
        ax.annotate(f"now · {head:.0f}% from limit", xy=(last.part, last.power_w / 1000),
                    xytext=(last.part - 0.6, 7.3), ha="right", fontsize=8.5, color=WALL, fontweight="bold",
                    arrowprops=dict(arrowstyle="-", color=WALL, lw=0.8))
    ax.set_ylim(5.0, 9.6)
    ax.set_xlim(df.part.min() - 0.5, max(df.part.max() + 3, 20))
    ax.set_xlabel("part number (4 min per part)")
    ax.set_ylabel("kW")
    if title:
        ax.set_title(title)
    return fig


def envelope(state: dict, lc: dict | None, parts_ahead: int = 30) -> plt.Figure:
    """Safe operating envelope in speed x torque: the walls close in as the tool wears."""
    fig, ax = _fig(7.2, 4.2)
    rpm = np.linspace(1250, 1700, 200)
    w = rpm * 2 * math.pi / 60
    t_hi, t_lo = M.PWF_MAX_W / w, M.PWF_MIN_W / w
    wear_now = state["wear"]
    wear_win = wear_now + M.WEAR_PER_PART[state["variant"]] * parts_ahead
    osf_now = M.OSF_LIMIT[state["variant"]] / wear_now
    osf_win = M.OSF_LIMIT[state["variant"]] / wear_win
    ax.fill_between(rpm, 30, np.minimum(t_hi, osf_win), where=rpm >= M.HDF_RPM, color=SAFE, alpha=0.08)
    ax.plot(rpm, t_hi, color=WALL, lw=1.6)
    ax.text(1690, 9000 / (1690 * 2 * math.pi / 60) - 2.2, "power ceiling 9 kW", color=WALL, fontsize=8.5, ha="right")
    if osf_now < 66:  # only draw it when it is on the chart; off-chart labels stretch the figure
        ax.axhline(osf_now, color=WALL, lw=1.0, ls=":", alpha=0.6)
        ax.text(1690, osf_now + 0.4, f"overstrain now ({osf_now:.0f} Nm)", color=WALL, fontsize=8.5, ha="right")
    ax.axhline(osf_win, color=WALL, lw=1.6)
    ax.text(1690, osf_win - 1.3, f"overstrain at shift change ({osf_win:.0f} Nm)", color=WALL, fontsize=8.5, ha="right")
    if state.get("d_temp", 10) < M.HDF_DT_K:
        ax.axvspan(1250, M.HDF_RPM, color=WALL, alpha=0.07)
        ax.text(1262, 33, "heat wall live\n(gap < 8.6 K)", color=WALL, fontsize=8.5)
    creep_end = state["torque"] + state["creep"] * parts_ahead
    ax.annotate("", xy=(state["rpm"], min(creep_end, 66)), xytext=(state["rpm"], state["torque"]),
                arrowprops=dict(arrowstyle="->", color=QUIET, lw=1, ls="--"))
    ax.scatter([state["rpm"]], [state["torque"]], s=70, color=WARN, zorder=5)
    ax.text(state["rpm"] + 10, state["torque"] - 2.6, "now: 56 Nm, 8.8 kW" if abs(state["torque"] - 56) < 0.5
            else f"now: {state['torque']:.0f} Nm", fontsize=9, color=INK)
    if lc:
        t_end = lc["torque"] + state["creep"] * parts_ahead
        ax.plot([lc["rpm"], lc["rpm"]], [lc["torque"], t_end], color=SAFE, lw=1.4, ls="--")
        ax.scatter([lc["rpm"]], [t_end], s=30, color=SAFE, zorder=6)
        ax.text(lc["rpm"] + 8, t_end - 0.4, f"at shift change: {t_end:.0f} Nm, inside both walls", color=SAFE,
                fontsize=8.5, ha="left", va="top")
        ax.scatter([lc["rpm"]], [lc["torque"]], s=80, color=SAFE, zorder=6, marker="D")
        ax.annotate("", xy=(lc["rpm"], lc["torque"]), xytext=(state["rpm"], state["torque"]),
                    arrowprops=dict(arrowstyle="->", color=SAFE, lw=1.8))
        ax.text(lc["rpm"] - 8, lc["torque"] - 2.2, f"Lift & Coast: {lc['rpm']:.0f} rpm, {lc['torque']:.0f} Nm",
                color=SAFE, fontsize=9, ha="right", fontweight="bold")
    ax.set_xlim(1250, 1700)
    ax.set_ylim(30, 68)
    ax.set_xlabel("spindle speed (rpm)")
    ax.set_ylabel("torque (Nm)")
    fig.subplots_adjust(top=0.96)
    return fig


# ------------------------------------------------------------------ towers
def fleet_map(today: pd.DataFrame, flagged: list[dict], focus: int | None = None) -> plt.Figure:
    fig, ax = _fig(7.2, 3.3)
    ax.grid(False)
    ax.set_xticks([])
    ax.set_yticks([])
    sites = list(dict.fromkeys(today["site"]))
    flag = {f["tower_id"]: f for f in flagged}
    x0 = 0
    for s in sites:
        ids = [int(i) for i in today.index[today.site == s]]
        cols = 6 if len(ids) > 12 else 4
        for k, tid in enumerate(ids):
            x, y = x0 + (k % cols), -(k // cols)
            c = QUIET
            if tid in flag:
                c = WALL if flag[tid]["detector"] in ("backlash", "acoustic", "grease_water") else WARN
            ax.scatter([x], [y], s=150 if tid != focus else 260, color=c, alpha=0.9 if tid in flag else 0.35,
                       edgecolor=ACCENT if tid == focus else "white", linewidth=2.2 if tid == focus else 0.8)
            if tid in flag or tid == focus:
                ax.text(x, y - 0.42, str(tid), ha="center", va="top", fontsize=8, color=INK)
        ax.text(x0 - 0.4, 0.75, s, fontsize=9, color=INK, fontweight="bold")
        x0 += cols + 1.5
    ax.set_xlim(-0.8, x0 - 1)
    ax.set_ylim(-3.9, 1.2)
    ax.set_title(f"Fleet today: {len(flagged)} of {len(today)} towers flagged (orange: friction, red: drive damage)")
    return fig


def tower_indicator(series: dict, alarm: float, fail_at: float, label: str, rul: dict | None) -> plt.Figure:
    fig, ax = _fig()
    d = pd.to_datetime(series["date"])
    v = np.array(series["value"], dtype=float)
    ax.plot(d, v, color=ACCENT, lw=2)
    ax.axhline(alarm, color=WARN, lw=1.1, ls="--")
    ax.text(d[-1], alarm, "alarm ", color=WARN, fontsize=8.5, va="bottom", ha="right")
    ax.axhline(fail_at, color=WALL, lw=1.3)
    ax.text(d[0], fail_at, " failure (calm air)", color=WALL, fontsize=8.5, va="bottom")
    if rul and rul.get("p50") is not None and rul["p50"] < 200:
        end = d[-1] + pd.Timedelta(days=rul["p50"])
        ax.plot([d[-1], end], [v[-1], fail_at], color=QUIET, ls=":", lw=1.4)
        if rul.get("p10") is not None and rul.get("p90") is not None:
            ax.axvspan(d[-1] + pd.Timedelta(days=rul["p10"]), d[-1] + pd.Timedelta(days=min(rul["p90"], 200)),
                       color=WALL, alpha=0.06)
    lo = min(v.min(), alarm) * 0.97
    ax.set_ylim(lo, fail_at + (fail_at - lo) * 0.12)
    ax.set_title(label)
    fig.autofmt_xdate()
    return fig


def option_risk(options: list[dict], visit_days: int) -> plt.Figure:
    fig, ax = _fig(7.2, 2.9)
    short = {"track": "Keep tracking", "coast": "Coast (15 deg steps, stow 30 mph)", "emergency": "Technician tomorrow"}
    names = [short.get(o["key"], o["title"]) for o in options]
    cost = [o["expected_cost_usd"] for o in options]
    best = int(np.argmin(cost))
    y = np.arange(len(options))[::-1]
    ax.barh(y, cost, color=[SAFE if i == best else QUIET for i in range(len(options))], alpha=0.85)
    for yi, o, c in zip(y, options, cost):
        ax.text(c, yi, f"  \\${c:,.0f}  (risk {100 * o['p_fail']:.0f}%, {o['energy_lost_kwh']:.0f} kWh)",
                va="center", fontsize=8.5, color=INK)
    ax.set_yticks(y)
    ax.set_yticklabels(names, fontsize=8.5)
    ax.set_xlim(0, max(cost) * 1.55)
    ax.set_xlabel(f"expected cost until the visit in {visit_days} days (USD)")
    ax.set_title("Park & Price: every option priced the same way")
    fig.subplots_adjust(left=0.33)
    return fig


def energy_window(daily: pd.DataFrame, start, days: int, park_az: int) -> plt.Figure:
    fig, ax = _fig(7.2, 2.9)
    idx = pd.date_range(start, periods=days, freq="D")
    sub = daily.reindex(idx.strftime("%Y-%m-%d"))
    ax.plot(idx, sub["track"], color=QUIET, lw=2, label="tracking")
    ax.plot(idx, sub["step15"], color=ACCENT, lw=1.5, ls="--", label="15 deg steps")
    ax.plot(idx, sub[f"park_{park_az:03d}"], color=WARN, lw=2, label=f"parked at {park_az} deg")
    ax.set_ylabel("kWh per tower per day")
    ax.legend(frameon=False, fontsize=8.5, loc="lower left")
    ax.set_title("Energy per option (Shadow Calculator field model, TR-08, Dallas, clear sky)")
    fig.autofmt_xdate()
    return fig


# ------------------------------------------------------------------ improve
def lots_chart(lots: list[dict]) -> plt.Figure:
    fig, ax = _fig(7.2, 3.0)
    fig.subplots_adjust(bottom=0.2)
    df = pd.DataFrame(lots)
    y = np.arange(len(df))[::-1]
    worst = df["rate_per_tower_year"].idxmax()
    for yi, (i, r) in zip(y, df.iterrows()):
        c = WALL if i == worst else QUIET
        ax.plot([r.rate_lo90, r.rate_hi90], [yi, yi], color=c, lw=2, alpha=0.6)
        ax.scatter([r.rate_per_tower_year], [yi], color=c, s=60, zorder=3)
        ax.text(r.rate_hi90, yi, f"  {r.rate_per_tower_year:.2f} ({r.failures} failures / {r.tower_years} tower-yr)",
                va="center", fontsize=8.5)
    ax.set_yticks(y)
    ax.set_yticklabels([f"lot {x}" for x in df["lot"]])
    ax.set_xlim(0, df["rate_hi90"].max() * 1.8)
    ax.set_xlabel("drive failures per tower-year (dot) with 90% interval")
    ax.set_title("Kaizen: supplier lot B fails far more often")
    return fig


def futures_chart(slots: list[dict], crew_value: float) -> plt.Figure:
    fig, ax = _fig(7.2, 3.0)
    df = pd.DataFrame(slots)
    rows = [("Crew acting on today's sensors", crew_value, 0.0)] + [
        (r["slot"], r["value_usd_per_tower_year"], r["unit_usd"]) for _, r in df.iterrows()]
    y = np.arange(len(rows))[::-1]
    for yi, (name, v, cost) in zip(y, rows):
        ax.barh(yi, v, color=SAFE if cost == 0 else ACCENT, alpha=0.85)
        ax.text(v, yi, f"  \\${v:,.0f}/tower-yr" + (f"  (hardware \\${cost:,.0f})" if cost else "  (software only)"),
                va="center", fontsize=8.5)
    ax.set_yticks(y)
    ax.set_yticklabels([r[0] for r in rows], fontsize=8.5)
    ax.set_xlim(0, max(r[1] for r in rows) * 2.1)
    ax.set_xlabel("failures turned into planned repairs, USD per tower-year")
    ax.set_title("Sensor Futures: what to put on the next tower")
    fig.subplots_adjust(left=0.42)
    return fig
