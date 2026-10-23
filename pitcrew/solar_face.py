"""Light and energy on a solar tower face that points at any azimuth.

A two-wing field model (Perez sky, SAPM cell temperature, other-losses factor) where the face azimuth is
an input instead of always the sun's azimuth. That lets PitCrew price "park the tower at 195 deg" or "track in 15 deg steps"
against normal tracking.

Only pvlib, numpy and pandas are needed. The table shipped in ``data/`` was produced by ``scripts/export_energy_table.py``.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import pvlib


@dataclass(frozen=True)
class TowerFace:
    """A tower's panel face: two wings each turned ``fold_deg`` off the centre line (ST-1: 60 deg tilt, 20 deg)."""

    rated_kw: float = 3.56  # 8 x 445 W modules (placeholder)
    tilt_deg: float = 60.0
    fold_deg: float = 20.0
    temp_coeff_per_c: float = -0.003
    sapm: tuple = ("open_rack", "glass_polymer")
    other_losses_factor: float = 0.90  # placeholder
    albedo: float = 0.2

    def wings(self) -> tuple:
        """((tilt, azimuth offset, share), ...) for each wing."""
        if self.fold_deg <= 0:
            return ((float(self.tilt_deg), 0.0, 1.0),)
        t, f = np.radians(self.tilt_deg), np.radians(self.fold_deg)
        nx, ny, nz = -np.sin(f), np.sin(t) * np.cos(f), np.cos(t) * np.cos(f)
        tilt = float(np.degrees(np.arccos(nz)))
        off = float(np.degrees(np.arctan2(-nx, ny)))
        return ((tilt, off, 0.5), (tilt, -off, 0.5))


DALLAS = dict(latitude=32.7767, longitude=-96.7970, altitude=139.0, tz="America/Chicago")


def clearsky_year(year: int = 2026, step_min: int = 10, site: dict = DALLAS) -> pd.DataFrame:
    """Clear-sky (Ineichen) sun and irradiance every ``step_min`` minutes with the sun up."""
    times = pd.date_range(f"{year}-01-01", f"{year + 1}-01-01", freq=f"{step_min}min", tz=site["tz"],
                          inclusive="left")
    loc = pvlib.location.Location(site["latitude"], site["longitude"], altitude=site["altitude"])
    sp = loc.get_solarposition(times)
    cs = loc.get_clearsky(times, model="ineichen", solar_position=sp)
    df = pd.DataFrame({
        "el": sp["apparent_elevation"].to_numpy(),
        "az": sp["azimuth"].to_numpy(),
        "dni": cs["dni"].to_numpy(), "dhi": cs["dhi"].to_numpy(), "ghi": cs["ghi"].to_numpy(),
    }, index=times)
    df = df[df["el"] > 1.0].copy()
    df["hours"] = step_min / 60.0
    df["temp_air"] = 20.0
    df["wind"] = 1.0
    return df


def face_power_kw(sun: pd.DataFrame, face_az, tower: TowerFace = TowerFace()) -> np.ndarray:
    """DC power (kW) of one tower whose face points at ``face_az`` (scalar or array, deg from north)."""
    el = sun["el"].to_numpy(float)
    az = sun["az"].to_numpy(float)
    zen = 90.0 - el
    dni, dhi, ghi = (sun[c].to_numpy(float) for c in ("dni", "dhi", "ghi"))
    face_az = np.broadcast_to(np.asarray(face_az, dtype=float), el.shape)
    dni_extra = np.asarray(pvlib.irradiance.get_extra_radiation(sun.index), dtype=float)
    am = np.asarray(pvlib.atmosphere.get_relative_airmass(zen), dtype=float)
    total = np.zeros_like(el)
    for tilt, off, share in tower.wings():
        tilt_a = np.full_like(el, tilt)
        surf_az = (face_az + off) % 360.0
        cos_aoi = np.asarray(pvlib.irradiance.aoi_projection(tilt_a, surf_az, zen, az), dtype=float)
        beam = dni * np.clip(cos_aoi, 0.0, None)
        comp = pvlib.irradiance.perez(tilt_a, surf_az, dhi, dni, dni_extra, zen, az, am, return_components=True)
        key = (lambda k: k if k in comp else f"poa_{k}")
        circ = np.nan_to_num(np.asarray(comp[key("circumsolar")], dtype=float)).clip(min=0)
        iso = np.nan_to_num(np.asarray(comp[key("isotropic")], dtype=float)
                            + np.asarray(comp[key("horizon")], dtype=float))
        # circumsolar light only reaches a face the sun is in front of (the engine shades it with the beam)
        circ = np.where(cos_aoi > 0, circ, 0.0)
        ground = ghi * tower.albedo * (1.0 - np.cos(np.radians(tilt))) / 2.0
        total += share * (beam + circ + iso.clip(min=0) + ground)
    p = pvlib.temperature.TEMPERATURE_MODEL_PARAMETERS["sapm"][f"{tower.sapm[0]}_{tower.sapm[1]}"]
    tcell = np.asarray(pvlib.temperature.sapm_cell(total, sun["temp_air"].to_numpy(float),
                                                   sun["wind"].to_numpy(float), p["a"], p["b"], p["deltaT"]))
    heat = np.clip(1.0 + tower.temp_coeff_per_c * (tcell - 25.0), 0.5, 1.2)
    return tower.rated_kw * total / 1000.0 * heat * tower.other_losses_factor


def step_azimuth(sun_az: np.ndarray, step_deg: float) -> np.ndarray:
    """Face azimuth when the tower only moves in ``step_deg`` steps (nearest step to the sun)."""
    return (np.round(np.asarray(sun_az, float) / step_deg) * step_deg) % 360.0


def daily_energy_table(sun: pd.DataFrame, tower: TowerFace = TowerFace(),
                       park_azimuths=range(60, 305, 5), steps=(10, 15, 30)) -> pd.DataFrame:
    """kWh per tower per day for tracking, step tracking and parking at fixed azimuths."""
    hours = sun["hours"].to_numpy(float)
    day = sun.index.normalize()
    cols = {"track": face_power_kw(sun, sun["az"].to_numpy(), tower) * hours}
    for s in steps:
        cols[f"step{s:02d}"] = face_power_kw(sun, step_azimuth(sun["az"].to_numpy(), s), tower) * hours
    for a in park_azimuths:
        cols[f"park_{a:03d}"] = face_power_kw(sun, float(a), tower) * hours
    df = pd.DataFrame(cols, index=sun.index).groupby(day).sum()
    df.index = pd.DatetimeIndex(df.index).tz_localize(None).date
    df.index.name = "date"
    return df
