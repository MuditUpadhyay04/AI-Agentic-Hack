"""The whole demo in the terminal: Run (mill, tower), Improve, Grow. Good for rehearsal and as a backup.

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
    ap.add_argument("--tower", type=int, default=7)
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    w = World()
    crew = Crew(w)
    out = {}
    p = crew.plan_mill()
    show(f"RUN · mill VM-07 (crew: {crew.mode})", p["turns"])
    e = crew.execute(p)
    show("RUN · mill VM-07 after Approve", e["turns"])
    t = crew.plan_tower(a.tower)
    show(f"RUN · Janta tower {a.tower}", t["turns"])
    te = crew.execute(t) if t.get("recommendation") else {"turns": []}
    show(f"RUN · tower {a.tower} after Approve", te["turns"])
    k = crew.improve()
    show("IMPROVE · Kaizen", k["turns"])
    for item in k["dcr"]["items"]:
        print(f"  - {item['id']} {item['area']}: {item['change']}\n      {item['evidence']}")
    g = crew.grow("lathe_l2_manual.md")
    show("GROW · Onboarder", g["turns"])
    w.onboard_manual("janta_tower_drive_public.md")
    w.install_slot("TR-08", "acoustic")
    t42 = crew.plan_tower(42)
    show("GROW · acoustic slot installed, tower 42", t42["turns"])
    out = {"mill": p, "mill_exec": e, "tower": t, "tower_exec": te, "improve": k, "grow": g, "tower42": t42,
           "trace": w.trace}
    if a.json:
        Path(a.json).write_text(json.dumps(_clean(out), indent=1, default=str))
        print(f"\nsaved {a.json}")


if __name__ == "__main__":
    main()
