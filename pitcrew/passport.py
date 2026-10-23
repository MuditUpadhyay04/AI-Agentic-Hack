"""Asset passports: everything the crew knows about a machine, written from its manual, signed by a human.

The passport is the unit of growth: adding the 100th machine means adding the 100th passport, not a new
model. Signals the manual lists as "not fitted" become *future hardware slots*: the agents that need them
exist already and switch on the day the sensor is installed.

``from_manual`` reads the manual's tables (offline, deterministic). With Bedrock available the Onboarder
agent can instead read free-form manuals and must return the same schema (``SCHEMA``); either way
``validate`` runs before a human signs.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

MANUALS = Path(__file__).resolve().parents[1] / "data" / "manuals"

SCHEMA = {
    "type": "object",
    "required": ["asset_class", "model", "agent_template", "walls", "signals", "slots", "maintenance", "parts"],
    "properties": {
        "asset_class": {"type": "string"}, "model": {"type": "string"}, "agent_template": {"type": "string"},
        "walls": {"type": "array", "items": {"type": "object", "required": ["name", "signal", "unit"]}},
        "signals": {"type": "array"}, "slots": {"type": "array"}, "maintenance": {"type": "array"},
        "parts": {"type": "array"},
    },
}

# which detectors a slot unlocks, by signal keyword
SLOT_UNLOCKS = {
    "grease": ["grease_water", "grease_iron"], "vibration": ["vibration"], "acoustic": ["acoustic"],
    "torque": ["torque"], "output absolute encoder": ["pointing"], "coolant": ["coolant_condition"],
    "way-oil": ["lube_level"],
}


def _tables(md: str) -> dict:
    """{section heading: list of row dicts} for every pipe table under a '## ' heading."""
    out, section, header = {}, None, None
    for line in md.splitlines():
        if line.startswith("## "):
            section, header = line[3:].strip(), None
            continue
        if not line.startswith("|") or section is None:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if all(re.fullmatch(r":?-+:?", c) for c in cells if c):
            continue
        if header is None:
            header = cells
            out[section] = []
        else:
            out[section].append(dict(zip(header, cells)))
    return out


def _num(s: str):
    s = (s or "").replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def _meta(md: str, key: str) -> str | None:
    m = re.search(rf"-\s*{re.escape(key)}:\s*(.+)", md)
    return m.group(1).strip() if m else None


def from_manual(path: str | Path, asset_id: str | None = None) -> dict:
    md = Path(path).read_text()
    t = _tables(md)
    walls = [{"name": r["Limit"], "signal": r["Signal"], "min": _num(r.get("Min")), "max": _num(r.get("Max")),
              "unit": r["Unit"], "condition": r.get("Condition", "")} for r in t.get("Operating limits", [])]
    signals, slots = [], []
    for r in t.get("Signals", []):
        fitted = r.get("Fitted today", "").lower().startswith("y")
        signals.append({"name": r["Signal"], "unit": r["Unit"], "fitted": fitted})
        if not fitted:
            key = next((k for k in SLOT_UNLOCKS if k in r["Signal"].lower()), None)
            slots.append({"signal": r["Signal"], "status": "empty", "unlocks": SLOT_UNLOCKS.get(key, ["custom"])})
    title = md.splitlines()[0].lstrip("# ").strip()
    passport = {
        "asset_id": asset_id or (_meta(md, "Model") or "asset").split()[0],
        "title": title,
        "asset_class": _meta(md, "Asset class"), "model": _meta(md, "Model"),
        "agent_template": _meta(md, "Agent template") or "rotating-machine-v1",
        "source": str(Path(path).name),
        "walls": walls, "signals": signals, "slots": slots,
        "maintenance": [{"task": r["Task"], "interval": r["Interval"]} for r in t.get("Maintenance", [])],
        "parts": [{"pn": r["Part number"], "desc": r["Description"]} for r in t.get("Parts", [])],
        "approved_by": None, "created": dt.date(2026, 10, 23).isoformat(),
    }
    passport["checks"] = validate(passport)
    return passport


def validate(p: dict) -> list[dict]:
    """Checks a human reads before signing: missing fields, walls without a number, odd units."""
    out = []
    for k in SCHEMA["required"]:
        if not p.get(k):
            out.append({"level": "error", "msg": f"missing {k}"})
    for w in p.get("walls", []):
        if w.get("min") is None and w.get("max") is None:
            out.append({"level": "error", "msg": f"wall '{w['name']}' has no number"})
        if w.get("min") is not None and w.get("max") is not None and w["min"] >= w["max"]:
            out.append({"level": "error", "msg": f"wall '{w['name']}' min >= max"})
        if not w.get("unit"):
            out.append({"level": "warn", "msg": f"wall '{w['name']}' has no unit"})
    if not any(s["fitted"] for s in p.get("signals", [])):
        out.append({"level": "error", "msg": "no fitted signals: nothing to monitor"})
    if not out:
        out.append({"level": "ok", "msg": f"{len(p['walls'])} walls, {sum(s['fitted'] for s in p['signals'])} live "
                                         f"signals, {len(p['slots'])} future hardware slots"})
    return out


def sign(p: dict, who: str) -> dict:
    if any(c["level"] == "error" for c in p.get("checks", [])):
        raise ValueError("passport has errors; fix them before signing")
    p = dict(p)
    p["approved_by"] = who
    return p


def install_slot(p: dict, signal_keyword: str) -> dict:
    """Mark a future slot installed: its detectors switch on with no code change."""
    p = json.loads(json.dumps(p))
    for s in p["slots"]:
        if signal_keyword.lower() in s["signal"].lower():
            s["status"] = "installed"
    return p


def manuals() -> list[str]:
    return sorted(x.name for x in MANUALS.glob("*.md"))
