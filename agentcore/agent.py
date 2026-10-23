"""PitCrew on Amazon Bedrock AgentCore Runtime.

Replace the starter kit's ``agent.py`` with this file (or point the kit's deploy step at it). One runtime
hosts the crew; the payload says which loop to run:

    {"action": "plan_mill"}                      Run loop, mill VM-07, stops at the approval card
    {"action": "approve", "plan": {...}}         Execute after the foreman approves
    {"action": "predict", "udi": 162}            Prevention: Matthew's failure model on one AI4I reading
    {"action": "grow", "manual": "lathe_l2_manual.md"}
    {"action": "sourcing"}                       Sourcing agent: urgent parts on site, restock hubs, buy

Set PITCREW_LLM=bedrock and PITCREW_MODEL_ID in the runtime's environment. Local test without AWS:
``PITCREW_LLM=offline python agentcore/agent.py`` then POST to http://localhost:8080/invocations.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bedrock_agentcore.runtime import BedrockAgentCoreApp  # noqa: E402

from pitcrew.crew import Crew  # noqa: E402
from pitcrew.world import World, _clean  # noqa: E402

app = BedrockAgentCoreApp()
WORLDS: dict[str, World] = {}  # one world per AgentCore session (sessions are isolated microVMs anyway)


def _world(session: str) -> World:
    if session not in WORLDS:
        WORLDS[session] = World()
    return WORLDS[session]


@app.entrypoint
def invoke(payload: dict, context=None):
    session = getattr(context, "session_id", None) or payload.get("session", "default")
    w = _world(session)
    crew = Crew(w, os.environ.get("PITCREW_LLM", "bedrock"))
    action = payload.get("action", "plan_mill")
    if action == "plan_mill":
        out = crew.plan_mill()
    elif action == "approve":
        out = crew.execute(payload["plan"], payload.get("who", "Foreman"))
    elif action == "predict":
        out = w.predict_failure(int(payload.get("udi", 162)))
    elif action == "sourcing":
        out = crew.sourcing()
    elif action == "grow":
        out = crew.grow(payload.get("manual", "lathe_l2_manual.md"))
    else:
        out = {"error": f"unknown action {action}"}
    return _clean(out)


if __name__ == "__main__":
    app.run()
