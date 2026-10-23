"""The shared state the crew works on, and every tool the agents can call.

Each tool is a plain function returning JSON-able data. The offline crew calls them directly; the Strands
crew wraps the same functions as ``@tool``s; AgentCore Gateway can expose them as MCP tools. Every call is
recorded in ``World.trace`` so the console can show which agent called what, with which numbers.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import time
from dataclasses import asdict
from functools import cached_property
from pathlib import Path

import numpy as np

from . import mill as millmod
from .decide import TowerEconomics, diagnose, park_and_price
from .futures import ranking
from .kaizen import design_change_request, lot_analysis, rediscover_ai4i, time_to_alarm_by_lot, tracking_tradeoff
from .ops import Ops, policy_check
from .passport import MANUALS, from_manual, install_slot, manuals, sign
from .sourcing import Network, demo_network, rank
from .tower import Fleet

ROOT = Path(__file__).resolve().parents[1]


def _clean(x):
    """numpy -> python, recursively, so every tool result is JSON."""
    if isinstance(x, dict):
        return {str(k): _clean(v) for k, v in x.items() if not callable(v)}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    if isinstance(x, np.ndarray):
        return [_clean(v) for v in x.tolist()]
    if isinstance(x, (np.floating,)):
        return None if not np.isfinite(x) else float(x)
    if isinstance(x, float) and not np.isfinite(x):
        return None
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.bool_,)):
        return bool(x)
    if type(x) is dt.date:  # plain dates only: leave pandas Timestamps as they were
        return x.isoformat()
    return x


class World:
    def __init__(self, seed: int = 5):
        self.seed = seed
        self.ops = Ops()
        self.trace: list[dict] = []
        self.agent = "system"
        self.passports: dict = {}
        self.installed_slots: tuple = ()
        self.mill_state = {"asset": "VM-07", "rpm": 1500.0, "torque": 56.0, "wear": 120.0, "d_temp": 8.2,
                           "creep": 0.3, "variant": "L", "parts_to_window": 30, "setpoint": "1500 rpm, feed 100%"}
        self.tower_modes: dict = {}
        self.econ = TowerEconomics()

    @cached_property
    def fleet(self) -> Fleet:
        return Fleet(seed=self.seed).run()

    @cached_property
    def network(self) -> Network:
        return demo_network()

    # ------------------------------------------------------------------ trace
    def _rec(self, tool: str, args: dict, result):
        res = _clean(result)
        self.trace.append({"t": time.time(), "agent": self.agent, "tool": tool, "args": _clean(args),
                           "result": res})
        return res

    # ------------------------------------------------------------------ mill
    def read_mill(self) -> dict:
        s = self.mill_state
        m = millmod.margins(s["rpm"], s["torque"], s["wear"], s["d_temp"], s["variant"])
        n, walls = millmod.parts_until_wall(s["rpm"], s["torque"], s["wear"], s["d_temp"], s["creep"], s["variant"])
        return self._rec("read_mill", {}, {**s, "power_w": round(s["torque"] * millmod.omega(s["rpm"])),
                                           "margins": {k: round(v, 3) for k, v in m.items()},
                                           "parts_until_wall": n, "walls_hit": walls,
                                           "wall_names": {w: millmod.WALL_NAMES[w] for w in walls}})

    def price_mill_options(self) -> dict:
        opts = millmod.mill_options(self.mill_state)
        rows = [o.__dict__ for o in opts]
        rec = min(rows, key=lambda o: o["cost_usd"])
        return self._rec("price_mill_options", {}, {"options": rows, "recommendation": rec["key"],
                                                    "assumptions": millmod.MillEconomics().__dict__})

    def search_manual(self, query: str, manual: str = "vm07_mill_manual.md") -> dict:
        text = (MANUALS / manual).read_text().splitlines()
        words = [w for w in re.findall(r"[a-z0-9]+", query.lower()) if len(w) > 2]
        hits = [(sum(w in ln.lower() for w in words), i, ln) for i, ln in enumerate(text)]
        hits = [h for h in sorted(hits, reverse=True) if h[0] > 0][:4]
        def tidy(ln: str) -> str:
            ln = ln.strip()
            if ln.startswith("|"):
                ln = " - ".join(c.strip() for c in ln.strip("|").split("|") if c.strip())
            return ln

        return self._rec("search_manual", {"query": query, "manual": manual},
                         {"manual": manual, "matches": [{"line": i + 1, "text": tidy(ln)} for _, i, ln in hits]})

    def write_mill_setpoint(self, rpm: float, torque: float, approved_by: str) -> dict:
        chk = policy_check("write_setpoint")
        if chk["needs_human"] and not approved_by:
            return self._rec("write_mill_setpoint", {"rpm": rpm, "torque": torque}, {"written": False, "policy": chk})
        self.mill_state.update(rpm=rpm, torque=torque, setpoint=f"{rpm:.0f} rpm, feed cut to {torque:.0f} Nm")
        return self._rec("write_mill_setpoint", {"rpm": rpm, "torque": torque, "approved_by": approved_by},
                         {"written": True, "setpoint": self.mill_state["setpoint"], "policy": chk})

    # ------------------------------------------------------------------ towers
    def fleet_overview(self) -> dict:
        td = self.fleet.today()
        flagged = []
        for tid in td.index:
            d = diagnose(self.fleet, int(tid), self.installed_slots)
            if d["primary"]:
                flagged.append({"tower_id": int(tid), "site": td.loc[tid, "site"], "lot": td.loc[tid, "lot"],
                                "detector": d["primary"]["detector"], "sensor": d["primary"]["sensor"],
                                "value": round(d["primary"]["value"], 3), "alarm": d["primary"]["alarm"]})
        return self._rec("fleet_overview", {"installed_slots": list(self.installed_slots)},
                         {"towers": int(len(td)), "flagged": flagged, "date": str(self.fleet.weather.index[-1].date())})

    def diagnose_tower(self, tower_id: int) -> dict:
        d = diagnose(self.fleet, tower_id, self.installed_slots)
        d.pop("series", None)
        return self._rec("diagnose_tower", {"tower_id": tower_id}, d)

    def price_tower_options(self, tower_id: int) -> dict:
        r = park_and_price(self.fleet, tower_id, self.ops, self.econ, runs=200, slots=self.installed_slots)
        r["diagnosis"].pop("series", None)
        return self._rec("price_tower_options", {"tower_id": tower_id}, r)

    def set_tower_mode(self, tower_id: int, mode: str, approved_by: str) -> dict:
        chk = policy_check("park_tower" if mode == "park" else "write_setpoint")
        if chk["needs_human"] and not approved_by:
            return self._rec("set_tower_mode", {"tower_id": tower_id, "mode": mode}, {"written": False, "policy": chk})
        self.tower_modes[tower_id] = mode
        return self._rec("set_tower_mode", {"tower_id": tower_id, "mode": mode, "approved_by": approved_by},
                         {"written": True, "mode": mode, "policy": chk})

    # ------------------------------------------------------------------ supply + people
    def check_stock(self, pn: str) -> dict:
        return self._rec("check_stock", {"pn": pn}, self.ops.stock(pn))

    def reserve_part(self, pn: str, qty: int, asset: str) -> dict:
        return self._rec("reserve_part", {"pn": pn, "qty": qty, "asset": asset}, self.ops.reserve(pn, qty, asset))

    def request_quotes(self, pn: str, need_by_days: float) -> dict:
        """Ask suppliers (A2A when PITCREW_SUPPLIER_URL is set; the local catalogue otherwise)."""
        return self._rec("request_quotes", {"pn": pn, "need_by_days": need_by_days},
                         self.ops.best_quote(pn, need_by_days))

    def draft_po(self, pn: str, qty: int, supplier: str, unit_usd: float, lead_days: int, extra_usd: float = 0.0):
        return self._rec("draft_po", {"pn": pn, "qty": qty, "supplier": supplier},
                         self.ops.draft_po(pn, qty, supplier, unit_usd, lead_days, extra_usd))

    def next_route_day(self, base: str = "DFW") -> dict:
        return self._rec("next_route_day", {"base": base}, self.ops.next_route_day(base))

    def create_work_order(self, asset: str, title: str, due: str, tech: str, parts: list, evidence: list) -> dict:
        return self._rec("create_work_order", {"asset": asset, "title": title, "due": due},
                         self.ops.create_work_order(asset, title, due, tech, parts, evidence))

    def approve(self, ref: str, who: str = "foreman") -> dict:
        return self._rec("approve", {"ref": ref, "who": who}, self.ops.approve(ref, who))

    # ------------------------------------------------------------------ sourcing (hubs + vendors)
    def job_queue(self) -> dict:
        jobs = [{"rank": i + 1, **asdict(j)} for i, j in enumerate(rank(self.network.jobs))]
        return self._rec("job_queue", {}, {"jobs": jobs, "today": self.network.today.isoformat()})

    def hub_stock(self, pn: str) -> dict:
        return self._rec("hub_stock", {"pn": pn}, self.network.hub_stock(pn))

    def fulfil_job(self, job_id: str) -> dict:
        job = next((j for j in self.network.jobs if j.job_id == job_id), None)
        if job is None:
            return self._rec("fulfil_job", {"job_id": job_id}, {"error": f"no job {job_id}"})
        return self._rec("fulfil_job", {"job_id": job_id}, self.network.fulfil(job))

    def restock_local_hubs(self, pn: str) -> dict:
        return self._rec("restock_local_hubs", {"pn": pn}, self.network.restock_local_hubs(pn))

    def plan_central_order(self, pn: str) -> dict:
        return self._rec("plan_central_order", {"pn": pn}, self.network.central_plan(pn))

    def place_order(self, pn: str, vendor: str, qty: int) -> dict:
        return self._rec("place_order", {"pn": pn, "vendor": vendor, "qty": qty},
                         self.network.place_order(pn, vendor, qty))

    # ------------------------------------------------------------------ improve
    def kaizen_rules(self) -> dict:
        return self._rec("kaizen_rules", {}, rediscover_ai4i())

    def kaizen_lots(self) -> dict:
        lots = lot_analysis(self.fleet).reset_index().to_dict(orient="records")
        tta = time_to_alarm_by_lot(self.fleet).reset_index().to_dict(orient="records")
        return self._rec("kaizen_lots", {}, {"lots": lots, "fresh_grease_to_alarm": tta})

    def sensor_futures(self) -> dict:
        rk, rp, ty = ranking(self.fleet, self.econ)
        crew_value = 0.0
        if len(rp):
            crew_value = float(rp[rp["saved_today"]]["saving_usd"].sum() / ty)
        return self._rec("sensor_futures", {}, {"tower_years": round(ty, 1), "failures": int(len(rp)),
                                                "caught_with_todays_sensors": int(rp["saved_today"].sum()) if len(rp) else 0,
                                                "crew_value_usd_per_tower_year": round(crew_value, 1),
                                                "slots": rk.to_dict(orient="records")})

    def design_change_request(self) -> dict:
        rk, _, _ = ranking(self.fleet, self.econ)
        return self._rec("design_change_request", {}, design_change_request(self.fleet, rk))

    def tracking_tradeoff(self) -> dict:
        return self._rec("tracking_tradeoff", {}, tracking_tradeoff())

    # ------------------------------------------------------------------ grow
    def list_manuals(self) -> dict:
        return self._rec("list_manuals", {}, {"manuals": manuals()})

    def onboard_manual(self, manual: str) -> dict:
        p = from_manual(MANUALS / manual)
        self.passports[p["asset_id"]] = p
        return self._rec("onboard_manual", {"manual": manual}, p)

    def sign_passport(self, asset_id: str, who: str) -> dict:
        p = sign(self.passports[asset_id], who)
        self.passports[asset_id] = p
        return self._rec("sign_passport", {"asset_id": asset_id, "who": who},
                         {"asset_id": asset_id, "approved_by": who, "agents_started": [
                             f"{asset_id}/sentinel", f"{asset_id}/diagnostician", f"{asset_id}/race-engineer"]})

    def install_slot(self, asset_id: str, signal_keyword: str) -> dict:
        p = install_slot(self.passports[asset_id], signal_keyword)
        self.passports[asset_id] = p
        unlocked = [d for s in p["slots"] if s["status"] == "installed" for d in s["unlocks"]]
        if asset_id.startswith("ST-1"):
            self.installed_slots = tuple(sorted(set(self.installed_slots) | set(unlocked)))
        return self._rec("install_slot", {"asset_id": asset_id, "slot": signal_keyword},
                         {"asset_id": asset_id, "detectors_live": unlocked})

    def dump(self) -> str:
        return json.dumps(self.trace, indent=1, default=str)
