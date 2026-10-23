"""
predict.py
==========
Self-contained inference module for the Machine Downtime Prediction model.

Public API
----------
predict(reading: dict) -> str
    Takes a single dict of sensor readings and returns one of three fixed
    status strings:

        "NORMAL"           – machine is operating within healthy parameters
        "CAUTION"          – sensors are drifting; monitor closely
        "FAILURE WARNING"  – high probability of imminent failure

predict_batch(readings: list[dict]) -> list[str]
    Same as predict() but accepts a list of readings and returns a list of
    status strings in the same order.

predict_with_details(reading: dict) -> dict
    Returns a dict with the status string plus the raw probability score and
    binary prediction flag, for callers that need more than just the label.

Usage
-----
    from predict import predict, predict_batch, predict_with_details

    status = predict({
        "Hydraulic_Pressure(bar)": 80.0,
        "Coolant_Pressure(bar)": 4.8,
        ...
    })
    # "FAILURE WARNING"

Notes
-----
- Both model files (best_model.pkl, scaler.pkl) must sit in the same directory
  as this script.
- The 12 sensor keys listed in SENSOR_COLS are required. Pass None or omit a
  key to have it filled with the training median automatically.
"""

import os
import sys
import joblib
import numpy as np

# ── Fixed return strings ───────────────────────────────────────────────────────

STATUS_NORMAL          = "NORMAL"
STATUS_CAUTION         = "CAUTION"
STATUS_FAILURE_WARNING = "FAILURE WARNING"

# ── Thresholds ─────────────────────────────────────────────────────────────────
# Probability of failure required to trigger each status.
# Adjust these to tune sensitivity without retraining.

_THRESHOLD_WARNING = 0.70   # >= this → FAILURE WARNING
_THRESHOLD_CAUTION = 0.40   # >= this → CAUTION
                             # <  this → NORMAL

# ── Sensor column order must match the training pipeline exactly ───────────────

SENSOR_COLS = [
    "Hydraulic_Pressure(bar)",
    "Coolant_Pressure(bar)",
    "Air_System_Pressure(bar)",
    "Coolant_Temperature",
    "Hydraulic_Oil_Temperature",
    "Spindle_Bearing_Temperature",
    "Spindle_Vibration",
    "Tool_Vibration",
    "Spindle_Speed(RPM)",
    "Voltage(volts)",
    "Torque(Nm)",
    "Cutting(kN)",
]

# Training-set medians used as fallback for missing sensor values
_TRAINING_MEDIANS = {
    "Hydraulic_Pressure(bar)":       101.52,
    "Coolant_Pressure(bar)":           4.96,
    "Air_System_Pressure(bar)":        6.50,
    "Coolant_Temperature":            21.70,
    "Hydraulic_Oil_Temperature":      47.70,
    "Spindle_Bearing_Temperature":    35.10,
    "Spindle_Vibration":               1.01,
    "Tool_Vibration":                 25.46,
    "Spindle_Speed(RPM)":          20194.00,
    "Voltage(volts)":                350.00,
    "Torque(Nm)":                     26.41,
    "Cutting(kN)":                     2.77,
}

# ── Load model once at import time ─────────────────────────────────────────────

_DIR = os.path.dirname(os.path.abspath(__file__))

try:
    _model  = joblib.load(os.path.join(_DIR, "best_model.pkl"))
    _scaler = joblib.load(os.path.join(_DIR, "scaler.pkl"))
except FileNotFoundError as e:
    raise RuntimeError(
        f"Model file not found: {e}\n"
        "Ensure best_model.pkl and scaler.pkl are in the same directory as predict.py."
    ) from e


# ── Internal helpers ───────────────────────────────────────────────────────────

def _reading_to_array(reading: dict) -> np.ndarray:
    """Convert a sensor dict to a scaled numpy row, filling missing keys with medians."""
    row = [
        float(reading.get(col) if reading.get(col) is not None else _TRAINING_MEDIANS[col])
        for col in SENSOR_COLS
    ]
    return _scaler.transform(np.array(row, dtype=float).reshape(1, -1))


def _prob_to_status(probability: float) -> str:
    """Map a failure probability to a fixed status string."""
    if probability >= _THRESHOLD_WARNING:
        return STATUS_FAILURE_WARNING
    if probability >= _THRESHOLD_CAUTION:
        return STATUS_CAUTION
    return STATUS_NORMAL


# ── Public API ─────────────────────────────────────────────────────────────────

def predict(reading: dict) -> str:
    """
    Predict the machine status from a single set of sensor readings.

    Parameters
    ----------
    reading : dict
        Keys are sensor names (see SENSOR_COLS). Missing keys are filled
        with training medians.

    Returns
    -------
    str — one of:
        "NORMAL"
        "CAUTION"
        "FAILURE WARNING"
    """
    X = _reading_to_array(reading)
    prob = float(_model.predict_proba(X)[0][1])
    return _prob_to_status(prob)


def predict_batch(readings: list) -> list:
    """
    Predict machine status for multiple readings at once.

    Parameters
    ----------
    readings : list of dict
        Each dict follows the same format as predict().

    Returns
    -------
    list of str — same length as readings, each element is one of:
        "NORMAL"
        "CAUTION"
        "FAILURE WARNING"
    """
    rows = np.vstack([_reading_to_array(r) for r in readings])
    probs = _model.predict_proba(rows)[:, 1]
    return [_prob_to_status(float(p)) for p in probs]


def predict_with_details(reading: dict) -> dict:
    """
    Predict machine status and return full detail.

    Parameters
    ----------
    reading : dict
        Keys are sensor names (see SENSOR_COLS).

    Returns
    -------
    dict with keys:
        status              : str  — "NORMAL" | "CAUTION" | "FAILURE WARNING"
        failure_probability : float — 0.0 to 1.0
        prediction          : int  — 0 (no failure) or 1 (failure)
    """
    X = _reading_to_array(reading)
    prob = float(_model.predict_proba(X)[0][1])
    pred = int(_model.predict(X)[0])
    return {
        "status":              _prob_to_status(prob),
        "failure_probability": round(prob, 4),
        "prediction":          pred,
    }
