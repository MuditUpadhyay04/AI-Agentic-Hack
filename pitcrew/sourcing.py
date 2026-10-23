"""Sourcing: get the part to the site first, then refill the hubs.

Every job in the priority queue names a part number and a customer site (a lifeline task from the
maintenance pipeline, a predicted failure from the failure-prediction model, or a cure). ``fulfil`` walks a
fixed ladder for that part:

1. The site's local hub has it: ship from there.
2. It doesn't: the central hub refills the local hub to its target (at least the job's quantity), then the
   local hub ships.
3. The central hub can't: another local hub with stock above its reorder level sends it.
4. Nobody has it: buy from the fastest verified vendor, straight to the local hub.

``restock_local_hubs`` refills local hubs at or below their reorder level from the central hub, and
``central_plan`` prices refilling the central hub from the verified vendor list: the cheapest vendor whose
order arrives by the need-by date, with the fastest shown beside it and the order-by date for each.
Unverified vendors are listed as excluded and never chosen.

All hubs, stock levels, vendors and prices in ``demo_network`` are placeholders.
"""
from __future__ import annotations

import datetime as dt
import itertools
from dataclasses import asdict, dataclass, field

from .ops import policy_check

TODAY = dt.date(2026, 10, 23)
CENTRAL = "Central hub"
KIND_RANK = {"cure": 0, "prevention": 1, "maintenance": 2}


@dataclass
class Job:
    """One task in the priority queue (the shape every pipeline writes; see idea.md section 6)."""

    job_id: str
    kind: str  # "cure" | "prevention" | "maintenance"
    pn: str
    site: str
    due: dt.date
    qty: int = 1
    reason: str = ""
    status: str = "open"


def rank(jobs: list[Job]) -> list[Job]:
    """Cure first, then prevention, then maintenance; within a kind, the earliest due date first."""
    return sorted(jobs, key=lambda j: (KIND_RANK[j.kind], j.due, j.job_id))


@dataclass
class Stock:
    on_hand: int
    reorder_level: int
    target: int


@dataclass(frozen=True)
class VendorQuote:
    vendor: str
    pn: str
    unit_usd: float
    lead_days: int  # order placed -> delivered to the central hub
    verified: bool = True
    shipping_usd: float = 0.0
    moq: int = 1


@dataclass
class Network:
    """Central hub, local hubs, customer sites, stock per hub and part, and the vendor list."""

    parts: dict  # pn -> name
    sites: dict  # site -> its local hub
    stock: dict  # (hub, pn) -> Stock
    quotes: dict  # pn -> [VendorQuote]
    today: dt.date = TODAY
    review_days: int = 10  # refill the central hub before the next review, or sooner if a job needs it
    hub_transit_days: int = 1  # central <-> local
    lateral_transit_days: int = 2  # local <-> local
    jobs: list = field(default_factory=list)
    moves: list = field(default_factory=list)
    inbound: list = field(default_factory=list)
    pos: list = field(default_factory=list)
    _po: itertools.count = field(default_factory=lambda: itertools.count(7711), repr=False)

    # ---- inventory
    @property
    def local_hubs(self) -> list[str]:
        return sorted(set(self.sites.values()))

    def _stock(self, hub: str, pn: str) -> Stock:
        return self.stock.setdefault((hub, pn), Stock(0, 0, 0))

    def hub_stock(self, pn: str) -> dict:
        rows = []
        for hub in [CENTRAL] + self.local_hubs:
            s = self._stock(hub, pn)
            inbound = sum(i["qty"] for i in self.inbound if i["pn"] == pn and i["to"] == hub)
            rows.append({"hub": hub, "on_hand": s.on_hand, "reorder_level": s.reorder_level, "target": s.target,
                         "inbound": inbound, "status": "low" if s.on_hand + inbound <= s.reorder_level else "ok"})
        return {"pn": pn, "name": self.parts.get(pn, pn), "hubs": rows}

    def _move(self, frm: str, to: str, pn: str, qty: int, why: str, days: int) -> dict:
        self._stock(frm, pn).on_hand -= qty
        if to == CENTRAL or to in self.local_hubs:
            self._stock(to, pn).on_hand += qty
        m = {"from": frm, "to": to, "pn": pn, "qty": qty, "why": why,
             "arrives": (self.today + dt.timedelta(days=days)).isoformat()}
        self.moves.append(m)
        return m

    # ---- the ladder
    def fulfil(self, job: Job) -> dict:
        """Get ``job.qty`` of ``job.pn`` to ``job.site``: local hub, else central, else another local hub,
        else buy from the fastest verified vendor."""
        local = self.sites[job.site]
        ls, cs = self._stock(local, job.pn), self._stock(CENTRAL, job.pn)
        moves, route = [], ""
        if ls.on_hand >= job.qty:
            route = "local"
        elif cs.on_hand >= job.qty - ls.on_hand:
            send = min(cs.on_hand, max(ls.target - ls.on_hand, job.qty - ls.on_hand))
            moves.append(self._move(CENTRAL, local, job.pn, send,
                                    f"{local} had {ls.on_hand}; refill to target {ls.target} for {job.job_id}",
                                    self.hub_transit_days))
            route = "central"
        else:
            donors = [h for h in self.local_hubs if h != local
                      and self._stock(h, job.pn).on_hand - job.qty >= self._stock(h, job.pn).reorder_level]
            if donors:
                donor = max(donors, key=lambda h: self._stock(h, job.pn).on_hand)
                moves.append(self._move(donor, local, job.pn, job.qty, f"lateral transfer for {job.job_id}",
                                        self.lateral_transit_days))
                route = "lateral"
            else:
                plan = self.central_plan(job.pn, qty=job.qty, need_by=job.due, deliver_to=local)
                po = self.place_order(job.pn, plan["fastest"]["vendor"], plan["qty"], deliver_to=local)
                return {"job": asdict(job), "route": "buy", "moves": [], "po": po,
                        "note": f"No hub has {job.pn}; bought from the fastest verified vendor."}
        days = 0 if route == "local" else (self.hub_transit_days if route == "central" else self.lateral_transit_days)
        moves.append(self._move(local, job.site, job.pn, job.qty, f"{job.kind} {job.job_id}", days))
        job.status = "part on site" if days == 0 else "part in transit"
        return {"job": asdict(job), "route": route, "moves": moves,
                "local_after": self._stock(local, job.pn).on_hand, "central_after": cs.on_hand}

    def restock_local_hubs(self, pn: str) -> dict:
        """Refill every local hub at or below its reorder level to its target, from the central hub."""
        cs, moves = self._stock(CENTRAL, pn), []
        for hub in self.local_hubs:
            s = self._stock(hub, pn)
            if s.on_hand <= s.reorder_level and s.target > s.on_hand and cs.on_hand > 0:
                qty = min(s.target - s.on_hand, cs.on_hand)
                moves.append(self._move(CENTRAL, hub, pn, qty, f"{hub} at {s.on_hand} (reorder level "
                                                               f"{s.reorder_level}); refill to {s.target}",
                                        self.hub_transit_days))
        return {"pn": pn, "moves": moves, "central_after": cs.on_hand,
                "central_low": cs.on_hand <= cs.reorder_level}

    # ---- buying
    def need_by(self, pn: str) -> dict:
        """The next review date, or earlier if an open job for this part would take the network below the
        local hubs' reorder levels (the stock kept for emergencies)."""
        default = self.today + dt.timedelta(days=self.review_days)
        level = sum(self._stock(h, pn).on_hand for h in [CENTRAL] + self.local_hubs)
        level += sum(i["qty"] for i in self.inbound if i["pn"] == pn)
        keep = sum(self._stock(h, pn).reorder_level for h in self.local_hubs)
        for j in rank([j for j in self.jobs if j.pn == pn and j.status == "open"]):
            level -= j.qty
            if level < keep and j.due < default:
                return {"date": j.due, "why": f"{j.job_id} on {j.due.isoformat()} would use the emergency stock"}
        return {"date": default, "why": f"next review in {self.review_days} days"}

    def central_plan(self, pn: str, qty: int | None = None, need_by: dt.date | None = None,
                     deliver_to: str = CENTRAL) -> dict:
        """How many to buy for the central hub, by when, and the cheapest-in-time vs fastest verified vendor."""
        cs = self._stock(CENTRAL, pn)
        inbound = sum(i["qty"] for i in self.inbound if i["pn"] == pn and i["to"] == CENTRAL)
        position = cs.on_hand + inbound
        if qty is None:
            if position > cs.reorder_level:
                return {"pn": pn, "needed": False, "position": position, "reorder_level": cs.reorder_level}
            qty = cs.target - position
        nb = {"date": need_by, "why": "the job's due date"} if need_by else self.need_by(pn)
        extra_days = 0 if deliver_to == CENTRAL else self.hub_transit_days
        options, excluded = [], []
        for q in self.quotes.get(pn, []):
            n = max(qty, q.moq)
            arrives = self.today + dt.timedelta(days=q.lead_days + extra_days)
            row = {"vendor": q.vendor, "qty": n, "unit_usd": q.unit_usd, "lead_days": q.lead_days + extra_days,
                   "arrives": arrives.isoformat(), "total_usd": round(n * q.unit_usd + q.shipping_usd, 2),
                   "in_time": arrives <= nb["date"],
                   "order_by": (nb["date"] - dt.timedelta(days=q.lead_days + extra_days)).isoformat()}
            (options if q.verified else excluded).append(row if q.verified else {**row, "why": "not verified"})
        in_time = [o for o in options if o["in_time"]]
        cheapest = min(in_time, key=lambda o: o["total_usd"]) if in_time else None
        fastest = min(options, key=lambda o: (o["arrives"], o["total_usd"])) if options else None
        pick = cheapest or fastest
        for o in options:
            o["label"] = ("choice: cheapest in time" if o is pick and o is cheapest else
                          "choice: fastest (nothing arrives in time)" if o is pick else
                          "fastest" if o is fastest else
                          "cheapest, but too late" if not o["in_time"] and o["total_usd"] < (pick or o)["total_usd"]
                          else "in time" if o["in_time"] else "too late")
        return {"pn": pn, "needed": True, "qty": qty, "position": position, "reorder_level": cs.reorder_level,
                "target": cs.target, "need_by": nb["date"].isoformat(), "need_by_why": nb["why"],
                "deliver_to": deliver_to, "options": sorted(options, key=lambda o: o["total_usd"]),
                "excluded": excluded, "cheapest_in_time": cheapest, "fastest": fastest, "pick": pick,
                "policy": policy_check("create_po", total_usd=pick["total_usd"]) if pick else None}

    def place_order(self, pn: str, vendor: str, qty: int, deliver_to: str = CENTRAL) -> dict:
        """Raise a PO with a verified vendor; the policy auto-approves small orders, larger ones wait for a planner."""
        q = next((q for q in self.quotes.get(pn, []) if q.vendor == vendor), None)
        if q is None or not q.verified:
            return {"placed": False, "why": f"{vendor} is not a verified vendor for {pn}"}
        n = max(qty, q.moq)
        extra_days = 0 if deliver_to == CENTRAL else self.hub_transit_days
        total = round(n * q.unit_usd + q.shipping_usd, 2)
        chk = policy_check("create_po", total_usd=total)
        po = {"po": f"PO-{next(self._po)}", "vendor": vendor, "pn": pn, "qty": n, "total_usd": total,
              "deliver_to": deliver_to,
              "arrives": (self.today + dt.timedelta(days=q.lead_days + extra_days)).isoformat(),
              "status": "approved (auto, under limit)" if chk["allowed"] else "awaiting planner",
              "policy": chk, "placed": True}
        self.pos.append(po)
        if chk["allowed"]:
            self.inbound.append({"po": po["po"], "pn": pn, "qty": n, "to": deliver_to, "arrives": po["arrives"]})
        return po

    def advance(self, to: dt.date) -> dict:
        """Move the clock forward and receive every shipment that has arrived."""
        self.today = to
        got = [i for i in self.inbound if dt.date.fromisoformat(i["arrives"]) <= to]
        for i in got:
            self._stock(i["to"], i["pn"]).on_hand += i["qty"]
        self.inbound = [i for i in self.inbound if i not in got]
        return {"today": to.isoformat(), "received": got}


def demo_jobs() -> list[Job]:
    """The queue in the pitch simulation (docs/SIMULATION_PROMPT.md, section 7)."""
    d = dt.date
    return [
        Job("MNT-198", "maintenance", "PN-3307", "E2", d(2026, 11, 6), reason="Rated 20,000 h, now at 18,900 h"),
        Job("MNT-199", "maintenance", "PN-1043", "S1", d(2026, 11, 9), reason="Rated 3 years, installed Nov 2023"),
        Job("MNT-200", "maintenance", "PN-2210", "N1", d(2026, 11, 12), reason="Rated 50,000 h, now at 47,800 h"),
        Job("MNT-201", "maintenance", "PN-3307", "W1", d(2026, 11, 14), reason="Rated 20,000 h, now at 18,600 h"),
        Job("MNT-202", "maintenance", "PN-4518", "N2", d(2026, 11, 20), reason="Rated 5 years, installed Nov 2021"),
        Job("PRV-031", "prevention", "PN-1043", "E1", d(2026, 10, 28), reason="Failure predicted in 5 days (80%)"),
        Job("CUR-007", "cure", "PN-2210", "S2", d(2026, 10, 23), reason="Storm power surge, line down"),
    ]


def demo_network() -> Network:
    """One central hub, four local hubs, eight customer sites, four parts, four vendors (one unverified)."""
    parts = {"PN-1043": "Cooling fan module", "PN-2210": "Power supply board", "PN-3307": "Sensor module",
             "PN-4518": "Controller board"}
    sites = {s: f"Local hub {h}" for h, ss in {"North": ("N1", "N2"), "East": ("E1", "E2"),
                                                "South": ("S1", "S2"), "West": ("W1", "W2")}.items() for s in ss}
    levels = {  # (hub, pn): (on_hand, reorder_level, target)
        (CENTRAL, "PN-1043"): (15, 10, 20), (CENTRAL, "PN-2210"): (11, 10, 20),
        (CENTRAL, "PN-3307"): (12, 6, 16), (CENTRAL, "PN-4518"): (6, 3, 8),
        ("Local hub East", "PN-1043"): (0, 1, 3), ("Local hub South", "PN-2210"): (2, 2, 4),
        ("Local hub North", "PN-2210"): (2, 1, 3), ("Local hub South", "PN-1043"): (2, 1, 3),
        ("Local hub East", "PN-3307"): (2, 1, 3), ("Local hub West", "PN-3307"): (2, 1, 3),
        ("Local hub North", "PN-4518"): (1, 0, 2),
    }
    quotes = {
        "PN-2210": [VendorQuote("Vendor A", "PN-2210", 38.0, 13), VendorQuote("Vendor B", "PN-2210", 46.0, 4),
                    VendorQuote("Vendor C", "PN-2210", 41.0, 7),
                    VendorQuote("Vendor D", "PN-2210", 31.0, 5, verified=False)],
        "PN-1043": [VendorQuote("Vendor A", "PN-1043", 22.0, 10), VendorQuote("Vendor B", "PN-1043", 29.0, 3)],
        "PN-3307": [VendorQuote("Vendor C", "PN-3307", 64.0, 6), VendorQuote("Vendor B", "PN-3307", 75.0, 2)],
        "PN-4518": [VendorQuote("Vendor A", "PN-4518", 180.0, 14), VendorQuote("Vendor C", "PN-4518", 205.0, 8)],
    }
    return Network(parts=parts, sites=sites, stock={k: Stock(*v) for k, v in levels.items()}, quotes=quotes,
                   jobs=demo_jobs())
