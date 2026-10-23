"""The crew on Amazon Bedrock: Strands agents, one per role, wired as a Graph.

Plan graph (before the human):   Sentinel -> Diagnostician -> Race Engineer
Execute graph (after Approve):   Quartermaster -> Dispatcher
Supply: Sourcing.  Grow: Onboarder.

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
    "Onboarder": "You are the Onboarder (Grow). Read the manual into a passport, report its walls, live "
                 "signals and future hardware slots, and ask a human to sign. " + RULES,
    "Sourcing": "You are the Sourcing agent (Supply). Every job in the priority queue names a part number and a "
                "customer site; get the part there first, then keep the hubs stocked. Work in this order: "
                "(1) read the job queue; (2) for each open cure job, then each open prevention job, call "
                "fulfil_job (it tries the site's local hub, then the central hub, then another local hub, then "
                "buys); (3) for every part you moved, call restock_local_hubs; (4) for every part you moved, call "
                "plan_central_order and, if a purchase is needed, place_order with the plan's pick and quantity. "
                "Only verified vendors; never pay for speed the need-by date doesn't require. Report what went "
                "where, what you bought from whom, the cheapest-in-time vs fastest trade-off, and anything that "
                "waits for a planner's approval. " + RULES,
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
        """Search an equipment manual (vm07_mill_manual.md or lathe_l2_manual.md) for lines about query."""
        return w.search_manual(query, manual)

    @tool
    def price_mill_options() -> dict:
        """Price run-as-is, stop-now and Lift & Coast for mill VM-07; returns options and the cheapest safe one."""
        return w.price_mill_options()

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
    def next_route_day(base: str = "Field") -> dict:
        """The next batched technician route day and its technician."""
        return w.next_route_day(base)

    @tool
    def create_work_order(asset: str, title: str, due: str, tech: str, parts: list, evidence: list) -> dict:
        """Create a work order with parts and the evidence behind it."""
        return w.create_work_order(asset, title, due, tech, parts, evidence)

    @tool
    def predict_failure(record_udi: int) -> dict:
        """Matthew's failure model: failure probability (act >= 0.70, watch >= 0.40) of one equipment reading
        (an AI4I 2020 record id), with each sensor compared with healthy peers of the same type."""
        return w.predict_failure(record_udi)

    @tool
    def onboard_manual(manual: str) -> dict:
        """Read a manual into an asset passport (walls, signals, future hardware slots, parts)."""
        return w.onboard_manual(manual)

    @tool
    def job_queue() -> dict:
        """The priority queue: every job with rank, kind (cure/prevention/maintenance), part number, site, due date."""
        return w.job_queue()

    @tool
    def hub_stock(pn: str) -> dict:
        """Stock of one part number at the central hub and every local hub, with reorder levels and targets."""
        return w.hub_stock(pn)

    @tool
    def fulfil_job(job_id: str) -> dict:
        """Get a job's part to its site: local hub, else central hub, else another local hub, else buy."""
        return w.fulfil_job(job_id)

    @tool
    def restock_local_hubs(pn: str) -> dict:
        """Refill local hubs at or below their reorder level from the central hub; says if the central hub is low."""
        return w.restock_local_hubs(pn)

    @tool
    def plan_central_order(pn: str) -> dict:
        """Whether the central hub needs a purchase, how many, need-by date, cheapest-in-time vs fastest vendor."""
        return w.plan_central_order(pn)

    @tool
    def place_order(pn: str, vendor: str, qty: int) -> dict:
        """Raise a PO with a verified vendor. Policy auto-approves up to the limit; above it a planner approves."""
        return w.place_order(pn, vendor, qty)

    return {
        "Sentinel": [read_mill, predict_failure],
        "Diagnostician": [search_manual],
        "Race Engineer": [price_mill_options],
        "Quartermaster": [check_stock, reserve_part, request_quotes, draft_po],
        "Dispatcher": [next_route_day, create_work_order],
        "Onboarder": [onboard_manual],
        "Sourcing": [job_queue, hub_stock, fulfil_job, restock_local_hubs, plan_central_order, place_order],
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
    p = _last(w, "price_mill_options") or w.price_mill_options()
    out.update(asset="VM-07", options=p["options"],
               recommendation=next(o for o in p["options"] if o["key"] == p["recommendation"]),
               assumptions=p["assumptions"])
    return out


def execute(w: World, plan_out: dict, who: str = "Foreman", model=None) -> dict:
    """After the foreman approves: apply the setpoint (a deterministic, logged action), then let the
    Quartermaster and Dispatcher act."""
    agents = build_agents(w, model)
    rec = plan_out["recommendation"]
    w.agent = "Foreman"
    if plan_out["asset"] == "VM-07" and rec["key"] == "lift_and_coast":
        w.write_mill_setpoint(rec["rpm"], rec["torque"], approved_by=who)
    names = ["Quartermaster", "Dispatcher"]
    start = len(w.trace)
    task = ("The foreman approved this plan. Carry it out.\n" + json.dumps(
        {k: plan_out.get(k) for k in ("asset", "recommendation", "fix", "route", "visit_in_days")}, default=str))
    res = _graph(agents, names)(task)
    turns = [{"agent": "Foreman", "stage": "Human", "say": f"Approved: {rec['title']}.", "tools": []}]
    return {"turns": turns + _turns(w, res, names, start), "work_order": _last(w, "create_work_order")}


def sourcing(w: World, model=None) -> dict:
    """The Sourcing agent on Bedrock; plans and POs are read back from the tools, not from model text."""
    out = single(w, "Sourcing", "Work the priority queue: get urgent parts on site, then restock the hubs.", model)
    out.update(plans=[t["result"] for t in w.trace if t["tool"] == "plan_central_order" and t["result"].get("needed")],
               pos=list(w.network.pos), moves=list(w.network.moves))
    return out


def single(w: World, name: str, task: str, model=None) -> dict:
    agents = build_agents(w, model)
    start = len(w.trace)
    r = agents[name](task)
    return {"turns": [{"agent": name, "stage": STAGES.get(name, ""), "say": str(r).strip(),
                       "tools": [t for t in w.trace[start:]]}]}
