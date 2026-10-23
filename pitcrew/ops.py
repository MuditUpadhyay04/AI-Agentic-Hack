"""The operational side the Execute agents act on: parts, purchase orders, technicians, work orders, policy.

A small in-memory "CMMS" so the demo runs anywhere. In the workshop account the same functions sit behind
AgentCore Gateway as MCP tools (``agentcore/``); a real CMMS (MaintainX, as in the AWS sample) replaces the
store without changing the agents.
"""
from __future__ import annotations

import datetime as dt
import itertools
from dataclasses import asdict, dataclass, field

TODAY = dt.date(2026, 10, 23)


@dataclass
class Part:
    pn: str
    desc: str
    unit_usd: float
    on_hand: int
    reorder_point: int
    reorder_qty: int
    preferred_supplier: str


@dataclass
class Quote:
    supplier: str
    pn: str
    unit_usd: float
    lead_days: int
    expedite_usd: float = 0.0
    expedite_lead_days: int | None = None
    field_mtbf_years: float | None = None  # from the Improve loop's supplier scorecard


@dataclass
class Technician:
    name: str
    base: str
    route_days: tuple  # weekday numbers (Mon=0) of the batched route
    emergency_usd: float


@dataclass
class WorkOrder:
    wo: str
    asset: str
    title: str
    due: str
    tech: str
    parts: list
    status: str = "proposed"
    evidence: list = field(default_factory=list)
    approved_by: str | None = None


@dataclass
class PurchaseOrder:
    po: str
    supplier: str
    pn: str
    qty: int
    total_usd: float
    lead_days: int
    status: str = "draft"
    approved_by: str | None = None


# --------------------------------------------------------------------------- policy
POLICY = {
    "po_auto_approve_usd": 500.0,
    "setpoint_change_needs_human": True,  # derate, park, change stow wind: always the foreman
    "park_autonomous_max_kwh_per_day": 0.0,  # 0 = never park without a human (raise to allow small autonomic moves)
    "min_margin_at_window": 0.08,  # Lift & Coast keeps at least 8% headroom to every wall
}


def policy_check(action: str, **kw) -> dict:
    """The same rules AgentCore Policy enforces on Gateway tool calls (Cedar), in code for offline runs."""
    if action == "create_po":
        ok = kw.get("total_usd", 0) <= POLICY["po_auto_approve_usd"]
        return {"allowed": ok, "needs_human": not ok,
                "rule": f"POs up to ${POLICY['po_auto_approve_usd']:.0f} auto-approve; above that the foreman approves"}
    if action in ("write_setpoint", "park_tower", "change_stow_wind"):
        lost = kw.get("kwh_per_day_lost", 1e9)
        auto = lost <= POLICY["park_autonomous_max_kwh_per_day"] and not POLICY["setpoint_change_needs_human"]
        return {"allowed": auto, "needs_human": not auto,
                "rule": "Changing how a machine runs always needs the foreman (setpoint_change_needs_human)"}
    return {"allowed": True, "needs_human": False, "rule": "no rule"}


class Ops:
    """In-memory parts room, suppliers, roster, work orders and POs."""

    def __init__(self):
        self.parts = {p.pn: p for p in [
            Part("INSERT-CNMG-L", "Carbide insert, L-grade steel", 42.0, 4, 4, 10, "Tooling Supply Co."),
            Part("GREASE-KIT-SD", "Slew-drive re-grease kit (EP2 grease, fittings)", 40.0, 12, 6, 24, "DriveParts TX"),
            Part("SEAL-KIT-SD", "Slew-drive seal kit", 65.0, 3, 4, 10, "DriveParts TX"),
            Part("BOLT-KIT-SD", "Drive mounting bolt kit (M16)", 25.0, 9, 4, 10, "DriveParts TX"),
            Part("DRIVE-WSD14", "Worm slew drive, 14 in class (ST-1)", 1200.0, 1, 2, 4, "Lot-A Supplier"),
        ]}
        self.quotes = {
            "DRIVE-WSD14": [
                Quote("Lot-A Supplier", "DRIVE-WSD14", 1200.0, 21, 180.0, 9, field_mtbf_years=11.0),
                Quote("Lot-B Supplier", "DRIVE-WSD14", 1040.0, 14, 0.0, None, field_mtbf_years=3.2),
                Quote("Lot-C Supplier", "DRIVE-WSD14", 1150.0, 28, 260.0, 12, field_mtbf_years=8.5),
            ],
            "SEAL-KIT-SD": [Quote("DriveParts TX", "SEAL-KIT-SD", 65.0, 3)],
            "GREASE-KIT-SD": [Quote("DriveParts TX", "GREASE-KIT-SD", 40.0, 2)],
            "INSERT-CNMG-L": [Quote("Tooling Supply Co.", "INSERT-CNMG-L", 42.0, 2)],
        }
        self.techs = [
            Technician("Rosa M.", "DFW", (3, 4), 400.0),  # batched route Thu/Fri; regional emergency $400
            Technician("Setter, Cell 3", "Plant", (0, 1, 2, 3, 4), 0.0),
        ]
        self.work_orders: list[WorkOrder] = []
        self.pos: list[PurchaseOrder] = []
        self.reservations: list[dict] = []
        self._wo = itertools.count(4101)
        self._po = itertools.count(7710)

    # ---- inventory
    def stock(self, pn: str) -> dict:
        p = self.parts[pn]
        held = sum(r["qty"] for r in self.reservations if r["pn"] == pn)
        return {**asdict(p), "reserved": held, "available": p.on_hand - held}

    def reserve(self, pn: str, qty: int, asset: str) -> dict:
        s = self.stock(pn)
        ok = s["available"] >= qty
        if ok:
            self.reservations.append({"pn": pn, "qty": qty, "asset": asset})
        after = self.stock(pn)
        return {"reserved": ok, "pn": pn, "qty": qty, "available_after": after["available"],
                "below_reorder_point": after["available"] < after["reorder_point"]}

    def best_quote(self, pn: str, need_by_days: float) -> dict:
        """Cheapest quote that arrives in time (expedite if needed); never the cheapest that arrives late."""
        rows = []
        for q in self.quotes.get(pn, []):
            arrive, extra = q.lead_days, 0.0
            if arrive > need_by_days and q.expedite_lead_days is not None and q.expedite_lead_days <= need_by_days:
                arrive, extra = q.expedite_lead_days, q.expedite_usd
            rows.append({**asdict(q), "arrives_in_days": arrive, "extra_usd": extra,
                         "in_time": arrive <= need_by_days, "landed_usd": q.unit_usd + extra})
        ok = [r for r in rows if r["in_time"]]
        pick = min(ok, key=lambda r: (r["landed_usd"] / max(r.get("field_mtbf_years") or 1, 1e-6)
                                      if r.get("field_mtbf_years") else r["landed_usd"])) if ok else None
        return {"pn": pn, "need_by_days": need_by_days, "quotes": rows, "pick": pick}

    def draft_po(self, pn: str, qty: int, supplier: str, unit_usd: float, lead_days: int, extra_usd: float = 0.0):
        total = round(unit_usd * qty + extra_usd, 2)
        po = PurchaseOrder(f"PO-{next(self._po)}", supplier, pn, qty, total, lead_days)
        chk = policy_check("create_po", total_usd=total)
        po.status = "approved (auto, under limit)" if chk["allowed"] else "awaiting foreman"
        if chk["allowed"]:
            po.approved_by = "policy"
        self.pos.append(po)
        return {**asdict(po), "policy": chk}

    # ---- people
    def next_route_day(self, base: str = "DFW") -> dict:
        t = next(x for x in self.techs if x.base == base)
        for k in range(1, 15):
            d = TODAY + dt.timedelta(days=k)
            if d.weekday() in t.route_days:
                return {"tech": t.name, "date": d.isoformat(), "in_days": k, "emergency_usd": t.emergency_usd}
        return {"tech": t.name, "date": None, "in_days": None, "emergency_usd": t.emergency_usd}

    def create_work_order(self, asset: str, title: str, due: str, tech: str, parts: list, evidence: list) -> dict:
        wo = WorkOrder(f"WO-{next(self._wo)}", asset, title, due, tech, parts, evidence=evidence)
        self.work_orders.append(wo)
        return asdict(wo)

    def approve(self, wo_or_po: str, who: str = "foreman") -> dict:
        for w in self.work_orders:
            if w.wo == wo_or_po:
                w.status, w.approved_by = "scheduled", who
                return asdict(w)
        for p in self.pos:
            if p.po == wo_or_po:
                p.status, p.approved_by = "sent to supplier", who
                return asdict(p)
        return {"error": f"{wo_or_po} not found"}
