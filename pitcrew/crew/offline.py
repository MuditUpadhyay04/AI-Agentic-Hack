"""The crew without a model: the same tools, the same order, narration written from the tool results.

Used when Bedrock is not available (tonight, a flaky venue network, a rehearsal) and as the reference the
Bedrock crew is tested against: both must reach the same recommendation from the same tool numbers.
"""
from __future__ import annotations

from ..mill import WALL_NAMES
from ..world import World

STAGES = {"Sentinel": "Monitor", "Diagnostician": "Analyze", "Race Engineer": "Plan", "Quartermaster": "Execute",
          "Dispatcher": "Execute", "Onboarder": "Grow", "Foreman": "Human", "Sourcing": "Supply",
          "Comms": "Notify"}


class Transcript:
    def __init__(self, world: World):
        self.w = world
        self.turns: list[dict] = []

    def speak(self, agent: str, say: str, since: int) -> None:
        self.turns.append({"agent": agent, "stage": STAGES.get(agent, ""), "say": say,
                           "tools": [t for t in self.w.trace[since:]]})

    def as_agent(self, agent: str) -> int:
        self.w.agent = agent
        return len(self.w.trace)


def _money(x) -> str:
    return f"${x:,.0f}"


# ---------------------------------------------------------------------------- mill
def mill_plan(w: World) -> dict:
    tr = Transcript(w)
    i = tr.as_agent("Sentinel")
    s = w.read_mill()
    near = min((k for k in s["margins"] if k != "TWF"), key=lambda k: s["margins"][k])
    tr.speak("Sentinel", (
        f"VM-07 changed its story. Torque is {s['torque']:.0f} Nm at {s['rpm']:.0f} rpm, so spindle power is "
        f"{s['power_w'] / 1000:.1f} kW: {100 * s['margins'][near]:.0f}% headroom to the wall '{WALL_NAMES[near]}'. "
        f"At +{s['creep']} Nm per part the first wall is about {s['parts_until_wall']} parts away "
        f"(~{4 * s['parts_until_wall']} min)."), i)
    i = tr.as_agent("Diagnostician")
    m = w.search_manual("tool change insert wear shift")
    gap = s["d_temp"]
    tr.speak("Diagnostician", (
        "Pattern: torque stepped up with the new steel lot and keeps creeping, which is a dulling insert on harder "
        f"stock. The process-to-air gap has closed to {gap:.1f} K, so the heat-dissipation wall goes live if the "
        "spindle drops below 1,380 rpm. "
        f"Manual: \"{m['matches'][0]['text'][:110]}\" (line {m['matches'][0]['line']})."), i)
    i = tr.as_agent("Race Engineer")
    p = w.price_mill_options()
    rec = next(o for o in p["options"] if o["key"] == p["recommendation"])
    others = [o for o in p["options"] if o["key"] != rec["key"]]
    tr.speak("Race Engineer", (
        f"Recommend **{rec['title']}**: {rec['detail']} Expected cost {_money(rec['cost_usd'])} against "
        + " and ".join(f"{_money(o['cost_usd'])} to {o['title'].lower()}" for o in others)
        + ". Needs the foreman: it changes how the machine runs."), i)
    return {"asset": "VM-07", "turns": tr.turns, "options": p["options"], "recommendation": rec,
            "assumptions": p["assumptions"], "needs_approval": True}


def mill_alert(w: World) -> dict:
    """Comms: tell the on-shift operator what to check, from the Sentinel's numbers (no model needed)."""
    tr = Transcript(w)
    s = w.read_mill()
    n = s["parts_until_wall"]
    i = tr.as_agent("Comms")
    a = w.send_alert(
        "VM-07", "SEV-2", ["Line 2 operator (on shift)", "Maintenance lead"],
        f"[SEV-2] VM-07 reaches its power limit in ~{4 * n} min. Check the insert",
        f"VM-07 is drawing {s['power_w'] / 1000:.1f} kW against its 9.0 kW power limit after the new steel lot. "
        f"Torque is creeping {s['creep']} Nm per part, so the limit is about {n} parts (~{4 * n} min) away. "
        "The crew is preparing a plan for the foreman; you do not need to change any setting.",
        ["Look at the insert on VM-07: chipping or a built-up edge?",
         "Listen for chatter at the spindle; stop the cycle if you hear it.",
         "Confirm the loaded bar is from the new steel lot."])
    tr.speak("Comms", (f"Sentinel flagged VM-07 at {s['power_w'] / 1000:.1f} kW. "
                       f"Emailed the Line 2 operator and the maintenance lead ({a['severity']}): check the insert "
                       f"within ~{4 * n} min. Escalates by SMS after {a['escalate_after_min']} min without an ack."), i)
    return {"turns": tr.turns, "alert": a}


def mill_execute(w: World, plan: dict, who: str = "Foreman") -> dict:
    tr = Transcript(w)
    rec = plan["recommendation"]
    i = tr.as_agent("Foreman")
    if rec["key"] == "lift_and_coast":
        w.write_mill_setpoint(rec["rpm"], rec["torque"], approved_by=who)
    tr.speak("Foreman", f"Approved: {rec['title']}.", i)
    i = tr.as_agent("Quartermaster")
    st = w.check_stock("INSERT-CNMG-L")
    r = w.reserve_part("INSERT-CNMG-L", 1, "VM-07")
    po_txt = ""
    if r["below_reorder_point"]:
        q = w.request_quotes("INSERT-CNMG-L", need_by_days=3)
        pick = q["pick"]
        po = w.draft_po("INSERT-CNMG-L", st["reorder_qty"], pick["supplier"], pick["unit_usd"], pick["arrives_in_days"])
        po_txt = f" Stock fell below the reorder point, so I drafted {po['po']} for {po['qty']} inserts ({_money(po['total_usd'])}): {po['status']}."
    tr.speak("Quartermaster", f"Reserved 1 insert for VM-07 ({r['available_after']} left on the shelf).{po_txt}", i)
    i = tr.as_agent("Dispatcher")
    wo = w.create_work_order("VM-07", "Change insert at shift change (Lift & Coast until then)", "today, shift change",
                             "Setter, Cell 3", [["INSERT-CNMG-L", 1]],
                             [f"{rec['title']}: {rec['detail']}", "Tool change procedure: manual p. 42"])
    w.approve(wo["wo"], who)
    tr.speak("Dispatcher", f"{wo['wo']} scheduled for the setter at shift change, with the evidence attached.", i)
    return {"turns": tr.turns, "work_order": wo}


# ---------------------------------------------------------------------------- grow
def grow(w: World, manual: str = "lathe_l2_manual.md") -> dict:
    tr = Transcript(w)
    i = tr.as_agent("Onboarder")
    p = w.onboard_manual(manual)
    errs = [c for c in p["checks"] if c["level"] == "error"]
    tr.speak("Onboarder", (
        f"Read {manual}: {p['asset_class']} {p['model']}. Wrote a passport with {len(p['walls'])} operating "
        f"walls, {sum(s['fitted'] for s in p['signals'])} live signals and {len(p['slots'])} future hardware slots "
        f"({', '.join(s['signal'].lower() for s in p['slots'])}). "
        + ("Ready for a human to sign." if not errs else f"{len(errs)} problems to fix before signing.")), i)
    return {"turns": tr.turns, "passport": p}


def grow_sign(w: World, asset_id: str, who: str = "Foreman") -> dict:
    tr = Transcript(w)
    i = tr.as_agent("Onboarder")
    r = w.sign_passport(asset_id, who)
    tr.speak("Onboarder", f"{asset_id} signed by {who}. Started {', '.join(r['agents_started'])}.", i)
    return {"turns": tr.turns, "result": r}


# ---------------------------------------------------------------------------- sourcing
_ROUTE = {"local": "from {local}", "central": "{local} had none, so the central hub sent stock first",
          "lateral": "{local} and the central hub had none, so another local hub sent it"}


def sourcing(w: World) -> dict:
    """Urgent jobs first (cure, then prevention), then refill the local hubs, then refill the central hub."""
    tr = Transcript(w)
    i = tr.as_agent("Sourcing")
    q = w.job_queue()
    urgent = [j for j in q["jobs"] if j["kind"] in ("cure", "prevention") and j["status"] == "open"]
    lines, parts = [], []
    for j in urgent:
        r = w.fulfil_job(j["job_id"])
        if j["pn"] not in parts:
            parts.append(j["pn"])
        if r["route"] == "buy":
            lines.append(f"{j['job_id']} ({j['pn']} to {j['site']}): no hub had it; {r['po']['po']} to "
                         f"{r['po']['vendor']}, arrives {r['po']['arrives']}.")
            continue
        local = w.network.sites[j["site"]]
        lines.append(f"{j['job_id']} ({j['kind']}, {j['pn']} to site {j['site']}): "
                     f"{_ROUTE[r['route']].format(local=local)}; {local} now holds {r['local_after']}.")
    tr.speak("Sourcing", " ".join(lines) or "No urgent jobs need parts.", i)

    i = tr.as_agent("Sourcing")
    lines, plans, pos = [], [], []
    for pn in parts:
        rs = w.restock_local_hubs(pn)
        for m in rs["moves"]:
            lines.append(f"Central hub sent {m['qty']} x {pn} to {m['to']} ({m['why']}).")
        p = w.plan_central_order(pn)
        if not p["needed"]:
            lines.append(f"Central hub has {p['position']} x {pn}, above its reorder level of "
                         f"{p['reorder_level']}: nothing to buy.")
            continue
        plans.append(p)
        pick, fast = p["pick"], p["fastest"]
        late = [o for o in p["options"] if not o["in_time"] and o["total_usd"] < pick["total_usd"]]
        lines.append(
            f"Central hub is down to {p['position']} x {pn} (reorder level {p['reorder_level']}): buy {p['qty']} "
            f"by {p['need_by']} ({p['need_by_why']}). Cheapest in time: {pick['vendor']}, "
            f"{_money(pick['total_usd'])}, arrives {pick['arrives']} (order by {pick['order_by']}). "
            + (f"Fastest: {fast['vendor']}, {_money(fast['total_usd'])}, arrives {fast['arrives']}. "
               if fast is not pick else "")
            + (f"{late[0]['vendor']} is cheaper but arrives {late[0]['arrives']}, too late. " if late else "")
            + (f"Excluded (not verified): {', '.join(x['vendor'] for x in p['excluded'])}. " if p["excluded"] else ""))
        po = w.place_order(pn, pick["vendor"], pick["qty"])
        pos.append(po)
        lines.append(f"{po['po']} {po['status']}.")
    tr.speak("Sourcing", " ".join(s.strip() for s in lines), i)
    return {"turns": tr.turns, "plans": plans, "pos": pos, "moves": list(w.network.moves)}
