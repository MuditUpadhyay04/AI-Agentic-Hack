"""PitCrew v0.2: the one place the console meets each teammate's part.

The console calls only the functions in this file. Each section names its owner and the shape the console
expects; swap the placeholder body for the real call and the screens pick it up unchanged.

    Internal fab   (Hari)     fab_status, fab_forecast       real model: machine_downtime_model/predict.py
    Prevention     (Matthew)  failure_risk                   real model: failure_model/predict.py (XGBoost, AI4I)
    Maintenance    (tbd)      lifelines, maintenance_jobs    placeholder (lifeline pipeline to plug in)
    Sourcing/Cure  (Mudit)    order_card, cure_events        placeholder (follows idea.md section 7a)
    Priority queue (console)  queue                          real: merges the three loops (idea.md section 6)

Every placeholder result carries ``source="placeholder"`` so the screens can label it. Names, prices,
hubs and lifetimes are placeholders, not real company values.
"""
from __future__ import annotations

import copy
import datetime as dt
import importlib.util
import math
import sys
import warnings
from functools import lru_cache
from pathlib import Path

from .ops import TODAY

ROOT = Path(__file__).resolve().parents[1]
PLACEHOLDER = "placeholder"
HORIZON_DAYS = 30
BUFFER = 2  # emergency spares per part per hub (idea.md: start with a fixed number)


def day(n: int) -> dt.date:
    return TODAY + dt.timedelta(days=n)


# ============================================================================ Internal fab (Hari)
FAB_MACHINES = {
    "MK-L1": {"name": "Makino L1", "line": "Shopfloor-L1", "makes": ["PN-6031"],
              "reading": {"Hydraulic_Pressure(bar)": 130.0, "Torque(Nm)": 32.0}},
    "MK-L2": {"name": "Makino L2", "line": "Shopfloor-L2", "makes": ["PN-5120"],
              "reading": {"Hydraulic_Pressure(bar)": 125.0, "Torque(Nm)": 30.0}},
    "MK-L3": {"name": "Makino L3", "line": "Shopfloor-L3", "makes": ["PN-1043"],
              "reading": {"Hydraulic_Pressure(bar)": 128.0, "Torque(Nm)": 31.0}},
}
# Hari's example of a failing machine (machine_downtime_model/example.py, FAILING_MACHINE).
FAILING_READING = {"Hydraulic_Pressure(bar)": 80.13, "Coolant_Pressure(bar)": 4.79, "Coolant_Temperature": 23.0,
                   "Spindle_Speed(RPM)": 19964.0, "Voltage(volts)": 348.0, "Torque(Nm)": 24.63, "Cutting(kN)": 2.84}
IN_HOUSE_BASE_LEAD = 3  # days to make a part in-house when the machine is healthy (placeholder)
IN_HOUSE_UNIT_USD = {"PN-1043": 300.0, "PN-6031": 90.0, "PN-5120": 120.0}  # internal cost (placeholder)
RESTORE_DAYS = 5  # when only the emergency buffer is short, restore it within this many days

_predict = None


def _load(name: str, path: Path):
    """Import a teammate's module by file under its own name: both model folders ship a ``predict.py``."""
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        try:
            spec.loader.exec_module(mod)
        except Exception:
            del sys.modules[name]
            raise
    return sys.modules[name]


def _model():
    global _predict
    if _predict is None:
        with warnings.catch_warnings():  # pickled with an older scikit-learn; loads fine
            warnings.simplefilter("ignore")
            _predict = _load("hari_downtime_predict", ROOT / "machine_downtime_model" / "predict.py").predict_with_details
    return _predict


def fab_status(machine_id: str, reading: dict) -> dict:
    """Hari: {status: NORMAL | CAUTION | FAILURE WARNING, failure_probability}."""
    try:
        out = _model()(reading)
        src = "machine_downtime_model"
    except Exception as exc:  # model or its native library missing: say so, never guess a status
        return {"machine": machine_id, "status": "UNAVAILABLE", "failure_probability": None,
                "source": f"model unavailable ({type(exc).__name__})"}
    return {"machine": machine_id, **out, "source": src}


def fab_forecast(part: str, statuses: dict) -> dict:
    """Hari (placeholder until fab_forecast lands): in-house lead time for a part from its machine's status."""
    m = next((k for k, v in FAB_MACHINES.items() if part in v["makes"]), None)
    if m is None:
        return {"part": part, "made_in_house": False, "source": PLACEHOLDER}
    st = statuses.get(m, {}).get("status", "NORMAL")
    extra = {"NORMAL": 0, "CAUTION": 1, "FAILURE WARNING": 2}.get(st, 0)
    return {"part": part, "made_in_house": True, "machine": m, "units_per_day": 4 if extra == 0 else 2,
            "lead_time_days": IN_HOUSE_BASE_LEAD + extra, "confidence": 0.7,
            "reason": f"{FAB_MACHINES[m]['name']} is {st}" + (f": +{extra} days" if extra else ""),
            "source": PLACEHOLDER}


# ============================================================================ Prevention (Matthew)
ACT, WATCH = 0.70, 0.40  # failure probability: >= ACT pulls the job forward, >= WATCH adds predicted demand
SENSORS = {  # AI4I feature: label on screen
    "Air temperature [K]": "Air temperature (K)", "Process temperature [K]": "Process temperature (K)",
    "Rotational speed [rpm]": "Spindle speed (rpm)", "Torque [Nm]": "Torque (Nm)", "Tool wear [min]": "Tool wear (min)",
}
_failure = None


def _failure_model():
    global _failure
    if _failure is None:
        _failure = _load("matthew_failure_predict", ROOT / "failure_model" / "predict.py")
    return _failure


@lru_cache(maxsize=3)
def _healthy_peers(machine_type: str):
    """Healthy AI4I records of the same machine type (L/M/H): the peer group a reading is compared with."""
    df = _failure_model().ai4i()
    return df[(df["Type"] == machine_type) & (df["Machine failure"] == 0)]


def failure_risk(product_id: str, reading: dict) -> dict:
    """Matthew: XGBoost failure probability for a product's current AI4I reading, plus each sensor against healthy
    peers of the same type (robust |z|) so the screen can say which reading is off."""
    try:
        risk = _failure_model().predict_from_sensor_data(reading)["failure_probability"]
    except Exception as exc:  # model or its libraries missing: say so, never guess a risk
        return {"product": product_id, "risk": None, "action": "normal", "worst_signal": "model unavailable",
                "signals": [], "peer_count": 0, "source": f"failure model unavailable ({type(exc).__name__})"}
    peers = _healthy_peers(reading["Type"])
    rows = []
    for key, label in SENSORS.items():
        vals = peers[key]
        med = float(vals.median())
        mad = float((vals - med).abs().median()) or 1e-9
        rows.append({"signal": key, "label": label, "value": round(float(reading[key]), 1),
                     "peer_median": round(med, 1), "peer_low": round(float(vals.quantile(0.05)), 1),
                     "peer_high": round(float(vals.quantile(0.95)), 1),
                     "z": round(abs(float(reading[key]) - med) / (1.4826 * mad), 2)})
    worst = max(rows, key=lambda r: r["z"])
    action = "act" if risk >= ACT else "watch" if risk >= WATCH else "normal"
    return {"product": product_id, "risk": risk, "action": action, "worst_signal": worst["label"], "signals": rows,
            "peer_count": len(peers), "machine_type": reading["Type"],
            "source": "failure_model (Matthew: XGBoost on AI4I 2020)"}


# ============================================================================ Maintenance (owner tbd)
def lifelines(product_id: str, plant: "Plant") -> list[dict]:
    """Lifeline pipeline (placeholder): rated life used per component and the projected due date."""
    return [dict(c, source=PLACEHOLDER) for c in plant.lifeline_table.get(product_id, [])]


# ============================================================================ Sourcing + Cure (Mudit)
ERROR_CODES = {  # placeholder table: which codes mean "down" (Cure) vs "warning" (a Prevention signal)
    "E-OVHT": {"meaning": "Overheat shutdown (heat dissipation)", "kind": "down", "component": "cooling fan module",
               "parts": [["PN-1043", 1]], "downtime_usd_per_h": 1200.0},
    "W-COMM": {"meaning": "Telemetry gaps", "kind": "warning", "component": "controller", "parts": []},
    "W-TORQ": {"meaning": "Spindle torque above baseline", "kind": "warning", "component": "spindle sensor module",
               "parts": [["PN-3307", 1]]},
}
HUBS = {
    "CENTRAL": {"name": "Central hub (factory)", "kind": "central"},
    "NORTH": {"name": "Local hub North", "kind": "local", "sites": ["Fab North"]},
    "EAST": {"name": "Local hub East", "kind": "local", "sites": ["Assembly & test East"]},
    "SOUTH": {"name": "Local hub South", "kind": "local", "sites": ["Fab South"]},
}
TRANSIT_DAYS = {("CENTRAL", "NORTH"): 1, ("CENTRAL", "EAST"): 1, ("CENTRAL", "SOUTH"): 2,
                ("NORTH", "EAST"): 1, ("NORTH", "SOUTH"): 2, ("EAST", "SOUTH"): 1}
VENDORS = {  # authorized vendors per part (placeholder prices: idea.md worked example)
    "PN-3307": [{"vendor": "Vendor X", "unit_usd": 58.0, "lead_days": 10, "ship_usd": 0.0},
                {"vendor": "Vendor B", "unit_usd": 65.0, "lead_days": 3, "ship_usd": 0.0},
                {"vendor": "Vendor Y", "unit_usd": 72.0, "lead_days": 1, "ship_usd": 0.0}],
    "PN-2210": [{"vendor": "Vendor E", "unit_usd": 22.0, "lead_days": 4, "ship_usd": 8.0},
                {"vendor": "Vendor Y", "unit_usd": 31.0, "lead_days": 1, "ship_usd": 0.0}],
    "PN-1043": [{"vendor": "Vendor F", "unit_usd": 410.0, "lead_days": 6, "ship_usd": 25.0},
                {"vendor": "Vendor B", "unit_usd": 465.0, "lead_days": 2, "ship_usd": 0.0}],
}


def transit(a: str, b: str) -> int:
    return 0 if a == b else TRANSIT_DAYS.get((a, b), TRANSIT_DAYS.get((b, a), 2))


def order_card(part: str, hub: str, plant: "Plant", allocation: dict) -> dict:
    """Mudit (placeholder following idea.md section 7a): enough for upcoming jobs + buffer? if not, when and
    from whom: the cheapest vendor that arrives in time vs the fastest one."""
    inv = plant.inventory[hub].get(part, {"on_hand": 0, "inbound": []})
    reserved = allocation.get((hub, part), 0)
    jobs = [j for j in plant.jobs_for_hub(hub) if part in [p for p, _ in j["parts"]]
            and (j["due_by"] - TODAY).days <= HORIZON_DAYS]
    scheduled = sum(q for j in jobs if j["type"] != "prevention-forecast" for p, q in j["parts"] if p == part)
    predicted = sum(round(j.get("p_need", 0) * q, 2) for j in plant.predicted_for_hub(hub)
                    for p, q in j["parts"] if p == part)
    inbound = sum(x["qty"] for x in inv["inbound"])
    position = inv["on_hand"] + inbound
    need = scheduled + predicted + BUFFER
    shortfall = round(need - position, 2)
    # need_by: walk the dated jobs. A job that can't be covered sets the date; if every job is covered but the
    # emergency buffer is not, restore the buffer within RESTORE_DAYS.
    stock, need_by, why = position, None, None
    for j in sorted(jobs, key=lambda j: j["due_by"]):
        stock -= sum(q for p, q in j["parts"] if p == part)
        if stock < 0:
            need_by, why = j["due_by"], f"cover {j.get('product', '')} on {j['due_by']:%b %d}"
            break
    if need_by is None and shortfall > 0:
        need_by, why = day(RESTORE_DAYS), f"restore the {BUFFER}-unit emergency buffer"
    qty = max(0, math.ceil(shortfall))
    options = []
    for v in VENDORS.get(part, []):
        arrives = day(v["lead_days"])
        options.append({**v, "arrives": arrives, "in_time": need_by is None or arrives <= need_by,
                        "landed_usd": round(v["unit_usd"] * qty + v["ship_usd"], 2),
                        "order_by": (need_by - dt.timedelta(days=v["lead_days"])) if need_by else None})
    fab = fab_forecast(part, plant.fab_statuses())
    if fab.get("made_in_house"):
        arrives = day(fab["lead_time_days"] + transit("CENTRAL", hub))
        unit = IN_HOUSE_UNIT_USD.get(part, 0.0)
        options.append({"vendor": f"In-house ({FAB_MACHINES[fab['machine']]['name']})", "unit_usd": unit,
                        "lead_days": fab["lead_time_days"], "ship_usd": 0.0, "arrives": arrives,
                        "in_time": need_by is None or arrives <= need_by, "landed_usd": round(unit * qty, 2),
                        "order_by": None, "in_house": True, "reason": fab["reason"]})
    ok = [o for o in options if o["in_time"]]
    cheapest = min(ok, key=lambda o: o["landed_usd"]) if ok else None
    fastest = min(options, key=lambda o: o["arrives"]) if options else None
    late = [o for o in options if not o["in_time"]]
    return {"part": part, "hub": hub, "on_hand": inv["on_hand"], "reserved": reserved, "inbound": inbound,
            "position": position, "scheduled": scheduled, "predicted": predicted, "buffer": BUFFER,
            "need": round(need, 2), "shortfall": shortfall, "order_qty": qty, "need_by": need_by, "need_why": why,
            "options": options, "cheapest": cheapest, "fastest": fastest, "late": late,
            "auto_approve": bool(cheapest and cheapest["landed_usd"] <= 500), "source": PLACEHOLDER}


# ============================================================================ the plant the demo runs on
class Plant:
    """Simulated fleet, hubs and factory for the v0.2 demo. One per console session."""

    def __init__(self):
        self.events: list[str] = []
        self.fab_readings = {k: dict(v["reading"]) for k, v in FAB_MACHINES.items()}
        # NXP equipment at fab and assembly/test sites (placeholder fleet). Each reading is a real AI4I 2020 record
        # (UDI), scored by Matthew's model; Type L/M/H is the AI4I quality variant.
        self.products = {
            "DS-07": {"id": "DS-07", "name": "Dicing saw 07", "hub": "NORTH", "site": "Fab North", "udi": 3},
            "DS-19": {"id": "DS-19", "name": "Dicing saw 19", "hub": "NORTH", "site": "Fab North", "udi": 4},
            "WB-23": {"id": "WB-23", "name": "Wire bonder 23", "hub": "NORTH", "site": "Fab North", "udi": 6},
            "WB-31": {"id": "WB-31", "name": "Wire bonder 31", "hub": "NORTH", "site": "Fab North", "udi": 9},
            "TH-12": {"id": "TH-12", "name": "Test handler 12", "hub": "EAST", "site": "Assembly & test East", "udi": 11},
            "PR-42": {"id": "PR-42", "name": "Wafer prober 42", "hub": "SOUTH", "site": "Fab South", "udi": 19},
        }
        self.readings = {k: _failure_model().record(v["udi"]) for k, v in self.products.items()}
        self.lifeline_table = {
            "WB-31": [{"component": "Spindle sensor module", "used_pct": 92, "due_by": day(5), "part": "PN-3307"}],
            "WB-23": [{"component": "Spindle sensor module", "used_pct": 88, "due_by": day(12), "part": "PN-3307"}],
            "DS-07": [{"component": "Spindle sensor module", "used_pct": 71, "due_by": day(28), "part": "PN-3307"},
                      {"component": "Power supply board", "used_pct": 64, "due_by": day(40), "part": "PN-2210"}],
            "TH-12": [{"component": "Power supply board", "used_pct": 90, "due_by": day(9), "part": "PN-2210"}],
            "PR-42": [{"component": "Power supply board", "used_pct": 84, "due_by": day(20), "part": "PN-2210"}],
            "DS-19": [{"component": "Cooling fan module", "used_pct": 55, "due_by": day(120), "part": "PN-1043"}],
        }
        self.inventory = {
            "CENTRAL": {"PN-3307": {"on_hand": 6, "inbound": []}, "PN-2210": {"on_hand": 12, "inbound": []},
                        "PN-1043": {"on_hand": 1, "inbound": []}},
            "NORTH": {"PN-3307": {"on_hand": 2, "inbound": []}, "PN-2210": {"on_hand": 4, "inbound": []},
                      "PN-1043": {"on_hand": 1, "inbound": []}},
            "EAST": {"PN-3307": {"on_hand": 4, "inbound": []}, "PN-2210": {"on_hand": 3, "inbound": []},
                     "PN-1043": {"on_hand": 0, "inbound": []}},
            "SOUTH": {"PN-3307": {"on_hand": 2, "inbound": []}, "PN-2210": {"on_hand": 3, "inbound": []},
                      "PN-1043": {"on_hand": 0, "inbound": []}},
        }
        self.cures: list[dict] = []
        self.pos: list[dict] = []

    # ---------------------------------------------------------------- demo events
    DRIFT_UDI = 162  # a real AI4I overstrain failure: torque 52.3 Nm with 218 min of tool wear

    def product_drifts(self, pid: str = "DS-07") -> None:
        """The demo's prevention event: the saw's next reading is a failing AI4I record of the same type."""
        self.readings[pid] = _failure_model().record(self.DRIFT_UDI)
        self.events.append(f"prevention:{pid}")

    def product_down(self, pid: str = "DS-19") -> dict:
        code = ERROR_CODES["E-OVHT"]
        c = {"id": f"INC-{301 + len(self.cures)}", "product": pid, "code": "E-OVHT", "opened": dt.datetime.now(),
             **code}
        self.cures.append(c)
        self.events.append(f"cure:{pid}")
        return c

    def fab_l3_degrades(self) -> None:
        self.fab_readings["MK-L3"] = dict(FAILING_READING)
        self.events.append("fab:MK-L3")

    def place_po(self, part: str, hub: str, option: dict, qty: int) -> dict:
        po = {"po": f"PO-{7720 + len(self.pos)}", "part": part, "hub": hub, "vendor": option["vendor"], "qty": qty,
              "total_usd": option["landed_usd"], "arrives": option["arrives"],
              "status": "approved (auto, under $500)" if option["landed_usd"] <= 500 else "approved by manager"}
        self.pos.append(po)
        self.inventory[hub].setdefault(part, {"on_hand": 0, "inbound": []})["inbound"].append(
            {"qty": qty, "eta": option["arrives"], "from": option["vendor"], "po": po["po"]})
        return po

    # ---------------------------------------------------------------- reads the screens use
    def fab_statuses(self) -> dict:
        return {k: fab_status(k, r) for k, r in self.fab_readings.items()}

    def prevention(self) -> dict:
        return {k: failure_risk(k, self.readings[k]) for k in self.products}

    def maintenance_jobs(self) -> list[dict]:
        out = []
        for pid, comps in self.lifeline_table.items():
            for c in comps:
                if (c["due_by"] - TODAY).days <= HORIZON_DAYS:
                    out.append({"type": "maintenance", "product": pid, "component": c["component"],
                                "parts": [[c["part"], 1]], "due_by": c["due_by"], "reason":
                                f"{c['component']} at {c['used_pct']}% of rated life", "source": PLACEHOLDER})
        return out

    def jobs_for_hub(self, hub: str) -> list[dict]:
        return [j for j in self.queue()["jobs"] if j["hub"] == hub]

    def predicted_for_hub(self, hub: str) -> list[dict]:
        out = []
        for pid, p in self.prevention().items():
            if self.products[pid]["hub"] == hub and p["action"] == "watch":
                for c in self.lifeline_table.get(pid, [])[:1]:
                    out.append({"product": pid, "parts": [[c["part"], 1]], "p_need": p["risk"]})
        return out

    def queue(self) -> dict:
        """Console: one priority queue from the three loops (idea.md section 6), then allocate stock in that order
        so a part is never promised twice."""
        prev = self.prevention()
        jobs = []
        for c in self.cures:
            jobs.append({"type": "cure", "product": c["product"], "component": c["component"], "parts": c["parts"],
                         "due_by": TODAY, "rank_key": (0, -c["downtime_usd_per_h"]),
                         "reason": f"{c['code']}: {c['meaning']} (product is down)", "incident": c["id"]})
        for m in self.maintenance_jobs():
            p = prev[m["product"]]
            if p["action"] == "act":
                promoted = day(6)  # next Thursday route (placeholder routing)
                jobs.append({**m, "type": "prevention", "due_by": promoted, "was_due": m["due_by"],
                             "rank_key": (1, -p["risk"]), "reason": f"failure risk {p['risk']:.0%} (Matthew's model; "
                             f"{p['worst_signal']} off peers); pulled forward from {m['due_by']:%b %d}"})
            else:
                jobs.append({**m, "rank_key": (2, (m["due_by"] - TODAY).days)})
        for pid, p in prev.items():  # a strong signal on a product with no due job still creates one
            if p["action"] == "act" and not any(j["product"] == pid for j in jobs):
                comps = self.lifeline_table.get(pid, [])
                if comps:
                    c = comps[0]
                    jobs.append({"type": "prevention", "product": pid, "component": c["component"],
                                 "parts": [[c["part"], 1]], "due_by": day(6), "was_due": c["due_by"],
                                 "rank_key": (1, -p["risk"]), "reason": f"failure risk {p['risk']:.0%} (Matthew's model; "
                                 f"{p['worst_signal']} off peers); pulled forward from {c['due_by']:%b %d}"})
        jobs.sort(key=lambda j: j["rank_key"])
        stock = {h: {k: v["on_hand"] for k, v in inv.items()} for h, inv in self.inventory.items()}
        allocation: dict = {}
        for i, j in enumerate(jobs, 1):
            hub = self.products[j["product"]]["hub"]
            j.update(job_id=f"JOB-{1040 + i}", rank=i, hub=hub, product_name=self.products[j["product"]]["name"],
                     site=self.products[j["product"]]["site"])
            status = []
            for part, q in j["parts"]:
                if stock[hub].get(part, 0) >= q:
                    stock[hub][part] -= q
                    allocation[(hub, part)] = allocation.get((hub, part), 0) + q
                    status.append({"part": part, "state": "reserved", "text": f"reserved at {HUBS[hub]['name']}"})
                    continue
                # nearest hub that keeps its own buffer, then central (idea.md section 4 ladder)
                donors = sorted((h for h in stock if h != hub and stock[h].get(part, 0) - q >= (0 if h == "CENTRAL"
                                                                                                else BUFFER)),
                                key=lambda h: (h == "CENTRAL", transit(h, hub)))
                if donors:
                    h = donors[0]
                    stock[h][part] -= q
                    status.append({"part": part, "state": "transfer", "from": h,
                                   "text": f"transfer from {HUBS[h]['name']}, arrives {day(transit(h, hub)):%b %d}"})
                    continue
                inbound = self.inventory[hub].get(part, {}).get("inbound", [])
                if inbound:
                    status.append({"part": part, "state": "on order",
                                   "text": f"on order ({inbound[0]['po']}), arrives {inbound[0]['eta']:%b %d}"})
                else:
                    status.append({"part": part, "state": "short", "text": "short: order needed"})
            j["parts_status"] = status
        counts = {t: sum(j["type"] == t for j in jobs) for t in ("cure", "prevention", "maintenance")}
        return {"jobs": jobs, "allocation": allocation, "counts": counts}

    def snapshot(self) -> "Plant":
        return copy.deepcopy(self)
