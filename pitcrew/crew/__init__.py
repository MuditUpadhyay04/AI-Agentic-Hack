"""One interface over the three ways to run the crew.

    PITCREW_LLM=offline   deterministic narration from tool results (default; no AWS needed)
    PITCREW_LLM=bedrock   Strands agents on Amazon Bedrock (PITCREW_MODEL_ID), Graph orchestration
    PITCREW_LLM=scripted  Strands agents with a scripted stand-in model (tests the agent plumbing offline)

In bedrock mode any model error falls back to the offline crew for that step and says so in the transcript,
so a venue network hiccup never ends the demo.
"""
from __future__ import annotations

import os
import traceback

from ..world import World
from . import offline


class Crew:
    def __init__(self, world: World, mode: str | None = None):
        self.w = world
        self.mode = (mode or os.environ.get("PITCREW_LLM", "offline")).lower()
        self.last_error: str | None = None

    def _model(self):
        if self.mode == "scripted":
            from .scripted_model import ScriptedModel

            return ScriptedModel()
        from .strands_crew import make_model

        return make_model()

    def _try(self, fn_llm, fn_offline):
        if self.mode == "offline":
            return fn_offline()
        try:
            out = fn_llm()
            out["mode"] = self.mode
            return out
        except Exception as exc:  # fall back, but say so
            self.last_error = f"{type(exc).__name__}: {exc}"
            out = fn_offline()
            out["mode"] = "offline (fallback)"
            out.setdefault("turns", []).insert(0, {"agent": "System", "stage": "", "tools": [],
                                                    "say": f"Model unavailable ({self.last_error[:160]}); "
                                                           "running the offline crew on the same tools."})
            traceback.print_exc()
            return out

    # ---- Run
    def plan_mill(self) -> dict:
        from . import strands_crew as S

        return self._try(lambda: S.plan(self.w, "Mill VM-07: the torque signal changed after a new steel lot "
                                                "arrived. Assess it and plan the response.", "mill", self._model()),
                         lambda: offline.mill_plan(self.w))

    def alert_mill(self) -> dict:
        # Comms tells the floor as soon as the Sentinel's numbers change; the message uses tool numbers only.
        return offline.mill_alert(self.w)

    def execute(self, plan: dict, who: str = "Foreman") -> dict:
        from . import strands_crew as S

        return self._try(lambda: S.execute(self.w, plan, who, self._model()),
                         lambda: offline.mill_execute(self.w, plan, who))

    # ---- Supply
    def sourcing(self) -> dict:
        from . import strands_crew as S

        return self._try(lambda: S.sourcing(self.w, self._model()), lambda: offline.sourcing(self.w))

    # ---- Grow
    def grow(self, manual: str) -> dict:
        return offline.grow(self.w, manual)

    def grow_sign(self, asset_id: str, who: str = "Foreman") -> dict:
        return offline.grow_sign(self.w, asset_id, who)
