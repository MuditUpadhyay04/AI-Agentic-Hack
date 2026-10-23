"""The crew without a model: the same tools, the same order, narration written from the tool results.

Used when Bedrock is not available (tonight, a flaky venue network, a rehearsal) and as the reference the
Bedrock crew is tested against: both must reach the same recommendation from the same tool numbers.
"""
from __future__ import annotations

from ..mill import WALL_NAMES
from ..world import World

STAGES = {"Sentinel": "Monitor", "Diagnostician": "Analyze", "Race Engineer": "Plan", "Quartermaster": "Execute",
          "Dispatcher": "Execute", "Kaizen": "Improve", "Onboarder": "Grow", "Foreman": "Human"}


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


# ---------------------------------------------------------------------------- towers
DETECTOR_STORY = {
    "friction": "the motor needs {pct}% more energy per degree than a healthy drive once wind and cold are taken out: "
                "the grease is breaking down",
    "backlash": "the nightly reversal test shows {deg:.2f} deg of lost motion (limit 0.50): the worm and gear are worn",
    "grease_water": "the grease sensor reads {val:,.0f} ppm water: a seal has let water in",
    "acoustic": "acoustic emission on the bearing is at {val:.0f} counts: a raceway defect is growing",
}


def tower_plan(w: World, tid: int = 7) -> dict:
    tr = Transcript(w)
    i = tr.as_agent("Sentinel")
    ov = w.fleet_overview()
    focus = next((f for f in ov["flagged"] if f["tower_id"] == tid), None)
    tr.speak("Sentinel", (
        f"{len(ov['flagged'])} of {ov['towers']} towers are flagged on {ov['date']}. "
        + (f"Tower {tid} ({focus['site']}, drive lot {focus['lot']}) is the most urgent: {focus['sensor']}."
           if focus else f"Tower {tid} shows nothing on today's sensors.")), i)
    i = tr.as_agent("Diagnostician")
    d = w.diagnose_tower(tid)
    if not d["primary"]:
        tr.speak("Diagnostician", f"No detector fires for tower {tid} with the sensors fitted today.", i)
        return {"asset": f"Tower {tid}", "turns": tr.turns, "options": [], "recommendation": None,
                "needs_approval": False}
    p = d["primary"]
    story = DETECTOR_STORY.get(p["detector"], "{detector} alarm").format(
        pct=round(100 * (p["value"] - 1)), deg=p["value"], val=p["value"], detector=p["detector"])
    query = {"friction": "re-grease slew drive grease", "backlash": "bolts re-torque reversal backlash",
             "grease_water": "seals leaks condensation", "acoustic": "bearing acoustic emission replace drive"}
    m = w.search_manual(query.get(p["detector"], "slew drive"), manual="janta_tower_drive_public.md")
    rul = d.get("rul") or {}
    rul_txt = (f" Trend alone says ~{rul['p50']:.0f} days to the limit (P10 {rul['p10']:.0f})."
               if rul.get("p50") is not None and rul["p50"] < 120 else
               " The trend is slow in calm air; the risk is the next windy day.")
    tr.speak("Diagnostician", f"Tower {tid}: {story}.{rul_txt} Manual: \"{m['matches'][0]['text'][:90]}\".", i)
    i = tr.as_agent("Race Engineer")
    r = w.price_tower_options(tid)
    rec = r["recommendation"]
    track = next(o for o in r["options"] if o["key"] == "track")
    head = f"The next batched route reaches tower {tid} in {r['visit_in_days']} days ({r['route']['date']}). "
    if track["p_fail"] < 0.05:
        say = (head + f"It can keep tracking until then (failure risk {round(100 * track['p_fail'])}%). "
               f"Recommend **{rec['title']}** and plan the fix on that route: {r['fix']['title'].lower()} "
               f"(expected {_money(rec['expected_cost_usd'])}, mostly the planned repair).")
    else:
        say = (head + f"Keeping it tracking risks a {round(100 * track['p_fail'])}% chance of a stall before then "
               f"(a failure costs ~{_money(r['failure_cost_usd'])}). Recommend **{rec['title']}**: "
               f"{round(100 * rec['p_fail'])}% risk, {rec['energy_lost_kwh']:.0f} kWh given up "
               f"({_money(rec['energy_lost_usd'])}), expected {_money(rec['expected_cost_usd'])}. "
               f"Then: {r['fix']['title'].lower()}.")
    tr.speak("Race Engineer", say, i)
    return {"asset": f"Tower {tid}", "tower_id": tid, "turns": tr.turns, "options": r["options"],
            "recommendation": rec, "fix": r["fix"], "route": r["route"], "visit_in_days": r["visit_in_days"],
            "energy": r["energy"], "failure_cost_usd": r["failure_cost_usd"], "economics": r["economics"],
            "needs_approval": True, "flagged": ov["flagged"]}


def tower_execute(w: World, plan: dict, who: str = "Foreman") -> dict:
    tr = Transcript(w)
    tid, rec, fix = plan["tower_id"], plan["recommendation"], plan["fix"]
    i = tr.as_agent("Foreman")
    if rec["key"] in ("park", "coast"):
        w.set_tower_mode(tid, rec["key"], approved_by=who)
    tr.speak("Foreman", f"Approved for tower {tid}: {rec['title']}.", i)
    i = tr.as_agent("Quartermaster")
    lines = []
    for pn, q in fix["parts"]:
        r = w.reserve_part(pn, q, f"Tower {tid}")
        if r["reserved"]:
            lines.append(f"reserved {q} x {pn}")
        if not r["reserved"] or r["below_reorder_point"]:
            qt = w.request_quotes(pn, need_by_days=plan["visit_in_days"])
            pick = qt["pick"]
            if pick:
                part = w.ops.parts[pn]
                po = w.draft_po(pn, part.reorder_qty, pick["supplier"], pick["unit_usd"], pick["arrives_in_days"],
                                pick["extra_usd"])
                cheapest = min(qt["quotes"], key=lambda x: x["unit_usd"])
                why = ("" if cheapest["supplier"] == pick["supplier"] else
                       f" (not {cheapest['supplier']}: cheaper but {cheapest['field_mtbf_years']} years field MTBF)")
                lines.append(f"drafted {po['po']} for {po['qty']} x {pn} from {pick['supplier']}{why}, "
                             f"{_money(po['total_usd'])}: {po['status']}")
    msg = "; ".join(lines)
    tr.speak("Quartermaster", (msg[:1].upper() + msg[1:] + ".") if msg else "Nothing to order.", i)
    i = tr.as_agent("Dispatcher")
    route = w.next_route_day()
    batch = [f["tower_id"] for f in plan.get("flagged", []) if f["tower_id"] != tid and f["detector"] == "friction"]
    wo = w.create_work_order(f"Tower {tid}", fix["title"], route["date"], route["tech"],
                             [list(x) for x in fix["parts"]],
                             [f"{rec['title']} until the visit",
                              f"Risk if left tracking: {round(100 * next(o for o in plan['options'] if o['key'] == 'track')['p_fail'])}%"])
    w.approve(wo["wo"], who)
    extra = (f" Batched {len(batch)} more flagged towers on the same truck roll for re-grease: "
             + ", ".join(str(b) for b in batch[:8]) + ".") if batch else ""
    tr.speak("Dispatcher", f"{wo['wo']} booked with {route['tech']} on {route['date']}.{extra}", i)
    return {"turns": tr.turns, "work_order": wo, "batched": batch}


# ---------------------------------------------------------------------------- improve
def improve(w: World) -> dict:
    tr = Transcript(w)
    i = tr.as_agent("Kaizen")
    rules = w.kaizen_rules()
    osf = next(r for r in rules["rules"] if r["mode"] == "OSF")
    tr.speak("Kaizen", (
        f"On {rules['rows']:,} AI4I rows the overstrain failures separate on one rule, {osf['rule']} "
        f"(precision {osf['precision']:.2f}, recall {osf['recall']:.2f}): the published wall, found from data. "
        f"Early warning at 90% of that wall would have caught {100 * rules['early_warning']['recall']:.0f}% of them."), i)
    i = tr.as_agent("Kaizen")
    lots = w.kaizen_lots()
    b = next((x for x in lots["lots"] if x["lot"] == "B"), None)
    tta = {x["lot"]: x["median_days_fresh_grease_to_alarm"] for x in lots["fresh_grease_to_alarm"]}
    tr.speak("Kaizen", (
        f"Across the fleet, drives from supplier lot B fail {b.get('rate_ratio_vs_A')}x as often as lot A "
        f"({b['failures']} failures in {b['tower_years']} tower-years). Fresh grease reaches the friction alarm in "
        f"{tta.get('B', 0):.0f} days on lot B against {tta.get('A', 0):.0f} on lot A."), i)
    i = tr.as_agent("Kaizen")
    trade = w.tracking_tradeoff()
    sf = w.sensor_futures()
    top = sf["slots"][0] if sf["slots"] else None
    tr.speak("Kaizen", (
        f"Two findings for R&D. Step tracking in 15 deg steps gives up {trade['energy_loss_step15_pct']}% of a "
        f"year's energy (Shadow Calculator field model) and cuts drive starts {trade['starts_cut_pct']:.0f}%. "
        f"And of {sf['failures']} past failures, today's sensors flagged {sf['caught_with_todays_sensors']} a week or "
        f"more ahead - nobody was watching: a crew is worth ~{_money(sf['crew_value_usd_per_tower_year'])} per "
        f"tower-year before any new hardware."
        + (f" The best next sensor is the {top['slot'].lower()}: ~{_money(top['value_usd_per_tower_year'])} per "
           f"tower-year for {_money(top['unit_usd'])} of hardware." if top else "")), i)
    i = tr.as_agent("Kaizen")
    dcr = w.design_change_request()
    tr.speak("Kaizen", f"Drafted {len(dcr['items'])} design changes for TR-09 for engineering to review.", i)
    return {"turns": tr.turns, "rules": rules, "lots": lots, "futures": sf, "dcr": dcr, "tracking": trade}


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
