"""
example.py
==========
Sample script demonstrating how to use the predict module.

Run from the export/ directory:
    python3 example.py

Three scenarios are shown:
  1. Healthy machine  — readings at the normal operating median
  2. Borderline       — hydraulic pressure and torque drifting toward failure range
  3. Likely failure   — readings matching the failure profile from training data

The predict module returns one of three fixed strings:
    "NORMAL"           – operating within healthy parameters
    "CAUTION"          – sensors drifting; monitor closely
    "FAILURE WARNING"  – high probability of imminent failure
"""

from predict import predict, predict_batch, predict_with_details, SENSOR_COLS

# ── Sample inputs ──────────────────────────────────────────────────────────────
# Each dict represents one snapshot of sensor readings from a machine.
# Values are grounded in the actual training data distributions.

HEALTHY_MACHINE = {
    # Hydraulic system — high pressure, good coolant flow
    "Hydraulic_Pressure(bar)":       120.20,
    "Coolant_Pressure(bar)":           5.16,
    "Air_System_Pressure(bar)":        6.50,
    # Temperatures — all within normal band
    "Coolant_Temperature":            20.60,
    "Hydraulic_Oil_Temperature":      47.70,
    "Spindle_Bearing_Temperature":    35.10,
    # Vibration — low and stable
    "Spindle_Vibration":               1.02,
    "Tool_Vibration":                 25.57,
    # Speed, power, load — normal operating point
    "Spindle_Speed(RPM)":          20194.00,
    "Voltage(volts)":                350.00,
    "Torque(Nm)":                     28.38,
    "Cutting(kN)":                     2.70,
}

BORDERLINE_MACHINE = {
    # Hydraulic pressure dropping — midway between healthy (120) and failure (80)
    "Hydraulic_Pressure(bar)":       100.00,
    "Coolant_Pressure(bar)":           4.95,
    "Air_System_Pressure(bar)":        6.50,
    # Temperature creeping up slightly
    "Coolant_Temperature":            21.80,
    "Hydraulic_Oil_Temperature":      48.50,
    "Spindle_Bearing_Temperature":    36.00,
    # Vibration still normal
    "Spindle_Vibration":               1.01,
    "Tool_Vibration":                 25.40,
    # Torque falling — midway between healthy (28.4) and failure (24.6)
    "Spindle_Speed(RPM)":          20100.00,
    "Voltage(volts)":                349.00,
    "Torque(Nm)":                     26.50,
    "Cutting(kN)":                     2.77,
}

FAILING_MACHINE = {
    # Hydraulic pressure at failure-profile median
    "Hydraulic_Pressure(bar)":        80.13,
    "Coolant_Pressure(bar)":           4.79,
    "Air_System_Pressure(bar)":        6.51,
    # Elevated coolant temperature
    "Coolant_Temperature":            23.00,
    "Hydraulic_Oil_Temperature":      47.60,
    "Spindle_Bearing_Temperature":    35.00,
    # Vibration at failure median
    "Spindle_Vibration":               1.00,
    "Tool_Vibration":                 25.33,
    # Lower speed and voltage, reduced torque, higher cutting force
    "Spindle_Speed(RPM)":          19964.00,
    "Voltage(volts)":                348.00,
    "Torque(Nm)":                     24.63,
    "Cutting(kN)":                     2.84,
}


# ── Helper ─────────────────────────────────────────────────────────────────────

def print_result(label: str, reading: dict, result):
    """Print a formatted block for one prediction result."""
    # result can be a plain string (from predict) or a dict (from predict_with_details)
    if isinstance(result, dict):
        status = result["status"]
        prob   = result["failure_probability"]
        pred   = result["prediction"]
        detail = f"  failure_probability : {prob:.1%}\n  prediction (0/1)    : {pred}"
    else:
        status = result
        detail = None

    status_icons = {
        "NORMAL":          "✅",
        "CAUTION":         "⚡",
        "FAILURE WARNING": "⚠️ ",
    }
    icon = status_icons.get(status, "")

    print(f"\n{'─' * 52}")
    print(f"  {label}")
    print(f"{'─' * 52}")
    print(f"  STATUS : {icon}  {status}")
    if detail:
        print(detail)


# ── 1. Simple usage — predict() returns a status string ───────────────────────

print("=" * 52)
print("  MACHINE DOWNTIME PREDICTION — EXAMPLE")
print("=" * 52)

print("\n\n[ 1 ] predict()  — returns a single status string\n")

status = predict(HEALTHY_MACHINE)
print(f"  Healthy machine  → \"{status}\"")

status = predict(BORDERLINE_MACHINE)
print(f"  Borderline       → \"{status}\"")

status = predict(FAILING_MACHINE)
print(f"  Failing machine  → \"{status}\"")


# ── 2. Batch usage — predict_batch() scores multiple readings at once ──────────

print("\n\n[ 2 ] predict_batch()  — list of readings → list of status strings\n")

readings = [HEALTHY_MACHINE, BORDERLINE_MACHINE, FAILING_MACHINE]
statuses = predict_batch(readings)

labels = ["Healthy machine ", "Borderline      ", "Failing machine "]
for label, s in zip(labels, statuses):
    print(f"  {label} → \"{s}\"")


# ── 3. Detailed usage — predict_with_details() includes probability ────────────

print("\n\n[ 3 ] predict_with_details()  — status string + probability + flag\n")

for label, reading in [
    ("Healthy machine ", HEALTHY_MACHINE),
    ("Borderline      ", BORDERLINE_MACHINE),
    ("Failing machine ", FAILING_MACHINE),
]:
    result = predict_with_details(reading)
    print(f"  {label} → {result}")


# ── 4. Using the fixed return constants in your own logic ──────────────────────

print("\n\n[ 4 ] Branching on the fixed status strings\n")

from predict import STATUS_NORMAL, STATUS_CAUTION, STATUS_FAILURE_WARNING

for label, reading in [
    ("Healthy machine ", HEALTHY_MACHINE),
    ("Borderline      ", BORDERLINE_MACHINE),
    ("Failing machine ", FAILING_MACHINE),
]:
    status = predict(reading)

    if status == STATUS_FAILURE_WARNING:
        action = "Stop machine and schedule immediate maintenance."
    elif status == STATUS_CAUTION:
        action = "Flag for inspection at next available window."
    else:  # STATUS_NORMAL
        action = "No action required. Continue monitoring."

    print(f"  {label} → \"{status}\"  |  {action}")

print(f"\n{'=' * 52}\n")
