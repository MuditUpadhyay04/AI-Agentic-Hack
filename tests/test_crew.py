import json

from pitcrew.crew import Crew
from pitcrew.world import World


def test_offline_run_improve_grow_end_to_end():
    w = World()
    c = Crew(w, "offline")
    p = c.plan_mill()
    assert p["recommendation"]["key"] == "lift_and_coast"
    e = c.execute(p)
    assert e["work_order"]["wo"].startswith("WO-")
    assert w.mill_state["rpm"] == 1400
    t = c.plan_tower(7)
    assert t["recommendation"]["key"] == "park"
    te = c.execute(t)
    assert te["batched"]
    k = c.improve()
    assert len(k["dcr"]["items"]) >= 3
    g = c.grow("lathe_l2_manual.md")
    assert g["passport"]["asset_id"] == "L-2"
    json.dumps(w.trace, default=str)  # every tool result is JSON


def test_policy_blocks_unapproved_setpoint():
    w = World()
    r = w.write_mill_setpoint(1400, 47, approved_by="")
    assert r["written"] is False and r["policy"]["needs_human"]


def test_strands_graph_with_scripted_model():
    w = World()
    c = Crew(w, "scripted")
    p = c.plan_mill()
    assert p["mode"] == "scripted"
    assert [t["agent"] for t in p["turns"]] == ["Sentinel", "Diagnostician", "Race Engineer"]
    assert any(x["tool"] == "price_mill_options" for x in p["turns"][2]["tools"])
    t = c.plan_tower(7)
    assert t["recommendation"]["key"] == "park"
