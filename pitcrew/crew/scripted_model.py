"""A stand-in Strands model for tests and rehearsals without Bedrock.

It reads the agent's system prompt to know which role it plays, calls that role's tools once (in order,
with arguments taken from the task), then writes a short summary built from the tool results. It exercises
the real Strands Agent, tool calling and Graph code paths, so a green test here means only the model is
missing when the workshop account plugs Bedrock in.
"""
from __future__ import annotations

import json
import re
import uuid
from typing import Any

from strands.models.model import Model

CALLS = {
    "Sentinel": lambda task: [("read_mill", {})] if "VM-07" in task else [("fleet_overview", {})],
    "Diagnostician": lambda task: ([("search_manual", {"query": "tool change insert wear shift"})] if "VM-07" in task
                                   else [("diagnose_tower", {"tower_id": _tid(task)}),
                                         ("search_manual", {"query": "re-grease seals",
                                                            "manual": "janta_tower_drive_public.md"})]),
    "Race Engineer": lambda task: ([("price_mill_options", {})] if "VM-07" in task
                                   else [("price_tower_options", {"tower_id": _tid(task)})]),
    "Quartermaster": lambda task: [("check_stock", {"pn": "INSERT-CNMG-L" if "VM-07" in task else "GREASE-KIT-SD"})],
    "Dispatcher": lambda task: [("next_route_day", {})],
    "Kaizen": lambda task: [("kaizen_lots", {}), ("tracking_tradeoff", {})],
    "Onboarder": lambda task: [("onboard_manual", {"manual": "lathe_l2_manual.md"})],
}


def _tid(task: str) -> int:
    m = re.search(r"[Tt]ower\s+(\d+)", task)
    return int(m.group(1)) if m else 7


class ScriptedModel(Model):
    def __init__(self):
        self.config = {"model_id": "scripted"}

    def update_config(self, **model_config: Any) -> None:
        self.config.update(model_config)

    def get_config(self):
        return self.config

    async def structured_output(self, output_model, prompt, system_prompt=None, **kwargs):  # pragma: no cover
        raise NotImplementedError

    async def stream(self, messages, tool_specs=None, system_prompt=None, **kwargs):
        role = next((r for r in CALLS if system_prompt and system_prompt.startswith(f"You are the {r}")), "Sentinel")
        task = json.dumps(messages[0]["content"]) if messages else ""
        done = sum(1 for m in messages if m["role"] == "user" and any("toolResult" in c for c in m["content"]))
        plan = CALLS[role](task)
        yield {"messageStart": {"role": "assistant"}}
        if done < len(plan):
            name, args = plan[done]
            yield {"contentBlockStart": {"start": {"toolUse": {"name": name, "toolUseId": f"t_{uuid.uuid4().hex[:12]}"}}}}
            yield {"contentBlockDelta": {"delta": {"toolUse": {"input": json.dumps(args)}}}}
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "tool_use"}}
            return
        results = []
        for m in messages:
            for c in m["content"]:
                if "toolResult" in c:
                    for part in c["toolResult"].get("content", []):
                        if "text" in part:
                            results.append(part["text"][:160])
                        elif "json" in part:
                            results.append(json.dumps(part["json"])[:160])
        text = f"[{role}, scripted] " + (" | ".join(results) if results else "nothing to report")
        yield {"contentBlockStart": {"start": {}}}
        yield {"contentBlockDelta": {"delta": {"text": text}}}
        yield {"contentBlockStop": {}}
        yield {"messageStop": {"stopReason": "end_turn"}}
