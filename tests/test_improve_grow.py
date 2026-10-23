import pytest

from pitcrew.futures import ranking
from pitcrew.kaizen import rediscover_ai4i, tracking_tradeoff
from pitcrew.passport import MANUALS, from_manual, install_slot, manuals, sign
from pitcrew.tower import Fleet


def test_kaizen_rediscovers_published_walls():
    r = {x["mode"]: x for x in rediscover_ai4i()["rules"]}
    assert r["OSF"]["rule"].startswith("strain_ratio > 1") and r["OSF"]["precision"] > 0.95
    assert "8.6" in r["HDF"]["rule"] or "8.5" in r["HDF"]["rule"] or "8.7" in r["HDF"]["rule"]
    assert r["PWF"]["f1"] > 0.9


def test_tracking_tradeoff():
    t = tracking_tradeoff()
    assert t["energy_loss_step15_pct"] < 0.5 and t["starts_cut_pct"] > 80


def test_sensor_futures_ranks_slots():
    rk, rp, ty = ranking(Fleet().run())
    assert len(rp) > 10 and ty > 100
    assert set(rk["key"]) == {"grease", "acoustic", "vibration", "torque"}


@pytest.mark.parametrize("name", manuals())
def test_every_manual_onboards_cleanly(name):
    p = from_manual(MANUALS / name)
    assert all(c["level"] == "ok" for c in p["checks"]), p["checks"]
    assert p["walls"] and p["slots"]
    signed = sign(p, "tester")
    assert signed["approved_by"] == "tester"


def test_slot_install_unlocks_detectors():
    p = from_manual(MANUALS / "tower_drive_manual.md")
    p2 = install_slot(p, "acoustic")
    assert any(s["status"] == "installed" and "acoustic" in s["unlocks"] for s in p2["slots"])
