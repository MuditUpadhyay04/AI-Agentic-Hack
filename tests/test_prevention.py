from pitcrew.contracts import ACT, Plant
from pitcrew.world import World


def test_failure_model_scores_the_fleet_healthy():
    plant = Plant()
    risks = {k: v["risk"] for k, v in plant.prevention().items()}
    assert all(r < 0.05 for r in risks.values()), risks


def test_drift_raises_risk_and_promotes_the_job():
    plant = Plant()
    plant.product_drifts("DS-07")
    r = plant.prevention()["DS-07"]
    assert r["risk"] >= ACT and r["action"] == "act"
    assert r["source"].startswith("failure_model")
    jobs = plant.queue()["jobs"]
    top = jobs[0]
    assert top["product"] == "DS-07" and top["type"] == "prevention" and top["was_due"] > top["due_by"]


def test_cure_still_outranks_prevention():
    plant = Plant()
    plant.product_drifts("DS-07")
    plant.product_down("DS-19")
    assert [j["type"] for j in plant.queue()["jobs"][:2]] == ["cure", "prevention"]


def test_predict_failure_tool_is_traced():
    w = World()
    r = w.predict_failure(162)
    assert r["action"] == "act" and w.trace[-1]["tool"] == "predict_failure"


def test_both_teammate_models_load_side_by_side():
    """Matthew's and Hari's folders both ship predict.py; each must load as itself."""
    plant = Plant()
    assert plant.prevention()["DS-07"]["source"].startswith("failure_model")
    assert all(s["status"] == "NORMAL" for s in plant.fab_statuses().values())
    plant.fab_l3_degrades()
    s = plant.fab_statuses()["MK-L3"]
    assert s["status"] == "FAILURE WARNING" and s["source"] == "machine_downtime_model"
