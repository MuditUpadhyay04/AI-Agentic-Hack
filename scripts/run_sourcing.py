"""Run the Sourcing agent once and print what it did.

    python scripts/run_sourcing.py                 # offline (no AWS)
    PITCREW_LLM=bedrock python scripts/run_sourcing.py   # on Amazon Bedrock (needs AWS credentials + model access)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pitcrew.crew import Crew  # noqa: E402
from pitcrew.world import World  # noqa: E402

if __name__ == "__main__":
    out = Crew(World(), os.environ.get("PITCREW_LLM", "offline")).sourcing()
    print(f"mode: {out.get('mode', 'offline')}\n")
    for t in out["turns"]:
        print(f"[{t['agent']}] {t['say']}\n")
    for po in out.get("pos", []):
        print(f"{po['po']}: {po['qty']} x {po['pn']} from {po['vendor']}, ${po['total_usd']:,.0f}, {po['status']}")
