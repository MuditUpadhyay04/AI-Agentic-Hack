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


def peer_compare(signals: list[dict]) -> plt.Figure:
    """One row per signal: the peers' range (bar), their median (tick) and this product (dot), on a shared
    'z vs peers' scale so different units sit on one chart."""
    fig, ax = _fig(7.2, 0.62 * len(signals) + 0.9)
    fig.subplots_adjust(left=0.30, right=0.95, top=0.92, bottom=0.22)
    for i, s in enumerate(signals):
        y = len(signals) - 1 - i
        ax.barh(y, 4, left=-2, height=0.36, color=GRID, zorder=1)
        ax.plot([0, 0], [y - 0.24, y + 0.24], color=QUIET, lw=1.4, zorder=2)
        z = max(min(s["z"], 7.5), -2.5)
        color = WALL if s["z"] > 3 else WARN if s["z"] >= 2 else SAFE
        ax.scatter([z], [y], s=70, color=color, zorder=3, edgecolor="white")
        ax.text(z + 0.25, y + 0.18, f"{s['value']:g} (peers {s['peer_median']:g})", fontsize=8.5, color=INK)
    ax.axvline(2, color=WARN, lw=1, ls=":")
    ax.axvline(3, color=WALL, lw=1, ls="--")
    ax.set_yticks(range(len(signals)))
    ax.set_yticklabels([s["label"] for s in reversed(signals)])
    ax.set_xlim(-2.5, 8)
    ax.set_xlabel("distance from healthy peers (robust |z|) · grey = peers' typical range")
    ax.grid(axis="y", visible=False)
    return fig
