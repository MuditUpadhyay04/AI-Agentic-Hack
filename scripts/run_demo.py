"""The demo in the terminal: mill crew, Prevention (Matthew's failure model), Sourcing, Grow.

    python scripts/run_demo.py                    # offline crew
    PITCREW_LLM=bedrock python scripts/run_demo.py  # Strands agents on Bedrock (workshop account)
    python scripts/run_demo.py --json out.json    # also save every turn and tool call
"""
from __future__ import annotations

import argparse
import json
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pitcrew.contracts import Plant  # noqa: E402
from pitcrew.crew import Crew  # noqa: E402
from pitcrew.world import World, _clean  # noqa: E402


def show(title: str, turns: list[dict]) -> None:
    print(f"\n=== {title} " + "=" * max(0, 70 - len(title)))
    for t in turns:
        tools = ", ".join(x["tool"] for x in t.get("tools", []))
        print(f"\n[{t['agent']} · {t.get('stage', '')}]" + (f"  tools: {tools}" if tools else ""))
        print(textwrap.fill(t["say"].replace("**", ""), 100, initial_indent="  ", subsequent_indent="  "))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    w = World()
    crew = Crew(w)
    p = crew.plan_mill()
    show(f"RUN · mill VM-07 (crew: {crew.mode})", p["turns"])
    e = crew.execute(p)
    show("RUN · mill VM-07 after Approve", e["turns"])

    plant = Plant()
    print("\n=== PREVENTION · Matthew's failure model " + "=" * 30)
    for pid, r in plant.prevention().items():
        print(f"  {plant.products[pid]['name']:<18} risk {r['risk']:>6.1%}  {r['action']}")
    plant.product_drifts("DS-07")
    r = plant.prevention()["DS-07"]
    job = next(j for j in plant.queue()["jobs"] if j["product"] == "DS-07")
    print(f"  Dicing saw 07 drifts: risk {r['risk']:.1%} -> {r['action']}; {job['job_id']} now rank {job['rank']} "
          f"({job['reason']})")

    s = crew.sourcing()
    show("SUPPLY · Sourcing agent", s["turns"])
    g = crew.grow("lathe_l2_manual.md")
    show("GROW · Onboarder", g["turns"])
    if a.json:
        out = {"mill": p, "mill_exec": e, "prevention": r, "sourcing": s, "grow": g, "trace": w.trace}
        Path(a.json).write_text(json.dumps(_clean(out), indent=1, default=str))
        print(f"\nsaved {a.json}")


if __name__ == "__main__":
    main()
