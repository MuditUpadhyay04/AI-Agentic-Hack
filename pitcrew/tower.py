"""A fleet of Janta towers on worm-gear slew drives: what wears, what the controller can see, and when.

The model is deliberately small and every coefficient lives in ``DriveModel`` so the team can argue with
it (and so the Kaizen loop can refit it from field data). It follows the field literature the playbook
cites:

- Grease breaks down with time, heat and churning (faster for a bad lot, in steps after water gets past
  a seal). Friction rises, so the motor needs more energy per degree and more peak current per move
  (rising minimum drive current flags gearbox wear: patent US11588425). A drive stalls when friction plus
  wind load exceed what the motor can turn, or seizes when the grease is gone.
- Worm and gear wear grow backlash; a nightly reversal test sees it as the encoder counts the motor turns
  before the current rises (patent US10498193). With a 1,024-pulse encoder on the motor and an 85:1
  worm, one output degree is about 242 counts.
- A slewing-bearing defect grows like the NASA IMS run-to-failure curves (slow, then fast). The output
  turns at under 1.5 rpm, so it is seen first on the worm/motor side, and earliest by acoustic emission.

What the TR-08 controller sees today (an assumption to confirm with engineering): motor energy and current
per move, the motor encoder, ambient temperature and site wind. Vibration, grease condition, acoustic
emission, a drive torque sensor and an output encoder are *future hardware slots*: simulated here as
ground truth so ``futures.py`` can price what each would have caught.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

COUNTS_PER_OUTPUT_DEG = 85 * 1024 / 360.0  # worm ratio x motor encoder pulses / 360 = 241.8
TODAY = "2026-10-23"
MODES = ("track", "step15", "stow_early", "coast", "park")  # coast = step15 + stow early


@dataclass
class DriveModel:
    """Every coefficient of the drive model (assumptions, labelled; Kaizen refits them from field data)."""

    grease_life_days: float = 2000.0  # e-folding life of healthy grease at 30 C with normal tracking
    bad_lot_life_factor: float = 0.30  # supplier lot B: grease ages ~3x faster
    heat_aging_per_c: float = 0.03  # +3% ageing per degC of drive temperature above 30 C
    churn_per_start: float = 0.006  # +0.6% ageing per daily start (normal tracking ~90 starts: +54%)
    regrease_days: int = 730  # re-grease every 24 months (TGB solar-drive guidance)
    friction_gain: float = 0.70  # energy per degree rises by this x (1 - grease)^1.5
    cold_viscosity_per_c: float = 0.006  # +0.6% energy per degC below 20 C
    wind_load_per_ms2: float = 0.0008  # energy per degree rises with wind speed squared (+25% at 40 mph)
    backlash0_deg: float = 0.12
    backlash_fail_deg: float = 0.50  # replace the drive above this (assumption)
    wear_per_start: float = 4.0e-7  # deg of backlash per start (shock, impact at reversal)
    wear_per_deg: float = 3.0e-8  # deg of backlash per degree travelled (sliding)
    wear_grease_mult: float = 4.0  # wear runs up to 5x faster on poor grease
    fretting_per_ms: float = 4.0e-6  # deg/day of backlash per m/s of wind while parked (holding, no grease film)
    stall_ratio: float = 1.50  # move energy per degree (incl. wind) at which the motor stalls
    seize_grease: float = 0.10
    bearing_rate: float = 0.028  # health index exp growth per day after onset (IMS-like)
    bearing_fail_hi: float = 6.0
    track_tolerance_deg: float = 2.0  # normal tracking moves when the sun is this far off
    stow_wind_ms: float = 17.9  # 40 mph: tracks up to this, stows above
    stow_early_factor: float = 0.75  # "stow earlier" option: 30 mph


@dataclass
class TowerState:
    tower_id: int
    site: str
    lot: str
    install_day: int = 0
    grease: float = 1.0
    backlash: float = 0.12
    bearing_hi: float = 0.0
    bearing_onset: int | None = None
    seal_leak_day: int | None = None
    wear_mult: float = 1.0  # loose bolts or misalignment multiply gear wear
    failed_day: int | None = None
    failure_mode: str | None = None


SITES = {
    "DFW warehouse roof": dict(exposure=1.15, towers=16),
    "Data center lot": dict(exposure=1.0, towers=20),
    "Open field, Ellis County": dict(exposure=1.30, towers=12),
}


def dfw_weather(days: int, seed: int = 11, end: str = TODAY) -> pd.DataFrame:
    """Daily weather shaped like DFW (synthetic until scripts/fetch_data.py pulls IEM ASOS for KDFW)."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range(end=end, periods=days, freq="D")
    doy = idx.dayofyear.to_numpy()
    t_mean = 19.5 - 10.5 * np.cos(2 * np.pi * (doy - 15) / 365.0) + rng.normal(0, 3.0, days)
    wind = np.clip(rng.weibull(2.0, days) * 5.0 + 0.6 * np.sin(2 * np.pi * (doy - 60) / 365.0), 0.5, None)
    gust = wind * rng.uniform(1.5, 2.1, days)
    storms = rng.random(days) < (0.025 + 0.03 * np.exp(-((doy - 120) / 40.0) ** 2))  # spring storm season
    gust[storms] += rng.uniform(6, 14, storms.sum())
    rain = rng.random(days) < 0.18 + storms * 0.6
    sweep = 124.0 + 112.0 * (0.5 - 0.5 * np.cos(2 * np.pi * (doy - 355) / 365.0))  # deg of azimuth per day
    return pd.DataFrame({"t_mean_c": t_mean, "wind_ms": wind, "gust_ms": gust, "storm": storms, "rain": rain,
                         "sweep_deg": sweep}, index=idx)


def daily_moves(sweep_deg: float, mode: str, m: DriveModel) -> tuple[float, float]:
    """(starts, degrees travelled) per day for a tracking mode; the night return counts as one start."""
    if mode == "park":
        return 0.0, 0.0
    step = 15.0 if mode in ("step15", "coast") else m.track_tolerance_deg
    return float(np.ceil(sweep_deg / step) + 1.0), 2.0 * float(sweep_deg)


def step_day(t: TowerState, day, exposure: float, mode: str, m: DriveModel, rng, d: int) -> dict:
    """Advance one tower by one day under ``mode``; return what the controller (and future slots) would log."""
    starts, degrees = daily_moves(day.sweep_deg, mode, m)
    life = m.grease_life_days * (m.bad_lot_life_factor if t.lot == "B" else 1.0)
    drive_t = day.t_mean_c + 6.0 + 4.0 * (1 - t.grease) + 0.02 * starts
    rate = (1.0 / life) * (1.0 + m.heat_aging_per_c * max(drive_t - 30.0, 0.0)) * (1.0 + m.churn_per_start * starts)
    t.grease *= np.exp(-rate)
    moisture = 80.0 + rng.normal(0, 8)
    if t.seal_leak_day is not None and d >= t.seal_leak_day:
        moisture += 900.0 + 40.0 * (d - t.seal_leak_day)
        if day.rain:
            t.grease *= 0.93
    poor = 1.0 + m.wear_grease_mult * (1.0 - t.grease)
    t.backlash += (starts * m.wear_per_start + degrees * m.wear_per_deg) * poor * t.wear_mult
    wind = day.wind_ms * exposure
    gust = day.gust_ms * exposure
    if mode == "park":
        t.backlash += m.fretting_per_ms * wind * poor
    if t.bearing_onset is not None and d >= t.bearing_onset:
        t.bearing_hi = float(np.expm1(m.bearing_rate * (d - t.bearing_onset)))
    stow_at = m.stow_wind_ms * (m.stow_early_factor if mode in ("stow_early", "coast") else 1.0)
    stowed = gust > stow_at
    fric = m.friction_gain * (1.0 - t.grease) ** 1.5
    cold = m.cold_viscosity_per_c * max(20.0 - day.t_mean_c, 0.0)
    windload = m.wind_load_per_ms2 * wind ** 2
    bearing_drag = 0.02 * min(t.bearing_hi, 8.0)
    epd = (1.0 + fric + cold + windload + bearing_drag) * rng.lognormal(0, 0.03)
    epd_norm = epd / (1.0 + cold + windload)  # the Sentinel's weather-normalised energy per degree
    worst_move_wind = min(gust, stow_at)  # the windiest moment it still moves in
    move_epd = 1.0 + fric + cold + m.wind_load_per_ms2 * worst_move_wind ** 2 + bearing_drag
    fail = None
    if t.grease <= m.seize_grease:
        fail = "seized (grease gone)"
    elif starts > 0 and move_epd >= m.stall_ratio:
        fail = "stall (friction + wind)"
    elif t.backlash >= m.backlash_fail_deg:
        fail = "backlash"
    elif t.bearing_hi >= m.bearing_fail_hi:
        fail = "bearing"
    return {
        "starts": starts, "stowed": bool(stowed), "grease": t.grease, "backlash_deg": t.backlash,
        "bearing_hi": t.bearing_hi, "epd": epd, "epd_norm": epd_norm, "move_epd": move_epd,
        "peak_a": 3.2 * (1.0 + 0.8 * (fric + bearing_drag) + windload) * rng.lognormal(0, 0.04),
        "deadzone_counts": t.backlash * COUNTS_PER_OUTPUT_DEG + rng.normal(0, 3.0),
        "pointing_deg": t.backlash * (0.6 + 0.08 * gust) + abs(rng.normal(0, 0.02)),
        "drive_temp_c": drive_t, "ambient_c": day.t_mean_c, "wind_ms": wind, "gust_ms": gust,
        # future hardware slots (ground truth with sensor noise)
        "vib_g": 0.05 * (1.0 + 0.12 * t.bearing_hi + 0.6 * (1 - t.grease)) * rng.lognormal(0, 0.08),
        "ae_counts": 4.0 + 30.0 * np.sqrt(t.bearing_hi) + 6.0 * (1 - t.grease) + rng.normal(0, 1.5),
        "moisture_ppm": moisture, "iron_ppm": 15.0 + 220.0 * (1 - t.grease) ** 2 + 6.0 * t.bearing_hi
        + rng.normal(0, 3),
        "torque_ratio": (1.0 + fric + bearing_drag) * rng.lognormal(0, 0.012),  # in-drive torque, wind removed
        "fail": fail,
    }


class Fleet:
    """Simulate ``days`` of a 48-tower fleet day by day, keeping what the controller sees and the truth."""

    DEMO = {7: "grease (supplier lot B)", 19: "seal leak", 31: "backlash", 42: "bearing"}
    REPLACE_DAYS = 21  # a failed drive waits this long for a new one

    def __init__(self, days: int = 1095, seed: int = 5, model: DriveModel | None = None, inject_demo: bool = True):
        self.m = model or DriveModel()
        self.days = days
        self.seed = seed
        self.rng = np.random.default_rng(seed)
        self.weather = dfw_weather(days, seed=seed + 6)
        self.towers: list[TowerState] = []
        tid = 1
        for site, cfg in SITES.items():
            for _ in range(cfg["towers"]):
                lot = str(self.rng.choice(["A", "B", "C"], p=[0.45, 0.25, 0.30]))
                install = int(self.rng.integers(0, 300))
                self.towers.append(TowerState(tid, site, lot, install_day=install))
                tid += 1
        self.exposure = {t.tower_id: SITES[t.site]["exposure"] for t in self.towers}
        self.events: dict = {}
        self._random_history()
        if inject_demo:
            self._inject_demo()
        self.incidents: list[dict] = []

    def _random_history(self) -> None:
        d = self.days
        for t in self.towers:
            if t.tower_id in self.DEMO:
                continue
            if self.rng.random() < 0.12:
                t.bearing_onset = int(self.rng.integers(120, d - 160))
            if self.rng.random() < 0.10:
                t.seal_leak_day = int(self.rng.integers(200, d - 120))
            if self.rng.random() < 0.08:  # loose bolts found late
                self.events[(t.tower_id, int(self.rng.integers(100, d - 300)))] = dict(backlash=0.30, wear_mult=8.0)

    def _inject_demo(self) -> None:
        """The four demo towers get a known story that peaks near today."""
        d = self.days
        self.events.update({
            (7, d - 330): dict(lot="B", grease=1.0, backlash=0.12, bearing_onset=None, seal_leak_day=None),
            (19, d - 200): dict(lot="A", grease=1.0, backlash=0.12, bearing_onset=None, seal_leak_day=d - 30),
            (31, d - 90): dict(lot="C", grease=0.8, backlash=0.40, wear_mult=10.0, bearing_onset=None,
                               seal_leak_day=None),
            (42, d - 300): dict(lot="A", grease=1.0, backlash=0.12, bearing_onset=d - 48, seal_leak_day=None),
        })

    def tower(self, tid: int) -> TowerState:
        return self.towers[tid - 1]

    def run(self) -> "Fleet":
        m, w, rng = self.m, self.weather, self.rng
        rec = []
        for d in range(self.days):
            day = w.iloc[d]
            for t in self.towers:
                ev = self.events.get((t.tower_id, d))
                if ev:
                    for k, v in ev.items():
                        setattr(t, k, v)
                    t.failed_day, t.failure_mode = None, None
                if d < t.install_day:
                    continue
                if t.failed_day is not None:
                    if d - t.failed_day < self.REPLACE_DAYS:
                        continue
                    self._replace(t)
                if d > t.install_day and (d - t.install_day) % m.regrease_days == 0 and t.tower_id not in self.DEMO:
                    t.grease = 1.0
                r = step_day(t, day, self.exposure[t.tower_id], "track", m, rng, d)
                if r["fail"] and d < self.days - 1 and t.tower_id not in self.DEMO:  # demo towers are scripted
                    t.failed_day, t.failure_mode = d, r["fail"]
                    self.incidents.append({"tower_id": t.tower_id, "site": t.site, "lot": t.lot, "day": d,
                                           "mode": r["fail"], "date": w.index[d].date().isoformat()})
                rec.append({"day": d, "tower_id": t.tower_id, "site": t.site, "lot": t.lot, **r})
        self.log_df = pd.DataFrame(rec)
        base = self.log_df[(self.log_df.grease > 0.85) & (self.log_df.bearing_hi < 0.05)]
        self.baseline_epd = float(base.epd_norm.median())
        return self

    def _replace(self, t: TowerState) -> None:
        t.grease, t.backlash, t.bearing_hi = 1.0, self.m.backlash0_deg, 0.0
        t.bearing_onset, t.seal_leak_day, t.failed_day, t.failure_mode = None, None, None, None
        t.wear_mult = 1.0
        t.lot = "A"  # replacement drives come from the current supplier

    def history(self, tid: int, last: int | None = None) -> pd.DataFrame:
        h = self.log_df[self.log_df.tower_id == tid].copy()
        h["date"] = self.weather.index[h["day"].to_numpy()]
        return h.tail(last) if last else h

    def today(self) -> pd.DataFrame:
        last = self.log_df.day.max()
        return self.log_df[self.log_df.day == last].set_index("tower_id")


# ------------------------------------------------------------------ detection
DETECTORS = {
    # name: (column, transform, alarm level, failure level, sensor, available today)
    "friction": ("epd_norm", "ratio_ewm", 1.15, 1.50, "motor energy per degree", True),
    "backlash": ("deadzone_counts", "deg_median", 0.36, 0.50, "motor encoder reversal test", True),
    "grease_iron": ("iron_ppm", "ewm", 45.0, 190.0, "grease condition sensor (iron)", False),
    "grease_water": ("moisture_ppm", "ewm", 400.0, 3000.0, "grease condition sensor (water)", False),
    "vibration": ("vib_g", "ewm", 0.068, 0.11, "worm-side accelerometer", False),
    "acoustic": ("ae_counts", "ewm", 14.0, 80.0, "acoustic emission on the bearing", False),
    "torque": ("torque_ratio", "ewm", 1.08, 1.45, "in-drive torque sensor", False),
}


def indicator(h: pd.DataFrame, name: str, baseline: float = 1.0) -> pd.Series:
    col, how, *_ = DETECTORS[name]
    s = h[col]
    if how == "ratio_ewm":
        return s.ewm(span=7).mean() / baseline
    if how == "deg_median":
        return s.rolling(7, min_periods=3).median() / COUNTS_PER_OUTPUT_DEG
    return s.ewm(span=5).mean()


def detect(h: pd.DataFrame, baseline: float, slots: tuple = ()) -> list[dict]:
    """Run today's detectors (plus any installed future slots) on one tower's history."""
    out = []
    for name, (col, how, alarm, fail_at, sensor, today) in DETECTORS.items():
        if not today and name not in slots:
            continue
        s = indicator(h, name, baseline)
        hit = s[s > alarm]
        if not len(hit):
            continue
        out.append({"detector": name, "sensor": sensor, "first_day": int(h.loc[hit.index[0], "day"]),
                    "value": float(s.iloc[-1]), "alarm": alarm, "fail_at": fail_at})
    return out


def rul_days(series: pd.Series, days: pd.Series, fail_at: float, window: int = 28, boots: int = 300,
             seed: int = 1, offset: float = 0.0) -> dict:
    """Days until ``series`` reaches ``fail_at``: exponential trend on the last ``window`` days of
    (series - offset) (offset 1 for ratios: the excess over baseline), bootstrap over residuals for P10/P50/P90."""
    y = series.tail(window).to_numpy(float) - offset
    fail_at = fail_at - offset
    x = days.tail(window).to_numpy(float)
    x = x - x[-1]
    rng = np.random.default_rng(seed)
    ly = np.log(np.clip(y, 1e-6, None))
    b, a = np.polyfit(x, ly, 1)
    resid = ly - (a + b * x)

    def solve(bb, aa):
        if bb <= 1e-6:
            return np.inf
        return max((np.log(fail_at) - aa) / bb, 0.0)

    sims = []
    for _ in range(boots):
        yy = a + b * x + rng.choice(resid, len(resid))
        bb, aa = np.polyfit(x, yy, 1)
        sims.append(solve(bb, aa))
    sims = np.array(sims)
    fin = sims[np.isfinite(sims)]
    return {"p50": float(solve(b, a)), "p10": float(np.percentile(fin, 10)) if len(fin) else np.inf,
            "p90": float(np.percentile(fin, 90)) if len(fin) else np.inf,
            "share_finite": float(len(fin) / boots), "trend_per_day": float(b)}


def project(fleet: Fleet, tid: int, mode: str, days: int, runs: int = 200, seed: int = 21) -> dict:
    """Monte Carlo forward from today for one tower under a tracking mode: chance of failing each day."""
    m = fleet.m
    base_state = fleet.tower(tid)
    w = fleet.weather
    clim = w.iloc[-365:]  # sample future days from the last year's weather (same season +/- 2 weeks)
    rng = np.random.default_rng(seed)
    fail_day = []
    doy0 = w.index[-1].dayofyear
    for _ in range(runs):
        t = copy.deepcopy(base_state)
        f = None
        for k in range(1, days + 1):
            target = (doy0 + k - 1) % 365 + 1
            pool = clim[(np.abs(clim.index.dayofyear - target) <= 14)]
            day = pool.iloc[int(rng.integers(len(pool)))]
            r = step_day(t, day, fleet.exposure[tid], mode, m, rng, fleet.days + k)
            if r["fail"]:
                f = k
                break
        fail_day.append(f)
    arr = np.array([x if x is not None else np.inf for x in fail_day], dtype=float)
    return {"mode": mode, "fail_days": arr, "runs": runs,
            "p_fail_by": lambda d: float(np.mean(arr <= d))}
