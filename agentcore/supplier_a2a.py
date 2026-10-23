"""A supplier's own agent, speaking A2A, for the Quartermaster to negotiate with.

Run locally:            python agentcore/supplier_a2a.py --supplier "Lot-A Supplier" --port 9001
Deploy on AgentCore:    the same file with --agentcore (serve_a2a on port 9000, as the AgentCore A2A guide
                        requires); then set PITCREW_SUPPLIER_URL for the crew.

The agent answers RFQs from its own catalogue: price, lead time, expedite option, and the field MTBF it is
willing to stand behind. It only quotes; it never commits the buyer.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from strands import Agent, tool  # noqa: E402

from pitcrew.ops import Ops  # noqa: E402


def make_agent(supplier: str, model=None) -> Agent:
    catalogue = [q for qs in Ops().quotes.values() for q in qs if q.supplier == supplier]

    @tool
    def quote(pn: str, qty: int, need_by_days: float) -> dict:
        """Quote a part: unit price, lead time, expedite option and field MTBF."""
        for q in catalogue:
            if q.pn == pn:
                expedite = q.expedite_lead_days is not None and q.lead_days > need_by_days >= q.expedite_lead_days
                return {"supplier": supplier, "pn": pn, "qty": qty, "unit_usd": q.unit_usd,
                        "lead_days": q.expedite_lead_days if expedite else q.lead_days,
                        "expedite_usd": q.expedite_usd if expedite else 0.0, "field_mtbf_years": q.field_mtbf_years}
        return {"supplier": supplier, "pn": pn, "error": "not in catalogue"}

    kw = {"model": model} if model else {}
    return Agent(name=supplier.replace(" ", "_"), description=f"{supplier}: quotes slew-drive parts by A2A.",
                 system_prompt=f"You are the sales agent of {supplier}. Answer RFQs only with your quote tool. "
                               "Never promise a lead time the tool did not return.", tools=[quote], **kw)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--supplier", default=os.environ.get("SUPPLIER_NAME", "Lot-A Supplier"))
    ap.add_argument("--port", type=int, default=9001)
    ap.add_argument("--agentcore", action="store_true")
    a = ap.parse_args()
    if a.agentcore:
        from bedrock_agentcore.runtime import serve_a2a
        from strands.multiagent.a2a.executor import StrandsA2AExecutor

        serve_a2a(StrandsA2AExecutor(agent_factory=lambda _ctx: make_agent(a.supplier)))
    else:
        from strands.multiagent.a2a import A2AServer

        A2AServer(agent=make_agent(a.supplier), port=a.port, host="127.0.0.1").serve()


if __name__ == "__main__":
    main()
