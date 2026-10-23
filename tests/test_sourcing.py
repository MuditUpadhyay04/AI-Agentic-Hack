import datetime as dt
import json

from pitcrew.crew import Crew
from pitcrew.sourcing import CENTRAL, Job, VendorQuote, demo_network, rank
from pitcrew.world import World


def _job(net, job_id):
    return next(j for j in net.jobs if j.job_id == job_id)


def _on_hand(net, hub, pn):
    return net.stock[(hub, pn)].on_hand


def test_queue_order_cure_then_prevention_then_maintenance():
    ids = [j.job_id for j in rank(demo_network().jobs)]
    assert ids == ["CUR-007", "PRV-031", "MNT-198", "MNT-199", "MNT-200", "MNT-201", "MNT-202"]


def test_local_hub_first():
    net = demo_network()
    r = net.fulfil(_job(net, "CUR-007"))
    assert r["route"] == "local"
    assert _on_hand(net, "Local hub South", "PN-2210") == 1


def test_central_hub_when_local_is_empty():
    net = demo_network()
    r = net.fulfil(_job(net, "PRV-031"))
    assert r["route"] == "central"
    assert [m["qty"] for m in r["moves"]] == [3, 1]  # central -> East (refill to target 3), East -> site E1
    assert _on_hand(net, CENTRAL, "PN-1043") == 12
    assert _on_hand(net, "Local hub East", "PN-1043") == 2


def test_restock_then_cheapest_vendor_that_arrives_in_time():
    """The pitch simulation's story, number for number (docs/SIMULATION_PROMPT.md, section 7)."""
    net = demo_network()
    net.fulfil(_job(net, "CUR-007"))
    net.fulfil(_job(net, "PRV-031"))
    rs = net.restock_local_hubs("PN-2210")
    assert _on_hand(net, "Local hub South", "PN-2210") == 4
    assert _on_hand(net, CENTRAL, "PN-2210") == 8 and rs["central_low"]
    assert net.central_plan("PN-1043")["needed"] is False  # 12 is above the reorder level of 10

    p = net.central_plan("PN-2210")
    assert p["qty"] == 12 and p["need_by"] == "2026-11-02"
    assert p["pick"]["vendor"] == "Vendor C" and p["pick"]["total_usd"] == 492
    assert p["fastest"]["vendor"] == "Vendor B" and p["fastest"]["arrives"] == "2026-10-27"
    late = next(o for o in p["options"] if o["vendor"] == "Vendor A")
    assert not late["in_time"] and late["label"] == "cheapest, but too late"
    assert [x["vendor"] for x in p["excluded"]] == ["Vendor D"]
    assert p["policy"]["allowed"]  # $492 is under the $500 auto-approve limit

    po = net.place_order("PN-2210", "Vendor C", 12)
    assert po["po"] == "PO-7711" and po["status"].startswith("approved")
    net.advance(dt.date(2026, 10, 30))
    assert _on_hand(net, CENTRAL, "PN-2210") == 20


def test_never_orders_from_an_unverified_vendor():
    net = demo_network()
    assert net.place_order("PN-2210", "Vendor D", 12)["placed"] is False


def test_lateral_transfer_then_buy_when_no_hub_has_it():
    net = demo_network()
    net.stock[(CENTRAL, "PN-3307")].on_hand = 0
    r = net.fulfil(Job("CUR-900", "cure", "PN-3307", "N1", dt.date(2026, 10, 23)))
    assert r["route"] == "lateral"  # North and central have none; East and West hold 2 with reorder level 1
    net.quotes["PN-9999"] = [VendorQuote("Vendor B", "PN-9999", 10.0, 2), VendorQuote("Vendor A", "PN-9999", 8.0, 9)]
    net.parts["PN-9999"] = "Spare"
    r = net.fulfil(Job("CUR-901", "cure", "PN-9999", "N1", dt.date(2026, 10, 24)))
    assert r["route"] == "buy" and r["po"]["vendor"] == "Vendor B"  # fastest, delivered to the local hub


def test_offline_sourcing_agent_end_to_end():
    w = World()
    out = Crew(w, "offline").sourcing()
    assert [t["agent"] for t in out["turns"]] == ["Sourcing", "Sourcing"]
    assert [po["vendor"] for po in out["pos"]] == ["Vendor C"]
    assert "Vendor C" in out["turns"][1]["say"] and "$492" in out["turns"][1]["say"]
    json.dumps(w.trace)  # every sourcing tool result is plain JSON


def test_sourcing_agent_with_scripted_model():
    w = World()
    out = Crew(w, "scripted").sourcing()
    assert out["mode"] == "scripted"
    tools = [t["tool"] for t in out["turns"][0]["tools"]]
    assert tools == ["job_queue", "fulfil_job", "restock_local_hubs", "plan_central_order"]
    assert out["plans"][0]["pick"]["vendor"] == "Vendor C"
