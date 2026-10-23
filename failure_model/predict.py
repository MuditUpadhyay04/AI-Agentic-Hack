"""Matthew's AI4I failure model: XGBoost classifier on the six AI4I features.

Adapted from his prediction agent (agents/prediction_agent.py) so the console can import it directly:

    predict_from_sensor_data(reading) -> {prediction, failure_probability, note}
    predict_flagged_records(threshold) -> every AI4I record at or above the threshold

The model classifies the current reading (is this machine failing now?), not time to failure.
Retrain with ``python failure_model/train_model.py --csv failure_model/ai4i2020.csv --out failure_model/failure_model.joblib``.
"""
from __future__ import annotations

import math
import sys
import warnings
from functools import lru_cache
from pathlib import Path

import joblib
import pandas as pd

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from train_model import FEATURES, prepare_features  # noqa: E402

DATA_PATH = HERE / "ai4i2020.csv"
MODEL_PATH = HERE / "failure_model.joblib"


@lru_cache(maxsize=1)
def _bundle():
    with warnings.catch_warnings():  # pickled by an older xgboost; loads fine
        warnings.simplefilter("ignore")
        return joblib.load(MODEL_PATH)


@lru_cache(maxsize=1)
def ai4i() -> pd.DataFrame:
    return pd.read_csv(DATA_PATH)


def record(udi: int) -> dict:
    """One AI4I record's six model features."""
    row = ai4i().loc[ai4i()["UDI"] == udi].iloc[0]
    return {k: (row[k] if k == "Type" else float(row[k])) for k in FEATURES}


def predict_from_sensor_data(sensor_data: dict) -> dict:
    """Failure classification for one reading of the six AI4I features."""
    missing = [n for n in FEATURES if n not in sensor_data]
    if missing:
        return {"error": f"Missing required features: {missing}"}
    if sensor_data["Type"] not in ("L", "M", "H"):
        return {"error": "Type must be L, M, or H"}
    clean = {"Type": sensor_data["Type"]}
    for n in FEATURES[1:]:
        v = float(sensor_data[n])
        if not math.isfinite(v) or v < 0:
            return {"error": f"{n} must be finite and nonnegative"}
        clean[n] = v
    b = _bundle()
    p = float(b["model"].predict_proba(prepare_features(pd.DataFrame([clean]), b["columns"]))[0, 1])
    return {"prediction": "Machine_Failure" if p >= 0.5 else "No_Machine_Failure",
            "failure_probability": round(p, 4),
            "note": "Current-record failure classification, not prediction of failure time."}


def predict_flagged_records(threshold: float = 0.5) -> dict:
    """Score every AI4I record; return all at or above the threshold, highest first."""
    b = _bundle()
    df = ai4i()
    p = b["model"].predict_proba(prepare_features(df, b["columns"]))[:, 1]
    flagged = sorted(({"record_udi": int(u), "failure_probability": round(float(s), 4)}
                      for u, s in zip(df["UDI"], p) if s >= threshold), key=lambda r: -r["failure_probability"])
    return {"scanned_records": len(df), "threshold": threshold, "flagged_count": len(flagged),
            "flagged_records": flagged}
