"""The crew on Amazon Bedrock: Strands agents, one per role, wired as a Graph.

Plan graph (before the human):   Sentinel -> Diagnostician -> Race Engineer
Execute graph (after Approve):   Quartermaster -> Dispatcher
Improve: Kaizen.  Grow: Onboarder.

Every number comes from a tool (the same ``World`` tools the offline crew uses), and the approval card is
built from the tool results in the trace, not from model text, so the model can explain and choose but
cannot invent a number. Set ``PITCREW_MODEL_ID`` to a Bedrock model or inference profile your workshop
account has enabled (the starter kit's ``infer.py`` tells you which work).
"""
from __future__ import annotations

import json
import os

from strands import Agent, tool
from strands.multiagent import GraphBuilder

from ..world import World
from .offline import STAGES

DEFAULT_MODEL = os.environ.get("PITCREW_MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250929-v1:0")

RULES = ("Rules: use your tools for every number and quote them exactly; never invent a number, part or date. "
         "Write 2-4 short sentences in plain language for a plant foreman. Name the wall or limit and its margin. "
         "Never change how a machine runs or spend money above the policy limit: that is the foreman's call.")

PROMPTS = {
    "Sentinel": "You are the Sentinel (Monitor). Read the live signals and say what changed and how far the "
                "machine is from each failure wall. " + RULES,
    "Diagnostician": "You are the Diagnostician (Analyze). Name the likely failure mode and its cause, and cite "
                     "the manual line you used. " + RULES,
    "Race Engineer": "You are the Race Engineer (Plan). Price the options with your tool and recommend the "
                     "lowest expected cost that keeps the safety margin. State the risk of each option. " + RULES,
    "Quartermaster": "You are the Quartermaster (Execute, supply). Reserve the parts the approved plan needs; if "
                     "stock falls below the reorder point, request quotes and draft a PO with the supplier that "
                     "arrives in time (not simply the cheapest). Report what you did. " + RULES,
    "Dispatcher": "You are the Dispatcher (Execute, people). Book the work on the next route or shift change "
                  "with the evidence attached, and batch other flagged assets on the same visit. " + RULES,
    "Kaizen": "You are the Kaizen agent (Improve). Use your tools to find rules, supplier patterns and the "
              "hardware worth adding; draft the design-change request. " + RULES,
    "Onboarder": "You are the Onboarder (Grow). Read the manual into a passport, report its walls, live "
                 "signals and future hardware slots, and ask a human to sign. " + RULES,
}


def make_model(model_id: str | None = None):
    from strands.models import BedrockModel

    return BedrockModel(model_id=model_id or DEFAULT_MODEL, temperature=0.2,
                        region_name=os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1")))


def tools_for(w: World) -> dict:
    """The World's tools as Strands tools, grouped by the agent allowed to call them."""

    @tool
    def read_mill() -> dict:
        """Live signals of mill VM-07 with the headroom to each failure wall and parts until the first wall."""
        return w.read_mill()

    @tool
    def search_manual(query: str, manual: str = "vm07_mill_manual.md") -> dict:
        """Search an equipment manual (vm07_mill_manual.md or tower_drive_manual.md) for lines about query."""
        return w.search_manual(query, manual)

    @tool
    def price_mill_options() -> dict:
        """Price run-as-is, stop-now and Lift & Coast for mill VM-07; returns options and the cheapest safe one."""
        return w.price_mill_options()

    @tool
    def fleet_overview() -> dict:
        """Which solar towers are flagged today, by which sensor."""
        return w.fleet_overview()

    @tool
    def diagnose_tower(tower_id: int) -> dict:
        """Detector findings and remaining-life estimate for one tower."""
        return w.diagnose_tower(tower_id)

    @tool
    def price_tower_options(tower_id: int) -> dict:
        """Park & Price: keep tracking, coast, park or emergency visit, each with failure risk, energy and cost."""
        return w.price_tower_options(tower_id)

    @tool
    def check_stock(pn: str) -> dict:
        """On-hand, reserved and available quantity of a part number."""
        return w.check_stock(pn)

    @tool
    def reserve_part(pn: str, qty: int, asset: str) -> dict:
        """Reserve parts for an asset; says whether stock fell below the reorder point."""
        return w.reserve_part(pn, qty, asset)

    @tool
    def request_quotes(pn: str, need_by_days: float) -> dict:
        """Quotes from suppliers with lead times, expedite options and field MTBF; picks one that arrives in time."""
        return w.request_quotes(pn, need_by_days)

    @tool
    def draft_po(pn: str, qty: int, supplier: str, unit_usd: float, lead_days: int, extra_usd: float = 0.0) -> dict:
        """Draft a purchase order. Policy auto-approves up to the limit; above it the foreman must approve."""
        return w.draft_po(pn, qty, supplier, unit_usd, lead_days, extra_usd)

    @tool
    def next_route_day(base: str = "DFW") -> dict:
        """The next batched technician route day and its technician."""
        return w.next_route_day(base)

    @tool
    def create_work_order(asset: str, title: str, due: str, tech: str, parts: list, evidence: list) -> dict:
        """Create a work order with parts and the evidence behind it."""
        return w.create_work_order(asset, title, due, tech, parts, evidence)

    @tool
    def kaizen_rules() -> dict:
        """Search AI4I for the simplest rule per failure mode, with precision and recall."""
        return w.kaizen_rules()

    @tool
    def kaizen_lots() -> dict:
        """Failure rate per tower-year by drive supplier lot, and days from fresh grease to the friction alarm."""
        return w.kaizen_lots()

    @tool
    def tracking_tradeoff() -> dict:
        """Energy given up by step tracking (field energy model) vs drive starts saved."""
        return w.tracking_tradeoff()

    @tool
    def sensor_futures() -> dict:
        """Replay past failures with each future hardware slot added; value per tower-year and payback."""
        return w.sensor_futures()

    @tool
    def design_change_request() -> dict:
        """Draft the ST-2 design-change request from the fleet evidence."""
        return w.design_change_request()

    @tool
    def onboard_manual(manual: str) -> dict:
        """Read a manual into an asset passport (walls, signals, future hardware slots, parts)."""
        return w.onboard_manual(manual)

    return {
        "Sentinel": [read_mill, fleet_overview],
        "Diagnostician": [search_manual, diagnose_tower],
        "Race Engineer": [price_mill_options, price_tower_options],
        "Quartermaster": [check_stock, reserve_part, request_quotes, draft_po],
        "Dispatcher": [next_route_day, create_work_order],
        "Kaizen": [kaizen_rules, kaizen_lots, tracking_tradeoff, sensor_futures, design_change_request],
        "Onboarder": [onboard_manual],
    }


class _Tagger:
    """Callback that marks which agent is speaking, so tool calls land in the trace under its name."""

    def __init__(self, w: World, name: str):
        self.w, self.name = w, name

    def __call__(self, **kwargs):
        self.w.agent = self.name


def build_agents(w: World, model=None) -> dict:
    model = model or make_model()
    tools = tools_for(w)
    return {name: Agent(name=name.replace(" ", "_"), model=model, system_prompt=PROMPTS[name], tools=tools[name],
                        callback_handler=_Tagger(w, name))
            for name in PROMPTS}


def _graph(agents: dict, names: list[str]):
    b = GraphBuilder()
    for n in names:
        b.add_node(agents[n], n)
    for a, c in zip(names, names[1:]):
        b.add_edge(a, c)
    b.set_entry_point(names[0])
    b.set_max_node_executions(len(names) * 2)
    b.set_execution_timeout(600)
    return b.build()


def _turns(w: World, result, names: list[str], start: int) -> list[dict]:
    turns = []
    for n in names:
        nr = result.results.get(n) if hasattr(result, "results") else None
        text = str(getattr(nr, "result", nr) or "").strip()
        turns.append({"agent": n, "stage": STAGES.get(n, ""), "say": text,
                      "tools": [t for t in w.trace[start:] if t["agent"] == n]})
    return turns


def _last(w: World, tool_name: str):
    for t in reversed(w.trace):
        if t["tool"] == tool_name:
            return t["result"]
    return None


def plan(w: World, task: str, kind: str, model=None) -> dict:
    """Run Sentinel -> Diagnostician -> Race Engineer on a task; the card comes from the priced tool output.
    Agents are built fresh for every run so no conversation leaks between incidents."""
    agents = build_agents(w, model)
    names = ["Sentinel", "Diagnostician", "Race Engineer"]
    start = len(w.trace)
    res = _graph(agents, names)(task)
    out = {"turns": _turns(w, res, names, start), "needs_approval": True}
    if kind == "mill":
        p = _last(w, "price_mill_options") or w.price_mill_options()
        out.update(asset="VM-07", options=p["options"],
                   recommendation=next(o for o in p["options"] if o["key"] == p["recommendation"]),
                   assumptions=p["assumptions"])
    else:
        p = _last(w, "price_tower_options")
        out.update(asset=f"Tower {p['tower_id']}", tower_id=p["tower_id"], options=p["options"],
                   recommendation=p["recommendation"], fix=p["fix"], route=p["route"],
                   visit_in_days=p["visit_in_days"], energy=p["energy"], failure_cost_usd=p["failure_cost_usd"],
                   economics=p["economics"], flagged=(_last(w, "fleet_overview") or {}).get("flagged", []))
    return out


def execute(w: World, plan_out: dict, who: str = "Foreman", model=None) -> dict:
    """After the foreman approves: apply the setpoint (a deterministic, logged action), then let the
    Quartermaster and Dispatcher act."""
    agents = build_agents(w, model)
    rec = plan_out["recommendation"]
    w.agent = "Foreman"
    if plan_out["asset"] == "VM-07" and rec["key"] == "lift_and_coast":
        w.write_mill_setpoint(rec["rpm"], rec["torque"], approved_by=who)
    elif plan_out.get("tower_id") and rec["key"] in ("park", "coast"):
        w.set_tower_mode(plan_out["tower_id"], rec["key"], approved_by=who)
    names = ["Quartermaster", "Dispatcher"]
    start = len(w.trace)
    task = ("The foreman approved this plan. Carry it out.\n" + json.dumps(
        {k: plan_out.get(k) for k in ("asset", "recommendation", "fix", "route", "visit_in_days")}, default=str))
    res = _graph(agents, names)(task)
    turns = [{"agent": "Foreman", "stage": "Human", "say": f"Approved: {rec['title']}.", "tools": []}]
    return {"turns": turns + _turns(w, res, names, start), "work_order": _last(w, "create_work_order")}


def single(w: World, name: str, task: str, model=None) -> dict:
    agents = build_agents(w, model)
    start = len(w.trace)
    r = agents[name](task)
    return {"turns": [{"agent": name, "stage": STAGES.get(name, ""), "say": str(r).strip(),
                       "tools": [t for t in w.trace[start:]]}]}
