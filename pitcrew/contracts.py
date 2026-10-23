"""PitCrew v0.2: the one place the console meets each teammate's part.

The console calls only the functions in this file. Each section names its owner and the shape the console
expects; swap the placeholder body for the real call and the screens pick it up unchanged.

    Internal fab   (Hari)     fab_status, fab_forecast       real model: machine_downtime_model/predict.py
    Prevention     (Matthew)  peer_deviation                 placeholder (AI4I model to plug in)
    Maintenance    (tbd)      lifelines, maintenance_jobs    placeholder (lifeline pipeline to plug in)
    Sourcing/Cure  (Mudit)    order_card, cure_events        placeholder (follows idea.md section 7a)
    Priority queue (console)  queue                          real: merges the three loops (idea.md section 6)

Every placeholder result carries ``source="placeholder"`` so the screens can label it. Names, prices,
hubs and lifetimes are placeholders, not Janta values.
"""
from __future__ import annotations

import copy
import datetime as dt
import math
import statistics as stats
import sys
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
    "MK-L1": {"name": "Makino L1", "line": "Shopfloor-L1", "makes": ["GEAR-SET-SD"],
              "reading": {"Hydraulic_Pressure(bar)": 130.0, "Torque(Nm)": 32.0}},
    "MK-L2": {"name": "Makino L2", "line": "Shopfloor-L2", "makes": ["HOUSING-SD"],
              "reading": {"Hydraulic_Pressure(bar)": 125.0, "Torque(Nm)": 30.0}},
    "MK-L3": {"name": "Makino L3", "line": "Shopfloor-L3", "makes": ["DRIVE-MOTOR-SD"],
              "reading": {"Hydraulic_Pressure(bar)": 128.0, "Torque(Nm)": 31.0}},
}
# Hari's example of a failing machine (machine_downtime_model/example.py, FAILING_MACHINE).
FAILING_READING = {"Hydraulic_Pressure(bar)": 80.13, "Coolant_Pressure(bar)": 4.79, "Coolant_Temperature": 23.0,
                   "Spindle_Speed(RPM)": 19964.0, "Voltage(volts)": 348.0, "Torque(Nm)": 24.63, "Cutting(kN)": 2.84}
IN_HOUSE_BASE_LEAD = 3  # days to make a part in-house when the machine is healthy (placeholder)
IN_HOUSE_UNIT_USD = {"DRIVE-MOTOR-SD": 300.0, "GEAR-SET-SD": 90.0, "HOUSING-SD": 120.0}  # internal cost (placeholder)
RESTORE_DAYS = 5  # when only the emergency buffer is short, restore it within this many days

_predict = None


def _model():
    global _predict
    if _predict is None:
        d = str(ROOT / "machine_downtime_model")
        if d not in sys.path:
            sys.path.insert(0, d)
        from predict import predict_with_details  # Hari's module

        _predict = predict_with_details
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
SIGNALS = {  # signal: (label, worse direction: +1 higher is worse, -1 lower is worse)
    "msgs_per_hour": ("Telemetry messages / hour", -1),
    "warnings_per_day": ("Warning codes / day", +1),
    "performance_ratio": ("Performance ratio", -1),
    "effort_per_deg": ("Drive energy per degree", +1),
}


def _peer_values(base: float, spread: float, n: int = 15) -> list[float]:
    return [round(base + spread * math.sin(1.7 * i + 0.4), 3) for i in range(n)]


def peer_deviation(product: dict, peers: dict) -> dict:
    """Matthew (placeholder until the AI4I model lands): robust z of a product vs its peers, worst signal wins.

    z = (x - median_peers) / (1.4826 * MAD_peers), signed so that worse is positive (idea.md section 4)."""
    rows = []
    for key, (label, sign) in SIGNALS.items():
        vals = peers[key]
        med = stats.median(vals)
        mad = stats.median(abs(v - med) for v in vals) or 1e-9
        z = sign * (product[key] - med) / (1.4826 * mad)
        rows.append({"signal": key, "label": label, "value": product[key], "peer_median": round(med, 3),
                     "peer_low": min(vals), "peer_high": max(vals), "z": round(z, 2)})
    worst = max(rows, key=lambda r: r["z"])
    d = worst["z"]
    action = "act" if d > 3 else "watch" if d >= 2 else "normal"
    return {"product": product["id"], "D": round(d, 2), "worst_signal": worst["label"], "action": action,
            "signals": rows, "peer_count": len(peers[next(iter(SIGNALS))]), "source": PLACEHOLDER}


# ============================================================================ Maintenance (owner tbd)
def lifelines(product_id: str, plant: "Plant") -> list[dict]:
    """Lifeline pipeline (placeholder): rated life used per component and the projected due date."""
    return [dict(c, source=PLACEHOLDER) for c in plant.lifeline_table.get(product_id, [])]


# ============================================================================ Sourcing + Cure (Mudit)
ERROR_CODES = {  # placeholder table: which codes mean "down" (Cure) vs "warning" (a Prevention signal)
    "E-STALL": {"meaning": "Drive stalled under load", "kind": "down", "component": "drive motor",
                "parts": [["DRIVE-MOTOR-SD", 1]], "downtime_usd_per_h": 18.0},
    "W-COMM": {"meaning": "Telemetry gaps", "kind": "warning", "component": "controller", "parts": []},
    "W-FRIC": {"meaning": "Drive friction above baseline", "kind": "warning", "component": "slew drive seal",
               "parts": [["SEAL-KIT-SD", 1]]},
}
HUBS = {
    "CENTRAL": {"name": "Central hub (factory)", "kind": "central"},
    "NORTH": {"name": "Local hub North", "kind": "local", "sites": ["DFW warehouse roof"]},
    "EAST": {"name": "Local hub East", "kind": "local", "sites": ["Data center lot"]},
    "SOUTH": {"name": "Local hub South", "kind": "local", "sites": ["Open field, Ellis County"]},
}
TRANSIT_DAYS = {("CENTRAL", "NORTH"): 1, ("CENTRAL", "EAST"): 1, ("CENTRAL", "SOUTH"): 2,
                ("NORTH", "EAST"): 1, ("NORTH", "SOUTH"): 2, ("EAST", "SOUTH"): 1}
VENDORS = {  # authorized vendors per part (placeholder prices: idea.md worked example)
    "SEAL-KIT-SD": [{"vendor": "Vendor X", "unit_usd": 58.0, "lead_days": 10, "ship_usd": 0.0},
                    {"vendor": "DriveParts TX", "unit_usd": 65.0, "lead_days": 3, "ship_usd": 0.0},
                    {"vendor": "Vendor Y", "unit_usd": 72.0, "lead_days": 1, "ship_usd": 0.0}],
    "GREASE-KIT-SD": [{"vendor": "Lube Supply", "unit_usd": 22.0, "lead_days": 4, "ship_usd": 8.0},
                      {"vendor": "Vendor Y", "unit_usd": 31.0, "lead_days": 1, "ship_usd": 0.0}],
    "DRIVE-MOTOR-SD": [{"vendor": "MotionCo", "unit_usd": 410.0, "lead_days": 6, "ship_usd": 25.0},
                       {"vendor": "DriveParts TX", "unit_usd": 465.0, "lead_days": 2, "ship_usd": 0.0}],
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
        self.products = {
            "T-07": {"id": "T-07", "name": "Tower 7", "hub": "NORTH", "site": "DFW warehouse roof"},
            "T-19": {"id": "T-19", "name": "Tower 19", "hub": "NORTH", "site": "DFW warehouse roof"},
            "T-23": {"id": "T-23", "name": "Tower 23", "hub": "NORTH", "site": "DFW warehouse roof"},
            "T-31": {"id": "T-31", "name": "Tower 31", "hub": "NORTH", "site": "DFW warehouse roof"},
            "T-12": {"id": "T-12", "name": "Tower 12", "hub": "EAST", "site": "Data center lot"},
            "T-42": {"id": "T-42", "name": "Tower 42", "hub": "SOUTH", "site": "Open field, Ellis County"},
        }
        healthy = {"msgs_per_hour": 60.0, "warnings_per_day": 1.0, "performance_ratio": 0.97, "effort_per_deg": 1.0}
        self.telemetry = {k: dict(healthy) for k in self.products}
        self.peers = {"msgs_per_hour": _peer_values(60, 3), "warnings_per_day": _peer_values(1.0, 0.5),
                      "performance_ratio": _peer_values(0.97, 0.015), "effort_per_deg": _peer_values(1.0, 0.05)}
        self.lifeline_table = {
            "T-31": [{"component": "Slew drive seal", "used_pct": 92, "due_by": day(5), "part": "SEAL-KIT-SD"}],
            "T-23": [{"component": "Slew drive seal", "used_pct": 88, "due_by": day(12), "part": "SEAL-KIT-SD"}],
            "T-07": [{"component": "Slew drive seal", "used_pct": 71, "due_by": day(28), "part": "SEAL-KIT-SD"},
                     {"component": "Drive grease", "used_pct": 64, "due_by": day(40), "part": "GREASE-KIT-SD"}],
            "T-12": [{"component": "Drive grease", "used_pct": 90, "due_by": day(9), "part": "GREASE-KIT-SD"}],
            "T-42": [{"component": "Drive grease", "used_pct": 84, "due_by": day(20), "part": "GREASE-KIT-SD"}],
            "T-19": [{"component": "Drive motor", "used_pct": 55, "due_by": day(120), "part": "DRIVE-MOTOR-SD"}],
        }
        self.inventory = {
            "CENTRAL": {"SEAL-KIT-SD": {"on_hand": 6, "inbound": []}, "GREASE-KIT-SD": {"on_hand": 12, "inbound": []},
                        "DRIVE-MOTOR-SD": {"on_hand": 1, "inbound": []}},
            "NORTH": {"SEAL-KIT-SD": {"on_hand": 2, "inbound": []}, "GREASE-KIT-SD": {"on_hand": 4, "inbound": []},
                      "DRIVE-MOTOR-SD": {"on_hand": 1, "inbound": []}},
            "EAST": {"SEAL-KIT-SD": {"on_hand": 4, "inbound": []}, "GREASE-KIT-SD": {"on_hand": 3, "inbound": []},
                     "DRIVE-MOTOR-SD": {"on_hand": 0, "inbound": []}},
            "SOUTH": {"SEAL-KIT-SD": {"on_hand": 2, "inbound": []}, "GREASE-KIT-SD": {"on_hand": 3, "inbound": []},
                      "DRIVE-MOTOR-SD": {"on_hand": 0, "inbound": []}},
        }
        self.cures: list[dict] = []
        self.pos: list[dict] = []

    # ---------------------------------------------------------------- demo events
    def tower7_drifts(self) -> None:
        self.telemetry["T-07"].update(msgs_per_hour=42.0, warnings_per_day=4.0, performance_ratio=0.95,
                                      effort_per_deg=1.08)
        self.events.append("prevention:T-07")

    def tower19_stalls(self) -> dict:
        code = ERROR_CODES["E-STALL"]
        c = {"id": f"INC-{301 + len(self.cures)}", "product": "T-19", "code": "E-STALL", "opened": dt.datetime.now(),
             **code}
        self.cures.append(c)
        self.events.append("cure:T-19")
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
        return {k: peer_deviation({"id": k, **self.telemetry[k]}, self.peers) for k in self.products}

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
                    out.append({"product": pid, "parts": [[c["part"], 1]], "p_need": 0.7})
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
                             "rank_key": (1, -p["D"]), "reason": f"D = {p['D']} vs {p['peer_count']} peers "
                             f"({p['worst_signal']}); pulled forward from {m['due_by']:%b %d}"})
            else:
                jobs.append({**m, "rank_key": (2, (m["due_by"] - TODAY).days)})
        for pid, p in prev.items():  # a strong signal on a product with no due job still creates one
            if p["action"] == "act" and not any(j["product"] == pid for j in jobs):
                comps = self.lifeline_table.get(pid, [])
                if comps:
                    c = comps[0]
                    jobs.append({"type": "prevention", "product": pid, "component": c["component"],
                                 "parts": [[c["part"], 1]], "due_by": day(6), "was_due": c["due_by"],
                                 "rank_key": (1, -p["D"]), "reason": f"D = {p['D']} vs {p['peer_count']} peers "
                                 f"({p['worst_signal']}); pulled forward from {c['due_by']:%b %d}"})
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
